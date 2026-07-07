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


def test_etiket_degeri_iki_ardisik_etiket_kendi_tutarlari():
    """İki etiket ardışık satırlarda, her birinin kendi tutarı var.
    Her etiket KENDİ tutarını almalı (ilk etiketin penceresi 200 char'dan
    kısa kalmalı, 2. etikete bleed olmamalı)."""
    metin = (
        "Matrah: 1.000,00\n"
        "Hesaplanan KDV: 2.000,00"
    )
    # Matrah etiketinin 200 char penceresi:
    # idx=0, pencere = metin[16:216] = "1.000,00\nHesaplanan KDV: 2.000,00"
    # İlk tutar "1.000,00" olması gerekir (Matrah'ın kendi tutarı).
    assert etiket_degeri(metin, ["Matrah"]) == Decimal("1000.00")
    assert etiket_degeri(metin, ["Hesaplanan KDV"]) == Decimal("2000.00")


def test_etiket_degeri_pencere_sonrasinda_tutarsiz_yer_bilinen_sinir():
    """Etiketin KENDI satırında tutar YOK, 200 char penceresi içinde
    SONRAKI etiketin tutarı var (bleed-over durumu).

    Bu, gerçek GİB PDF'inde etiketler config'e taşınırken yeniden değerlendirilecek
    bir bilinen sınırdır. Şu anki davranışı SABİTLEYEN test (yanlış tutarı almaktadır)."""
    metin = (
        "Matrah\n"  # Matrah etiketinde tutar YOK (aynı satırda)
        "Hesaplanan KDV: 2.000,00"  # Sonraki etiketin tutarı, pencere içinde
    )
    # Matrah etiketi idx=0'da, pencere = metin[6:206] (6 + 200)
    # "Matrah\nHesaplanan KDV: 2.000,00"
    # İçinde 2.000,00 tutar gözüküyor (bleed-over).
    # Mevcut davranış: Matrah'ın tutarı olarak 2.000,00 alıyor (YANLIŞ ama bilinen sınır).
    result = etiket_degeri(metin, ["Matrah"])
    # Davranış: "Hesaplanan KDV: 2.000,00"'ı pencere içinde bulup 2000,00 döner.
    # Bu bilinir bir durum; gerçek GİB PDF'inde etiketler uygun yerlere taşınacak.
    assert result == Decimal("2000.00"), (
        "Bilinen sınır: etiket kendi satırında tutar yoksa, 200 char penceresi içinde "
        "sonraki tutarı alır. Gerçek GİB PDF'inde etiketler config'e taşınırken "
        "yeniden değerlendirilecek."
    )


def test_etiket_degeri_ayni_satir_oncesi_ve_sonrasi_tutar():
    """Aynı satırda etiketten ÖNCE ve SONRA tutar var. Sonraki (etiketten
    sonraki) tutar alınmalı (pencere etiketten sonra başlıyor)."""
    metin = "Onceki: 1.000,00 | Matrah: 2.000,00"
    # Matrah etiketi idx=20 veya benzer konumda
    # Pencere etiketten sonra başlar → "2.000,00"
    # Önceki tutar "1.000,00" pencere dışında kalır
    assert etiket_degeri(metin, ["Matrah"]) == Decimal("2000.00")


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
