"""Kimlik ayirici (maskeleme/ayirici.py) ve sizinti dogrulayici (maskeleme/dogrulayici.py) testleri.

kimlik.db, veri.db'den fiziksel olarak AYRI bir SQLite dosyasidir; bu testler
kendi baglantisini kurup kimlik tablosunu dogrudan sorgular (Depo kullanilmaz).
"""

from __future__ import annotations

import sqlite3
from decimal import Decimal

import pytest

from ymm.maskeleme.ayirici import kimlik_ayir
from ymm.maskeleme.dogrulayici import MaskeIhlali, sizinti_tara
from ymm.modeller import MizanSatiri


def _satir(hesap_kodu: str, hesap_adi: str) -> MizanSatiri:
    return MizanSatiri(
        hesap_kodu=hesap_kodu,
        hesap_adi=hesap_adi,
        borc_toplam=Decimal("0.00"),
        alacak_toplam=Decimal("0.00"),
        borc_bakiye=Decimal("0.00"),
        alacak_bakiye=Decimal("0.00"),
    )


def _kimlik_satirlari(kimlik_db):
    baglanti = sqlite3.connect(kimlik_db)
    try:
        return baglanti.execute(
            "SELECT takma_kod, tip, gercek_ad, vkn_tckn FROM kimlik ORDER BY takma_kod"
        ).fetchall()
    finally:
        baglanti.close()


# --- Senaryo 1: "131.01 AHMET YILMAZ" -> "131.01 [KISI-001]" + kimlik.db eslemesi ---


def test_buyuk_harf_ad_soyad_maskelenir_ve_kimlik_db_yazilir(tmp_path):
    kimlik_db = tmp_path / "kimlik.db"
    satirlar = [_satir("131.01", "AHMET YILMAZ")]

    sonuc = kimlik_ayir(satirlar, kimlik_db)

    assert len(sonuc) == 1
    assert sonuc[0].hesap_adi == "[KISI-001]"
    assert f"{sonuc[0].hesap_kodu} {sonuc[0].hesap_adi}" == "131.01 [KISI-001]"
    # diger alanlar degismemis olmali
    assert sonuc[0].hesap_kodu == "131.01"

    kayitlar = _kimlik_satirlari(kimlik_db)
    assert kayitlar == [("KISI-001", "KISI", "AHMET YILMAZ", None)]


def test_koseli_parantez_etiketi_maskelenir_dummy_bicimi(tmp_path):
    """ornek_veri/uret.py bicimi: 'Ortaklardan Alacaklar [ORTAK-A]'."""
    kimlik_db = tmp_path / "kimlik.db"
    satirlar = [_satir("131.01", "Ortaklardan Alacaklar [ORTAK-A]")]

    sonuc = kimlik_ayir(satirlar, kimlik_db)

    assert sonuc[0].hesap_adi == "Ortaklardan Alacaklar [KISI-001]"
    kayitlar = _kimlik_satirlari(kimlik_db)
    assert kayitlar == [("KISI-001", "KISI", "ORTAK-A", None)]


def test_kimlik_iceren_olmayan_hesap_adi_degismez(tmp_path):
    kimlik_db = tmp_path / "kimlik.db"
    satirlar = [_satir("100", "Kasa"), _satir("770", "Genel Yönetim Giderleri")]

    sonuc = kimlik_ayir(satirlar, kimlik_db)

    assert sonuc[0].hesap_adi == "Kasa"
    assert sonuc[1].hesap_adi == "Genel Yönetim Giderleri"
    assert _kimlik_satirlari(kimlik_db) == []


def test_siralama_deterministik_ilk_gorulme_sirasina_gore(tmp_path):
    kimlik_db = tmp_path / "kimlik.db"
    satirlar = [
        _satir("320.01", "Satıcılar [TEDARIKCI-B]"),
        _satir("131.01", "Ortaklardan Alacaklar [ORTAK-A]"),
    ]

    sonuc = kimlik_ayir(satirlar, kimlik_db)

    assert sonuc[0].hesap_adi == "Satıcılar [KISI-001]"
    assert sonuc[1].hesap_adi == "Ortaklardan Alacaklar [KISI-002]"


