"""risk/tarayici.py testleri: önceki dönem karşılaştırması (Task 2.2).

Senaryolar (bkz. .superpowers/sdd/task-2.2-brief.md + mimar kararları):
- 770: 2024=500.000, 2025=800.000 -> %60 artış (eşik %40) -> B-770-ARTIS,
  seviye=orta, tutar_fark=300.000, yuzde_fark=60.0, yon=artis.
- Eşik altı değişim -> bulgu yok.
- Taban altı cari (< esik_mutlak_taban) -> yüzdeye bakılmaz, bulgu yok.
- Taban TAM eşitlikte (cari == taban) -> değerlendirilir (taban aşılması değil,
  altında kalma muafiyeti).
- Önceki dönem 0, cari > taban -> "yeni oluşan yüksek bakiye" bulgusu,
  yuzde_fark=None.
- Önceki dönem 0, cari <= taban -> bulgu yok.
- Azalış yönü (önceki > cari, eşik üstü) -> yon=azalis.
- Önceki dönem mizanı hiç yoksa (donem_bul None) -> karşılaştırmalı kurallar
  atlanır + logger.warning; statik kurallar yine çalışır.
- risk_konfig_yukle fail-fast: karsilastirmali için de bilinmeyen kural tipi /
  geçersiz seviye / sayı olmayan esik_yuzde / Decimal'e çevrilemeyen
  esik_mutlak_taban -> ValueError.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from ymm.db.depo import Depo
from ymm.modeller import Donem, MizanSatiri
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


def _donem_yukle(depo, mukellef_id, yil, satirlar):
    donem_id = depo.donem_ekle(mukellef_id, Donem(yil=yil, tip="YILLIK", sira=0))
    depo.mizan_yaz(donem_id, satirlar)
    return donem_id


def _sadece(konfig: dict, *kodlar: str) -> dict:
    """``konfig["karsilastirmali"]``'yi verilen kodlarla sınırlar; ``statik``
    listesini boşaltır (yalnız karşılaştırmalı kurallar test edilsin)."""
    konfig = dict(konfig)
    konfig["statik"] = []
    konfig["karsilastirmali"] = [
        k for k in konfig.get("karsilastirmali", []) if k["kod"] in kodlar
    ]
    return konfig


# --------------------------------------------------------------------------
# risk_konfig_yukle: karsilastirmali fail-fast doğrulama
# --------------------------------------------------------------------------


def test_risk_konfig_yukle_karsilastirmali_kodlari_yuklenir():
    konfig = risk_konfig_yukle(_KONFIG_YOLU)
    kodlar = {k["kod"] for k in konfig["karsilastirmali"]}
    assert kodlar == {"B-770-ARTIS", "B-131-ARTIS"}


def test_risk_konfig_yukle_karsilastirmali_bilinmeyen_kural_tipi_valueerror(tmp_path):
    bozuk = tmp_path / "bozuk.yaml"
    bozuk.write_text(
        """
statik: []
karsilastirmali:
  - kod: B-TEST
    hesap_prefix: "770"
    kural: bilinmeyen_kural
    esik_yuzde: 40
    esik_mutlak_taban: "250000.00"
    seviye: orta
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        risk_konfig_yukle(bozuk)


