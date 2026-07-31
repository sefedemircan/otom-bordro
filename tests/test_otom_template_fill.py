from datetime import time
from io import BytesIO
from pathlib import Path

import pandas as pd
from openpyxl import Workbook, load_workbook

from otom_template_fill import (
    compute_carryover_hours,
    detect_puantaj_sheet,
    fill_otom_template,
    monthly_codes_by_person,
    resolve_day_columns,
)
from puantaj_report import build_report, prepare_daily, read_puantaj_file, _normalized_text
from test_puantaj_report import sample_frame


WEB_PUBLIC = Path(r"c:\Users\efecan.demircan\Desktop\otom-bordro-web\otom\public")
JULY_TEMPLATE = WEB_PUBLIC / "TEMMUZ OTOM PUANTAJ KOPYA.xlsx"
JULY_CSV = WEB_PUBLIC / "download 2.csv"


def _mini_template(year: int = 2026, month: int = 6) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "2026 Puantaj"
    headers = [
        "Ayid",
        "SN",
        " ADI SOYADI",
        "Görevi",
        "ŞUBE",
        "Departman",
        "m/s",
        "Saatlik",
        "Ücret",
        "GİRİŞ",
        "ÇIKIŞ",
        "Yıl",
        "Ay",
    ]
    for col, header in enumerate(headers, 1):
        ws.cell(2, col, header)
    ws.cell(2, 23, "Önceki ay son hafta devreden fiili çalışma s.")
    for offset, label in enumerate(("Pt1", "Sa1", "Ça1", "Pe1", "Cu1", "Ct1", "Pz1")):
        ws.cell(1, 24 + offset, offset + 1)
        ws.cell(2, 24 + offset, label)
    ws.cell(2, 31, "1")
    for offset, label in enumerate(("Pt2", "Sa2", "Ça2", "Pe2", "Cu2", "Ct2", "Pz2")):
        ws.cell(1, 43 + offset, 8 + offset)
        ws.cell(2, 43 + offset, label)
    for offset, label in enumerate(("Pt3", "Sa3", "Ça3", "Pe3", "Cu3", "Ct3", "Pz3")):
        ws.cell(2, 62 + offset, label)
    for offset, label in enumerate(("Pt4", "Sa4", "Ça4", "Pe4", "Cu4", "Ct4", "Pz4")):
        ws.cell(2, 81 + offset, label)
    for offset, label in enumerate(("Pt5", "Sa5", "Ça5", "Pe5", "Cu5", "Ct5", "Pz5")):
        ws.cell(2, 100 + offset, label)

    ws.cell(3, 3, "  TEST PERSONEL")
    ws.cell(3, 12, year)
    ws.cell(3, 13, month)
    ws.cell(4, 3, "  UNKNOWN PERSON")
    ws.cell(4, 12, year)
    ws.cell(4, 13, month)

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_resolve_day_columns_monday_start_june():
    # June 2026 starts Monday → day 1 = Pt1
    wb = load_workbook(BytesIO(_mini_template(2026, 6)))
    ws = detect_puantaj_sheet(wb)
    mapping = resolve_day_columns(ws, 2026, 6)
    assert mapping[1] == 24  # Pt1
    assert mapping[7] == 30  # Pz1
    assert mapping[8] == 43  # Pt2


def test_resolve_day_columns_wednesday_start_july():
    # July 2026 starts Wednesday → day 1 = Ça1, Pt1/Sa1 unused
    wb = load_workbook(BytesIO(_mini_template(2026, 7)))
    ws = detect_puantaj_sheet(wb)
    mapping = resolve_day_columns(ws, 2026, 7)
    assert mapping[1] == 26  # Ça1
    assert mapping[2] == 27  # Pe1
    assert mapping[5] == 30  # July 5 Sunday = Pz1
    assert mapping[6] == 43  # July 6 Monday = Pt2
    assert mapping[31] == 104  # July 31 Friday = Cu5
    assert 24 not in mapping.values()  # Pt1 unused
    assert 25 not in mapping.values()  # Sa1 unused


