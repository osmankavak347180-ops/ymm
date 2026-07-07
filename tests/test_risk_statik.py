"""risk/tarayici.py + risk/seviye.py testleri: statik risk kuralları (Task 2.1).

Senaryolar (bkz. .superpowers/sdd/task-2.1-brief.md):
- 131=150.000 (dummy ankor) -> B-131-ORTAK, seviye=yuksek.
- 689=45.000 (>10.000 eşik) -> B-689-KKEG, seviye=orta.
- 331 bakiyesiz (borç toplamı == alacak toplamı, net bakiye 0) -> bulgu yok.
- Eşik TAM eşitlikte tolerans İÇİNDE sayılır (bulgu YOK): değer == esik ise
  bulgu üretilmez (Modül A "tam eşitlik tolerans içi" konvansiyonuyla tutarlı).
- Eşik altı: 689=5.000 -> bulgu yok.
- Ana hesap önceliği: 131 + 131.01 aynı bakiyeyi taşıyor -> TEK bulgu, 150.000
  (300.000 DEĞİL — çifte sayma yok).
- bakiye_var kuralı sıfır bakiyede bulgu üretmez.
- Dönem yoksa boş liste + logger.warning.
- risk_konfig_yukle fail-fast: bilinmeyen kural tipi / geçersiz seviye /
  Decimal'e çevrilemeyen eşik -> ValueError.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from ymm.db.depo import Depo
from ymm.modeller import Donem, MizanSatiri
from ymm.risk.seviye import GECERLI_SEVIYELER, seviye_dogrula
from ymm.risk.tarayici import risk_konfig_yukle, riskleri_tara

_KONFIG_YOLU = Path(__file__).parent.parent / "config" / "risk_hesaplari.yaml"


@pytest.fixture
def depo(tmp_path):
    return Depo(tmp_path / "veri.db")


def _yukle_konfig() -> dict:
    return yaml.safe_load(_KONFIG_YOLU.read_text(encoding="utf-8"))


def _satir(hesap_kodu, hesap_adi, borc_bakiye="0.00", alacak_bakiye="0.00",
           borc_toplam=None, alacak_toplam=None) -> MizanSatiri:
    return MizanSatiri(
        hesap_kodu=hesap_kodu,
        hesap_adi=hesap_adi,
        borc_toplam=Decimal(borc_toplam if borc_toplam is not None else borc_bakiye),
        alacak_toplam=Decimal(alacak_toplam if alacak_toplam is not None else alacak_bakiye),
        borc_bakiye=Decimal(borc_bakiye),
        alacak_bakiye=Decimal(alacak_bakiye),
    )


def _mizan_yukle(depo, mukellef_id, satirlar, yil=2025):
    donem_id = depo.donem_ekle(mukellef_id, Donem(yil=yil, tip="YILLIK", sira=0))
    depo.mizan_yaz(donem_id, satirlar)
    return donem_id


def _sadece(konfig: dict, *kodlar: str) -> dict:
    konfig = dict(konfig)
    konfig["statik"] = [k for k in konfig["statik"] if k["kod"] in kodlar]
    return konfig


# --------------------------------------------------------------------------
# risk_konfig_yukle: geçerli config + fail-fast doğrulama
# --------------------------------------------------------------------------


def test_risk_konfig_yukle_gecerli_config_basarili_yuklenir():
    konfig = risk_konfig_yukle(_KONFIG_YOLU)
    kodlar = {k["kod"] for k in konfig["statik"]}
    assert kodlar == {
        "B-131-ORTAK", "B-231-ORTAK", "B-331-ORTAK", "B-431-ORTAK",
        "B-689-KKEG", "B-679-GELIR", "B-100-KASA", "B-190-DEVREDEN",
    }


def test_risk_konfig_yukle_bilinmeyen_kural_tipi_fail_fast_valueerror(tmp_path):
    bozuk = tmp_path / "bozuk.yaml"
    bozuk.write_text(
        """
statik:
  - kod: B-TEST
    hesap_prefix: "131"
    kural: bilinmeyen_kural
    seviye: yuksek
    not: "test"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        risk_konfig_yukle(bozuk)


