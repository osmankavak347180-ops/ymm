"""MUHSGK (Muhtasar ve Prim Hizmet) beyanname PDF parser testleri (Task 3.2).

KVKK: gerçek GİB PDF'i kullanılmaz — dummy fixture tmp_path'e üretilir
(bkz. tests/yardimci_pdf.py).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from yardimci_pdf import dummy_beyanname_pdf
from ymm.parsers.beyanname.muhtasar import _ALAN_ETIKETLERI, muhsgk_parse

_ORNEK_TUTARLAR: dict[str, Decimal] = {
    "brut_ucret_toplam": Decimal("408333.33"),
    "gelir_vergisi_kesintisi": Decimal("61250.00"),
}


def test_muhsgk_parse_dogru_tutarlari_decimal_dondurur(tmp_path):
    dosya = dummy_beyanname_pdf(
        tmp_path / "muhsgk.pdf", _ALAN_ETIKETLERI, _ORNEK_TUTARLAR
    )

    sonuc = muhsgk_parse(dosya)

    assert sonuc["brut_ucret_toplam"] == Decimal("408333.33")
    assert sonuc["gelir_vergisi_kesintisi"] == Decimal("61250.00")
    for deger in sonuc.values():
        assert isinstance(deger, Decimal)


def test_muhsgk_parse_eksik_etiket_none_ve_uyari(tmp_path, caplog):
    dosya = dummy_beyanname_pdf(
        tmp_path / "muhsgk_eksik.pdf",
        _ALAN_ETIKETLERI,
        _ORNEK_TUTARLAR,
        eksik_alan="brut_ucret_toplam",
    )

    with caplog.at_level("WARNING"):
        sonuc = muhsgk_parse(dosya)

    assert sonuc["brut_ucret_toplam"] is None
    assert sonuc["gelir_vergisi_kesintisi"] == Decimal("61250.00")
    assert any("brut_ucret_toplam" in kayit.message for kayit in caplog.records)


def test_muhsgk_parse_bozuk_dosya_anlasilir_hata():
    sahte_pdf = Path(__file__)  # bu .py dosyası, geçerli bir PDF değil

    with pytest.raises(ValueError):
        muhsgk_parse(sahte_pdf)


def test_muhsgk_parse_donen_sozluk_yalnizca_tutar_alanlari_icerir():
    """KVKK: muhsgk_parse mükellef kimlik alanı (unvan/vkn/adres) DÖNDÜRMEZ.
    Kontrol motorunun A-MUHSGK-UCRET kuralı `brut_ucret_toplam` bekler —
    bu alan kümede OLMALI."""
    assert set(_ALAN_ETIKETLERI) == {
        "brut_ucret_toplam",
        "gelir_vergisi_kesintisi",
    }
