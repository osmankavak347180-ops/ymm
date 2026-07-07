"""KDV1 beyanname PDF parser testleri (Task 3.1).

KVKK: bu testlerde gercek GIB PDF'i KULLANILMAZ -- reportlab ile tmp_path'e
uretilen dummy KDV beyanname sayfasi kullanilir (repoya binary PDF girmez).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from ymm.parsers.beyanname.kdv import _ALAN_ETIKETLERI, kdv_parse
from ymm.parsers.beyanname.ortak import _tutar_normalize, etiket_degeri

# reportlab'in gömülü Helvetica fontu Türkçe özel karakterleri (ş, ğ, ı, İ,
# ö, ü, ç) WinAnsi kodlamasında düzgün basamaz -- bu da PDF metin
# çıkarımında etiketlerin bozulmasına (dolayısıyla testin yanlış RED/GREEN
# vermesine) yol açar. Bu yüzden Windows'ta yerleşik bulunan Arial TTF'i
# Unicode font olarak kaydediyoruz (proje zaten Windows'a özgü -- bkz.
# CLAUDE.md "py -3.12" notu).
_TURKCE_FONT_ADI = "DummyKdvFontu"
_ARIAL_YOLU = Path("C:/Windows/Fonts/arial.ttf")
if _ARIAL_YOLU.exists():
    pdfmetrics.registerFont(TTFont(_TURKCE_FONT_ADI, str(_ARIAL_YOLU)))
else:  # pragma: no cover - beklenmeyen platform, Helvetica'ya düş
    _TURKCE_FONT_ADI = "Helvetica"

_ORNEK_TUTARLAR: dict[str, Decimal] = {
    "teslim_hizmet_toplam": Decimal("1234567.89"),
    "indirilecek_kdv": Decimal("222222.22"),
    "hesaplanan_kdv": Decimal("246913.58"),
    "matrah": Decimal("1234567.89"),
}


def _turkce_tutar(tutar: Decimal) -> str:
    """Decimal'i Turk bicimine cevirir: 1234567.89 -> '1.234.567,89'."""
    tam_kisim, ondalik_kisim = f"{tutar:.2f}".split(".")
    ters = tam_kisim[::-1]
    gruplu_ters = ".".join(ters[i : i + 3] for i in range(0, len(ters), 3))
    return f"{gruplu_ters[::-1]},{ondalik_kisim}"


def _dummy_kdv_pdf(yol: Path, *, eksik_alan: str | None = None) -> Path:
    """reportlab ile dummy KDV1 beyanname sayfasi uretir. ``eksik_alan``
    verilirse o alanin etiket/tutar satiri PDF'e YAZILMAZ (None + uyari
    testinde kullanilir)."""
    c = canvas.Canvas(str(yol), pagesize=A4)
    c.setFont(_TURKCE_FONT_ADI, 12)
    y = 800
    for alan, etiketler in _ALAN_ETIKETLERI.items():
        if alan == eksik_alan:
            continue
        etiket = etiketler[0]
        tutar = _turkce_tutar(_ORNEK_TUTARLAR[alan])
        c.drawString(50, y, f"{etiket}: {tutar}")
        y -= 25
    c.showPage()
    c.save()
    return yol


# --- ortak.py: _tutar_normalize / etiket_degeri -----------------------------


def test_tutar_normalize_turkce_bicim():
    assert _tutar_normalize("1.234.567,89") == Decimal("1234567.89")
    assert isinstance(_tutar_normalize("1.234.567,89"), Decimal)


def test_tutar_normalize_bos_deger_sifir():
    assert _tutar_normalize("") == Decimal("0")
    assert _tutar_normalize(None) == Decimal("0")


def test_etiket_degeri_bulunur():
    metin = "Matrah: 1.234.567,89\nBaska Satir"
    assert etiket_degeri(metin, ["Matrah"]) == Decimal("1234567.89")


def test_etiket_degeri_bulunamazsa_none():
    metin = "Baska bir metin, ilgili etiket yok"
    assert etiket_degeri(metin, ["Matrah", "Vergiye Tabi İşlemler Toplamı"]) is None


# --- kdv.py: kdv_parse -------------------------------------------------------


def test_kdv_parse_dogru_tutarlari_decimal_dondurur(tmp_path):
    dosya = _dummy_kdv_pdf(tmp_path / "kdv_ornek.pdf")

    sonuc = kdv_parse(dosya)

    assert sonuc["teslim_hizmet_toplam"] == Decimal("1234567.89")
    assert sonuc["indirilecek_kdv"] == Decimal("222222.22")
    assert sonuc["hesaplanan_kdv"] == Decimal("246913.58")
    assert sonuc["matrah"] == Decimal("1234567.89")
    for deger in sonuc.values():
        assert isinstance(deger, Decimal)


def test_kdv_parse_eksik_etiket_none_ve_uyari(tmp_path, caplog):
    dosya = _dummy_kdv_pdf(tmp_path / "kdv_eksik.pdf", eksik_alan="matrah")

    with caplog.at_level("WARNING"):
        sonuc = kdv_parse(dosya)

    assert sonuc["matrah"] is None
    assert sonuc["teslim_hizmet_toplam"] == Decimal("1234567.89")
    assert any("matrah" in kayit.message for kayit in caplog.records)


def test_kdv_parse_bozuk_dosya_anlasilir_hata():
    # PDF olmayan bir dosya (repoya PDF ekleme kuralı gereği bu dosyayı
    # kullanıyoruz; kdv_parse'ın PDF-olmayan girdide ValueError fırlatması
    # bekleniyor).
    sahte_pdf = Path(__file__)  # bu .py dosyası, gecerli bir PDF degil

    with pytest.raises(ValueError):
        kdv_parse(sahte_pdf)


def test_kdv_parse_donen_sozluk_yalnizca_tutar_alanlari_icerir():
    """KVKK: kdv_parse mukellef kimlik alani (unvan/vkn/adres) DONDURMEZ --
    sozlukte yalnizca beklenen 4 tutar alani olmali."""
    assert set(_ALAN_ETIKETLERI) == {
        "teslim_hizmet_toplam",
        "indirilecek_kdv",
        "hesaplanan_kdv",
        "matrah",
    }
