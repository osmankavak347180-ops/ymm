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
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from typer.testing import CliRunner

from yardimci_pdf import dummy_beyanname_pdf

from ymm.cli import app
from ymm.db.depo import Depo
from ymm.parsers.beyanname.gecici import _ALAN_ETIKETLERI as _GECICI_ETIKETLER
from ymm.parsers.beyanname.kdv import _ALAN_ETIKETLERI
from ymm.parsers.beyanname.kurumlar import _ALAN_ETIKETLERI as _KV_ETIKETLER
from ymm.parsers.beyanname.muhtasar import _ALAN_ETIKETLERI as _MUHSGK_ETIKETLER

_PROJE_KOKU = Path(__file__).parent.parent
_MIZAN_XLSX = _PROJE_KOKU / "ornek_veri" / "mizan_2025.xlsx"
_BEYANNAME_OZET_JSON = _PROJE_KOKU / "ornek_veri" / "beyanname_ozet.json"
_KOLON_HARITASI = _PROJE_KOKU / "config" / "kolon_haritasi.yaml"
_KONTROL_KONFIG = _PROJE_KOKU / "config" / "kontrol_kurallari.yaml"
_RISK_KONFIG = _PROJE_KOKU / "config" / "risk_hesaplari.yaml"

runner = CliRunner()

# --- Task 3.1: yukle beyanname (KDV1 PDF) icin dummy fixture uretimi -------
# Bkz. tests/test_parser_kdv.py -- ayni Turkce font gerekcesi burada da
# gecerli (reportlab'in gomulu Helvetica'si Turkce ozel karakterleri
# basamiyor).

_TURKCE_FONT_ADI_CLI = "DummyKdvFontuCli"
_ARIAL_YOLU_CLI = Path("C:/Windows/Fonts/arial.ttf")
if _ARIAL_YOLU_CLI.exists():
    pdfmetrics.registerFont(TTFont(_TURKCE_FONT_ADI_CLI, str(_ARIAL_YOLU_CLI)))
else:  # pragma: no cover - beklenmeyen platform
    _TURKCE_FONT_ADI_CLI = "Helvetica"

_KDV_ORNEK_TUTARLAR: dict[str, Decimal] = {
    "teslim_hizmet_toplam": Decimal("1234567.89"),
    "indirilecek_kdv": Decimal("222222.22"),
    "hesaplanan_kdv": Decimal("246913.58"),
    "matrah": Decimal("1234567.89"),
}


def _turkce_tutar_cli(tutar: Decimal) -> str:
    tam_kisim, ondalik_kisim = f"{tutar:.2f}".split(".")
    ters = tam_kisim[::-1]
    gruplu_ters = ".".join(ters[i : i + 3] for i in range(0, len(ters), 3))
    return f"{gruplu_ters[::-1]},{ondalik_kisim}"


def _dummy_kdv_pdf_cli(yol: Path, *, eksik_alan: str | None = None) -> Path:
    c = canvas.Canvas(str(yol), pagesize=A4)
    c.setFont(_TURKCE_FONT_ADI_CLI, 12)
    y = 800
    for alan, etiketler in _ALAN_ETIKETLERI.items():
        if alan == eksik_alan:
            continue
        etiket = etiketler[0]
        tutar = _turkce_tutar_cli(_KDV_ORNEK_TUTARLAR[alan])
        c.drawString(50, y, f"{etiket}: {tutar}")
        y -= 25
    c.showPage()
    c.save()
    return yol


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


# --- yukle beyanname (KDV1 PDF, Task 3.1) ------------------------------------


def _yukle_beyanname_pdf(db_yollari, dosya, *, mukellef="MUK-001", donem="2025-03",
                          tip="KDV1", onayla=False):
    args = [
        "yukle",
        "beyanname",
        str(dosya),
        "--tip",
        tip,
        "--donem",
        donem,
        "--mukellef",
        mukellef,
        "--veri-db",
        str(db_yollari["veri_db"]),
    ]
    if onayla:
        args.append("--onayla")
    return runner.invoke(app, args)


def test_yukle_beyanname_onaysiz_dbye_yazmaz_exit_0(db_yollari, tmp_path):
    dosya = _dummy_kdv_pdf_cli(tmp_path / "kdv.pdf")

    sonuc = _yukle_beyanname_pdf(db_yollari, dosya)

    assert sonuc.exit_code == 0, sonuc.output
    assert "onayla" in sonuc.output.lower()

    # DB'ye hiçbir şey yazılmamış olmalı (mükellef bile oluşmamış).
    assert not db_yollari["veri_db"].exists() or Depo(
        db_yollari["veri_db"]
    ).mukellef_bul("MUK-001") is None


def test_yukle_beyanname_onaysiz_tabloda_gosterir(db_yollari, tmp_path):
    dosya = _dummy_kdv_pdf_cli(tmp_path / "kdv.pdf")

    sonuc = _yukle_beyanname_pdf(db_yollari, dosya)

    assert sonuc.exit_code == 0, sonuc.output
    assert "teslim_hizmet_toplam" in sonuc.output
    assert "1234567.89" in sonuc.output


