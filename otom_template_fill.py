"""OTOM aylık puantaj şablonunu rapor çıktısıyla doldurur."""

from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from puantaj_report import ReportResult, _column_key, _normalized_text


DAY_SLOT_PATTERN = re.compile(
    r"^(PT|SA|CA|PE|CU|CT|PZ)(\d+)$",
    re.IGNORECASE,
)
DAY_COLUMN_PATTERN = re.compile(r"^(0[1-9]|[12]\d|3[01]) (Pt|Sa|Ça|Pe|Cu|Ct|Pz)$")


@dataclass
class FillStats:
    matched: int = 0
    unmatched_template: list[str] = field(default_factory=list)
    unmatched_source: list[str] = field(default_factory=list)
    filled_cells: int = 0
    sheet_name: str = ""
    year: int | None = None
    month: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "matched": self.matched,
            "unmatched_template": self.unmatched_template,
            "unmatched_source": self.unmatched_source,
            "filled_cells": self.filled_cells,
            "sheet_name": self.sheet_name,
            "year": self.year,
            "month": self.month,
        }


def _header_row(ws: Worksheet) -> int:
    for row in range(1, min(6, ws.max_row + 1)):
        for col in range(1, min(20, ws.max_column + 1)):
            if _column_key(ws.cell(row, col).value) == "ADISOYADI":
                return row
    raise ValueError("Şablonda 'ADI SOYADI' başlığı bulunamadı.")


def _find_name_column(ws: Worksheet, header_row: int) -> int:
    for col in range(1, ws.max_column + 1):
        if _column_key(ws.cell(header_row, col).value) == "ADISOYADI":
            return col
    raise ValueError("Şablonda 'ADI SOYADI' kolonu bulunamadı.")


def _sheet_day_slot_count(ws: Worksheet) -> int:
    try:
        header_row = _header_row(ws)
    except ValueError:
        return 0
    return sum(
        1
        for col in range(1, ws.max_column + 1)
        if _slot_key(ws.cell(header_row, col).value)
    )


def detect_puantaj_sheet(wb) -> Worksheet:
    candidates: list[tuple[int, Worksheet]] = []
    for ws in wb.worksheets:
        slot_count = _sheet_day_slot_count(ws)
        if slot_count == 0:
            continue
        # Prefer sheets named like "2026 Puantaj".
        bonus = 100 if "PUANTAJ" in _normalized_text(ws.title) else 0
        candidates.append((slot_count + bonus, ws))
    if not candidates:
        raise ValueError("OTOM puantaj şablonu sheet'i bulunamadı (ADI SOYADI + Pt1… gerekli).")
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _slot_key(value: object) -> tuple[int, int] | None:
    text = _normalized_text(value).replace(" ", "")
    # Ça → CA after accent strip
    match = DAY_SLOT_PATTERN.fullmatch(text)
    if not match:
        return None
    weekday_token, week_text = match.group(1).upper(), match.group(2)
    weekday_order = {"PT": 0, "SA": 1, "CA": 2, "PE": 3, "CU": 4, "CT": 5, "PZ": 6}
    weekday = weekday_order.get(weekday_token)
    if weekday is None:
        return None
    return int(week_text), weekday


def resolve_day_columns(ws: Worksheet, year: int, month: int) -> dict[int, int]:
    """Ay günü (1..N) → Excel kolon index (1-based)."""
    header_row = _header_row(ws)
    week_starts: dict[int, int] = {}
    for col in range(1, ws.max_column + 1):
        slot = _slot_key(ws.cell(header_row, col).value)
        if not slot:
            continue
        week_index, weekday = slot
        if weekday == 0:
            week_starts[week_index] = col
        elif week_index not in week_starts:
            week_starts[week_index] = col - weekday

    if not week_starts:
        raise ValueError("Şablonda haftalık gün kolonları (Pt1, Sa1, …) bulunamadı.")

    days_in_month = int(pd.Timestamp(year=year, month=month, day=1).days_in_month)
    mapping: dict[int, int] = {}
    for day in range(1, days_in_month + 1):
        week_index = math.ceil(day / 7)
        offset = (day - 1) % 7
        start = week_starts.get(week_index)
        if start is None:
            continue
        mapping[day] = start + offset
    if not mapping:
        raise ValueError("Şablon gün kolonları dönem günleriyle eşleştirilemedi.")
    return mapping


def _cell_value_for_template(raw: object) -> object | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        number = float(raw)
        if number <= 0:
            return None
        return int(number) if number.is_integer() else round(number, 2)
    text = str(raw).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return None
    if text == "Z*":
        return "Z"
    # Numeric hours stored as string (e.g. "9" / "9,5")
    numeric = text.replace(",", ".")
    try:
        number = float(numeric)
    except ValueError:
        return text
    if number <= 0:
        return None
    return int(number) if number.is_integer() else round(number, 2)


def monthly_codes_by_person(monthly: pd.DataFrame) -> dict[str, dict[int, object]]:
    if monthly is None or monthly.empty:
        return {}
    day_columns = [column for column in monthly.columns if DAY_COLUMN_PATTERN.fullmatch(str(column))]
    by_person: dict[str, dict[int, object]] = {}
    for row in monthly.to_dict(orient="records"):
        name = _normalized_text(row.get("Personel", ""))
        if not name:
            continue
        day_map: dict[int, object] = {}
        for column in day_columns:
            day = int(str(column)[:2])
            value = _cell_value_for_template(row.get(column))
            if value is not None:
                day_map[day] = value
        by_person[name] = day_map
    return by_person


def fill_otom_template(
    template_bytes: bytes,
    result: ReportResult,
    year: int,
    month: int,
) -> tuple[bytes, FillStats]:
    wb = load_workbook(io.BytesIO(template_bytes))
    ws = detect_puantaj_sheet(wb)
    header_row = _header_row(ws)
    name_col = _find_name_column(ws, header_row)
    day_columns = resolve_day_columns(ws, year, month)
    source_by_name = monthly_codes_by_person(result.monthly)
    used_source: set[str] = set()

    stats = FillStats(sheet_name=ws.title, year=year, month=month)

    for row_idx in range(header_row + 1, ws.max_row + 1):
        raw_name = ws.cell(row_idx, name_col).value
        if raw_name is None or not str(raw_name).strip():
            continue
        key = _normalized_text(raw_name)
        day_map = source_by_name.get(key)
        if day_map is None:
            stats.unmatched_template.append(str(raw_name).strip())
            continue
        used_source.add(key)
        stats.matched += 1
        for day, col_idx in day_columns.items():
            if day not in day_map:
                continue
            ws.cell(row_idx, col_idx, day_map[day])
            stats.filled_cells += 1

    stats.unmatched_source = sorted(name for name in source_by_name if name not in used_source)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue(), stats