def test_risk_konfig_yukle_karsilastirmali_gecersiz_seviye_valueerror(tmp_path):
    bozuk = tmp_path / "bozuk.yaml"
    bozuk.write_text(
        """
statik: []
karsilastirmali:
  - kod: B-TEST
    hesap_prefix: "770"
    kural: yuzde_degisim
    esik_yuzde: 40
    esik_mutlak_taban: "250000.00"
    seviye: cok_yuksek
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        risk_konfig_yukle(bozuk)


def test_risk_konfig_yukle_karsilastirmali_esik_yuzde_sayi_degilse_valueerror(tmp_path):
    bozuk = tmp_path / "bozuk.yaml"
    bozuk.write_text(
        """
statik: []
karsilastirmali:
  - kod: B-TEST
    hesap_prefix: "770"
    kural: yuzde_degisim
    esik_yuzde: "yuzde kirk"
    esik_mutlak_taban: "250000.00"
    seviye: orta
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        risk_konfig_yukle(bozuk)


def test_risk_konfig_yukle_karsilastirmali_taban_decimale_cevrilemiyorsa_valueerror(tmp_path):
    bozuk = tmp_path / "bozuk.yaml"
    bozuk.write_text(
        """
statik: []
karsilastirmali:
  - kod: B-TEST
    hesap_prefix: "770"
    kural: yuzde_degisim
    esik_yuzde: 40
    esik_mutlak_taban: "iki yuz elli bin"
    seviye: orta
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        risk_konfig_yukle(bozuk)


# --------------------------------------------------------------------------
# riskleri_tara: karşılaştırmalı kurallar
# --------------------------------------------------------------------------


def test_770_yuzde_60_artis_orta_bulgu_uretir(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _donem_yukle(depo, mukellef_id, 2024, [
        _satir("770", "Genel Yönetim Giderleri", borc_bakiye="500000.00"),
    ])
    _donem_yukle(depo, mukellef_id, 2025, [
        _satir("770", "Genel Yönetim Giderleri", borc_bakiye="800000.00"),
    ])

    konfig = _sadece(_yukle_konfig(), "B-770-ARTIS")
    bulgular = riskleri_tara(depo, mukellef_id, 2025, konfig)

    assert len(bulgular) == 1
    bulgu = bulgular[0]
    assert bulgu.kaynak == "B"
    assert bulgu.kontrol_kodu == "B-770-ARTIS"
    assert bulgu.seviye == "orta"
    assert bulgu.tutar_fark == Decimal("300000.00")
    assert bulgu.yuzde_fark == pytest.approx(60.0)
    assert bulgu.mukellef_id == mukellef_id
    assert bulgu.yil == 2025
    assert bulgu.detay["hesap_kodu"] == "770"
    assert bulgu.detay["cari"] == "800000.00"
    assert bulgu.detay["onceki"] == "500000.00"
    assert bulgu.detay["yon"] == "artis"
    assert bulgu.detay["esik_yuzde"] == 40
    assert bulgu.detay["esik_mutlak_taban"] == Decimal("250000.00")


def test_esik_alti_degisim_bulgu_uretmez(depo):
    """%6.67 değişim (<%40 eşik) -> bulgu yok."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _donem_yukle(depo, mukellef_id, 2024, [
        _satir("770", "Genel Yönetim Giderleri", borc_bakiye="750000.00"),
    ])
    _donem_yukle(depo, mukellef_id, 2025, [
        _satir("770", "Genel Yönetim Giderleri", borc_bakiye="800000.00"),
    ])

    konfig = _sadece(_yukle_konfig(), "B-770-ARTIS")
    bulgular = riskleri_tara(depo, mukellef_id, 2025, konfig)

    assert bulgular == []


def test_cari_taban_altinda_bulgu_uretmez(depo):
    """cari (200.000) < esik_mutlak_taban (250.000) -> yüzdeye bakılmaz, bulgu yok
    (değişim yüzdesi burada %100 olsa bile)."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _donem_yukle(depo, mukellef_id, 2024, [
        _satir("770", "Genel Yönetim Giderleri", borc_bakiye="100000.00"),
    ])
    _donem_yukle(depo, mukellef_id, 2025, [
        _satir("770", "Genel Yönetim Giderleri", borc_bakiye="200000.00"),
    ])

    konfig = _sadece(_yukle_konfig(), "B-770-ARTIS")
    bulgular = riskleri_tara(depo, mukellef_id, 2025, konfig)

    assert bulgular == []


def test_cari_taban_esitse_degerlendirilir(depo):
    """cari == esik_mutlak_taban (taban dahil, altında kalma muafiyeti değil) ->
    yüzde eşiği aşılırsa bulgu üretilir."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _donem_yukle(depo, mukellef_id, 2024, [
        _satir("770", "Genel Yönetim Giderleri", borc_bakiye="100000.00"),
    ])
    _donem_yukle(depo, mukellef_id, 2025, [
        _satir("770", "Genel Yönetim Giderleri", borc_bakiye="250000.00"),  # == taban
    ])

    konfig = _sadece(_yukle_konfig(), "B-770-ARTIS")
    bulgular = riskleri_tara(depo, mukellef_id, 2025, konfig)

    assert len(bulgular) == 1
    assert bulgular[0].detay["cari"] == "250000.00"