def test_ayni_gercek_ad_ayni_token_alir_idempotent_tek_cagri(tmp_path):
    """Aynı isim iki farkli alt hesapta gecerse ayni token'i almali (yeni token uretilmemeli)."""
    kimlik_db = tmp_path / "kimlik.db"
    satirlar = [
        _satir("131.01", "AHMET YILMAZ"),
        _satir("131.02", "AHMET YILMAZ"),
    ]

    sonuc = kimlik_ayir(satirlar, kimlik_db)

    assert sonuc[0].hesap_adi == "[KISI-001]"
    assert sonuc[1].hesap_adi == "[KISI-001]"
    assert len(_kimlik_satirlari(kimlik_db)) == 1


def test_ayni_gercek_ad_ikinci_cagrida_yeni_token_uretmez(tmp_path):
    """Idempotentlik: kimlik_ayir ikinci kez cagrildiginda kimlik.db'den bulur, yeni token uretmez."""
    kimlik_db = tmp_path / "kimlik.db"

    ilk_sonuc = kimlik_ayir([_satir("131.01", "AHMET YILMAZ")], kimlik_db)
    assert ilk_sonuc[0].hesap_adi == "[KISI-001]"

    ikinci_sonuc = kimlik_ayir([_satir("131.03", "AHMET YILMAZ")], kimlik_db)
    assert ikinci_sonuc[0].hesap_adi == "[KISI-001]"
    assert len(_kimlik_satirlari(kimlik_db)) == 1

    # Yeni bir isim eklenirse siradaki numarayi almali (001 tekrar kullanilmaz)
    ucuncu_sonuc = kimlik_ayir([_satir("320.01", "Satıcılar [TEDARIKCI-B]")], kimlik_db)
    assert ucuncu_sonuc[0].hesap_adi == "Satıcılar [KISI-002]"


# --- Senaryo 2 & 3: sizinti_tara ---


def test_sizinti_tara_vkn_regex_ile_yakalar(tmp_path):
    kimlik_db = tmp_path / "kimlik.db"
    sonuc = sizinti_tara("Mukellef VKN 1234567890 ile kayitlidir.", kimlik_db)
    assert sonuc != []
    assert "1234567890" in sonuc


def test_sizinti_tara_tckn_regex_ile_yakalar(tmp_path):
    kimlik_db = tmp_path / "kimlik.db"
    sonuc = sizinti_tara("TCKN: 12345678901 numarali kisi.", kimlik_db)
    assert "12345678901" in sonuc


def test_sizinti_tara_iban_regex_ile_yakalar(tmp_path):
    kimlik_db = tmp_path / "kimlik.db"
    iban = "TR" + "1" * 24
    sonuc = sizinti_tara(f"Hesap IBAN {iban} numarasina odeme yapildi.", kimlik_db)
    assert iban in sonuc


def test_sizinti_tara_temiz_metin_bos_liste_doner(tmp_path):
    kimlik_db = tmp_path / "kimlik.db"
    sonuc = sizinti_tara("Bu metinde hicbir kimlik bilgisi yok, sadece genel aciklama.", kimlik_db)
    assert sonuc == []


def test_sizinti_tara_kimlik_db_deki_gercek_ad_yakalanir(tmp_path):
    kimlik_db = tmp_path / "kimlik.db"
    kimlik_ayir([_satir("131.01", "AHMET YILMAZ")], kimlik_db)

    sonuc = sizinti_tara("Rapor taslaginda AHMET YILMAZ adi geciyor, bu sizinti.", kimlik_db)

    assert sonuc != []
    assert "AHMET YILMAZ" in sonuc


def test_sizinti_tara_case_insensitive_kucuk_harfle_de_yakalar(tmp_path):
    """Turkce dogru kucuk harf: 'YILMAZ' -> 'yılmaz' (noktasiz ı) --
    bkz. _tr_fold / Critical-1 fix (naif ASCII 'yilmaz' Turkce'de yanlis
    kucuk harf bicimidir, gercek metinlerde 'yılmaz' gecer)."""
    kimlik_db = tmp_path / "kimlik.db"
    kimlik_ayir([_satir("131.01", "AHMET YILMAZ")], kimlik_db)

    sonuc = sizinti_tara("metinde ahmet yılmaz kucuk harfle geciyor.", kimlik_db)

    assert sonuc != []


def test_maske_ihlali_exception_raise_edilebilir():
    with pytest.raises(MaskeIhlali):
        raise MaskeIhlali("test ihlali")