def test_yukle_beyanname_onayli_dbye_yazar(db_yollari, tmp_path):
    dosya = _dummy_kdv_pdf_cli(tmp_path / "kdv.pdf")

    sonuc = _yukle_beyanname_pdf(db_yollari, dosya, onayla=True)

    assert sonuc.exit_code == 0, sonuc.output

    depo = Depo(db_yollari["veri_db"])
    mukellef_id = depo.mukellef_bul("MUK-001")
    assert mukellef_id is not None

    donem_id = depo.donem_bul(mukellef_id, 2025, "AY", sira=3)
    assert donem_id is not None

    kayitlar = depo.beyanname_oku(mukellef_id, "KDV1", 2025)
    assert len(kayitlar) == 1
    assert kayitlar[0]["teslim_hizmet_toplam"] == "1234567.89"
    assert kayitlar[0]["matrah"] == "1234567.89"


def test_yukle_beyanname_eksik_alan_dbye_konmaz(db_yollari, tmp_path):
    """None dönen alanlar dict'e KONMAZ (motor zaten atlıyor konvansiyonu)."""
    dosya = _dummy_kdv_pdf_cli(tmp_path / "kdv_eksik.pdf", eksik_alan="matrah")

    sonuc = _yukle_beyanname_pdf(db_yollari, dosya, onayla=True)

    assert sonuc.exit_code == 0, sonuc.output

    depo = Depo(db_yollari["veri_db"])
    mukellef_id = depo.mukellef_bul("MUK-001")
    kayitlar = depo.beyanname_oku(mukellef_id, "KDV1", 2025)

    assert len(kayitlar) == 1
    assert "matrah" not in kayitlar[0]
    assert kayitlar[0]["teslim_hizmet_toplam"] == "1234567.89"


def test_yukle_beyanname_gecersiz_tip_hata(db_yollari, tmp_path):
    """Task 3.2: KDV1/MUHSGK/GECICI/KV desteklenir; tanınmayan tip anlaşılır
    hatayla reddedilir (geçerli tipler mesajda listelenir)."""
    dosya = _dummy_kdv_pdf_cli(tmp_path / "kdv.pdf")

    sonuc = _yukle_beyanname_pdf(db_yollari, dosya, tip="XYZ")

    assert sonuc.exit_code == 1
    assert "Traceback" not in sonuc.output
    assert "MUHSGK" in sonuc.output  # geçerli tipler listeleniyor


def test_yukle_beyanname_gecersiz_donem_formati_hata(db_yollari, tmp_path):
    dosya = _dummy_kdv_pdf_cli(tmp_path / "kdv.pdf")

    sonuc = _yukle_beyanname_pdf(db_yollari, dosya, donem="2025/03")

    assert sonuc.exit_code == 1
    assert "Traceback" not in sonuc.output


def test_yukle_beyanname_bozuk_dosya_anlasilir_hata_exit_1(db_yollari, tmp_path):
    bozuk = tmp_path / "bozuk.pdf"
    bozuk.write_text("bu bir PDF degil", encoding="utf-8")

    sonuc = _yukle_beyanname_pdf(db_yollari, bozuk)

    assert sonuc.exit_code == 1
    assert "Traceback" not in sonuc.output


def test_yukle_beyanname_iki_ay_farkli_donemlere_yazilir(db_yollari, tmp_path):
    """Aynı yılın farklı ayları (sira farklı) birbirine karışmamalı --
    donem_bul'un sira ile ayırt etmesinin CLI üzerinden doğrulanması."""
    dosya = _dummy_kdv_pdf_cli(tmp_path / "kdv.pdf")

    assert _yukle_beyanname_pdf(db_yollari, dosya, donem="2025-01", onayla=True).exit_code == 0
    assert _yukle_beyanname_pdf(db_yollari, dosya, donem="2025-02", onayla=True).exit_code == 0

    depo = Depo(db_yollari["veri_db"])
    mukellef_id = depo.mukellef_bul("MUK-001")
    kayitlar = depo.beyanname_oku_donemli(mukellef_id, "KDV1", 2025)

    assert [k["sira"] for k in kayitlar] == [1, 2]


# --- yukle beyanname (MUHSGK/GECICI/KV, Task 3.2) ----------------------------


def test_yukle_beyanname_muhsgk_onayli_ay_donemine_yazar(db_yollari, tmp_path):
    dosya = dummy_beyanname_pdf(
        tmp_path / "muhsgk.pdf",
        _MUHSGK_ETIKETLER,
        {
            "brut_ucret_toplam": Decimal("408333.33"),
            "gelir_vergisi_kesintisi": Decimal("61250.00"),
        },
    )

    sonuc = _yukle_beyanname_pdf(
        db_yollari, dosya, tip="MUHSGK", donem="2025-03", onayla=True
    )

    assert sonuc.exit_code == 0, sonuc.output

    depo = Depo(db_yollari["veri_db"])
    mukellef_id = depo.mukellef_bul("MUK-001")
    assert depo.donem_bul(mukellef_id, 2025, "AY", sira=3) is not None

    kayitlar = depo.beyanname_oku(mukellef_id, "MUHSGK", 2025)
    assert len(kayitlar) == 1
    assert kayitlar[0]["brut_ucret_toplam"] == "408333.33"


