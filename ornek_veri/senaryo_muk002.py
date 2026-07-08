"""MUK-002 dummy senaryo verisi ureticisi (`ornek_veri/uret.py` model alinmistir).

Deterministik: her calistirmada AYNI dosyalari uretir (tutarlar sabit
listelerdedir, rastgelelik yoktur). Ciktilar `output/senaryo/` altina yazilir
(gitignored) -- bu script DB'ye YAZMAZ, yalniz xlsx/json dosyasi uretir;
depoya yukleme CLI komutlariyla (`ymm yukle mizan` / `yukle beyanname-ozet`)
yapilir.

KVKK notu: tamami DUMMY veridir; gercekci kisi/firma adi KULLANILMAZ. Ortak
hesaplarinda notr takma etiket ("[ORTAK-X]") kullanilir -- bu, maskeleme
katmanini (ymm.maskeleme) tetikleyen bir isarettir.

Senaryo, Modul A (capraz kontrol) ve Modul B (statik + karsilastirmali risk
taramasi) icin onceden hesaplanmis 11 bulgu uretecek sekilde tasarlanmistir
(bkz. cagiran gorev tanimindaki "Beklenen bulgular" tablosu).
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

BASLIKLAR = [
    "Hesap Kodu",
    "Hesap Adı",
    "Borç Toplam",
    "Alacak Toplam",
    "Borç Bakiye",
    "Alacak Bakiye",
]

HEDEF_DIZIN = Path(__file__).parent.parent / "output" / "senaryo"

# (hesap_kodu, hesap_adi, borc_toplam, alacak_toplam, borc_bakiye, alacak_bakiye)
MIZAN_2025: list[tuple[str, str, Decimal, Decimal, Decimal, Decimal]] = [
    ("100", "Kasa", Decimal("900000.00"), Decimal("825000.00"), Decimal("75000.00"), Decimal("0.00")),
    ("131", "Ortaklardan Alacaklar [ORTAK-X]", Decimal("650000.00"), Decimal("200000.00"), Decimal("450000.00"), Decimal("0.00")),
    ("190", "Devreden KDV", Decimal("120000.00"), Decimal("0.00"), Decimal("120000.00"), Decimal("0.00")),
    ("191", "İndirilecek KDV", Decimal("900000.00"), Decimal("0.00"), Decimal("900000.00"), Decimal("0.00")),
    ("331", "Ortaklara Borçlar [ORTAK-X]", Decimal("100000.00"), Decimal("400000.00"), Decimal("0.00"), Decimal("300000.00")),
    ("391", "Hesaplanan KDV", Decimal("0.00"), Decimal("1500000.00"), Decimal("0.00"), Decimal("1500000.00")),
    ("600", "Yurtiçi Satışlar", Decimal("0.00"), Decimal("8000000.00"), Decimal("0.00"), Decimal("8000000.00")),
    ("689", "Diğer Olağandışı Gid.ve Zar.", Decimal("25000.00"), Decimal("0.00"), Decimal("25000.00"), Decimal("0.00")),
    ("770", "Genel Yönetim Giderleri", Decimal("1400000.00"), Decimal("0.00"), Decimal("1400000.00"), Decimal("0.00")),
]

# 2024 (onceki donem) -- Modul B karsilastirmali taramasi icin girdi
# (yalnizca karsilastirmali kurallarda kullanilan 131/770 hesaplari + baglam
# icin 600; bu dosya kendi basina dengeli bir mizan degildir, yalnizca
# karsilastirma girdisidir -- mizan_oku bunu zorunlu kilmaz).
MIZAN_2024: list[tuple[str, str, Decimal, Decimal, Decimal, Decimal]] = [
    ("131", "Ortaklardan Alacaklar [ORTAK-X]", Decimal("300000.00"), Decimal("100000.00"), Decimal("200000.00"), Decimal("0.00")),
    ("600", "Yurtiçi Satışlar", Decimal("0.00"), Decimal("6000000.00"), Decimal("0.00"), Decimal("6000000.00")),
    ("770", "Genel Yönetim Giderleri", Decimal("800000.00"), Decimal("0.00"), Decimal("800000.00"), Decimal("0.00")),
]


def _yaz(
    satirlar: list[tuple[str, str, Decimal, Decimal, Decimal, Decimal]],
    sheet_baslik: str,
    hedef: Path,
) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_baslik
    ws.append(BASLIKLAR)
    for hesap_kodu, hesap_adi, borc_toplam, alacak_toplam, borc_bakiye, alacak_bakiye in satirlar:
        ws.append(
            [
                hesap_kodu,
                hesap_adi,
                float(borc_toplam),
                float(alacak_toplam),
                float(borc_bakiye),
                float(alacak_bakiye),
            ]
        )
    hedef.parent.mkdir(parents=True, exist_ok=True)
    wb.save(hedef)
    return hedef


def uret_mizan_2025(hedef: Path | None = None) -> Path:
    """Deterministik dummy mizan_muk002_2025.xlsx uretir."""
    hedef = hedef or (HEDEF_DIZIN / "mizan_muk002_2025.xlsx")
    return _yaz(MIZAN_2025, "Mizan 2025", hedef)


def uret_mizan_2024(hedef: Path | None = None) -> Path:
    """Deterministik dummy mizan_muk002_2024.xlsx uretir (onceki donem)."""
    hedef = hedef or (HEDEF_DIZIN / "mizan_muk002_2024.xlsx")
    return _yaz(MIZAN_2024, "Mizan 2024", hedef)


def _kdv1_kayitlari() -> list[dict]:
    kayitlar: list[dict] = []
    for ay in range(1, 13):
        # 11 ay 641.666,67 + son ay 641.666,63 -> yillik kumulatif tam
        # 7.700.000,00 (kurus yuvarlama farki son aya yansitilir).
        teslim = "641666.63" if ay == 12 else "641666.67"
        kayitlar.append(
            {
                "tip": "KDV1",
                "yil": 2025,
                "donem_tip": "AY",
                "sira": ay,
                "alanlar": {
                    "teslim_hizmet_toplam": teslim,
                    "hesaplanan_kdv": "115500.00",
                    "indirilecek_kdv": "75000.00",
                },
            }
        )
    return kayitlar


def _muhsgk_kayitlari() -> list[dict]:
    return [
        {
            "tip": "MUHSGK",
            "yil": 2025,
            "donem_tip": "AY",
            "sira": ay,
            "alanlar": {"brut_ucret_toplam": "50000.00"},
        }
        for ay in range(1, 13)
    ]


def _gecici_kayitlari() -> list[dict]:
    matrahlar = ["250000.00", "500000.00", "725000.00", "950000.00"]
    return [
        {
            "tip": "GECICI",
            "yil": 2025,
            "donem_tip": "CEYREK",
            "sira": ceyrek,
            "alanlar": {"matrah": matrah},
        }
        for ceyrek, matrah in enumerate(matrahlar, start=1)
    ]


def _kv_kayitlari() -> list[dict]:
    return [
        {
            "tip": "KV",
            "yil": 2025,
            "donem_tip": "YILLIK",
            "sira": 0,
            "alanlar": {"matrah": "980000.00"},
        }
    ]


def uret_beyanname_json(hedef: Path | None = None) -> Path:
    """`beyanname_ozet.json` semasinda (bkz. `ornek_veri/beyanname_ozet.json`)
    deterministik dummy beyanname_muk002.json uretir."""
    hedef = hedef or (HEDEF_DIZIN / "beyanname_muk002.json")
    veri = {
        "beyannameler": (
            _kdv1_kayitlari()
            + _muhsgk_kayitlari()
            + _gecici_kayitlari()
            + _kv_kayitlari()
        )
    }
    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    return hedef


if __name__ == "__main__":
    for uretici in (uret_mizan_2025, uret_mizan_2024, uret_beyanname_json):
        yol = uretici()
        print(f"Uretildi: {yol}")