# --- Critical-1: Turkce I/ı/İ/i casefold yalancı negatifi ---


def test_sizinti_tara_turkce_isik_insaat_buyuk_kucuk_donusum_yakalar(tmp_path):
    """db'de 'Işık İnşaat' (karisik harf), taranan metinde 'IŞIK İNŞAAT'
    (tamamen buyuk) -- naif casefold() bunu yakalamiyordu (Critical-1)."""
    kimlik_db = tmp_path / "kimlik.db"
    baglanti = sqlite3.connect(kimlik_db)
    try:
        baglanti.executescript(
            "CREATE TABLE IF NOT EXISTS kimlik ("
            "takma_kod TEXT PRIMARY KEY, tip TEXT NOT NULL, "
            "gercek_ad TEXT NOT NULL, vkn_tckn TEXT)"
        )
        baglanti.execute(
            "INSERT INTO kimlik (takma_kod, tip, gercek_ad, vkn_tckn) "
            "VALUES ('MUK-001', 'MUKELLEF', 'Işık İnşaat', NULL)"
        )
        baglanti.commit()
    finally:
        baglanti.close()

    sonuc = sizinti_tara("Faturada IŞIK İNŞAAT unvanina rastlandi.", kimlik_db)

    assert sonuc != []
    assert "Işık İnşaat" in sonuc


def test_sizinti_tara_turkce_sitki_buyuk_kucuk_donusum_yakalar(tmp_path):
    """db'de 'Sıtkı', taranan metinde 'SITKI' -- ayni Turkce I/ı sorunu."""
    kimlik_db = tmp_path / "kimlik.db"
    baglanti = sqlite3.connect(kimlik_db)
    try:
        baglanti.executescript(
            "CREATE TABLE IF NOT EXISTS kimlik ("
            "takma_kod TEXT PRIMARY KEY, tip TEXT NOT NULL, "
            "gercek_ad TEXT NOT NULL, vkn_tckn TEXT)"
        )
        baglanti.execute(
            "INSERT INTO kimlik (takma_kod, tip, gercek_ad, vkn_tckn) "
            "VALUES ('KISI-001', 'KISI', 'Sıtkı', NULL)"
        )
        baglanti.commit()
    finally:
        baglanti.close()

    sonuc = sizinti_tara("Yetkili SITKI bey ile gorusuldu.", kimlik_db)

    assert sonuc != []
    assert "Sıtkı" in sonuc


# --- Important-3: bosluklu IBAN kacagi ---


def test_sizinti_tara_iban_bosluklu_bicimi_yakalar(tmp_path):
    kimlik_db = tmp_path / "kimlik.db"
    iban_bosluklu = "TR12 3456 7890 1234 5678 9012 34"

    sonuc = sizinti_tara(f"Odeme IBAN {iban_bosluklu} hesabina yapildi.", kimlik_db)

    assert sonuc != []
    assert iban_bosluklu in sonuc


def test_sizinti_tara_iban_bitisik_ve_bosluklu_ikisi_de_yakalar(tmp_path):
    kimlik_db = tmp_path / "kimlik.db"
    iban_bitisik = "TR" + "1" * 24
    iban_bosluklu = "TR98 7654 3210 9876 5432 1098 76"
    metin = f"Birinci hesap {iban_bitisik}, ikinci hesap {iban_bosluklu}."

    sonuc = sizinti_tara(metin, kimlik_db)

    assert iban_bitisik in sonuc
    assert iban_bosluklu in sonuc


# --- Minor-5: bracket + buyuk harf ad karisik deseni sirali maskeleme ---


def test_bracket_ve_buyuk_harf_ad_birlikte_sirali_maskelenir(tmp_path):
    """'AHMET YILMAZ [ORTAK-A]' -- iki tespit katmani SIRALI uygulanmali:
    once bracket maskelenir, sonra kalan metindeki buyuk harfli ad da
    maskelenir (else degil -- ikisi de acikta kalmamali)."""
    kimlik_db = tmp_path / "kimlik.db"
    satirlar = [_satir("131.05", "AHMET YILMAZ [ORTAK-A]")]

    sonuc = kimlik_ayir(satirlar, kimlik_db)

    hesap_adi = sonuc[0].hesap_adi
    assert "AHMET YILMAZ" not in hesap_adi
    assert "ORTAK-A" not in hesap_adi
    assert hesap_adi.count("KISI-") == 2
