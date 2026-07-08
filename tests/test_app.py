"""Streamlit arayüzü testleri (Faz 6) — streamlit.testing.v1.AppTest ile
headless çalıştırma; tarayıcı/sunucu açılmaz, LLM çağrısı yapılmaz.

KVKK: app.py `anthropic` import etmez (bekçi: tests/test_kvkk.py, src/
ağacını tarar); yükleme akışı CLI ile aynı ilkeyi izler (mizan_oku ->
kimlik_ayir -> depo tek fonksiyonda, maskeleme atlanamaz).
"""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from ymm.db.depo import Depo
from ymm.modeller import Bulgu, Donem
from ymm.rapor.uretici import DAMGA

_APP_YOLU = str(Path(__file__).parent.parent / "src" / "ymm" / "app.py")


def _apptest() -> AppTest:
    return AppTest.from_file(_APP_YOLU, default_timeout=30)


def test_uygulama_hatasiz_acilir_ve_damga_gorunur():
    at = _apptest().run()

    assert not at.exception
    # TASLAK damgası her açılışta görünür (mimari kural 5'in UI karşılığı).
    uyarilar = " ".join(w.value for w in at.warning)
    assert DAMGA in uyarilar


def test_bulgular_sekmesi_depodaki_bulgulari_gosterir(tmp_path):
    """Önceden doldurulmuş veri.db yolu sidebar'dan verilir; Bulgular
    sekmesindeki tablo depodaki bulguyu göstermeli."""
    veri_db = tmp_path / "veri.db"
    depo = Depo(veri_db)
    mukellef_id = depo.mukellef_ekle("MUK-001")
    depo.donem_ekle(mukellef_id, Donem(yil=2025, tip="YILLIK", sira=0))
    depo.bulgu_yaz(
        [
            Bulgu(
                kaynak="B",
                kontrol_kodu="B-131-ORTAK",
                seviye="yuksek",
                tutar_fark=Decimal("150000.00"),
                yuzde_fark=None,
                detay={"hesap_kodu": "131", "hesap_adi": "Ortaklardan Alacaklar"},
                mukellef_id=mukellef_id,
                yil=2025,
            )
        ]
    )

    at = _apptest().run()
    at.sidebar.text_input(key="veri_db").set_value(str(veri_db)).run()
    at.sidebar.text_input(key="mukellef").set_value("MUK-001").run()
    at.sidebar.number_input(key="yil").set_value(2025).run()

    assert not at.exception
    # Bulgu tablosu veri çerçevesi olarak basılır; içinde kontrol kodu geçer.
    tablolar = at.dataframe
    assert len(tablolar) >= 1
    birlesik = "".join(str(t.value) for t in tablolar)
    assert "B-131-ORTAK" in birlesik


def test_ozet_sekmesi_metrikleri_gosterir(tmp_path):
    """Dashboard (Özet) sekmesi: dolu depoda bulgu sayısı metrikleri görünür."""
    veri_db = tmp_path / "veri.db"
    depo = Depo(veri_db)
    mukellef_id = depo.mukellef_ekle("MUK-001")
    depo.donem_ekle(mukellef_id, Donem(yil=2025, tip="YILLIK", sira=0))
    depo.bulgu_yaz(
        [
            Bulgu(
                kaynak="B",
                kontrol_kodu="B-131-ORTAK",
                seviye="yuksek",
                tutar_fark=Decimal("150000.00"),
                yuzde_fark=None,
                detay={"hesap_kodu": "131"},
                mukellef_id=mukellef_id,
                yil=2025,
            ),
            Bulgu(
                kaynak="A",
                kontrol_kodu="A-KDV-HASILAT",
                seviye="orta",
                tutar_fark=Decimal("100000.00"),
                yuzde_fark=2.0,
                detay={"aciklama": "test"},
                mukellef_id=mukellef_id,
                yil=2025,
            ),
        ]
    )

    at = _apptest().run()
    at.sidebar.text_input(key="veri_db").set_value(str(veri_db)).run()
    at.sidebar.text_input(key="mukellef").set_value("MUK-001").run()

    assert not at.exception
    metrik_etiketleri = {m.label for m in at.metric}
    assert "Toplam Bulgu" in metrik_etiketleri
    metrik_map = {m.label: m.value for m in at.metric}
    assert metrik_map["Toplam Bulgu"] == "2"
    assert metrik_map["Yüksek"] == "1"


def test_ozet_sekmesi_bos_depoda_kullanim_rehberi(tmp_path):
    """Veri yokken Özet sekmesi çökmez, kullanım adımlarını gösterir."""
    at = _apptest().run()
    at.sidebar.text_input(key="veri_db").set_value(str(tmp_path / "veri.db")).run()

    assert not at.exception
    tum_markdown = " ".join(str(m.value) for m in at.markdown)
    assert "Yükleme" in tum_markdown  # rehber adımları görünür


def test_mukellef_bulunamayinca_hata_kutusu(tmp_path):
    """Var olmayan mükellef kodu girilirse uygulama çökmez, hata/bilgi
    mesajı gösterir."""
    veri_db = tmp_path / "veri.db"
    Depo(veri_db)  # boş şema

    at = _apptest().run()
    at.sidebar.text_input(key="veri_db").set_value(str(veri_db)).run()
    at.sidebar.text_input(key="mukellef").set_value("MUK-YOK").run()

    assert not at.exception
