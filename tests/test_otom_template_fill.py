from io import BytesIO
from pathlib import Path

import pandas as pd
from openpyxl import Workbook, load_workbook

from otom_template_fill import (
    detect_puantaj_sheet,
    fill_otom_template,
    monthly_codes_by_person,
    resolve_day_columns,
)
from puantaj_report import build_report, read_puantaj_file
from test_puantaj_report import sample_frame


FIXTURES = Path(__file__).resolve().parents[1]
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
    # Week1 day slots at cols 24-30
    for offset, label in enumerate(("Pt1", "Sa1", "Ça1", "Pe1", "Cu1", "Ct1", "Pz1")):
        ws.cell(1, 24 + offset, offset + 1)
        ws.cell(2, 24 + offset, label)
    ws.cell(2, 31, "1")
    # Week2
    for offset, label in enumerate(("Pt2", "Sa2", "Ça2", "Pe2", "Cu2", "Ct2", "Pz2")):
        ws.cell(1, 43 + offset, 8 + offset)
        ws.cell(2, 43 + offset, label)

    ws.cell(3, 3, "  TEST PERSONEL")
    ws.cell(3, 12, year)
    ws.cell(3, 13, month)
    ws.cell(4, 3, "  UNKNOWN PERSON")
    ws.cell(4, 12, year)
    ws.cell(4, 13, month)

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_resolve_day_columns_sequential_weeks():
    wb = load_workbook(BytesIO(_mini_template()))
    ws = detect_puantaj_sheet(wb)
    mapping = resolve_day_columns(ws, 2026, 6)
    assert mapping[1] == 24
    assert mapping[7] == 30
    assert mapping[8] == 43
    assert mapping[14] == 49


def test_fill_otom_template_writes_day_codes():
    result = build_report(sample_frame(), 2026, 6)
    filled, stats = fill_otom_template(_mini_template(), result, 2026, 6)
    assert stats.matched == 1
    assert stats.unmatched_template == ["UNKNOWN PERSON"]
    assert stats.filled_cells > 0

    wb = load_workbook(BytesIO(filled))
    ws = detect_puantaj_sheet(wb)
    # June 1 2026 is Monday → col 24
    assert ws.cell(3, 24).value is not None
    # Unknown person stays empty
    assert ws.cell(4, 24).value is None


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
    from puantaj_report import read_puantaj_file

    df = read_puantaj_file(JULY_CSV.open("rb"), filename=JULY_CSV.name)
    result = build_report(df, 2026, 7)
    filled, stats = fill_otom_template(JULY_TEMPLATE.read_bytes(), result, 2026, 7)
    assert stats.sheet_name.strip().endswith("Puantaj")
    assert stats.matched >= 200
    assert stats.filled_cells >= 5000
    assert filled.startswith(b"PK")
