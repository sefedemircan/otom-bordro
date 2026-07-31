"""Aylık puantaj raporu (Streamlit sayfa 2) endpoints."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import Response

from api.deps import (
    api_error,
    dataframe_to_records,
    format_hour_columns,
    load_report_dataframe,
    read_upload_bytes,
)
from api.schemas import (
    PeriodItem,
    PeriodsResponse,
    ReportBuildResponse,
    ReportFillStats,
    ReportMeta,
    ReportV3BuildResponse,
)
from api.services.report_snapshots import (
    load_report_response_from_snapshot,
    load_report_result_from_snapshot,
    persist_report_snapshot,
)
from api.services.supabase import SupabaseError
from api.services.uploads import get_upload, load_upload_dataframe
from otom_template_fill import fill_otom_template
from puantaj_report import (
    ReportResult,
    available_periods,
    build_report,
    create_excel_report,
    format_hours,
)

router = APIRouter(prefix="/api/v1/report", tags=["report"])


def _period_label(year: int, month: int) -> str:
    return f"{month:02d}.{year}"


def _validate_month(month: int) -> None:
    if not (1 <= month <= 12):
        raise api_error(400, "INVALID_PERIOD", "month 1–12 arasında olmalıdır.")


def _report_value_error(exc: ValueError) -> None:
    message = str(exc)
    code = "MISSING_COLUMNS" if "Zorunlu sütunlar" in message else "INVALID_PERIOD"
    if "bulunamadı" in message.lower():
        code = "NO_PERIODS"
    raise api_error(400, code, message) from exc


async def _load_report_dataframe_from_request(
    file: UploadFile | None,
    upload_id: str | None,
):
    """Returns (df, upload_id_or_none)."""
    if upload_id:
        try:
            _, df = load_upload_dataframe(upload_id, "report")
        except SupabaseError as exc:
            raise api_error(404, "UPLOAD_NOT_FOUND", str(exc)) from exc
        return df, upload_id
    if file is None:
        raise api_error(400, "INVALID_FILE", "file veya upload_id gönderilmelidir.")
    data, filename = await read_upload_bytes(file)
    return load_report_dataframe(data, filename), None


def _build_result_or_raise(df, year: int, month: int) -> ReportResult:
    try:
        return build_report(df, year, month)
    except ValueError as exc:
        _report_value_error(exc)
        raise  # pragma: no cover


def _build_response_payload(result: ReportResult, year: int, month: int) -> ReportBuildResponse:
    summary = format_hour_columns(
        result.summary,
        ["Normal Çalışma", "Fazla Mesai", "FM→NM Aktarım"],
    )
    weekly = format_hour_columns(
        result.weekly,
        ["Hafta İçi NM", "Hafta Sonu Ham FM", "FM→NM Aktarım", "Toplam NM", "Kalan FM"],
    )
    daily = result.daily.copy()
    hour_cols = [c for c in daily.columns if str(c).endswith("_h")]
    daily = format_hour_columns(daily, hour_cols)

    total_nm = float(result.summary["Normal Çalışma"].sum()) if not result.summary.empty else 0.0
    total_fm = float(result.summary["Fazla Mesai"].sum()) if not result.summary.empty else 0.0

    meta = ReportMeta(
        year=year,
        month=month,
        label=_period_label(year, month),
        period_start=result.period_start.strftime("%d.%m.%Y"),
        period_end=result.period_end.strftime("%d.%m.%Y"),
        employee_count=len(result.summary),
        record_count=len(result.daily),
        total_nm=total_nm,
        total_fm=total_fm,
        total_nm_fmt=format_hours(total_nm),
        total_fm_fmt=format_hours(total_fm),
    )
    return ReportBuildResponse(
        meta=meta,
        quality=dataframe_to_records(result.quality),
        monthly=dataframe_to_records(result.monthly),
        summary=dataframe_to_records(summary),
        weekly=dataframe_to_records(weekly),
        daily=dataframe_to_records(daily),
    )


async def _resolve_report_result(
    file: UploadFile | None,
    upload_id: str | None,
    year: int,
    month: int,
    *,
    prefer_snapshot: bool,
) -> ReportResult:
    if prefer_snapshot and upload_id:
        try:
            return load_report_result_from_snapshot(upload_id, year, month)
        except SupabaseError:
            pass
        except ValueError as exc:
            raise api_error(400, "INVALID_PERIOD", str(exc)) from exc

    df, resolved_upload_id = await _load_report_dataframe_from_request(file, upload_id)
    result = _build_result_or_raise(df, year, month)
    if resolved_upload_id:
        try:
            persist_report_snapshot(resolved_upload_id, year, month, result)
        except SupabaseError as exc:
            raise api_error(500, "REPORT_STORE_ERROR", str(exc)) from exc
    return result


@router.post("/periods", response_model=PeriodsResponse)
async def list_periods(
    file: UploadFile | None = File(default=None),
    upload_id: str | None = Form(default=None),
) -> PeriodsResponse:
    if upload_id:
        try:
            upload = get_upload(upload_id, "report", touch=True)
        except SupabaseError as exc:
            raise api_error(404, "UPLOAD_NOT_FOUND", str(exc)) from exc
        metadata = upload.get("metadata") or {}
        periods = metadata.get("periods") or []
        if periods:
            return PeriodsResponse(
                periods=[
                    PeriodItem(year=int(item["year"]), month=int(item["month"]), label=str(item["label"]))
                    for item in periods
                ]
            )
        try:
            _, df = load_upload_dataframe(upload_id, "report")
        except SupabaseError as exc:
            raise api_error(404, "UPLOAD_NOT_FOUND", str(exc)) from exc
    else:
        if file is None:
            raise api_error(400, "INVALID_FILE", "file veya upload_id gönderilmelidir.")
        data, filename = await read_upload_bytes(file)
        df = load_report_dataframe(data, filename)
    periods = available_periods(df)
    if not periods:
        raise api_error(400, "NO_PERIODS", "Dosyada geçerli bir mesaitarih alanı bulunamadı.")
    return PeriodsResponse(
        periods=[
            PeriodItem(year=year, month=month, label=_period_label(year, month))
            for year, month in periods
        ]
    )


@router.post("/build", response_model=ReportBuildResponse)
async def build_monthly_report(
    file: UploadFile | None = File(default=None),
    year: int = Form(...),
    month: int = Form(...),
    upload_id: str | None = Form(default=None),
) -> ReportBuildResponse:
    _validate_month(month)

    # Preferred path: serve already-computed report snapshot for this upload/period.
    if upload_id:
        try:
            payload = load_report_response_from_snapshot(upload_id, year, month)
            return ReportBuildResponse(**payload)
        except SupabaseError:
            pass

    result = await _resolve_report_result(
        file,
        upload_id,
        year,
        month,
        prefer_snapshot=False,
    )
    return _build_response_payload(result, year, month)


@router.post("/excel")
async def download_excel_report(
    file: UploadFile | None = File(default=None),
    year: int = Form(...),
    month: int = Form(...),
    upload_id: str | None = Form(default=None),
) -> Response:
    _validate_month(month)
    result = await _resolve_report_result(
        file,
        upload_id,
        year,
        month,
        prefer_snapshot=True,
    )
    report_bytes = create_excel_report(result)
    out_name = f"Aylik_Puantaj_Raporu_{year}_{month:02d}.xlsx"
    return Response(
        content=report_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
    )


async def _read_template_bytes(template: UploadFile) -> bytes:
    data, filename = await read_upload_bytes(template)
    lower = filename.lower()
    if not lower.endswith((".xlsx", ".xlsm")):
        raise api_error(400, "INVALID_TEMPLATE", "OTOM şablonu xlsx/xlsm olmalıdır.")
    return data


@router.post("/v3/build", response_model=ReportV3BuildResponse)
async def build_monthly_report_v3(
    template: UploadFile = File(...),
    file: UploadFile | None = File(default=None),
    year: int = Form(...),
    month: int = Form(...),
    upload_id: str | None = Form(default=None),
) -> ReportV3BuildResponse:
    _validate_month(month)
    template_bytes = await _read_template_bytes(template)
    result = await _resolve_report_result(
        file,
        upload_id,
        year,
        month,
        prefer_snapshot=True,
    )
    try:
        _, fill_stats = fill_otom_template(template_bytes, result, year, month)
    except ValueError as exc:
        raise api_error(400, "INVALID_TEMPLATE", str(exc)) from exc

    base = _build_response_payload(result, year, month)
    return ReportV3BuildResponse(
        **base.model_dump(),
        fill=ReportFillStats(**fill_stats.as_dict()),
    )


@router.post("/v3/excel")
async def download_filled_template_v3(
    template: UploadFile = File(...),
    file: UploadFile | None = File(default=None),
    year: int = Form(...),
    month: int = Form(...),
    upload_id: str | None = Form(default=None),
) -> Response:
    _validate_month(month)
    template_bytes = await _read_template_bytes(template)
    result = await _resolve_report_result(
        file,
        upload_id,
        year,
        month,
        prefer_snapshot=True,
    )
    try:
        filled_bytes, _ = fill_otom_template(template_bytes, result, year, month)
    except ValueError as exc:
        raise api_error(400, "INVALID_TEMPLATE", str(exc)) from exc

    out_name = f"OTOM_Puantaj_Doldurulmus_{year}_{month:02d}.xlsx"
    return Response(
        content=filled_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
    )
