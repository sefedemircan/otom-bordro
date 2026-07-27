from datetime import time

import pandas as pd

from puantaj_calc import calculate_puantaj


def july_week_with_june_context(*, june_absent: bool = True):
    """Temmuz 2026 Çarşamba başlar; ISO hafta: 29–30 Haz + 1–5 Tem."""
    rows = []
    for day in (29, 30):
        rows.append({
            "sicilno": "00010",
            "Ad": "BAGLAM",
            "Soyad": "TEST",
            "mesaitarih": pd.Timestamp(2026, 6, day),
            "NM": time(0) if june_absent else time(9),
            "FM": time(0),
            "MS": time(9),
            "EM": time(0),
            "IZS": time(0),
            "YIZS": time(0),
            "SGKIZS": time(0),
            "UCZIZS": time(0),
            "RM": time(0),
            "İzin Açıklama": "#__#",
        })
    for day in range(1, 6):
        is_weekday = day <= 3
        rows.append({
            "sicilno": "00010",
            "Ad": "BAGLAM",
            "Soyad": "TEST",
            "mesaitarih": pd.Timestamp(2026, 7, day),
            "NM": time(9) if is_weekday else time(0),
            "FM": time(0),
            "MS": time(9) if is_weekday else time(0),
            "EM": time(0),
            "IZS": time(0),
            "YIZS": time(0),
            "SGKIZS": time(0),
            "UCZIZS": time(0),
            "RM": time(0),
            "İzin Açıklama": "#__#",
        })
    return pd.DataFrame(rows)


def test_context_absence_burns_sunday_but_excluded_from_totals():
    _, daily, weekly, _, summary = calculate_puantaj(july_week_with_june_context(june_absent=True))

    assert summary["period_year"] == 2026
    assert summary["period_month"] == 7
    assert summary["baglam_gun"] == 2
    assert summary["toplam_nm"] == 27.0
    assert summary["toplam_gun"] == 5
    assert summary["devamsizlik_gun"] == 0
    assert summary["pazar_yanan_hafta"] == 1
    assert weekly.loc[0, "Pazar Durumu"] == "Yanar"
    assert weekly.loc[0, "Pazar Kaynağı"] == "Bağlam"
    assert weekly.loc[0, "Tür"] == "Tam"
    assert weekly.loc[0, "Gün (dosyada)"] == 7

    context_rows = daily[daily["Bağlam"] == "Evet"]
    assert len(context_rows) == 2
    period_rows = daily[daily["Bağlam"] == "Hayır"]
    assert len(period_rows) == 5


def test_context_worked_keeps_sunday_and_excludes_june_nm():
    _, daily, weekly, _, summary = calculate_puantaj(
        july_week_with_june_context(june_absent=False)
    )

    assert summary["toplam_nm"] == 27.0  # Haziran 2×9 dönem toplamına girmez
    assert summary["baglam_gun"] == 2
    assert summary["pazar_yanan_hafta"] == 0
    assert weekly.loc[0, "Pazar Durumu"] == "Hak Edildi"
    assert set(daily.loc[daily["Bağlam"] == "Evet", "Gün Durumu"]) == {"Çalışma"}


def test_explicit_period_overrides_majority_month():
    # Daha çok Haziran günü olsa bile year/month ile Temmuz seçilir
    rows = []
    for day in range(20, 31):
        rows.append({
            "sicilno": "1",
            "Ad": "A",
            "Soyad": "B",
            "mesaitarih": pd.Timestamp(2026, 6, day),
            "NM": time(9) if pd.Timestamp(2026, 6, day).dayofweek < 5 else time(0),
            "FM": time(0),
            "MS": time(9),
            "İzin Açıklama": "#__#",
        })
    for day in range(1, 6):
        rows.append({
            "sicilno": "1",
            "Ad": "A",
            "Soyad": "B",
            "mesaitarih": pd.Timestamp(2026, 7, day),
            "NM": time(9) if day <= 3 else time(0),
            "FM": time(0),
            "MS": time(9) if day <= 3 else time(0),
            "İzin Açıklama": "#__#",
        })
    _, _, weekly, _, summary = calculate_puantaj(pd.DataFrame(rows), year=2026, month=7)
    assert summary["period_month"] == 7
    assert summary["baglam_gun"] == 11
    assert summary["toplam_gun"] == 5
    assert weekly.loc[0, "Tür"] == "Tam"
