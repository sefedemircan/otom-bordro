"""Persist monthly report outputs for AI SQL queries."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from api.deps import dataframe_to_records
from api.services.supabase import SupabaseClient, SupabaseError
from puantaj_report import ReportResult, format_hours

# PostgREST requires all objects in a batch insert to share the same keys.
_ROW_KEYS = (
    "run_id",
    "upload_id",
    "dataset",
    "row_index",
    "sicil_no",
    "personel",
    "firma",
    "bolum",
    "pozisyon",
    "calisma_gunu",
    "normal_calisma",
    "fazla_mesai",
    "fm_nm_aktarim",
    "yillik_izin_gun",
    "ucretli_izin_gun",
    "rapor_gun",
    "ucretsiz_izin_gun",
    "devamsizlik_gun",
    "hafta_tatili_gun",
    "pazar_kesintisi",
    "hafta",
    "tarih",
    "kod",
    "durum_aciklamasi",
    "pazar_durumu",
    "nm_guncel",
    "fm_guncel",
    "row_data",
)


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


def _safe_int(value: Any) -> int | None:
    number = _safe_float(value)
    if number is None:
        return None
    return int(number)


def _parse_date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    text = str(value).strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _chunked(rows: list[dict[str, Any]], size: int = 400) -> list[list[dict[str, Any]]]:
    return [rows[i : i + size] for i in range(0, len(rows), size)]


def _base_row(upload_id: str, run_id: str, dataset: str, row_index: int, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "upload_id": upload_id,
        "dataset": dataset,
        "row_index": row_index,
        "sicil_no": row.get("Sicil No"),
        "personel": row.get("Personel"),
        "firma": row.get("Firma"),
        "bolum": row.get("Bölüm"),
        "pozisyon": row.get("Pozisyon"),
        "calisma_gunu": None,
        "normal_calisma": None,
        "fazla_mesai": None,
        "fm_nm_aktarim": None,
        "yillik_izin_gun": None,
        "ucretli_izin_gun": None,
        "rapor_gun": None,
        "ucretsiz_izin_gun": None,
        "devamsizlik_gun": None,
        "hafta_tatili_gun": None,
        "pazar_kesintisi": None,
        "hafta": None,
        "tarih": None,
        "kod": None,
        "durum_aciklamasi": None,
        "pazar_durumu": None,
        "nm_guncel": None,
        "fm_guncel": None,
        "row_data": row,
    }


def _normalize_keys(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row.get(key) for key in _ROW_KEYS}


def _summary_rows(upload_id: str, run_id: str, summary_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(summary_records):
        item = _base_row(upload_id, run_id, "summary", idx, row)
        item.update(
            {
                "calisma_gunu": _safe_int(row.get("Çalışma Günü")),
                "normal_calisma": _safe_float(row.get("Normal Çalışma")),
                "fazla_mesai": _safe_float(row.get("Fazla Mesai")),
                "fm_nm_aktarim": _safe_float(row.get("FM→NM Aktarım")),
                "yillik_izin_gun": _safe_int(row.get("Yıllık İzin (gün)")),
                "ucretli_izin_gun": _safe_int(row.get("Ücretli İzin (gün)")),
                "rapor_gun": _safe_int(row.get("Rapor (gün)")),
                "ucretsiz_izin_gun": _safe_int(row.get("Ücretsiz İzin (gün)")),
                "devamsizlik_gun": _safe_int(row.get("Devamsızlık (gün)")),
                "hafta_tatili_gun": _safe_int(row.get("Hafta Tatili (gün)")),
                "pazar_kesintisi": _safe_int(row.get("Pazar Kesintisi")),
            }
        )
        out.append(_normalize_keys(item))
    return out


def _weekly_rows(upload_id: str, run_id: str, weekly_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(weekly_records):
        item = _base_row(upload_id, run_id, "weekly", idx, row)
        item.update(
            {
                "hafta": row.get("Hafta"),
                "normal_calisma": _safe_float(row.get("Toplam NM") or row.get("Hafta İçi NM")),
                "fazla_mesai": _safe_float(row.get("Kalan FM") or row.get("Hafta Sonu Ham FM")),
                "fm_nm_aktarim": _safe_float(row.get("FM→NM Aktarım")),
                "pazar_durumu": row.get("Pazar Durumu"),
            }
        )
        out.append(_normalize_keys(item))
    return out


def _daily_rows(upload_id: str, run_id: str, daily_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(daily_records):
        item = _base_row(upload_id, run_id, "daily", idx, row)
        item.update(
            {
                "tarih": _parse_date(row.get("Tarih")),
                "kod": None if row.get("Kod") is None else str(row.get("Kod")),
                "durum_aciklamasi": row.get("Durum Açıklaması"),
                "pazar_durumu": row.get("Pazar Durumu"),
                "nm_guncel": _safe_float(row.get("NM Güncel_h")),
                "fm_guncel": _safe_float(row.get("FM Güncel_h")),
            }
        )
        out.append(_normalize_keys(item))
    return out


def _monthly_rows(upload_id: str, run_id: str, monthly_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(monthly_records):
        item = _base_row(upload_id, run_id, "monthly", idx, row)
        out.append(_normalize_keys(item))
    return out


def _insert_dataset(client: SupabaseClient, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    for chunk in _chunked(rows):
        client.insert_rows("payroll_report_rows", chunk)


def persist_report_snapshot(
    upload_id: str,
    year: int,
    month: int,
    result: ReportResult,
) -> dict[str, Any]:
    client = SupabaseClient.from_env()
    # Replace previous snapshot for the same period.
    client.delete_rows(
        "payroll_report_runs",
        filters={
            "upload_id": ("eq", upload_id),
            "year": ("eq", year),
            "month": ("eq", month),
        },
    )

    summary_records = dataframe_to_records(result.summary)
    weekly_records = dataframe_to_records(result.weekly)
    daily_records = dataframe_to_records(result.daily)
    monthly_records = dataframe_to_records(result.monthly)

    total_nm = float(result.summary["Normal Çalışma"].sum()) if not result.summary.empty else 0.0
    total_fm = float(result.summary["Fazla Mesai"].sum()) if not result.summary.empty else 0.0
    label = f"{month:02d}.{year}"

    run = client.insert_row(
        "payroll_report_runs",
        {
            "upload_id": upload_id,
            "year": year,
            "month": month,
            "label": label,
            "period_start": result.period_start.date().isoformat(),
            "period_end": result.period_end.date().isoformat(),
            "employee_count": len(result.summary),
            "record_count": len(result.daily),
            "total_nm": total_nm,
            "total_fm": total_fm,
            "meta": {
                "total_nm_fmt": format_hours(total_nm),
                "total_fm_fmt": format_hours(total_fm),
            },
        },
    )

    run_id = run["id"]
    _insert_dataset(client, _summary_rows(upload_id, run_id, summary_records))
    _insert_dataset(client, _weekly_rows(upload_id, run_id, weekly_records))
    _insert_dataset(client, _daily_rows(upload_id, run_id, daily_records))
    _insert_dataset(client, _monthly_rows(upload_id, run_id, monthly_records))
    return run


def get_report_run(upload_id: str, year: int, month: int) -> dict[str, Any]:
    client = SupabaseClient.from_env()
    run = client.select_single(
        "payroll_report_runs",
        filters={
            "upload_id": ("eq", upload_id),
            "year": ("eq", year),
            "month": ("eq", month),
        },
        order="created_at.desc",
    )
    if not run:
        raise SupabaseError(
            f"Bu dönem için rapor snapshot bulunamadı ({month:02d}.{year}). Önce raporu oluşturun."
        )
    return run
