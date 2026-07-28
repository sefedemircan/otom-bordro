"""Puantaj hesaplama (Streamlit sayfa 1) endpoints."""

from __future__ import annotations

from typing import Any

import pandas as pd
from fastapi import APIRouter, File, Form, Request, UploadFile
from starlette.datastructures import UploadFile as StarletteUploadFile

from api.deps import (
    api_error,
    dataframe_to_records,
    load_calc_dataframe,
    read_upload_bytes,
    rows_to_dataframe,
)
from api.schemas import ComputeJsonRequest, ComputeResponse, InspectResponse
from api.services.supabase import SupabaseError
from api.services.uploads import load_upload_dataframe
from puantaj_calc import (
    build_employee_list,
    calculate_puantaj,
    filter_employee_df,
    is_bulk_file,
    normalize_meyer_rows,
)

router = APIRouter(prefix="/api/v1/calc", tags=["calc"])


def _employee_label(df: pd.DataFrame, fallback: str = "Personel") -> str:
    if "Ad" in df.columns and "Soyad" in df.columns and not df.empty:
        return f"{df['Ad'].iloc[0]} {df['Soyad'].iloc[0]}".strip() or fallback
    return fallback


def _parse_optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        raise api_error(400, "INVALID_PERIOD", "year ve month tam sayı olmalıdır.") from None


def _compute_payload(
    df: pd.DataFrame,
    employee_label: str | None = None,
    sicilno: str | None = None,
    year: int | None = None,
    month: int | None = None,
) -> dict[str, Any]:
    if (year is None) ^ (month is None):
        raise api_error(400, "INVALID_PERIOD", "year ve month birlikte gönderilmelidir.")
    if month is not None and not (1 <= month <= 12):
        raise api_error(400, "INVALID_PERIOD", "month 1–12 arasında olmalıdır.")
    try:
        processed_df, daily_df, weekly_df, leave_breakdown_df, summary = calculate_puantaj(
            df, year=year, month=month
        )
    except ValueError as exc:
        message = str(exc)
        if "döneminde kayıt" in message or "month 1–12" in message:
            code = "INVALID_PERIOD"
        elif "Zorunlu sütunlar" in message:
            code = "MISSING_COLUMNS"
        else:
            code = "INVALID_FILE"
        raise api_error(400, code, message) from exc

    summary = dict(summary)
    summary["employee_label"] = employee_label or _employee_label(df)
    if sicilno:
        summary["sicilno"] = str(sicilno).zfill(5)
    elif "sicilno" in df.columns and not df.empty:
        try:
            summary["sicilno"] = str(int(df["sicilno"].iloc[0])).zfill(5)
        except (TypeError, ValueError):
            summary["sicilno"] = str(df["sicilno"].iloc[0])
    return {
        "summary": summary,
        "leave_breakdown": dataframe_to_records(leave_breakdown_df),
        "daily": dataframe_to_records(daily_df),
        "weekly": dataframe_to_records(weekly_df),
        "processed": dataframe_to_records(processed_df),
    }


@router.post("/inspect", response_model=InspectResponse)
async def inspect_file(
    file: UploadFile | None = File(default=None),
    upload_id: str | None = Form(default=None),
) -> InspectResponse:
    if upload_id:
        try:
            _, df = load_upload_dataframe(upload_id, "calc")
        except SupabaseError as exc:
            raise api_error(404, "UPLOAD_NOT_FOUND", str(exc)) from exc
    else:
        if file is None:
            raise api_error(400, "INVALID_FILE", "file veya upload_id gönderilmelidir.")
        data, filename = await read_upload_bytes(file)
        df = load_calc_dataframe(data, filename)
    bulk = is_bulk_file(df)
    employees: list[dict[str, Any]] = []
    if bulk or ("sicilno" in df.columns and df["sicilno"].notna().any()):
        try:
            employees = dataframe_to_records(build_employee_list(df))
        except Exception as exc:  # noqa: BLE001
            raise api_error(400, "INVALID_FILE", f"Personel listesi oluşturulamadı: {exc}") from exc
    return InspectResponse(is_bulk=bulk, record_count=len(df), employees=employees)


@router.post("/compute", response_model=ComputeResponse)
async def compute(request: Request) -> ComputeResponse:
    """Dosya (multipart) veya JSON rows ile hesaplama.

    - `multipart/form-data`: `file` (+ toplu dosyada `sicilno`)
    - `application/json`: `{ "rows": [...], "employee_label"?: string }`
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        payload = await request.json()
        body = ComputeJsonRequest.model_validate(payload)
        df = rows_to_dataframe(body.rows)
        return ComputeResponse(
            **_compute_payload(
                df,
                body.employee_label,
                year=body.year,
                month=body.month,
            )
        )

    form = await request.form()
    upload = form.get("file")
    sicil_raw = form.get("sicilno")
    upload_id_raw = form.get("upload_id")
    upload_id = str(upload_id_raw).strip() if upload_id_raw not in (None, "") else None
    sicilno = str(sicil_raw).strip() if sicil_raw not in (None, "") else None
    year = _parse_optional_int(form.get("year"))
    month = _parse_optional_int(form.get("month"))
    if upload_id:
        try:
            _, master_df = load_upload_dataframe(upload_id, "calc")
        except SupabaseError as exc:
            raise api_error(404, "UPLOAD_NOT_FOUND", str(exc)) from exc
    else:
        if upload is None or not isinstance(upload, (UploadFile, StarletteUploadFile)):
            raise api_error(
                400,
                "INVALID_FILE",
                "multipart/form-data ile `file` veya `upload_id` gönderin ya da application/json ile `rows` gönderin.",
            )
        data, filename = await read_upload_bytes(upload)  # type: ignore[arg-type]
        master_df = load_calc_dataframe(data, filename)
    bulk = is_bulk_file(master_df)

    if bulk:
        if not sicilno:
            raise api_error(
                400,
                "EMPLOYEE_NOT_FOUND",
                "Toplu dosyada sicilno zorunludur. Önce /inspect ile personel listesini alın.",
            )
        employee_df = filter_employee_df(master_df, sicilno)
        if employee_df.empty:
            raise api_error(400, "EMPLOYEE_NOT_FOUND", f"Sicil bulunamadı: {sicilno}")
        employee_df = normalize_meyer_rows(employee_df)
        label = _employee_label(employee_df)
        return ComputeResponse(
            **_compute_payload(employee_df, label, sicilno, year=year, month=month)
        )

    df = normalize_meyer_rows(master_df)
    if sicilno:
        filtered = filter_employee_df(master_df, sicilno)
        if filtered.empty:
            raise api_error(400, "EMPLOYEE_NOT_FOUND", f"Sicil bulunamadı: {sicilno}")
        df = normalize_meyer_rows(filtered)
    label = _employee_label(df)
    return ComputeResponse(**_compute_payload(df, label, sicilno, year=year, month=month))