def test_fill_otom_template_writes_day_codes():
    result = build_report(sample_frame(), 2026, 6)
    filled, stats = fill_otom_template(_mini_template(), result, 2026, 6)
    assert stats.matched == 1
    assert stats.unmatched_template == ["UNKNOWN PERSON"]
    assert stats.filled_cells > 0

    wb = load_workbook(BytesIO(filled))
    ws = detect_puantaj_sheet(wb)
    assert ws.cell(3, 24).value is not None
    assert ws.cell(4, 24).value is None


def test_july_alignment_leaves_pt1_sa1_empty_and_fills_carry():
    rows = []
    # Previous month Mon-Tue that belong to July's first week
    for day, nm in ((29, 9), (30, 9)):
        rows.append({
            "sicilno": "00001",
            "Ad": "TEST",
            "Soyad": "PERSONEL",
            "mesaitarih": pd.Timestamp(2026, 6, day),
            "NM": time(nm),
            "FM": time(0),
            "MS": time(9),
            "EM": time(0),
            "IZS": time(0),
            "YIZS": time(0),
            "SGKIZS": time(0),
            "UCZIZS": time(0),
            "RM": time(0),
            "İzin Açıklama": "#__#",
            "Bölüm": "Üretim",
        })
    # July days Wed-Sun
    for day in range(1, 8):
        rows.append({
            "sicilno": "00001",
            "Ad": "TEST",
            "Soyad": "PERSONEL",
            "mesaitarih": pd.Timestamp(2026, 7, day),
            "NM": time(9) if day <= 5 else time(0),
            "FM": time(0),
            "MS": time(9) if day <= 5 else time(0),
            "EM": time(0),
            "IZS": time(0),
            "YIZS": time(0),
            "SGKIZS": time(0),
            "UCZIZS": time(0),
            "RM": time(0),
            "İzin Açıklama": "#__#",
            "Bölüm": "Üretim",
        })
    source = pd.DataFrame(rows)
    result = build_report(source, 2026, 7)
    filled, stats = fill_otom_template(
        _mini_template(2026, 7),
        result,
        2026,
        7,
        source_df=source,
    )
    wb = load_workbook(BytesIO(filled))
    ws = detect_puantaj_sheet(wb)

    assert ws.cell(3, 24).value is None  # Pt1 empty
    assert ws.cell(3, 25).value is None  # Sa1 empty
    assert ws.cell(3, 26).value is not None  # Ça1 = July 1
    assert ws.cell(3, 23).value == 18  # 9+9 carry
    assert stats.carry_filled == 1


def test_monthly_codes_normalize_z_star():
    monthly = pd.DataFrame(
        [
            {
                "Personel": "Ali Veli",
                "01 Pt": "Z*",
                "02 Sa": 9.0,
                "03 Ça": "T",
            }
        ]
    )
    by_person = monthly_codes_by_person(monthly)
    assert by_person["ALI VELI"][1] == "Z"
    assert by_person["ALI VELI"][2] == 9
    assert by_person["ALI VELI"][3] == "T"


def test_july_real_files_smoke():
    if not JULY_TEMPLATE.exists() or not JULY_CSV.exists():
        return

    df = read_puantaj_file(JULY_CSV.open("rb"), filename=JULY_CSV.name)
    result = build_report(df, 2026, 7)
    filled, stats = fill_otom_template(
        JULY_TEMPLATE.read_bytes(),
        result,
        2026,
        7,
        source_df=df,
    )
    assert stats.sheet_name.strip().endswith("Puantaj")
    assert stats.matched >= 200
    assert stats.filled_cells >= 5000
    assert stats.carry_filled >= 1
    assert filled.startswith(b"PK")

    wb = load_workbook(BytesIO(filled))
    ws = detect_puantaj_sheet(wb)
    src = {_normalized_text(p) for p in result.monthly["Personel"]}
    matched_row = None
    for row_idx in range(3, ws.max_row + 1):
        name = ws.cell(row_idx, 3).value
        if name and _normalized_text(name) in src:
            matched_row = row_idx
            break
    assert matched_row is not None
    assert ws.cell(matched_row, 24).value in (None, "")
    assert ws.cell(matched_row, 25).value in (None, "")
    assert ws.cell(matched_row, 26).value is not None  # Ça1
