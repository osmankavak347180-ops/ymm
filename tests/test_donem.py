"""kontrol/donem.py testleri: yıllık kümülatif toplama + eksik dönem uyarıları.

Beyanname kayıt biçimi (bkz. ornek_veri/beyanname_ozet.json):
    {"tip": str, "yil": int, "donem_tip": "AY"|"CEYREK"|"YILLIK", "sira": int,
     "alanlar": {alan_adi: "tutar-string"}}
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from ymm.kontrol.donem import yillik_kumulatif

_ORNEK_VERI = Path(__file__).parent.parent / "ornek_veri" / "beyanname_ozet.json"


def _ay_kaydi(sira: int, tutar: str) -> dict:
    return {
        "tip": "KDV1",
        "yil": 2025,
        "donem_tip": "AY",
        "sira": sira,
        "alanlar": {"teslim_hizmet_toplam": tutar},
    }


def test_12_aylik_kayitla_kumulatif_toplam_dogru_ve_uyari_bos():
    kayitlar = [_ay_kaydi(i, "408333.33") for i in range(1, 12)] + [
        _ay_kaydi(12, "408333.37")
    ]

    toplam, uyarilar = yillik_kumulatif(kayitlar, "teslim_hizmet_toplam")

    assert toplam == Decimal("4900000.00")
    assert isinstance(toplam, Decimal)
    assert uyarilar == []


def test_11_kayitla_eksik_donem_uyarisi_uretilir_ve_sira_belirtilir():
    # sira 12 eksik
    kayitlar = [_ay_kaydi(i, "408333.33") for i in range(1, 12)]

    toplam, uyarilar = yillik_kumulatif(kayitlar, "teslim_hizmet_toplam")

    assert len(uyarilar) == 1
    assert "12" in uyarilar[0]


def test_ortadaki_ay_eksikse_o_sira_raporlanir():
    kayitlar = [_ay_kaydi(i, "100.00") for i in range(1, 13) if i != 7]

    toplam, uyarilar = yillik_kumulatif(kayitlar, "teslim_hizmet_toplam")

    assert toplam == Decimal("1100.00")
    assert len(uyarilar) == 1
    assert "7" in uyarilar[0]


def test_ceyreklik_4_kayitla_uyari_yok():
    kayitlar = [
        {
            "tip": "GECICI",
            "yil": 2025,
            "donem_tip": "CEYREK",
            "sira": i,
            "alanlar": {"matrah": tutar},
        }
        for i, tutar in enumerate(
            ["150000.00", "300000.00", "450000.00", "600000.00"], start=1
        )
    ]

    toplam, uyarilar = yillik_kumulatif(kayitlar, "matrah")

    assert toplam == Decimal("1500000.00")
    assert uyarilar == []


def test_ceyreklik_3_kayitla_eksik_ceyrek_uyarisi():
    kayitlar = [
        {
            "tip": "GECICI",
            "yil": 2025,
            "donem_tip": "CEYREK",
            "sira": i,
            "alanlar": {"matrah": "100000.00"},
        }
        for i in (1, 2, 3)
    ]

    _, uyarilar = yillik_kumulatif(kayitlar, "matrah")

    assert len(uyarilar) == 1
    assert "4" in uyarilar[0]


def test_bos_liste_toplam_sifir_ve_uyari_doner():
    toplam, uyarilar = yillik_kumulatif([], "teslim_hizmet_toplam")

    assert toplam == Decimal("0")
    assert uyarilar != []


def test_ornek_veri_kdv1_kumulatif_tam_4900000():
    """Sabit anchor: Task 1.2/1.3 bu değeri kullanır."""
    veri = json.loads(_ORNEK_VERI.read_text(encoding="utf-8"))
    kdv_kayitlari = [
        k
        for k in veri["beyannameler"]
        if k["tip"] == "KDV1" and k["yil"] == 2025
    ]

    toplam, uyarilar = yillik_kumulatif(kdv_kayitlari, "teslim_hizmet_toplam")

    assert toplam == Decimal("4900000.00")
    assert uyarilar == []


def test_ornek_veri_gecici_dorduncu_donem_ve_kv_farki_1000_tl_ustunde():
    veri = json.loads(_ORNEK_VERI.read_text(encoding="utf-8"))
    gecici_4 = next(
        k
        for k in veri["beyannameler"]
        if k["tip"] == "GECICI" and k["sira"] == 4
    )
    kv = next(k for k in veri["beyannameler"] if k["tip"] == "KV")

    fark = Decimal(kv["alanlar"]["matrah"]) - Decimal(gecici_4["alanlar"]["matrah"])

    assert fark > Decimal("1000.00")