def test_yukle_beyanname_gecici_onayli_ceyrek_donemine_yazar(db_yollari, tmp_path):
    """GECICI dönem biçimi YYYY-QN (ör. 2025-Q4) -> CEYREK tipli dönem.
    A-GECICI-KV kontrolü son çeyrek (sira=4) kaydını bekler."""
    dosya = dummy_beyanname_pdf(
        tmp_path / "gecici.pdf",
        _GECICI_ETIKETLER,
        {
            "matrah": Decimal("950000.00"),
            "hesaplanan_gecici_vergi": Decimal("237500.00"),
        },
    )

    sonuc = _yukle_beyanname_pdf(
        db_yollari, dosya, tip="GECICI", donem="2025-Q4", onayla=True
    )

    assert sonuc.exit_code == 0, sonuc.output

    depo = Depo(db_yollari["veri_db"])
    mukellef_id = depo.mukellef_bul("MUK-001")
    assert depo.donem_bul(mukellef_id, 2025, "CEYREK", sira=4) is not None

    kayitlar = depo.beyanname_oku(mukellef_id, "GECICI", 2025)
    assert len(kayitlar) == 1
    assert kayitlar[0]["matrah"] == "950000.00"


def test_yukle_beyanname_kv_onayli_yillik_donemine_yazar(db_yollari, tmp_path):
    """KV dönem biçimi yalnız YYYY (ör. 2025) -> YILLIK (sira=0) dönem."""
    dosya = dummy_beyanname_pdf(
        tmp_path / "kv.pdf",
        _KV_ETIKETLER,
        {
            "matrah": Decimal("950000.00"),
            "hesaplanan_kurumlar_vergisi": Decimal("237500.00"),
        },
    )

    sonuc = _yukle_beyanname_pdf(
        db_yollari, dosya, tip="KV", donem="2025", onayla=True
    )

    assert sonuc.exit_code == 0, sonuc.output

    depo = Depo(db_yollari["veri_db"])
    mukellef_id = depo.mukellef_bul("MUK-001")
    assert depo.donem_bul(mukellef_id, 2025, "YILLIK", sira=0) is not None

    kayitlar = depo.beyanname_oku(mukellef_id, "KV", 2025)
    assert len(kayitlar) == 1
    assert kayitlar[0]["matrah"] == "950000.00"


def test_yukle_beyanname_gecici_ay_bicimi_reddedilir(db_yollari, tmp_path):
    """GECICI için YYYY-MM biçimi (ay) geçersizdir -- beklenen YYYY-QN."""
    dosya = dummy_beyanname_pdf(
        tmp_path / "gecici.pdf",
        _GECICI_ETIKETLER,
        {
            "matrah": Decimal("950000.00"),
            "hesaplanan_gecici_vergi": Decimal("237500.00"),
        },
    )

    sonuc = _yukle_beyanname_pdf(db_yollari, dosya, tip="GECICI", donem="2025-03")

    assert sonuc.exit_code == 1
    assert "Traceback" not in sonuc.output
    assert "Q" in sonuc.output  # beklenen biçim mesajda gösteriliyor


def test_yukle_beyanname_kv_ay_bicimi_reddedilir(db_yollari, tmp_path):
    """KV için YYYY-MM biçimi geçersizdir -- beklenen yalnız YYYY."""
    dosya = dummy_beyanname_pdf(
        tmp_path / "kv.pdf",
        _KV_ETIKETLER,
        {
            "matrah": Decimal("950000.00"),
            "hesaplanan_kurumlar_vergisi": Decimal("237500.00"),
        },
    )

    sonuc = _yukle_beyanname_pdf(db_yollari, dosya, tip="KV", donem="2025-03")

    assert sonuc.exit_code == 1
    assert "Traceback" not in sonuc.output


def test_yukle_beyanname_muhsgk_onaysiz_dbye_yazmaz(db_yollari, tmp_path):
    """Onay akışı (R3 azaltımı) yeni tipler için de geçerli."""
    dosya = dummy_beyanname_pdf(
        tmp_path / "muhsgk.pdf",
        _MUHSGK_ETIKETLER,
        {
            "brut_ucret_toplam": Decimal("408333.33"),
            "gelir_vergisi_kesintisi": Decimal("61250.00"),
        },
    )

    sonuc = _yukle_beyanname_pdf(db_yollari, dosya, tip="MUHSGK", donem="2025-03")

    assert sonuc.exit_code == 0, sonuc.output
    assert "brut_ucret_toplam" in sonuc.output
    assert not db_yollari["veri_db"].exists() or Depo(
        db_yollari["veri_db"]
    ).mukellef_bul("MUK-001") is None
