"""Persist monthly report outputs for AI SQL queries."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from api.deps import dataframe_to_records
from api.services.supabase import SupabaseClient, SupabaseError
from puantaj_report import ReportResult, format_hours


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


def _summary_rows(upload_id: str, run_id: str, summary_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(summary_records):
        out.append(
            {
                "run_id": run_id,
                "upload_id": upload_id,
                "dataset": "summary",
                "row_index": idx,
                "sicil_no": row.get("Sicil No"),
                "personel": row.get("Personel"),
                "firma": row.get("Firma"),
                "bolum": row.get("Bölüm"),
                "pozisyon": row.get("Pozisyon"),
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
                "row_data": row,
            }
        )
    return out


def _weekly_rows(upload_id: str, run_id: str, weekly_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(weekly_records):
        out.append(
            {
                "run_id": run_id,
                "upload_id": upload_id,
                "dataset": "weekly",
                "row_index": idx,
                "sicil_no": row.get("Sicil No"),
                "personel": row.get("Personel"),
                "hafta": row.get("Hafta"),
                "normal_calisma": _safe_float(row.get("Toplam NM") or row.get("Hafta İçi NM")),
                "fazla_mesai": _safe_float(row.get("Kalan FM") or row.get("Hafta Sonu Ham FM")),
                "fm_nm_aktarim": _safe_float(row.get("FM→NM Aktarım")),
                "pazar_durumu": row.get("Pazar Durumu"),
                "row_data": row,
            }
        )
    return out


def _daily_rows(upload_id: str, run_id: str, daily_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(daily_records):
        out.append(
            {
                "run_id": run_id,
                "upload_id": upload_id,
                "dataset": "daily",
                "row_index": idx,
                "sicil_no": row.get("Sicil No"),
                "personel": row.get("Personel"),
                "firma": row.get("Firma"),
                "bolum": row.get("Bölüm"),
                "pozisyon": row.get("Pozisyon"),
                "tarih": _parse_date(row.get("Tarih")),
                "kod": row.get("Kod"),
                "durum_aciklamasi": row.get("Durum Açıklaması"),
                "pazar_durumu": row.get("Pazar Durumu"),
                "nm_guncel": _safe_float(row.get("NM Güncel_h")),
                "fm_guncel": _safe_float(row.get("FM Güncel_h")),
                "row_data": row,
            }
        )
    return out


def _monthly_rows(upload_id: str, run_id: str, monthly_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(monthly_records):
        out.append(
            {
                "run_id": run_id,
                "upload_id": upload_id,
                "dataset": "monthly",
                "row_index": idx,
                "sicil_no": row.get("Sicil No"),
                "personel": row.get("Personel"),
                "firma": row.get("Firma"),
                "bolum": row.get("Bölüm"),
                "pozisyon": row.get("Pozisyon"),
                "row_data": row,
            }
        )
    return out


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

    rows = (
        _summary_rows(upload_id, run["id"], summary_records)
        + _weekly_rows(upload_id, run["id"], weekly_records)
        + _daily_rows(upload_id, run["id"], daily_records)
        + _monthly_rows(upload_id, run["id"], monthly_records)
    )
    for chunk in _chunked(rows):
        client.insert_rows("payroll_report_rows", chunk)
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
