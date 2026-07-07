"""Modül C — rapor taslağı metin katmanı testleri (Task 5.1).

KVKK: LLM ÇAĞRISI YOK — `uretici._llm_uret` monkeypatch'lenir. Gerçek
müşteri verisi yok; dummy bulgular ve dummy kimlik.db kullanılır.

Kapsam (plan Task 5.1):
- Bulgu tipi -> j2 kalıp paragraf doldurma (SKILL.md §2 kalıpları).
- 2 bulgulu senaryoda üretilen metin her iki kontrolün tutarlarını içerir.
- LLM yanıt doğrulaması: yanıt girdideki tutarları birebir içermiyorsa
  kalıp paragraflara geri düşülür (SKILL.md §4).
- [KISI-nnn] token'ları LLM'den SONRA yerelde geri yerleştirilir.
"""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from ymm.db.depo import Depo
from ymm.modeller import Bulgu, Donem
from ymm.rapor.uretici import bulgu_paragraflari, geri_yerlestir, rapor_metni_uret


def _bulgu_a_kdv(mukellef_id=1, yil=2025) -> Bulgu:
    return Bulgu(
        kaynak="A",
        kontrol_kodu="A-KDV-HASILAT",
        seviye="orta",
        tutar_fark=Decimal("100000.00"),
        yuzde_fark=2.0,
        detay={
            "sol_tutar": "4900000.00",
            "sag_tutar": "5000000.00",
            "formul": "600 + 601 - 610",
            "aciklama": "KDV kümülatif ~ net satışlar",
            "eksik_donem_uyarilari": [],
            "eslesmeyen_hesaplar": [],
        },
        mukellef_id=mukellef_id,
        yil=yil,
    )


def _bulgu_b_131(mukellef_id=1, yil=2025) -> Bulgu:
    return Bulgu(
        kaynak="B",
        kontrol_kodu="B-131-ORTAK",
        seviye="yuksek",
        tutar_fark=Decimal("150000.00"),
        yuzde_fark=None,
        detay={
            "hesap_kodu": "131",
            "hesap_adi": "Ortaklardan Alacaklar [KISI-001]",
            "kural": "bakiye_var",
            "not": "adatlandırma",
        },
        mukellef_id=mukellef_id,
        yil=yil,
    )


def _bulgu_b_artis(mukellef_id=1, yil=2025) -> Bulgu:
    return Bulgu(
        kaynak="B",
        kontrol_kodu="B-770-ARTIS",
        seviye="orta",
        tutar_fark=Decimal("300000.00"),
        yuzde_fark=60.0,
        detay={
            "hesap_kodu": "770",
            "cari": "800000.00",
            "onceki": "500000.00",
            "yon": "artis",
            "esik_yuzde": 40,
            "esik_mutlak_taban": "250000",
            "not": None,
        },
        mukellef_id=mukellef_id,
        yil=yil,
    )


def _kimlik_db_olustur(yol: Path) -> Path:
    baglanti = sqlite3.connect(yol)
    baglanti.execute(
        "CREATE TABLE kimlik (takma_kod TEXT, tip TEXT, gercek_ad TEXT, vkn_tckn TEXT)"
    )
    baglanti.execute(
        "INSERT INTO kimlik VALUES ('KISI-001', 'KISI', 'Örnek Ortak', NULL)"
    )
    baglanti.commit()
    baglanti.close()
    return yol


@pytest.fixture
def kimlik_db(tmp_path):
    return _kimlik_db_olustur(tmp_path / "kimlik.db")


@pytest.fixture
def llm_yanki(monkeypatch):
    """LLM mock'u: gateway yerine istemi AYNEN geri döndürür (redaksiyonsuz
    yankı) — tutar doğrulaması her zaman geçer."""
    monkeypatch.setattr(
        "ymm.rapor.uretici._llm_uret", lambda istem, sistem, kimlik_db: istem
    )


# --- bulgu_paragraflari: kalıp doldurma ---------------------------------------


def test_a_kdv_hasilat_paragrafinda_tutarlar_turk_biciminde():
    paragraflar = bulgu_paragraflari([_bulgu_a_kdv()])

    assert len(paragraflar) == 1
    p = paragraflar[0]
    assert "4.900.000,00 TL" in p
    assert "5.000.000,00 TL" in p
    assert "100.000,00 TL" in p
    assert "incelenmesi gerekmektedir" in p


def test_b_131_ortak_paragrafinda_bakiye_ve_adatlandirma():
    paragraflar = bulgu_paragraflari([_bulgu_b_131()])

    p = paragraflar[0]
    assert "150.000,00 TL" in p
    assert "131" in p
    assert "adatlandırma" in p  # KVK md.13 kalıbı (SKILL.md §2)


def test_b_artis_paragrafinda_onceki_cari_yuzde():
    paragraflar = bulgu_paragraflari([_bulgu_b_artis()])

    p = paragraflar[0]
    assert "500.000,00 TL" in p
    assert "800.000,00 TL" in p
    assert "60,00" in p  # yüzde Türk biçimi (virgül)


def test_bilinmeyen_kontrol_kodu_genel_kaliba_duser():
    bulgu = _bulgu_b_131()
    bulgu.kontrol_kodu = "B-999-YENI"

    paragraflar = bulgu_paragraflari([bulgu])

    p = paragraflar[0]
    assert "150.000,00 TL" in p
    assert "B-999-YENI" in p
    assert "incelenmesi" in p


