"""CLI v1 testleri (Task 2.3): `ymm yukle mizan/beyanname-ozet`, `kontrol`,
`tara`, `bulgular` — typer `CliRunner` ile uçtan uca.

KVKK notu: yukle mizan akışında `kimlik_ayir` ATLANAMAZ (bkz. cli.py). Bu
dosyadaki testler DB'ye yazılan verinin gerçekten maskeli olduğunu doğrudan
`Depo` üzerinden de kontrol eder (CLI tablo çıktısı bu dummy veri setinde
maskelenen alt hesabı yansıtan bir kontrol/risk kuralı içermediği için —
B-131-ORTAK ana "131" hesabını kullanır, "131.01"i değil).
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ymm.cli import app
from ymm.db.depo import Depo

_PROJE_KOKU = Path(__file__).parent.parent
_MIZAN_XLSX = _PROJE_KOKU / "ornek_veri" / "mizan_2025.xlsx"
_BEYANNAME_OZET_JSON = _PROJE_KOKU / "ornek_veri" / "beyanname_ozet.json"
_KOLON_HARITASI = _PROJE_KOKU / "config" / "kolon_haritasi.yaml"
_KONTROL_KONFIG = _PROJE_KOKU / "config" / "kontrol_kurallari.yaml"
_RISK_KONFIG = _PROJE_KOKU / "config" / "risk_hesaplari.yaml"

runner = CliRunner()


@pytest.fixture
def db_yollari(tmp_path):
    return {
        "veri_db": tmp_path / "veri.db",
        "kimlik_db": tmp_path / "kimlik.db",
    }


def _yukle_mizan(db_yollari, mukellef="MUK-001", yil="2025"):
    return runner.invoke(
        app,
        [
            "yukle",
            "mizan",
            str(_MIZAN_XLSX),
            "--mukellef",
            mukellef,
            "--yil",
            yil,
            "--veri-db",
            str(db_yollari["veri_db"]),
            "--kimlik-db",
            str(db_yollari["kimlik_db"]),
        ],
    )


def _yukle_beyanname_ozet(db_yollari, mukellef="MUK-001"):
    return runner.invoke(
        app,
        [
            "yukle",
            "beyanname-ozet",
            str(_BEYANNAME_OZET_JSON),
            "--mukellef",
            mukellef,
            "--veri-db",
            str(db_yollari["veri_db"]),
        ],
    )


def _kontrol(db_yollari, mukellef="MUK-001", yil="2025"):
    return runner.invoke(
        app,
        [
            "kontrol",
            "--mukellef",
            mukellef,
            "--yil",
            yil,
            "--veri-db",
            str(db_yollari["veri_db"]),
        ],
    )


def _tara(db_yollari, mukellef="MUK-001", yil="2025"):
    return runner.invoke(
        app,
        [
            "tara",
            "--mukellef",
            mukellef,
            "--yil",
            yil,
            "--veri-db",
            str(db_yollari["veri_db"]),
        ],
    )


def _bulgular(db_yollari, mukellef="MUK-001", yil="2025", seviye=None):
    args = [
        "bulgular",
        "--mukellef",
        mukellef,
        "--yil",
        yil,
        "--veri-db",
        str(db_yollari["veri_db"]),
    ]
    if seviye is not None:
        args += ["--seviye", seviye]
    return runner.invoke(app, args)


# --- yukle mizan -----------------------------------------------------------


def test_yukle_mizan_basarili_cikis_kodu_0(db_yollari):
    sonuc = _yukle_mizan(db_yollari)
    assert sonuc.exit_code == 0, sonuc.output


def test_yukle_mizan_mukellef_ve_donem_yoksa_olusturur(db_yollari):
    _yukle_mizan(db_yollari)

    depo = Depo(db_yollari["veri_db"])
    mukellef_id = depo.mukellef_bul("MUK-001")
    assert mukellef_id is not None
    donem_id = depo.donem_bul(mukellef_id, 2025, "YILLIK")
    assert donem_id is not None
    satirlar = depo.mizan_oku(donem_id)
    assert len(satirlar) > 0


def test_yukle_mizan_maskeleme_atlanamaz_gercek_ad_depoda_yok(db_yollari):
    """kimlik_ayir akıştan çıkarılamaz: 131.01 alt hesabındaki köşeli parantez
    etiketi depoda [KISI-nnn] token'ına dönüşmüş olmalı, ham "[ORTAK-A]"
    dizgisi DEPODA bulunmamalı."""
    _yukle_mizan(db_yollari)

    depo = Depo(db_yollari["veri_db"])
    mukellef_id = depo.mukellef_bul("MUK-001")
    donem_id = depo.donem_bul(mukellef_id, 2025, "YILLIK")
    satirlar = depo.mizan_oku(donem_id)

    alt_hesap = next(s for s in satirlar if s.hesap_kodu == "131.01")
    assert "[KISI-" in alt_hesap.hesap_adi
    assert "ORTAK-A" not in alt_hesap.hesap_adi


def test_yukle_mizan_tekrar_yuklenirse_eski_satirlar_silinir(db_yollari):
    ilk = _yukle_mizan(db_yollari)
    assert ilk.exit_code == 0

    depo = Depo(db_yollari["veri_db"])
    mukellef_id = depo.mukellef_bul("MUK-001")
    donem_id = depo.donem_bul(mukellef_id, 2025, "YILLIK")
    ilk_sayi = len(depo.mizan_oku(donem_id))

    ikinci = _yukle_mizan(db_yollari)
    assert ikinci.exit_code == 0

    ikinci_sayi = len(depo.mizan_oku(donem_id))
    assert ikinci_sayi == ilk_sayi  # ikiye katlanmadı


# --- yukle beyanname-ozet ---------------------------------------------------


def test_yukle_beyanname_ozet_basarili_cikis_kodu_0(db_yollari):
    sonuc = _yukle_beyanname_ozet(db_yollari)
    assert sonuc.exit_code == 0, sonuc.output


def test_yukle_beyanname_ozet_kayitlari_depoya_yazar(db_yollari):
    _yukle_beyanname_ozet(db_yollari)

    depo = Depo(db_yollari["veri_db"])
    mukellef_id = depo.mukellef_bul("MUK-001")
    assert mukellef_id is not None

    kdv_kayitlari = depo.beyanname_oku(mukellef_id, "KDV1", 2025)
    assert len(kdv_kayitlari) == 12

    kv_kayitlari = depo.beyanname_oku(mukellef_id, "KV", 2025)
    assert len(kv_kayitlari) == 1


# --- kontrol / tara ----------------------------------------------------------


def test_kontrol_konfig_hatasinda_kirmizi_mesaj_ve_exit_1(db_yollari, tmp_path):
    _yukle_mizan(db_yollari)
    _yukle_beyanname_ozet(db_yollari)

    bozuk_konfig = tmp_path / "bozuk_kontrol.yaml"
    bozuk_konfig.write_text(
        "kontroller:\n"
        "  - kod: X\n"
        "    sol:\n"
        "      kaynak: beyanname\n"
        "      tip: KDV1\n"
        "      alan: teslim_hizmet_toplam\n"
        "      donem: GECERSIZ_DEGER\n"
        "    sag:\n"
        "      kaynak: mizan\n"
        "      formul: '600'\n"
        "    tolerans:\n"
        "      mutlak: '10000.00'\n"
        "      oransal: 1.0\n"
        "    seviye_esikleri:\n"
        "      orta: 1.0\n"
        "      yuksek: 5.0\n",
        encoding="utf-8",
    )

    sonuc = runner.invoke(
        app,
        [
            "kontrol",
            "--mukellef",
            "MUK-001",
            "--yil",
            "2025",
            "--veri-db",
            str(db_yollari["veri_db"]),
            "--konfig",
            str(bozuk_konfig),
        ],
    )

    assert sonuc.exit_code == 1
    assert "Traceback" not in sonuc.output
    assert "GECERSIZ_DEGER" in sonuc.output or "hata" in sonuc.output.lower()


def test_kontrol_bulgu_uretir_ve_tabloda_gosterir(db_yollari):
    _yukle_mizan(db_yollari)
    _yukle_beyanname_ozet(db_yollari)

    sonuc = _kontrol(db_yollari)

    assert sonuc.exit_code == 0, sonuc.output
    assert "A-KDV-HASILAT" in sonuc.output

    depo = Depo(db_yollari["veri_db"])
    mukellef_id = depo.mukellef_bul("MUK-001")
    bulgular = depo.bulgular(mukellef_id, 2025)
    assert any(b.kontrol_kodu == "A-KDV-HASILAT" for b in bulgular)


def test_tara_bulgu_uretir_ve_tabloda_gosterir(db_yollari):
    _yukle_mizan(db_yollari)

    sonuc = _tara(db_yollari)

    assert sonuc.exit_code == 0, sonuc.output
    assert "B-131-ORTAK" in sonuc.output

    depo = Depo(db_yollari["veri_db"])
    mukellef_id = depo.mukellef_bul("MUK-001")
    bulgular = depo.bulgular(mukellef_id, 2025)
    assert any(b.kontrol_kodu == "B-131-ORTAK" for b in bulgular)


# --- bulgular ----------------------------------------------------------------


def test_bulgular_seviye_filtresiz_ikisini_de_gosterir(db_yollari):
    _yukle_mizan(db_yollari)
    _yukle_beyanname_ozet(db_yollari)
    _kontrol(db_yollari)
    _tara(db_yollari)

    sonuc = _bulgular(db_yollari)

    assert sonuc.exit_code == 0, sonuc.output
    assert "A-KDV-HASILAT" in sonuc.output
    assert "B-131-ORTAK" in sonuc.output


def test_bulgular_seviye_yuksek_filtresi_ortayi_gizler(db_yollari):
    _yukle_mizan(db_yollari)
    _yukle_beyanname_ozet(db_yollari)
    _kontrol(db_yollari)
    _tara(db_yollari)

    sonuc = _bulgular(db_yollari, seviye="yuksek")

    assert sonuc.exit_code == 0, sonuc.output
    assert "B-131-ORTAK" in sonuc.output  # yuksek
    assert "A-KDV-HASILAT" not in sonuc.output  # orta -> gizli


# --- tam uçtan uca akış -------------------------------------------------------


def test_uctan_uca_yukle_kontrol_tara_bulgular(db_yollari):
    """Brief'teki uçtan uca senaryo: mizan yükle -> beyanname-ozet yükle ->
    kontrol -> tara -> bulgular çıktısında A-KDV-HASILAT VE B-131-ORTAK
    dizgileri var; --seviye yuksek filtresi A-KDV-HASILAT'ı (orta) gizler."""
    assert _yukle_mizan(db_yollari).exit_code == 0
    assert _yukle_beyanname_ozet(db_yollari).exit_code == 0
    assert _kontrol(db_yollari).exit_code == 0
    assert _tara(db_yollari).exit_code == 0

    tum_bulgular = _bulgular(db_yollari)
    assert "A-KDV-HASILAT" in tum_bulgular.output
    assert "B-131-ORTAK" in tum_bulgular.output

    filtreli = _bulgular(db_yollari, seviye="yuksek")
    assert "B-131-ORTAK" in filtreli.output
    assert "A-KDV-HASILAT" not in filtreli.output

    # KVKK: maskeleme atlanmadı -- depoda ham "[ORTAK-A]" dizgisi yok.
    depo = Depo(db_yollari["veri_db"])
    mukellef_id = depo.mukellef_bul("MUK-001")
    donem_id = depo.donem_bul(mukellef_id, 2025, "YILLIK")
    satirlar = depo.mizan_oku(donem_id)
    alt_hesap = next(s for s in satirlar if s.hesap_kodu == "131.01")
    assert "[KISI-" in alt_hesap.hesap_adi


