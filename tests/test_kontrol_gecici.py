"""kontrol/motor.py testi: A-GECICI-KV kontrolü.

Senaryolar (bkz. .superpowers/sdd/task-1.3-brief.md):
- pozitif: GECICI 4. dönem (sira=4, KÜMÜLATİF DEĞİL) matrah 600.000,00 ~ KV
  matrah 605.000,00 -> fark 5.000,00 (%0,83) -> seviye "orta" (dar tolerans:
  mutlak 1.000,00 / oransal %0.0 fiilen devre dışı).
- negatif: fark <= 1.000,00 (mutlak tolerans içi) -> bulgu YOK.
- `sol.donem: son_ceyrek` kümülatif toplama YAPMAZ, yalnız sira=4 kaydını
  kullanır (kümülatif olsaydı farklı bir sonuç çıkardı) -- ayrı test.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from ymm.db.depo import Depo
from ymm.kontrol.motor import kontrolleri_calistir
from ymm.modeller import Donem

_KONFIG_YOLU = Path(__file__).parent.parent / "config" / "kontrol_kurallari.yaml"


@pytest.fixture
def depo(tmp_path):
    return Depo(tmp_path / "veri.db")


def _gecici_beyannameleri_yukle(depo, mukellef_id, yil=2025, tutarlar=None):
    """4 çeyreklik GECICI beyannamesi yazar (varsayılan 4. dönem: 600.000,00)."""
    tutarlar = tutarlar or ["150000.00", "300000.00", "450000.00", "600000.00"]
    for sira, tutar in enumerate(tutarlar, start=1):
        donem_id = depo.donem_ekle(mukellef_id, Donem(yil=yil, tip="CEYREK", sira=sira))
        depo.beyanname_yaz(donem_id, "GECICI", {"matrah": tutar})


def _kv_beyannamesi_yukle(depo, mukellef_id, matrah: str, yil=2025):
    donem_id = depo.donem_ekle(mukellef_id, Donem(yil=yil, tip="YILLIK", sira=0))
    depo.beyanname_yaz(donem_id, "KV", {"matrah": matrah})


def _yukle_konfig() -> dict:
    return yaml.safe_load(_KONFIG_YOLU.read_text(encoding="utf-8"))


def _yalniz_gecici_kv_kontrolu(konfig: dict) -> dict:
    konfig = dict(konfig)
    konfig["kontroller"] = [
        k for k in konfig["kontroller"] if k["kod"] == "A-GECICI-KV"
    ]
    return konfig


def test_pozitif_fark_orta_seviye_bulgu_uretir(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _gecici_beyannameleri_yukle(depo, mukellef_id)  # 4. dönem: 600.000,00
    _kv_beyannamesi_yukle(depo, mukellef_id, "605000.00")

    konfig = _yalniz_gecici_kv_kontrolu(_yukle_konfig())
    bulgular = kontrolleri_calistir(depo, mukellef_id, 2025, konfig)

    assert len(bulgular) == 1
    bulgu = bulgular[0]
    assert bulgu.kaynak == "A"
    assert bulgu.kontrol_kodu == "A-GECICI-KV"
    assert bulgu.tutar_fark == Decimal("5000.00")
    assert bulgu.yuzde_fark == pytest.approx(5000 / 605000 * 100, abs=0.01)
    assert bulgu.seviye == "orta"
    assert bulgu.detay["sol_tutar"] == "600000.00"
    assert bulgu.detay["sag_tutar"] == "605000.00"


def test_negatif_fark_1000_tl_esik_altinda_bulgu_uretilmez(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _gecici_beyannameleri_yukle(
        depo,
        mukellef_id,
        tutarlar=["150000.00", "300000.00", "450000.00", "600500.00"],
    )  # 4. dönem: 600.500,00
    _kv_beyannamesi_yukle(depo, mukellef_id, "601000.00")  # fark 500,00 <= 1.000,00

    konfig = _yalniz_gecici_kv_kontrolu(_yukle_konfig())
    bulgular = kontrolleri_calistir(depo, mukellef_id, 2025, konfig)

    assert bulgular == []


def test_negatif_tolerans_siniri_tam_esitlikte_bulgu_uretilmez(depo):
    """Sınır değer: fark tam 1.000,00 -> tolerans İÇİ (<=), bulgu yok."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _gecici_beyannameleri_yukle(depo, mukellef_id)  # 4. dönem: 600.000,00
    _kv_beyannamesi_yukle(depo, mukellef_id, "601000.00")  # fark tam 1.000,00

    konfig = _yalniz_gecici_kv_kontrolu(_yukle_konfig())
    bulgular = kontrolleri_calistir(depo, mukellef_id, 2025, konfig)

    assert bulgular == []


def test_sol_son_ceyrek_kumulatif_degil_yalniz_dorduncu_donem_kullanilir(depo):
    """`sol.donem: son_ceyrek` -> yalnızca sira=4 kaydı. Kümülatif olsaydı
    150.000+300.000+450.000+600.000 = 1.500.000,00 olurdu; ama sol_tutar
    600.000,00 olmalı."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _gecici_beyannameleri_yukle(depo, mukellef_id)
    _kv_beyannamesi_yukle(depo, mukellef_id, "605000.00")

    konfig = _yalniz_gecici_kv_kontrolu(_yukle_konfig())
    bulgular = kontrolleri_calistir(depo, mukellef_id, 2025, konfig)

    assert len(bulgular) == 1
    assert bulgular[0].detay["sol_tutar"] == "600000.00"


def test_dorduncu_donem_kaydi_yoksa_eksik_donem_uyarisi_ve_sifir_tutar(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    # yalnız ilk 3 çeyrek -- sira=4 (son çeyrek) kaydı yok
    _gecici_beyannameleri_yukle(
        depo, mukellef_id, tutarlar=["150000.00", "300000.00", "450000.00"]
    )
    _kv_beyannamesi_yukle(depo, mukellef_id, "605000.00")

    konfig = _yalniz_gecici_kv_kontrolu(_yukle_konfig())
    bulgular = kontrolleri_calistir(depo, mukellef_id, 2025, konfig)

    assert len(bulgular) == 1
    bulgu = bulgular[0]
    assert bulgu.detay["sol_tutar"] == "0"
    assert any("4" in uyari for uyari in bulgu.detay["eksik_donem_uyarilari"])