def test_paragraflar_seviye_sirasiyla_dizilir():
    """yüksek -> orta -> düşük (SKILL.md §3)."""
    paragraflar = bulgu_paragraflari([_bulgu_a_kdv(), _bulgu_b_131()])

    assert len(paragraflar) == 2
    # B-131 yüksek seviyeli, önce gelmeli.
    assert "131" in paragraflar[0]
    assert "4.900.000,00 TL" in paragraflar[1]


# --- geri_yerlestir -------------------------------------------------------------


def test_geri_yerlestir_token_gercek_adla_degisir(kimlik_db):
    metin = "Ortaklardan Alacaklar [KISI-001] hesabında bakiye vardır."

    sonuc = geri_yerlestir(metin, kimlik_db)

    assert "[KISI-001]" not in sonuc
    assert "Örnek Ortak" in sonuc


def test_geri_yerlestir_eslesmeyen_token_aynen_kalir(kimlik_db):
    metin = "Mükellef [MUK-001] dönemi."  # kimlik.db'de MUK-001 kaydı yok

    sonuc = geri_yerlestir(metin, kimlik_db)

    assert "[MUK-001]" in sonuc


# --- rapor_metni_uret: uçtan uca metin katmanı ---------------------------------


@pytest.fixture
def dolu_depo(tmp_path):
    depo = Depo(tmp_path / "veri.db")
    mukellef_id = depo.mukellef_ekle("MUK-001")
    depo.donem_ekle(mukellef_id, Donem(yil=2025, tip="YILLIK", sira=0))
    depo.bulgu_yaz([_bulgu_a_kdv(mukellef_id), _bulgu_b_131(mukellef_id)])
    return depo, mukellef_id


def test_iki_bulgulu_senaryo_her_iki_kontrolun_tutarlari_metinde(
    dolu_depo, kimlik_db, llm_yanki
):
    """Plan Task 5.1 ana kabul kriteri."""
    depo, mukellef_id = dolu_depo

    metin = rapor_metni_uret(
        depo, mukellef_id, 2025, kimlik_db=kimlik_db, takma_kod="MUK-001"
    )

    assert "4.900.000,00 TL" in metin  # A-KDV-HASILAT
    assert "150.000,00 TL" in metin  # B-131-ORTAK


def test_rapor_metni_damga_ve_yer_tutucular(dolu_depo, kimlik_db, llm_yanki):
    depo, mukellef_id = dolu_depo

    metin = rapor_metni_uret(
        depo, mukellef_id, 2025, kimlik_db=kimlik_db, takma_kod="MUK-001"
    )

    assert "İNCELENMESİ GEREKEN TASLAK — YMM ONAYI GEREKLİDİR" in metin
    assert "[YMM GÖRÜŞÜ — ELLE DOLDURULACAK]" in metin
    assert "[ELLE DOLDURULACAK" in metin


def test_rapor_metninde_token_geri_yerlestirilmis(dolu_depo, kimlik_db, llm_yanki):
    """B-131 bulgusunun hesap adındaki [KISI-001] token'ı nihai metinde
    gerçek adla değişmiş olmalı (LLM-SONRASI yerel adım)."""
    depo, mukellef_id = dolu_depo

    metin = rapor_metni_uret(
        depo, mukellef_id, 2025, kimlik_db=kimlik_db, takma_kod="MUK-001"
    )

    assert "[KISI-001]" not in metin
    assert "Örnek Ortak" in metin


def test_llm_yaniti_tutarlari_icermiyorsa_kaliba_geri_dusulur(
    dolu_depo, kimlik_db, monkeypatch
):
    """SKILL.md §4 güvenli geri düşüş: yanıt girdideki tutarları birebir
    içermiyorsa redaksiyon REDDEDİLİR, kalıp paragraflar kullanılır."""
    depo, mukellef_id = dolu_depo
    monkeypatch.setattr(
        "ymm.rapor.uretici._llm_uret",
        lambda istem, sistem, kimlik_db: "Tutarsız, sayıları yutan bir yanıt.",
    )

    metin = rapor_metni_uret(
        depo, mukellef_id, 2025, kimlik_db=kimlik_db, takma_kod="MUK-001"
    )

    assert "Tutarsız, sayıları yutan" not in metin
    assert "4.900.000,00 TL" in metin
    assert "150.000,00 TL" in metin


def test_bulgusuz_mukellef_llm_cagrilmadan_metin_uretir(kimlik_db, tmp_path, monkeypatch):
    """Bulgu yoksa LLM'e gidecek paragraf da yoktur — gateway HİÇ çağrılmaz,
    rapor iskeleti yine üretilir (bulgu bölümleri 'bulgu yok' notuyla)."""
    depo = Depo(tmp_path / "veri.db")
    mukellef_id = depo.mukellef_ekle("MUK-001")

    def patlat(istem, sistem, kimlik_db):  # pragma: no cover - çağrılmamalı
        raise AssertionError("Bulgusuz senaryoda LLM çağrılmamalı")

    monkeypatch.setattr("ymm.rapor.uretici._llm_uret", patlat)

    metin = rapor_metni_uret(
        depo, mukellef_id, 2025, kimlik_db=kimlik_db, takma_kod="MUK-001"
    )

    assert "İNCELENMESİ GEREKEN TASLAK — YMM ONAYI GEREKLİDİR" in metin