def test_risk_konfig_yukle_gecersiz_seviye_fail_fast_valueerror(tmp_path):
    bozuk = tmp_path / "bozuk.yaml"
    bozuk.write_text(
        """
statik:
  - kod: B-TEST
    hesap_prefix: "131"
    kural: bakiye_var
    seviye: cok_yuksek
    not: "test"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        risk_konfig_yukle(bozuk)


def test_risk_konfig_yukle_esik_decimale_cevrilemiyorsa_fail_fast_valueerror(tmp_path):
    bozuk = tmp_path / "bozuk.yaml"
    bozuk.write_text(
        """
statik:
  - kod: B-TEST
    hesap_prefix: "689"
    kural: bakiye_esik_ustu
    esik: "on bin"
    seviye: orta
    not: "test"
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        risk_konfig_yukle(bozuk)


def test_seviye_dogrula_gecerli_seviyeler():
    for seviye in GECERLI_SEVIYELER:
        assert seviye_dogrula(seviye) == seviye


def test_seviye_dogrula_gecersiz_seviye_valueerror():
    with pytest.raises(ValueError):
        seviye_dogrula("cok_yuksek")


# --------------------------------------------------------------------------
# riskleri_tara: uçtan uca (Depo üzerinden)
# --------------------------------------------------------------------------


def test_131_ortaklardan_alacak_yuksek_bulgu_uretir(depo):
    """Dummy ankor: 131=150.000 -> B-131-ORTAK, seviye=yuksek."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _mizan_yukle(depo, mukellef_id, [
        _satir("131", "Ortaklardan Alacaklar", borc_bakiye="150000.00"),
    ])

    konfig = _sadece(_yukle_konfig(), "B-131-ORTAK")
    bulgular = riskleri_tara(depo, mukellef_id, 2025, konfig)

    assert len(bulgular) == 1
    bulgu = bulgular[0]
    assert bulgu.kaynak == "B"
    assert bulgu.kontrol_kodu == "B-131-ORTAK"
    assert bulgu.seviye == "yuksek"
    assert bulgu.tutar_fark == Decimal("150000.00")
    assert bulgu.yuzde_fark is None
    assert bulgu.mukellef_id == mukellef_id
    assert bulgu.yil == 2025
    assert bulgu.detay["hesap_kodu"] == "131"
    assert bulgu.detay["hesap_adi"] == "Ortaklardan Alacaklar"
    assert bulgu.detay["kural"] == "bakiye_var"
    assert "esik" not in bulgu.detay
    assert bulgu.detay["not"]


def test_689_esik_ustu_orta_bulgu_uretir(depo):
    """Dummy ankor: 689=45.000 (>10.000 eşik) -> B-689-KKEG, seviye=orta."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _mizan_yukle(depo, mukellef_id, [
        _satir("689", "Diğer Olağandışı Gider ve Zararlar", borc_bakiye="45000.00"),
    ])

    konfig = _sadece(_yukle_konfig(), "B-689-KKEG")
    bulgular = riskleri_tara(depo, mukellef_id, 2025, konfig)

    assert len(bulgular) == 1
    bulgu = bulgular[0]
    assert bulgu.kontrol_kodu == "B-689-KKEG"
    assert bulgu.seviye == "orta"
    assert bulgu.tutar_fark == Decimal("45000.00")
    assert bulgu.detay["esik"] == Decimal("10000.00")


def test_331_bakiyesiz_bulgu_uretmez(depo):
    """331 borç toplamı == alacak toplamı, net bakiye 0 -> bulgu yok."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _mizan_yukle(depo, mukellef_id, [
        _satir("331", "Ortaklara Borçlar", borc_bakiye="0.00", alacak_bakiye="0.00",
               borc_toplam="80000.00", alacak_toplam="80000.00"),
    ])

    konfig = _sadece(_yukle_konfig(), "B-331-ORTAK")
    bulgular = riskleri_tara(depo, mukellef_id, 2025, konfig)

    assert bulgular == []


def test_esik_alti_689_bulgu_uretmez(depo):
    """689=5.000 (<10.000 eşik) -> bulgu yok."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _mizan_yukle(depo, mukellef_id, [
        _satir("689", "Diğer Olağandışı Gider ve Zararlar", borc_bakiye="5000.00"),
    ])

    konfig = _sadece(_yukle_konfig(), "B-689-KKEG")
    bulgular = riskleri_tara(depo, mukellef_id, 2025, konfig)

    assert bulgular == []