def test_kontrol_iki_kez_isletilirse_bulgular_mukerra_olmaz(db_yollari):
    """kontrol komutu iki kez çalıştırıldığında, aynı A-KDV-HASILAT bulgusu
    mükerrer olmamalı (sadece bir defa gösterilmeli). bulgu_sil akışı
    önceki A bulgularını siler, ardından yeni olanlar yazılır."""
    _yukle_mizan(db_yollari)
    _yukle_beyanname_ozet(db_yollari)

    # İlk kontrol
    sonuc_1 = _kontrol(db_yollari)
    assert sonuc_1.exit_code == 0

    depo = Depo(db_yollari["veri_db"])
    mukellef_id = depo.mukellef_bul("MUK-001")
    bulgular_sonra_1_kontrol = depo.bulgular(mukellef_id, 2025)
    kdv_hasilat_sayisi_1 = sum(
        1 for b in bulgular_sonra_1_kontrol if b.kontrol_kodu == "A-KDV-HASILAT"
    )
    toplam_1 = len(bulgular_sonra_1_kontrol)

    # İkinci kontrol (kontrol tekrarı)
    sonuc_2 = _kontrol(db_yollari)
    assert sonuc_2.exit_code == 0

    bulgular_sonra_2_kontrol = depo.bulgular(mukellef_id, 2025)
    kdv_hasilat_sayisi_2 = sum(
        1 for b in bulgular_sonra_2_kontrol if b.kontrol_kodu == "A-KDV-HASILAT"
    )
    toplam_2 = len(bulgular_sonra_2_kontrol)

    # A kaynağı bulgular mükerrer olmamalı: sayı aynı kalmalı
    assert kdv_hasilat_sayisi_2 == kdv_hasilat_sayisi_1
    # toplam saymada da değişiklik olmamalı (A bulgular yerine aynı olanlar yazılır)
    assert toplam_2 == toplam_1


