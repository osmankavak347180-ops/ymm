"""Depo (veri.db repository) testleri."""

from decimal import Decimal

import pytest

from ymm.db.depo import Depo
from ymm.modeller import Bulgu, Donem, MizanSatiri


@pytest.fixture
def depo(tmp_path):
    return Depo(tmp_path / "veri.db")


def test_mizan_yaz_oku_decimal_round_trip(depo):
    """Decimal tutarlar string olarak saklanır ama Decimal("1234.56") olarak aynen döner."""
    mukellef_id = depo.mukellef_ekle("MUK-001")
    donem_id = depo.donem_ekle(mukellef_id, Donem(yil=2025, tip="YILLIK", sira=0))

    satir = MizanSatiri(
        hesap_kodu="770",
        hesap_adi="Genel Yönetim Giderleri",
        borc_toplam=Decimal("1234.56"),
        alacak_toplam=Decimal("0.00"),
        borc_bakiye=Decimal("1234.56"),
        alacak_bakiye=Decimal("0.00"),
    )
    depo.mizan_yaz(donem_id, [satir])

    okunan = depo.mizan_oku(donem_id)

    assert len(okunan) == 1
    assert okunan[0] == satir
    assert okunan[0].borc_toplam == Decimal("1234.56")
    assert isinstance(okunan[0].borc_toplam, Decimal)


def test_mukellef_ekle_farkli_takma_kodlar_farkli_id_doner(depo):
    id1 = depo.mukellef_ekle("MUK-001")
    id2 = depo.mukellef_ekle("MUK-002")
    assert id1 != id2


