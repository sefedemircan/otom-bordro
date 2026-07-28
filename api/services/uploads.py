"""Persist and reload temporary payroll uploads from Supabase."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from api.deps import dataframe_to_records, load_calc_dataframe, load_report_dataframe, rows_to_dataframe
from api.services.supabase import SupabaseClient, SupabaseError
from puantaj_calc import build_employee_list, is_bulk_file
from puantaj_report import available_periods

UploadSource = Literal["report", "calc"]

_NUMERIC_KEYS = ("MS", "NM", "FM", "IZS", "YIZS", "SGKIZS", "UCZIZS", "RM", "EM")
_UPLOAD_TTL_HOURS = 24


def _pick(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _parse_date(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d.%m.%Y %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _normalize_row(upload_id: str, row_index: int, row: dict[str, Any]) -> dict[str, Any]:
    dt = _parse_date(_pick(row, "mesaitarih", "Tarih"))
    ad = _pick(row, "Ad")
    soyad = _pick(row, "Soyad")
    personel = _pick(row, "Personel")
    if not personel and (ad or soyad):
        personel = " ".join(part for part in [str(ad or "").strip(), str(soyad or "").strip()] if part).strip()
    normalized = {
        "upload_id": upload_id,
        "row_index": row_index,
        "sicilno": _pick(row, "sicilno", "Sicil No", "Sicil"),
        "ad": ad,
        "soyad": soyad,
        "personel": personel or None,
        "firma": _pick(row, "Firma"),
        "bolum": _pick(row, "Bölüm", "Bolum"),
        "pozisyon": _pick(row, "Pozisyon"),
        "mesaitarih": dt.date().isoformat() if dt else None,
        "row_year": dt.year if dt else None,
        "row_month": dt.month if dt else None,
        "row_data": row,
    }
    for key in _NUMERIC_KEYS:
        normalized[key.lower()] = _safe_float(row.get(key))
    return normalized


def _chunked(rows: list[dict[str, Any]], size: int = 500) -> list[list[dict[str, Any]]]:
    return [rows[i : i + size] for i in range(0, len(rows), size)]


def _build_report_metadata(records: list[dict[str, Any]]) -> dict[str, Any]:
    df = rows_to_dataframe(records)
    periods = available_periods(df)
    return {
        "columns": list(df.columns),
        "periods": [{"year": year, "month": month, "label": f"{month:02d}.{year}"} for year, month in periods],
    }


def _build_calc_metadata(records: list[dict[str, Any]]) -> dict[str, Any]:
    df = rows_to_dataframe(records)
    bulk = is_bulk_file(df)
    employees = dataframe_to_records(build_employee_list(df)) if bulk or ("sicilno" in df.columns and df["sicilno"].notna().any()) else []
    return {
        "columns": list(df.columns),
        "is_bulk": bulk,
        "employees": employees,
    }


def _build_metadata(source_type: UploadSource, records: list[dict[str, Any]]) -> dict[str, Any]:
    if source_type == "report":
        return _build_report_metadata(records)
    return _build_calc_metadata(records)


def _load_source_dataframe(data: bytes, filename: str, source_type: UploadSource):
    if source_type == "report":
        return load_report_dataframe(data, filename)
    return load_calc_dataframe(data, filename)


def _ensure_upload(upload: dict[str, Any] | None, upload_id: str, source_type: UploadSource | None = None) -> dict[str, Any]:
    if not upload:
        raise SupabaseError(f"Upload kaydı bulunamadı: {upload_id}")
    expires_at = _parse_date(upload.get("expires_at"))
    if expires_at and expires_at <= datetime.utcnow():
        raise SupabaseError("Upload süresi dolmuş. Dosyayı yeniden yükleyin.")
    if source_type and upload.get("source_type") != source_type:
        raise SupabaseError("Upload türü beklenen veri seti ile uyuşmuyor.")
    return upload


def create_upload(
    data: bytes,
    filename: str,
    source_type: UploadSource,
    *,
    content_type: str | None = None,
) -> dict[str, Any]:
    df = _load_source_dataframe(data, filename, source_type)
    records = dataframe_to_records(df)
    metadata = _build_metadata(source_type, records)
    client = SupabaseClient.from_env()
    upload = client.insert_row(
        "payroll_uploads",
        {
            "source_type": source_type,
            "filename": filename,
            "content_type": content_type or "application/octet-stream",
            "file_size": len(data),
            "row_count": len(records),
            "metadata": metadata,
        },
    )
    normalized_rows = [_normalize_row(upload["id"], idx, row) for idx, row in enumerate(records)]
    for chunk in _chunked(normalized_rows):
        client.insert_rows("payroll_upload_rows", chunk)
    return upload


def get_upload(upload_id: str, source_type: UploadSource | None = None, *, touch: bool = False) -> dict[str, Any]:
    client = SupabaseClient.from_env()
    upload = client.select_single(
        "payroll_uploads",
        filters={"id": ("eq", upload_id)},
    )
    upload = _ensure_upload(upload, upload_id, source_type)
    if touch:
        updated = client.update_rows(
            "payroll_uploads",
            {"last_accessed_at": datetime.utcnow().isoformat()},
            filters={"id": ("eq", upload_id)},
        )
        if updated:
            upload = updated[0]
    return upload


def load_upload_rows(upload_id: str, source_type: UploadSource | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    upload = get_upload(upload_id, source_type, touch=True)
    client = SupabaseClient.from_env()
    rows = client.select_rows(
        "payroll_upload_rows",
        columns="row_data",
        filters={"upload_id": ("eq", upload_id)},
        order="row_index.asc",
    )
    records = [row["row_data"] for row in rows if isinstance(row.get("row_data"), dict)]
    return upload, records


def load_upload_dataframe(upload_id: str, source_type: UploadSource | None = None):
    upload, records = load_upload_rows(upload_id, source_type)
    return upload, rows_to_dataframe(records)

