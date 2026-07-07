"""kontrol/motor.py testi: A-MUHSGK-UCRET kontrolü.

Senaryolar (bkz. .superpowers/sdd/task-1.3-brief.md):
- pozitif: MUHSGK kümülatif brüt ücret 1.200.000,00 (12 ay x 100.000,00) ~
  mizan 770 borç bakiye 800.000,00 -> fark 400.000,00, %50 -> seviye "yuksek".
- negatif: mizan 770 tutarı MUHSGK kümülatifine eşitse (tolerans içi) ->
  bulgu YOK.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from ymm.db.depo import Depo
from ymm.kontrol.motor import kontrolleri_calistir
from ymm.modeller import Donem, MizanSatiri

_KONFIG_YOLU = Path(__file__).parent.parent / "config" / "kontrol_kurallari.yaml"


@pytest.fixture
def depo(tmp_path):
    return Depo(tmp_path / "veri.db")


def _muhsgk_beyannameleri_yukle(depo, mukellef_id, yil=2025, aylik_tutar="100000.00"):
    """12 aylık MUHSGK beyannamesi yazar (varsayılan kümülatif 1.200.000,00)."""
    for sira in range(1, 13):
        donem_id = depo.donem_ekle(mukellef_id, Donem(yil=yil, tip="AY", sira=sira))
        depo.beyanname_yaz(donem_id, "MUHSGK", {"brut_ucret_toplam": aylik_tutar})


def _770_satiri(borc_bakiye: str) -> MizanSatiri:
    return MizanSatiri(
        hesap_kodu="770",
        hesap_adi="Genel Yönetim Giderleri",
        borc_toplam=Decimal(borc_bakiye),
        alacak_toplam=Decimal("0"),
        borc_bakiye=Decimal(borc_bakiye),
        alacak_bakiye=Decimal("0"),
    )


def _mizan_yukle(depo, mukellef_id, satirlar, yil=2025):
    donem_id = depo.donem_ekle(mukellef_id, Donem(yil=yil, tip="YILLIK", sira=0))
    depo.mizan_yaz(donem_id, satirlar)


def _yukle_konfig() -> dict:
    return yaml.safe_load(_KONFIG_YOLU.read_text(encoding="utf-8"))


def _yalniz_muhsgk_kontrolu(konfig: dict) -> dict:
    """Diğer kontroller (A-KDV-HASILAT vb.) devreye girmesin diye yalnız
    A-MUHSGK-UCRET'i içeren bir konfig dönerir."""
    konfig = dict(konfig)
    konfig["kontroller"] = [
        k for k in konfig["kontroller"] if k["kod"] == "A-MUHSGK-UCRET"
    ]
    return konfig


def test_pozitif_fark_yuksek_seviye_bulgu_uretir(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _muhsgk_beyannameleri_yukle(depo, mukellef_id)  # kümülatif 1.200.000,00
    _mizan_yukle(depo, mukellef_id, [_770_satiri("800000.00")])

    konfig = _yalniz_muhsgk_kontrolu(_yukle_konfig())
    bulgular = kontrolleri_calistir(depo, mukellef_id, 2025, konfig)

    assert len(bulgular) == 1
    bulgu = bulgular[0]
    assert bulgu.kaynak == "A"
    assert bulgu.kontrol_kodu == "A-MUHSGK-UCRET"
    assert bulgu.tutar_fark == Decimal("400000.00")
    assert bulgu.yuzde_fark == pytest.approx(50.0, abs=0.01)
    assert bulgu.seviye == "yuksek"
    assert bulgu.detay["sol_tutar"] == "1200000.00"
    assert bulgu.detay["sag_tutar"] == "800000.00"
    assert bulgu.mukellef_id == mukellef_id
    assert bulgu.yil == 2025


def test_negatif_mizan_kumulatife_esitse_bulgu_uretilmez(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _muhsgk_beyannameleri_yukle(depo, mukellef_id)  # kümülatif 1.200.000,00
    _mizan_yukle(depo, mukellef_id, [_770_satiri("1200000.00")])  # tam eşit

    konfig = _yalniz_muhsgk_kontrolu(_yukle_konfig())
    bulgular = kontrolleri_calistir(depo, mukellef_id, 2025, konfig)

    assert bulgular == []


def test_negatif_tolerans_siniri_icinde_bulgu_uretilmez(depo):
    """Mutlak fark tam eşiğe (10.000,00) eşit -> tolerans İÇİ (<=), bulgu yok."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _muhsgk_beyannameleri_yukle(depo, mukellef_id)  # kümülatif 1.200.000,00
    _mizan_yukle(depo, mukellef_id, [_770_satiri("1190000.00")])  # fark 10.000,00

    konfig = _yalniz_muhsgk_kontrolu(_yukle_konfig())
    bulgular = kontrolleri_calistir(depo, mukellef_id, 2025, konfig)

    assert bulgular == []