def test_onceki_sifir_cari_taban_ustu_yeni_bakiye_bulgusu(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _donem_yukle(depo, mukellef_id, 2024, [
        _satir("770", "Genel Yönetim Giderleri", borc_bakiye="0.00"),
    ])
    _donem_yukle(depo, mukellef_id, 2025, [
        _satir("770", "Genel Yönetim Giderleri", borc_bakiye="300000.00"),
    ])

    konfig = _sadece(_yukle_konfig(), "B-770-ARTIS")
    bulgular = riskleri_tara(depo, mukellef_id, 2025, konfig)

    assert len(bulgular) == 1
    bulgu = bulgular[0]
    assert bulgu.tutar_fark == Decimal("300000.00")
    assert bulgu.yuzde_fark is None
    assert bulgu.detay["onceki"] == "0.00"
    assert bulgu.detay["yon"] == "artis"
    assert bulgu.detay["not"] == "yeni oluşan yüksek bakiye"


def test_onceki_sifir_cari_taban_alti_bulgu_uretmez(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _donem_yukle(depo, mukellef_id, 2024, [
        _satir("770", "Genel Yönetim Giderleri", borc_bakiye="0.00"),
    ])
    _donem_yukle(depo, mukellef_id, 2025, [
        _satir("770", "Genel Yönetim Giderleri", borc_bakiye="200000.00"),
    ])

    konfig = _sadece(_yukle_konfig(), "B-770-ARTIS")
    bulgular = riskleri_tara(depo, mukellef_id, 2025, konfig)

    assert bulgular == []


def test_azalis_yonu_esik_ustu_bulgu_uretir(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _donem_yukle(depo, mukellef_id, 2024, [
        _satir("770", "Genel Yönetim Giderleri", borc_bakiye="800000.00"),
    ])
    _donem_yukle(depo, mukellef_id, 2025, [
        _satir("770", "Genel Yönetim Giderleri", borc_bakiye="300000.00"),
    ])

    konfig = _sadece(_yukle_konfig(), "B-770-ARTIS")
    bulgular = riskleri_tara(depo, mukellef_id, 2025, konfig)

    assert len(bulgular) == 1
    bulgu = bulgular[0]
    assert bulgu.tutar_fark == Decimal("500000.00")
    assert bulgu.yuzde_fark == pytest.approx(62.5)
    assert bulgu.detay["yon"] == "azalis"


def test_onceki_donem_yoksa_karsilastirmali_atlanir_statikler_calisir(depo, caplog):
    """2024 dönemi hiç yüklenmemiş -> karşılaştırmalı kurallar atlanır (bulgu
    üretilmez) + warning; statik kurallar (ör. B-131-ORTAK) yine çalışır."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _donem_yukle(depo, mukellef_id, 2025, [
        _satir("131", "Ortaklardan Alacaklar", borc_bakiye="150000.00"),
        _satir("770", "Genel Yönetim Giderleri", borc_bakiye="800000.00"),
    ])

    konfig = _yukle_konfig()

    with caplog.at_level(logging.WARNING):
        bulgular = riskleri_tara(depo, mukellef_id, 2025, konfig)

    kodlar = {b.kontrol_kodu for b in bulgular}
    assert "B-131-ORTAK" in kodlar
    assert "B-770-ARTIS" not in kodlar
    assert "B-131-ARTIS" not in kodlar
    assert any("önceki dönem" in rec.message for rec in caplog.records)


def test_131_artis_yuksek_bulgu_uretir(depo):
    """B-131-ARTIS: esik_yuzde=50, esik_mutlak_taban=100.000, seviye=yuksek."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _donem_yukle(depo, mukellef_id, 2024, [
        _satir("131", "Ortaklardan Alacaklar", borc_bakiye="100000.00"),
    ])
    _donem_yukle(depo, mukellef_id, 2025, [
        _satir("131", "Ortaklardan Alacaklar", borc_bakiye="200000.00"),
    ])

    konfig = _sadece(_yukle_konfig(), "B-131-ARTIS")
    bulgular = riskleri_tara(depo, mukellef_id, 2025, konfig)

    assert len(bulgular) == 1
    bulgu = bulgular[0]
    assert bulgu.kontrol_kodu == "B-131-ARTIS"
    assert bulgu.seviye == "yuksek"
    assert bulgu.tutar_fark == Decimal("100000.00")
    assert bulgu.yuzde_fark == pytest.approx(100.0)


def test_tum_karsilastirmali_kurallar_ve_statikler_birlikte_calisir(depo):
    """Tam config (statik + karşılaştırmalı) tek seferde çalıştırıldığında
    çökme olmaz; hem statik hem karşılaştırmalı bulgular birlikte üretilir."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _donem_yukle(depo, mukellef_id, 2024, [
        _satir("770", "Genel Yönetim Giderleri", borc_bakiye="500000.00"),
        _satir("131", "Ortaklardan Alacaklar", borc_bakiye="150000.00"),
    ])
    _donem_yukle(depo, mukellef_id, 2025, [
        _satir("770", "Genel Yönetim Giderleri", borc_bakiye="800000.00"),
        _satir("131", "Ortaklardan Alacaklar", borc_bakiye="150000.00"),
        _satir("689", "Diğer Olağandışı Gider ve Zararlar", borc_bakiye="45000.00"),
    ])

    bulgular = riskleri_tara(depo, mukellef_id, 2025, risk_konfig_yukle(_KONFIG_YOLU))
    kod_map = {b.kontrol_kodu: b for b in bulgular}

    assert set(kod_map) == {"B-131-ORTAK", "B-689-KKEG", "B-770-ARTIS"}
    assert kod_map["B-770-ARTIS"].seviye == "orta"
    # 131 değişmedi (%0) -> B-131-ARTIS tetiklenmez.
    assert "B-131-ARTIS" not in kod_map
