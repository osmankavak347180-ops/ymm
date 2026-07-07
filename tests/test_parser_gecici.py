"""GECICI (Geçici Vergi) beyanname PDF parser testleri (Task 3.2).

KVKK: gerçek GİB PDF'i kullanılmaz — dummy fixture tmp_path'e üretilir
(bkz. tests/yardimci_pdf.py).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from yardimci_pdf import dummy_beyanname_pdf
from ymm.parsers.beyanname.gecici import _ALAN_ETIKETLERI, gecici_parse

_ORNEK_TUTARLAR: dict[str, Decimal] = {
    "matrah": Decimal("950000.00"),
    "hesaplanan_gecici_vergi": Decimal("237500.00"),
}


def test_gecici_parse_dogru_tutarlari_decimal_dondurur(tmp_path):
    dosya = dummy_beyanname_pdf(
        tmp_path / "gecici.pdf", _ALAN_ETIKETLERI, _ORNEK_TUTARLAR
    )

    sonuc = gecici_parse(dosya)

    assert sonuc["matrah"] == Decimal("950000.00")
    assert sonuc["hesaplanan_gecici_vergi"] == Decimal("237500.00")
    for deger in sonuc.values():
        assert isinstance(deger, Decimal)


def test_gecici_parse_eksik_etiket_none_ve_uyari(tmp_path, caplog):
    dosya = dummy_beyanname_pdf(
        tmp_path / "gecici_eksik.pdf",
        _ALAN_ETIKETLERI,
        _ORNEK_TUTARLAR,
        eksik_alan="matrah",
    )

    with caplog.at_level("WARNING"):
        sonuc = gecici_parse(dosya)

    assert sonuc["matrah"] is None
    assert sonuc["hesaplanan_gecici_vergi"] == Decimal("237500.00")
    assert any("matrah" in kayit.message for kayit in caplog.records)


def test_gecici_parse_bozuk_dosya_anlasilir_hata():
    sahte_pdf = Path(__file__)  # bu .py dosyası, geçerli bir PDF değil

    with pytest.raises(ValueError):
        gecici_parse(sahte_pdf)


def test_gecici_parse_donen_sozluk_yalnizca_tutar_alanlari_icerir():
    """KVKK: gecici_parse mükellef kimlik alanı DÖNDÜRMEZ. Kontrol motorunun
    A-GECICI-KV kuralı `matrah` bekler — bu alan kümede OLMALI."""
    assert set(_ALAN_ETIKETLERI) == {
        "matrah",
        "hesaplanan_gecici_vergi",
    }
