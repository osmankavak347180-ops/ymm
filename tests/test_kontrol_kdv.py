"""kontrol/motor.py + kontrol/kurallar.py testleri: A-KDV-HASILAT kontrolü.

Senaryolar (bkz. .superpowers/sdd/task-1.2-brief.md):
- pozitif: mizan 600=5.000.000 (alacak), KDV kümülatif 4.900.000 -> fark
  100.000, %2.0 -> Bulgu(seviye="orta", tutar_fark=Decimal("100000.00"))
- tolerans içi: mutlak VE oransal eşiğin İKİSİ DE aşılmalı; biri aşılmazsa
  bulgu YOK.
- mutabakat kalemi: formül sonucuna eklenen/çıkarılan kalem farkı kapatır.
- ana hesap önceliği: "131" + "131.01" çifte sayılmaz (kurallar.py birim testi).
- eksik dönem uyarısı: yillik_kumulatif'ten gelen uyarı detay'a girer.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from ymm.db.depo import Depo
from ymm.kontrol.kurallar import formul_degerlendir, hesap_degeri, karsilastir
from ymm.kontrol.motor import kontrolleri_calistir
from ymm.modeller import Donem, MizanSatiri

_KONFIG_YOLU = Path(__file__).parent.parent / "config" / "kontrol_kurallari.yaml"

_AYLIK_TUTARLAR = ["408333.33"] * 11 + ["408333.37"]  # toplam 4.900.000.00


@pytest.fixture
def depo(tmp_path):
    return Depo(tmp_path / "veri.db")


def _kdv_beyannameleri_yukle(depo, mukellef_id, yil=2025, tutarlar=None):
    """12 aylık KDV1 beyannamesi yazar (kümülatif toplam 4.900.000.00)."""
    tutarlar = tutarlar or _AYLIK_TUTARLAR
    for sira, tutar in enumerate(tutarlar, start=1):
        donem_id = depo.donem_ekle(mukellef_id, Donem(yil=yil, tip="AY", sira=sira))
        depo.beyanname_yaz(donem_id, "KDV1", {"teslim_hizmet_toplam": tutar})


def _mizan_yukle(depo, mukellef_id, satirlar, yil=2025):
    donem_id = depo.donem_ekle(mukellef_id, Donem(yil=yil, tip="YILLIK", sira=0))
    depo.mizan_yaz(donem_id, satirlar)


def _600_satiri(alacak_bakiye: str) -> MizanSatiri:
    return MizanSatiri(
        hesap_kodu="600",
        hesap_adi="Yurtiçi Satışlar",
        borc_toplam=Decimal("0"),
        alacak_toplam=Decimal(alacak_bakiye),
        borc_bakiye=Decimal("0"),
        alacak_bakiye=Decimal(alacak_bakiye),
    )


def _yukle_konfig() -> dict:
    return yaml.safe_load(_KONFIG_YOLU.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# kurallar.py birim testleri
# --------------------------------------------------------------------------


def test_hesap_degeri_borc_bakiye_pozitifse_onu_doner():
    satir = MizanSatiri(
        hesap_kodu="770",
        hesap_adi="Genel Yönetim Giderleri",
        borc_toplam=Decimal("1000.00"),
        alacak_toplam=Decimal("0"),
        borc_bakiye=Decimal("1000.00"),
        alacak_bakiye=Decimal("0"),
    )
    assert hesap_degeri([satir], "770") == Decimal("1000.00")


def test_hesap_degeri_ana_hesap_varsa_alt_hesaplar_yok_sayilir_cifte_sayim_yok():
    """131 ve 131.01 aynı bakiyeyi taşıyor — ana hesap satırı önceliklidir."""
    ana = MizanSatiri(
        hesap_kodu="131",
        hesap_adi="Ortaklardan Alacaklar",
        borc_toplam=Decimal("50000.00"),
        alacak_toplam=Decimal("0"),
        borc_bakiye=Decimal("50000.00"),
        alacak_bakiye=Decimal("0"),
    )
    alt = MizanSatiri(
        hesap_kodu="131.01",
        hesap_adi="Ortaklardan Alacaklar [KISI-001]",
        borc_toplam=Decimal("50000.00"),
        alacak_toplam=Decimal("0"),
        borc_bakiye=Decimal("50000.00"),
        alacak_bakiye=Decimal("0"),
    )
    assert hesap_degeri([ana, alt], "131") == Decimal("50000.00")


def test_hesap_degeri_ana_hesap_yoksa_alt_hesaplar_toplanir():
    alt1 = MizanSatiri("600.01", "Yurtiçi A", Decimal("0"), Decimal("3000000.00"), Decimal("0"), Decimal("3000000.00"))
    alt2 = MizanSatiri("600.02", "Yurtiçi B", Decimal("0"), Decimal("2000000.00"), Decimal("0"), Decimal("2000000.00"))
    assert hesap_degeri([alt1, alt2], "600") == Decimal("5000000.00")


def test_formul_degerlendir_isaretlere_gore_toplar_ve_cikarir():
    satirlar = [
        _600_satiri("5000000.00"),
        MizanSatiri("610", "İadeler", Decimal("200000.00"), Decimal("0"), Decimal("200000.00"), Decimal("0")),
    ]
    sonuc = formul_degerlendir("600 + 601 + 602 - 610 - 611 - 612", satirlar)
    assert sonuc == Decimal("4800000.00")


def test_formul_degerlendir_tek_terim_isaretli_mutabakat_kalemi():
    satirlar = [
        MizanSatiri("679", "Duran Varlık Satış Karı", Decimal("0"), Decimal("150000.00"), Decimal("0"), Decimal("150000.00")),
    ]
    assert formul_degerlendir("+679", satirlar) == Decimal("150000.00")
    assert formul_degerlendir("-679", satirlar) == Decimal("-150000.00")


def test_karsilastir_ikisi_de_asilmazsa_none_doner():
    # fark 5000 < mutlak esik 10000
    assert karsilastir(Decimal("4995000"), Decimal("5000000"), {"mutlak": "10000.00", "oransal": 1.0}, {"orta": 1.0, "yuksek": 5.0}) is None


def test_karsilastir_yalnizca_mutlak_asilirsa_bulgu_yok():
    # fark 15000 > mutlak esik 10000 ama yuzde %0.3 <= oransal esik 1.0
    sonuc = karsilastir(Decimal("4985000"), Decimal("5000000"), {"mutlak": "10000.00", "oransal": 1.0}, {"orta": 1.0, "yuksek": 5.0})
    assert sonuc is None


def test_karsilastir_ikisi_de_asilirsa_seviye_orta():
    tutar_fark, yuzde_fark, seviye = karsilastir(
        Decimal("4900000"), Decimal("5000000"), {"mutlak": "10000.00", "oransal": 1.0}, {"orta": 1.0, "yuksek": 5.0}
    )
    assert tutar_fark == Decimal("100000.00")
    assert yuzde_fark == pytest.approx(2.0)
    assert seviye == "orta"


def test_karsilastir_yuksek_esigi_asilirsa_seviye_yuksek():
    _, yuzde_fark, seviye = karsilastir(
        Decimal("4700000"), Decimal("5000000"), {"mutlak": "10000.00", "oransal": 1.0}, {"orta": 1.0, "yuksek": 5.0}
    )
    assert yuzde_fark == pytest.approx(6.0)
    assert seviye == "yuksek"


# --------------------------------------------------------------------------
# motor.py uçtan uca testleri (Depo üzerinden)
# --------------------------------------------------------------------------


def test_pozitif_fark_orta_seviye_bulgu_uretir(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _kdv_beyannameleri_yukle(depo, mukellef_id)
    _mizan_yukle(depo, mukellef_id, [_600_satiri("5000000.00")])

    bulgular = kontrolleri_calistir(depo, mukellef_id, 2025, _yukle_konfig())

    assert len(bulgular) == 1
    bulgu = bulgular[0]
    assert bulgu.kaynak == "A"
    assert bulgu.kontrol_kodu == "A-KDV-HASILAT"
    assert bulgu.seviye == "orta"
    assert bulgu.tutar_fark == Decimal("100000.00")
    assert bulgu.yuzde_fark == pytest.approx(2.0, abs=0.01)
    assert bulgu.mukellef_id == mukellef_id
    assert bulgu.yil == 2025
    assert bulgu.detay["eksik_donem_uyarilari"] == []
    assert bulgu.detay["formul"] == "600 + 601 + 602 - 610 - 611 - 612"


def test_tolerans_icinde_ise_bulgu_uretilmez(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    # KDV kümülatif 4.985.000,00; mizan 5.000.000,00 -> mutlak fark 15.000
    # (mutlak eşik 10.000'i aşar) ama yüzde fark %0.3 (oransal eşik %1.0'i
    # AŞMAZ) -> ikisi de aşılmadığından bulgu YOK.
    _kdv_beyannameleri_yukle(depo, mukellef_id, tutarlar=["415416.66"] * 11 + ["415416.74"])  # toplam 4.985.000,00
    _mizan_yukle(depo, mukellef_id, [_600_satiri("5000000.00")])

    bulgular = kontrolleri_calistir(depo, mukellef_id, 2025, _yukle_konfig())

    assert bulgular == []


def test_mutabakat_kalemi_farki_kapatirsa_bulgu_uretilmez(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _kdv_beyannameleri_yukle(depo, mukellef_id)  # kümülatif 4.900.000,00
    _mizan_yukle(
        depo,
        mukellef_id,
        [
            _600_satiri("4750000.00"),
            MizanSatiri(
                "679", "Duran Varlık Satış Karı",
                Decimal("0"), Decimal("150000.00"), Decimal("0"), Decimal("150000.00"),
            ),
        ],
    )

    konfig = _yukle_konfig()
    konfig["kontroller"][0]["mutabakat_kalemleri"] = [
        {"ad": "duran_varlik_satisi", "formul": "+679"}
    ]

    bulgular = kontrolleri_calistir(depo, mukellef_id, 2025, konfig)

    assert bulgular == []


def test_eksik_donem_uyarisi_detaya_girer(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    # yalnizca 11 ay (sira 12 eksik)
    _kdv_beyannameleri_yukle(depo, mukellef_id, tutarlar=_AYLIK_TUTARLAR[:11])
    _mizan_yukle(depo, mukellef_id, [_600_satiri("5000000.00")])

    bulgular = kontrolleri_calistir(depo, mukellef_id, 2025, _yukle_konfig())

    assert len(bulgular) == 1
    uyarilar = bulgular[0].detay["eksik_donem_uyarilari"]
    assert len(uyarilar) == 1
    assert "12" in uyarilar[0]
