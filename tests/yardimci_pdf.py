"""Beyanname parser testleri için ortak dummy PDF fixture yardımcıları
(Task 3.2).

KVKK: testlerde gerçek GİB PDF'i KULLANILMAZ — reportlab ile tmp_path'e
üretilen dummy beyanname sayfaları kullanılır (repoya binary PDF girmez).

Türkçe font gerekçesi: reportlab'in gömülü Helvetica fontu Türkçe özel
karakterleri (ş, ğ, ı, İ, ö, ü, ç) WinAnsi kodlamasında düzgün basamaz —
bu da PDF metin çıkarımında etiketlerin bozulmasına yol açar. Windows'ta
yerleşik Arial TTF Unicode font olarak kaydedilir (proje zaten Windows'a
özgü tek-makine aracı, bkz. tests/test_parser_kdv.py).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

_TURKCE_FONT_ADI = "DummyBeyannameFontu"
_ARIAL_YOLU = Path("C:/Windows/Fonts/arial.ttf")
if _ARIAL_YOLU.exists():
    pdfmetrics.registerFont(TTFont(_TURKCE_FONT_ADI, str(_ARIAL_YOLU)))
else:  # pragma: no cover - beklenmeyen platform, Helvetica'ya düş
    _TURKCE_FONT_ADI = "Helvetica"


def turkce_tutar(tutar: Decimal) -> str:
    """Decimal'i Türk biçimine çevirir: 1234567.89 -> '1.234.567,89'."""
    tam_kisim, ondalik_kisim = f"{tutar:.2f}".split(".")
    ters = tam_kisim[::-1]
    gruplu_ters = ".".join(ters[i : i + 3] for i in range(0, len(ters), 3))
    return f"{gruplu_ters[::-1]},{ondalik_kisim}"


def dummy_beyanname_pdf(
    yol: Path,
    alan_etiketleri: dict[str, list[str]],
    tutarlar: dict[str, Decimal],
    *,
    eksik_alan: str | None = None,
) -> Path:
    """reportlab ile dummy beyanname sayfası üretir. Her alan için ilk
    etiket varyantı + Türk biçimli tutar tek satıra basılır. ``eksik_alan``
    verilirse o alanın satırı PDF'e YAZILMAZ (None + uyarı testlerinde
    kullanılır)."""
    c = canvas.Canvas(str(yol), pagesize=A4)
    c.setFont(_TURKCE_FONT_ADI, 12)
    y = 800
    for alan, etiketler in alan_etiketleri.items():
        if alan == eksik_alan:
            continue
        c.drawString(50, y, f"{etiketler[0]}: {turkce_tutar(tutarlar[alan])}")
        y -= 25
    c.showPage()
    c.save()
    return yol
