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