def test_esik_tam_esitlikte_bulgu_uretmez(depo):
    """Değer == esik (tam eşitlik) -> bulgu YOK (>, >= değil)."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _mizan_yukle(depo, mukellef_id, [
        _satir("689", "Diğer Olağandışı Gider ve Zararlar", borc_bakiye="10000.00"),
    ])

    konfig = _sadece(_yukle_konfig(), "B-689-KKEG")
    bulgular = riskleri_tara(depo, mukellef_id, 2025, konfig)

    assert bulgular == []


def test_ana_hesap_onceligi_131_ve_131_01_tek_bulgu_cifte_saymaz(depo):
    """131 VE 131.01 aynı bakiyeyi taşıyor -> TEK bulgu, 150.000 (300.000 değil)."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _mizan_yukle(depo, mukellef_id, [
        _satir("131", "Ortaklardan Alacaklar", borc_bakiye="150000.00"),
        _satir("131.01", "Ortaklardan Alacaklar [ORTAK-A]", borc_bakiye="150000.00"),
    ])

    konfig = _sadece(_yukle_konfig(), "B-131-ORTAK")
    bulgular = riskleri_tara(depo, mukellef_id, 2025, konfig)

    assert len(bulgular) == 1
    assert bulgular[0].tutar_fark == Decimal("150000.00")


def test_bakiye_var_sifir_bakiyede_bulgu_uretmez(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _mizan_yukle(depo, mukellef_id, [
        _satir("231", "Ortaklardan Alacaklar (Uzun Vadeli)", borc_bakiye="0.00", alacak_bakiye="0.00"),
    ])

    konfig = _sadece(_yukle_konfig(), "B-231-ORTAK")
    bulgular = riskleri_tara(depo, mukellef_id, 2025, konfig)

    assert bulgular == []


def test_hesap_mizanda_hic_yoksa_bulgu_uretmez(depo):
    """Hesap prefix mizanda hiç yoksa değer sessizce 0 -> bakiye_var bulgu üretmez."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _mizan_yukle(depo, mukellef_id, [
        _satir("100", "Kasa", borc_bakiye="30000.00"),
    ])

    konfig = _sadece(_yukle_konfig(), "B-431-ORTAK")
    bulgular = riskleri_tara(depo, mukellef_id, 2025, konfig)

    assert bulgular == []


def test_donem_yoksa_bos_liste_ve_warning(depo, caplog):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    konfig = _yukle_konfig()

    with caplog.at_level(logging.WARNING):
        bulgular = riskleri_tara(depo, mukellef_id, 2025, konfig)

    assert bulgular == []
    assert any("2025" in rec.message for rec in caplog.records)


def test_tum_statik_kurallar_tam_config_ile_calisir(depo):
    """Tüm 8 statik kural tek seferde, dummy ankorlara yakın bir mizanla
    çalıştırıldığında çökme olmaz ve beklenen bulgular üretilir."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _mizan_yukle(depo, mukellef_id, [
        _satir("100", "Kasa", borc_bakiye="30000.00"),  # < 50.000 esik -> bulgu yok
        _satir("131", "Ortaklardan Alacaklar", borc_bakiye="150000.00"),
        _satir("131.01", "Ortaklardan Alacaklar [ORTAK-A]", borc_bakiye="150000.00"),
        _satir("190", "Devreden KDV", borc_bakiye="120000.00"),  # > 100.000 esik
        _satir("231", "Ortaklardan Alacaklar (Uzun Vadeli)"),  # bakiyesiz
        _satir("331", "Ortaklara Borçlar", borc_toplam="80000.00", alacak_toplam="80000.00"),  # net 0
        _satir("431", "Ortaklara Borçlar (Uzun Vadeli)"),  # bakiyesiz
        _satir("679", "Diğer Olağandışı Gelir ve Karlar", alacak_bakiye="10000.00"),  # == esik -> bulgu yok
        _satir("689", "Diğer Olağandışı Gider ve Zararlar", borc_bakiye="45000.00"),
    ])

    bulgular = riskleri_tara(depo, mukellef_id, 2025, risk_konfig_yukle(_KONFIG_YOLU))
    kod_map = {b.kontrol_kodu: b for b in bulgular}

    assert set(kod_map) == {"B-131-ORTAK", "B-190-DEVREDEN", "B-689-KKEG"}
    assert kod_map["B-131-ORTAK"].seviye == "yuksek"
    assert kod_map["B-190-DEVREDEN"].seviye == "dusuk"
    assert kod_map["B-689-KKEG"].seviye == "orta"