def test_beyanname_yaz_oku_round_trip(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    donem_id = depo.donem_ekle(mukellef_id, Donem(yil=2025, tip="AY", sira=3))

    alanlar = {"matrah": "1250000.00", "hesaplanan_kdv": "225000.00"}
    depo.beyanname_yaz(donem_id, "KDV1", alanlar)

    okunan = depo.beyanname_oku(mukellef_id, "KDV1", 2025)

    assert okunan == [alanlar]


def test_beyanname_oku_bos_donerse_liste_bos(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    assert depo.beyanname_oku(mukellef_id, "KDV1", 2025) == []


def test_bulgu_yaz_bulgular_round_trip(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")

    bulgu = Bulgu(
        kaynak="A",
        kontrol_kodu="A-KDV-HASILAT",
        seviye="orta",
        tutar_fark=Decimal("100000.00"),
        yuzde_fark=2.0,
        detay={"beyan_kumulatif": "4900000.00", "mizan_hesaplanan": "5000000.00"},
        mukellef_id=mukellef_id,
        yil=2025,
    )
    depo.bulgu_yaz([bulgu])

    okunan = depo.bulgular(mukellef_id, 2025)

    assert okunan == [bulgu]
    assert isinstance(okunan[0].tutar_fark, Decimal)


def test_bulgu_yaz_tutar_fark_none_destekler(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")

    bulgu = Bulgu(
        kaynak="B",
        kontrol_kodu="B-131-ORTAK",
        seviye="yuksek",
        tutar_fark=None,
        yuzde_fark=None,
        detay={"hesap": "131.01"},
        mukellef_id=mukellef_id,
        yil=2025,
    )
    depo.bulgu_yaz([bulgu])

    okunan = depo.bulgular(mukellef_id, 2025)

    assert okunan == [bulgu]
    assert okunan[0].tutar_fark is None


def test_bulgular_yil_ile_filtrelenir(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    depo.bulgu_yaz(
        [
            Bulgu(
                kaynak="A",
                kontrol_kodu="A-X",
                seviye="dusuk",
                tutar_fark=None,
                yuzde_fark=None,
                detay={},
                mukellef_id=mukellef_id,
                yil=2024,
            )
        ]
    )

    assert depo.bulgular(mukellef_id, 2025) == []


def test_beyanname_yaz_decimal_detay(depo):
    """Beyanname'nin alanlar dict'inde Decimal varsa, json.dumps başarısız olmamalı.

    TDD: Decimal("1.50") string "1.50" olarak saklanır ve geri döner.
    """
    mukellef_id = depo.mukellef_ekle("MUK-001")
    donem_id = depo.donem_ekle(mukellef_id, Donem(yil=2025, tip="AY", sira=3))

    # Decimal içeren alanlar dict'i
    alanlar = {"matrah": Decimal("1.50"), "kdv": Decimal("0.27")}
    depo.beyanname_yaz(donem_id, "KDV1", alanlar)

    okunan = depo.beyanname_oku(mukellef_id, "KDV1", 2025)

    # Decimal'ler string olarak saklanır ve döner
    assert okunan == [{"matrah": "1.50", "kdv": "0.27"}]
    assert isinstance(okunan[0]["matrah"], str)


def test_donem_bul_var_olan_donemin_id_sini_doner(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    donem_id = depo.donem_ekle(mukellef_id, Donem(yil=2025, tip="YILLIK", sira=0))

    assert depo.donem_bul(mukellef_id, 2025, "YILLIK") == donem_id


def test_donem_bul_yoksa_none_doner(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")

    assert depo.donem_bul(mukellef_id, 2025, "YILLIK") is None


def test_donem_bul_tip_ve_yil_ayirt_eder(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    depo.donem_ekle(mukellef_id, Donem(yil=2024, tip="YILLIK", sira=0))
    donem_2025 = depo.donem_ekle(mukellef_id, Donem(yil=2025, tip="YILLIK", sira=0))
    depo.donem_ekle(mukellef_id, Donem(yil=2025, tip="AY", sira=1))

    assert depo.donem_bul(mukellef_id, 2025, "YILLIK") == donem_2025


def test_beyanname_oku_donemli_donem_tip_ve_sira_ile_doner(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    donem_id_2 = depo.donem_ekle(mukellef_id, Donem(yil=2025, tip="AY", sira=2))
    donem_id_1 = depo.donem_ekle(mukellef_id, Donem(yil=2025, tip="AY", sira=1))

    depo.beyanname_yaz(donem_id_2, "KDV1", {"teslim_hizmet_toplam": "200.00"})
    depo.beyanname_yaz(donem_id_1, "KDV1", {"teslim_hizmet_toplam": "100.00"})

    kayitlar = depo.beyanname_oku_donemli(mukellef_id, "KDV1", 2025)

    assert kayitlar == [
        {"donem_tip": "AY", "sira": 1, "alanlar": {"teslim_hizmet_toplam": "100.00"}},
        {"donem_tip": "AY", "sira": 2, "alanlar": {"teslim_hizmet_toplam": "200.00"}},
    ]


def test_beyanname_oku_donemli_bos_donerse_liste_bos(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    assert depo.beyanname_oku_donemli(mukellef_id, "KDV1", 2025) == []


def test_mukellef_bul_var_olan_id_yi_doner(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")

    assert depo.mukellef_bul("MUK-001") == mukellef_id


def test_mukellef_bul_yoksa_none_doner(depo):
    assert depo.mukellef_bul("MUK-999") is None


def test_mizan_sil_donemin_tum_satirlarini_siler(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    donem_id = depo.donem_ekle(mukellef_id, Donem(yil=2025, tip="YILLIK", sira=0))
    satir = MizanSatiri(
        hesap_kodu="770",
        hesap_adi="Genel Yönetim Giderleri",
        borc_toplam=Decimal("100.00"),
        alacak_toplam=Decimal("0.00"),
        borc_bakiye=Decimal("100.00"),
        alacak_bakiye=Decimal("0.00"),
    )
    depo.mizan_yaz(donem_id, [satir])
    assert len(depo.mizan_oku(donem_id)) == 1

    depo.mizan_sil(donem_id)

    assert depo.mizan_oku(donem_id) == []


def test_mizan_sil_baska_donemin_satirlarina_dokunmaz(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    donem_id_1 = depo.donem_ekle(mukellef_id, Donem(yil=2025, tip="YILLIK", sira=0))
    donem_id_2 = depo.donem_ekle(mukellef_id, Donem(yil=2024, tip="YILLIK", sira=0))
    satir = MizanSatiri(
        hesap_kodu="770",
        hesap_adi="Genel Yönetim Giderleri",
        borc_toplam=Decimal("100.00"),
        alacak_toplam=Decimal("0.00"),
        borc_bakiye=Decimal("100.00"),
        alacak_bakiye=Decimal("0.00"),
    )
    depo.mizan_yaz(donem_id_1, [satir])
    depo.mizan_yaz(donem_id_2, [satir])

    depo.mizan_sil(donem_id_1)

    assert depo.mizan_oku(donem_id_1) == []
    assert len(depo.mizan_oku(donem_id_2)) == 1


def test_bulgu_yaz_decimal_detay(depo):
    """Bulgu'nun detay dict'inde Decimal varsa, json.dumps başarısız olmamalı.

    TDD: detay{"fark": Decimal("100000.00")} string "100000.00" olarak saklanır.
    """
    mukellef_id = depo.mukellef_ekle("MUK-001")

    bulgu = Bulgu(
        kaynak="A",
        kontrol_kodu="A-TEST",
        seviye="orta",
        tutar_fark=Decimal("50000.00"),
        yuzde_fark=1.5,
        detay={"fark": Decimal("100000.00"), "matrah": Decimal("1234567.89")},
        mukellef_id=mukellef_id,
        yil=2025,
    )
    depo.bulgu_yaz([bulgu])

    okunan = depo.bulgular(mukellef_id, 2025)

    assert len(okunan) == 1
    # detay'daki Decimal'ler string olarak döner
    assert okunan[0].detay["fark"] == "100000.00"
    assert okunan[0].detay["matrah"] == "1234567.89"
    assert isinstance(okunan[0].detay["fark"], str)
