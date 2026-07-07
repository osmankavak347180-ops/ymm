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
from ymm.kontrol.kurallar import (
    formul_degerlendir,
    formul_terimlerini_ayikla,
    hesap_degeri,
    hesap_eslesir,
    karsilastir,
)
from ymm.kontrol.motor import konfig_yukle, kontrolleri_calistir
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


def _yalniz_kdv_hasilat_kontrolu(konfig: dict) -> dict:
    """Task 1.3 ile config'e A-MUHSGK-UCRET/A-GECICI-KV/A-KDV-INDIRIM kontrolleri
    eklendi; bu dosyanın A-KDV-HASILAT'a özgü fixture'ları (MUHSGK/GECICI/KV
    beyannamesi yazmaz, indirilecek_kdv alanı içermez) o kontrollerle
    çalıştırılırsa eksik alan/kayıt nedeniyle hataya düşer. Testleri izole
    etmek için yalnız A-KDV-HASILAT'ı içeren bir konfig döner."""
    konfig = dict(konfig)
    konfig["kontroller"] = [
        k for k in konfig["kontroller"] if k["kod"] == "A-KDV-HASILAT"
    ]
    return konfig


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


def test_karsilastir_yalnizca_yuzde_asilirsa_bulgu_yok():
    """AND-tolerans diğer kol: yüzde fark eşiği aşar (4.0%) ama mutlak fark
    (200) mutlak eşiği (10000.00) aşmaz -> ikisi de aşılmadığından bulgu yok."""
    sonuc = karsilastir(
        Decimal("4800"), Decimal("5000"), {"mutlak": "10000.00", "oransal": 1.0}, {"orta": 1.0, "yuksek": 5.0}
    )
    assert sonuc is None


def test_karsilastir_esikler_tam_esitlikte_tolerans_ici_sayilir():
    """Sınır değer: mutlak_fark == mutlak_esik (10000.00) VE yuzde_fark ==
    oransal_esik (%1.0) -> ikisi de "aşılmadı" (<=) sayılır, bulgu yok."""
    sonuc = karsilastir(
        Decimal("990000.00"), Decimal("1000000.00"),
        {"mutlak": "10000.00", "oransal": 1.0}, {"orta": 1.0, "yuksek": 5.0},
    )
    assert sonuc is None


# --------------------------------------------------------------------------
# formul parser: TAM tüketim doğrulaması (sessiz sıfır / sessiz yanlış aritmetik)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bozuk_formul",
    [
        "600 ++ 601",
        "600 -- 601",
        "600 + 601 -",
        "600 & 601",
        "600 601",  # çıplak boşluk — operatörsüz iki terim
        "600  601",  # birden fazla çıplak boşluk
        "600 601 - 610",  # ilk iki terim arasında operatörsüz boşluk
    ],
)
def test_formul_terimlerini_ayikla_bozuk_sozdizimi_valueerror(bozuk_formul):
    with pytest.raises(ValueError):
        formul_terimlerini_ayikla(bozuk_formul)


def test_formul_degerlendir_bozuk_sozdizimi_valueerror():
    with pytest.raises(ValueError):
        formul_degerlendir("600 ++ 601", [])


@pytest.mark.parametrize(
    "gecerli_formul",
    [
        "600+601",  # boşluksuz
        "600 + 601 - 610",  # operatörlere bitişik boşluklar
        " 600 ",  # tek terim, kenar boşlukları
        "-600",  # öncü işaret
        "+ 600 + 601",  # baştaki + ile explicit
        "  +  600  +  601  -  610  ",  # eksiksiz boşluklar ama operatör çevresinde
    ],
)
def test_formul_terimlerini_ayikla_gecerli_formuller(gecerli_formul):
    """Geçerli formüllerin başarıyla ayrıştırıldığı regresyon testleri."""
    # Yalnızca parse hatasız çalıştığını test et; kesin çıktı diğer testlere bırak
    terimler = formul_terimlerini_ayikla(gecerli_formul)
    assert isinstance(terimler, list)
    assert all(isinstance(t, tuple) and len(t) == 2 for t in terimler)


def test_formul_terimlerini_ayikla_gecerli_formulu_dogru_ayirir():
    assert formul_terimlerini_ayikla("600 + 601 - 610") == [
        ("+", "600"), ("+", "601"), ("-", "610"),
    ]