def test_tara_iki_kez_isletilirse_bulgular_mukerra_olmaz(db_yollari):
    """tara komutu iki kez çalıştırıldığında, B kaynağı bulgular mükerrer
    olmamalı."""
    _yukle_mizan(db_yollari)

    # İlk tara
    sonuc_1 = _tara(db_yollari)
    assert sonuc_1.exit_code == 0

    depo = Depo(db_yollari["veri_db"])
    mukellef_id = depo.mukellef_bul("MUK-001")
    bulgular_sonra_1_tara = depo.bulgular(mukellef_id, 2025)
    b_ortak_sayisi_1 = sum(
        1 for b in bulgular_sonra_1_tara if b.kontrol_kodu == "B-131-ORTAK"
    )
    toplam_1 = len(bulgular_sonra_1_tara)

    # İkinci tara (tara tekrarı)
    sonuc_2 = _tara(db_yollari)
    assert sonuc_2.exit_code == 0

    bulgular_sonra_2_tara = depo.bulgular(mukellef_id, 2025)
    b_ortak_sayisi_2 = sum(
        1 for b in bulgular_sonra_2_tara if b.kontrol_kodu == "B-131-ORTAK"
    )
    toplam_2 = len(bulgular_sonra_2_tara)

    # B kaynağı bulgular mükerrer olmamalı
    assert b_ortak_sayisi_2 == b_ortak_sayisi_1
    assert toplam_2 == toplam_1


