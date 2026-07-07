"""Uçtan uca entegrasyon testi: DEĞİŞTİRİLMEMİŞ `config/kontrol_kurallari.yaml`
+ gerçek `ornek_veri/beyanname_ozet.json` + `ornek_veri/uret.py` MİZAN_SATIRLARI
ile 4 kontrolün (A-KDV-HASILAT, A-MUHSGK-UCRET, A-GECICI-KV, A-KDV-INDIRIM)
birlikte doğru çalıştığını kanıtlar (bkz. .superpowers/sdd/task-1.3-brief.md).

`uret.py`'ye DOKUNULMADI — yalnızca ANKOR değerleri (191 borç toplamı vb.)
okunuyor (bkz. test_mizan_parser.py'deki importlib deseni).
"""

from __future__ import annotations

import importlib.util
import json
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from ymm.db.depo import Depo
from ymm.kontrol.motor import konfig_yukle, kontrolleri_calistir
from ymm.modeller import Donem, MizanSatiri

_PROJE_KOKU = Path(__file__).parent.parent
_KONFIG_YOLU = _PROJE_KOKU / "config" / "kontrol_kurallari.yaml"
_ORNEK_VERI_YOLU = _PROJE_KOKU / "ornek_veri" / "beyanname_ozet.json"


def _uret_modulunu_import_et():
    """ornek_veri/uret.py bir paket değil; importlib ile dosyadan yükle."""
    uret_yolu = _PROJE_KOKU / "ornek_veri" / "uret.py"
    spec = importlib.util.spec_from_file_location("ornek_veri_uret_t13", uret_yolu)
    uret_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(uret_mod)
    return uret_mod


@pytest.fixture
def depo(tmp_path):
    return Depo(tmp_path / "veri.db")


def _mizan_satirlarini_yukle() -> list[MizanSatiri]:
    """uret.py'deki MIZAN_SATIRLARI sabitini MizanSatiri listesine çevirir
    (uret.py DEĞİŞTİRİLMEDİ — yalnızca okunuyor)."""
    uret_mod = _uret_modulunu_import_et()
    return [
        MizanSatiri(
            hesap_kodu=kod,
            hesap_adi=ad,
            borc_toplam=borc_toplam,
            alacak_toplam=alacak_toplam,
            borc_bakiye=borc_bakiye,
            alacak_bakiye=alacak_bakiye,
        )
        for kod, ad, borc_toplam, alacak_toplam, borc_bakiye, alacak_bakiye in uret_mod.MIZAN_SATIRLARI
    ]


def _gercek_veriyi_depoya_yukle(depo: Depo, mukellef_id: int, yil: int = 2025) -> None:
    """Beyannameleri + mizanı depoya yazar.

    Dikkat: KV beyannamesi de mizan da aynı (mukellef_id, yil, "YILLIK", sira=0)
    dönem üçlüsüne aittir (bkz. ``docs/01-MIMARI.md`` §3 — ``donem`` bir mükellef
    için (yil, tip, sira) başına TEK satırdır). Bu yüzden KV kaydı için
    oluşturulan dönem id'si mizan için de TEKRAR KULLANILIR — ayrı bir YILLIK
    dönem satırı açılırsa ``Depo.donem_bul`` (ilk eşleşeni döner) hangi id'yi
    seçtiğine bağlı olarak mizanı veya KV'yi "görünmez" kılabilir.
    """
    veri = json.loads(_ORNEK_VERI_YOLU.read_text(encoding="utf-8"))
    yillik_donem_id: int | None = None
    for kayit in veri["beyannameler"]:
        assert kayit["yil"] == yil
        if kayit["donem_tip"] == "YILLIK" and kayit["sira"] == 0:
            if yillik_donem_id is None:
                yillik_donem_id = depo.donem_ekle(
                    mukellef_id, Donem(yil=yil, tip="YILLIK", sira=0)
                )
            donem_id = yillik_donem_id
        else:
            donem_id = depo.donem_ekle(
                mukellef_id, Donem(yil=yil, tip=kayit["donem_tip"], sira=kayit["sira"])
            )
        depo.beyanname_yaz(donem_id, kayit["tip"], kayit["alanlar"])

    if yillik_donem_id is None:
        yillik_donem_id = depo.donem_ekle(mukellef_id, Donem(yil=yil, tip="YILLIK", sira=0))
    depo.mizan_yaz(yillik_donem_id, _mizan_satirlarini_yukle())


def test_gercek_veriyle_degistirilmemis_config_dort_kontrolu_dogru_hesaplar(depo):
    mukellef_id = depo.mukellef_ekle("MUK-001")
    _gercek_veriyi_depoya_yukle(depo, mukellef_id)

    konfig = konfig_yukle(_KONFIG_YOLU)  # fail-fast doğrulamalı gerçek config
    bulgular = kontrolleri_calistir(depo, mukellef_id, 2025, konfig)

    bulgu_map = {b.kontrol_kodu: b for b in bulgular}

    # A-KDV-HASILAT: KDV kümülatif 4.900.000 ~ mizan 600 = 5.000.000 -> orta.
    assert bulgu_map["A-KDV-HASILAT"].seviye == "orta"

    # A-MUHSGK-UCRET: MUHSGK kümülatif 1.200.000 ~ mizan 770 = 800.000 -> yuksek.
    assert bulgu_map["A-MUHSGK-UCRET"].seviye == "yuksek"
    assert bulgu_map["A-MUHSGK-UCRET"].tutar_fark == Decimal("400000.00")

    # A-GECICI-KV: GECICI 4. dönem 600.000 ~ KV 605.000 -> orta.
    assert bulgu_map["A-GECICI-KV"].seviye == "orta"
    assert bulgu_map["A-GECICI-KV"].tutar_fark == Decimal("5000.00")

    # A-KDV-INDIRIM: kümülatif indirilecek KDV (120.000) == 191 borç toplamı
    # (120.000) -> UYUMLU, bulgu YOK.
    assert "A-KDV-INDIRIM" not in bulgu_map

    assert len(bulgular) == 3