def test_hesap_eslesir_ana_hesap_varsa_true():
    satir = _600_satiri("5000000.00")
    assert hesap_eslesir("600", [satir]) is True


def test_hesap_eslesir_alt_hesap_varsa_true():
    alt = MizanSatiri("600.01", "Yurtiçi A", Decimal("0"), Decimal("100.00"), Decimal("0"), Decimal("100.00"))
    assert hesap_eslesir("600", [alt]) is True


def test_hesap_eslesir_hic_eslesmiyorsa_false():
    satir = _600_satiri("5000000.00")
    assert hesap_eslesir("999", [satir]) is False


def test_konfig_yukle_bozuk_formul_fail_fast_valueerror(tmp_path):
    """Config yüklenirken formüller ön-doğrulanır: bozuk formüllü config
    ValueError ile reddedilir (kontrol çalıştırma zamanına kadar beklenmez)."""
    bozuk_yaml = tmp_path / "bozuk.yaml"
    bozuk_yaml.write_text(
        """
kontroller:
  - kod: A-BOZUK
    aciklama: "test"
    sol:
      kaynak: beyanname
      tip: KDV1
      alan: teslim_hizmet_toplam
      donem: yillik_kumulatif
    sag:
      kaynak: mizan
      formul: "600 ++ 601"
    mutabakat_kalemleri: []
    tolerans:
      mutlak: "10000.00"
      oransal: 1.0
    seviye_esikleri:
      orta: 1.0
      yuksek: 5.0
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        konfig_yukle(bozuk_yaml)


def test_konfig_yukle_gecerli_config_basarili_yuklenir():
    konfig = konfig_yukle(_KONFIG_YOLU)
    assert konfig["kontroller"][0]["kod"] == "A-KDV-HASILAT"


# --------------------------------------------------------------------------
# motor.py uçtan uca testleri (Depo üzerinden)
# --------------------------------------------------------------------------


def test_pozitif_fark_orta_seviye_bulgu_uretir(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _kdv_beyannameleri_yukle(depo, mukellef_id)
    _mizan_yukle(depo, mukellef_id, [_600_satiri("5000000.00")])

    bulgular = kontrolleri_calistir(depo, mukellef_id, 2025, _yalniz_kdv_hasilat_kontrolu(_yukle_konfig()))

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

    bulgular = kontrolleri_calistir(depo, mukellef_id, 2025, _yalniz_kdv_hasilat_kontrolu(_yukle_konfig()))

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

    konfig = _yalniz_kdv_hasilat_kontrolu(_yukle_konfig())
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

    bulgular = kontrolleri_calistir(depo, mukellef_id, 2025, _yalniz_kdv_hasilat_kontrolu(_yukle_konfig()))

    assert len(bulgular) == 1
    uyarilar = bulgular[0].detay["eksik_donem_uyarilari"]
    assert len(uyarilar) == 1
    assert "12" in uyarilar[0]


# --------------------------------------------------------------------------
# A-KDV-INDIRIM (bonus): yıllık indirilecek KDV ~ 191 hesabı BORÇ TOPLAMI
# --------------------------------------------------------------------------


def _191_satiri(borc_toplam: str, alacak_toplam: str = "0", borc_bakiye: str | None = None) -> MizanSatiri:
    """191 hesap satırı. ``borc_bakiye`` verilmezse ``borc_toplam``'a eşitlenir
    (tek satırlı basit senaryo); farklı verildiğinde borç TOPLAMI ile borç
    BAKİYESİ'nin ayrı okunduğunu test etmek için kullanılır."""
    return MizanSatiri(
        hesap_kodu="191",
        hesap_adi="İndirilecek KDV",
        borc_toplam=Decimal(borc_toplam),
        alacak_toplam=Decimal(alacak_toplam),
        borc_bakiye=Decimal(borc_bakiye if borc_bakiye is not None else borc_toplam),
        alacak_bakiye=Decimal("0"),
    )


def _kdv1_indirilecek_beyannameleri_yukle(depo, mukellef_id, yil=2025, tutarlar=None):
    """12 aylık KDV1 beyannamesi yazar, yalnızca ``indirilecek_kdv`` alanıyla
    (varsayılan kümülatif 120.000,00 -- ornek_veri/uret.py'deki 191 hesabı
    borç toplamı ile aynı)."""
    tutarlar = tutarlar or ["10000.00"] * 12
    for sira, tutar in enumerate(tutarlar, start=1):
        donem_id = depo.donem_ekle(mukellef_id, Donem(yil=yil, tip="AY", sira=sira))
        depo.beyanname_yaz(donem_id, "KDV1", {"indirilecek_kdv": tutar})


def _yalniz_kdv_indirim_kontrolu(konfig: dict) -> dict:
    konfig = dict(konfig)
    konfig["kontroller"] = [
        k for k in konfig["kontroller"] if k["kod"] == "A-KDV-INDIRIM"
    ]
    return konfig


def test_kdv_indirim_negatif_uyumlu_senaryoda_bulgu_uretilmez(depo):
    """Varsayılan/uyumlu senaryo: kümülatif indirilecek KDV (120.000,00) ==
    191 hesabı borç TOPLAMI (120.000,00) -> bulgu yok."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _kdv1_indirilecek_beyannameleri_yukle(depo, mukellef_id)  # kümülatif 120.000,00
    _mizan_yukle(depo, mukellef_id, [_191_satiri("120000.00")])

    konfig = _yalniz_kdv_indirim_kontrolu(_yukle_konfig())
    bulgular = kontrolleri_calistir(depo, mukellef_id, 2025, konfig)

    assert bulgular == []


def test_kdv_indirim_pozitif_deger_tipi_borc_toplam_uzerinden_bulgu_uretir(depo):
    """Pozitif senaryo (test-içi fixture): 191 hesabının borç BAKİYESİ
    (40.000,00) ile borç TOPLAMI (100.000,00) FARKLI -- ``sag.deger_tipi:
    borc_toplam`` doğru alanı (toplamı, bakiyeyi değil) okuduğunu kanıtlar.
    Kümülatif indirilecek KDV 120.000,00 ~ borç toplamı 100.000,00 -> fark
    20.000,00 (%20) -> mutlak (5.000) VE oransal (%1) eşiklerin ikisi de
    aşılır -> bulgu, seviye yüksek (%20 >= %5)."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _kdv1_indirilecek_beyannameleri_yukle(depo, mukellef_id)  # kümülatif 120.000,00
    _mizan_yukle(
        depo,
        mukellef_id,
        [_191_satiri(borc_toplam="100000.00", alacak_toplam="60000.00", borc_bakiye="40000.00")],
    )

    konfig = _yalniz_kdv_indirim_kontrolu(_yukle_konfig())
    bulgular = kontrolleri_calistir(depo, mukellef_id, 2025, konfig)

    assert len(bulgular) == 1
    bulgu = bulgular[0]
    assert bulgu.kontrol_kodu == "A-KDV-INDIRIM"
    # sag_tutar borç TOPLAMI (100.000,00) olmalı, borç BAKİYESİ (40.000,00) DEĞİL.
    assert bulgu.detay["sag_tutar"] == "100000.00"
    assert bulgu.tutar_fark == Decimal("20000.00")
    assert bulgu.seviye == "yuksek"


def test_formuldeki_mizanda_olmayan_hesap_detayda_eslesmeyen_hesap_olarak_gorunur(depo):
    """Sessiz sıfır katkısı: formülde geçen ama mizanda hiç eşleşmeyen bir hesap
    kodu ("999") sessizce Decimal(0) katkı yapmak yerine detay'da uyarı izi
    bırakmalı — bulgu üretimini engellemiyor, yalnızca iz düşüyor."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _kdv_beyannameleri_yukle(depo, mukellef_id)
    _mizan_yukle(depo, mukellef_id, [_600_satiri("5000000.00")])

    konfig = _yalniz_kdv_hasilat_kontrolu(_yukle_konfig())
    konfig["kontroller"][0]["sag"]["formul"] = "600 + 999"

    bulgular = kontrolleri_calistir(depo, mukellef_id, 2025, konfig)

    assert len(bulgular) == 1
    assert bulgular[0].detay["eslesmeyen_hesaplar"] == ["999"]