def test_kontrol_tara_kontrol_siklis_isletilirse_b_bulgular_korunur(db_yollari):
    """kontrol -> tara -> kontrol sırasında, kontrol tekrarı A bulgularını
    siler ama B bulgularını KORUR."""
    _yukle_mizan(db_yollari)
    _yukle_beyanname_ozet(db_yollari)

    # kontrol
    assert _kontrol(db_yollari).exit_code == 0

    # tara
    assert _tara(db_yollari).exit_code == 0

    depo = Depo(db_yollari["veri_db"])
    mukellef_id = depo.mukellef_bul("MUK-001")
    bulgular_sonra_tara = depo.bulgular(mukellef_id, 2025)
    b_bulgular_sayisi = sum(1 for b in bulgular_sonra_tara if b.kaynak == "B")

    # kontrol tekrarı
    assert _kontrol(db_yollari).exit_code == 0

    bulgular_sonra_ikinci_kontrol = depo.bulgular(mukellef_id, 2025)
    b_bulgular_sayisi_sonra = sum(
        1 for b in bulgular_sonra_ikinci_kontrol if b.kaynak == "B"
    )

    # B bulgularının sayısı değişmemiş olmalı
    assert b_bulgular_sayisi == b_bulgular_sayisi_sonra


def test_tara_konfig_hatasinda_kirmizi_mesaj_ve_exit_1(db_yollari, tmp_path):
    """tara komutu da kontrol komutu gibi config hatasında exit 1 ve traceback
    olmadan mesaj verir."""
    _yukle_mizan(db_yollari)

    bozuk_konfig = tmp_path / "bozuk_risk.yaml"
    bozuk_konfig.write_text(
        "statik:\n"
        "  - kod: X\n"
        "    hesap_prefix: '131'\n"
        "    kural: GECERSIZ_KURAL_TIPI\n"
        "    seviye: yuksek\n",
        encoding="utf-8",
    )

    sonuc = runner.invoke(
        app,
        [
            "tara",
            "--mukellef",
            "MUK-001",
            "--yil",
            "2025",
            "--veri-db",
            str(db_yollari["veri_db"]),
            "--konfig",
            str(bozuk_konfig),
        ],
    )

    assert sonuc.exit_code == 1
    assert "Traceback" not in sonuc.output


def test_bulgular_seviye_gecersiz_hata_donduruyor(db_yollari):
    """bulgular komutu geçersiz --seviye değeri aldığında hata verir."""
    _yukle_mizan(db_yollari)
    _yukle_beyanname_ozet(db_yollari)
    _kontrol(db_yollari)

    sonuc = runner.invoke(
        app,
        [
            "bulgular",
            "--mukellef",
            "MUK-001",
            "--yil",
            "2025",
            "--seviye",
            "gecersiz",
            "--veri-db",
            str(db_yollari["veri_db"]),
        ],
    )

    assert sonuc.exit_code != 0
    assert "Geçersiz" in sonuc.output or "gecersiz" in sonuc.output.lower()
