"""LLM geçidi testleri (Task 4.1).

KVKK: bu testlerde GERÇEK API ÇAĞRISI YOKTUR — anthropic istemcisi
mock'lanır (`sahte_istemci` fixture'ı `gateway._istemci_olustur`'u değiştirir).
Gateway'in sözleşmesi:
- Her istekte (istem + sistem) `sizinti_tara` çalışır; bulgu varsa
  `MaskeIhlali` fırlatılır ve API HİÇ ÇAĞRILMAZ, diske log YAZILMAZ.
- Temiz istekte yanıt döner ve `output/llm_log/` altına istek+yanıt JSON'u
  yazılır (denetim izi).
- `ANTHROPIC_API_KEY` yoksa açıklayıcı hata.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ymm.llm.gateway import uret
from ymm.llm.istemler import RAPOR_SISTEM_ISTEMI, redaksiyon_istemi
from ymm.maskeleme.dogrulayici import MaskeIhlali

_KAYITLI_VKN = "1234567890"
_KAYITLI_AD = "Işık İnşaat A.Ş."


def _kimlik_db_olustur(yol: Path) -> Path:
    baglanti = sqlite3.connect(yol)
    baglanti.execute(
        "CREATE TABLE kimlik (takma_kod TEXT, tip TEXT, gercek_ad TEXT, vkn_tckn TEXT)"
    )
    baglanti.execute(
        "INSERT INTO kimlik VALUES ('MUK-001', 'FIRMA', ?, ?)",
        (_KAYITLI_AD, _KAYITLI_VKN),
    )
    baglanti.commit()
    baglanti.close()
    return yol


@pytest.fixture
def kimlik_db(tmp_path):
    return _kimlik_db_olustur(tmp_path / "kimlik.db")


@pytest.fixture
def calisma_dizini(tmp_path, monkeypatch):
    """`output/llm_log/` göreli yol olduğundan testler tmp_path'te çalışır —
    repo ağacına log dosyası sızmaz."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def sahte_istemci(monkeypatch):
    """Gateway'in kurduğu anthropic istemcisini mock'lar; `messages.create`
    mock'unu döner (çağrı sayısı/argümanları buradan denetlenir)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anahtar")
    yanit = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="REDAKTE EDILMIS METIN")],
        model="claude-sonnet-5",
    )
    mock_create = MagicMock(return_value=yanit)
    sahte = SimpleNamespace(messages=SimpleNamespace(create=mock_create))
    monkeypatch.setattr("ymm.llm.gateway._istemci_olustur", lambda: sahte)
    return mock_create


# --- sızıntı taraması (KVKK kapısı) ------------------------------------------


def test_istemde_kayitli_vkn_maskeihlali_ve_api_cagrilmaz(
    kimlik_db, sahte_istemci, calisma_dizini
):
    istem = f"Mükellefin VKN'si {_KAYITLI_VKN} olan dönem bulguları..."

    with pytest.raises(MaskeIhlali):
        uret(istem, "Sistem istemi.", kimlik_db)

    sahte_istemci.assert_not_called()
    # İhlalli istem diske de yazılmamalı (log dosyası kimlik sızdırırdı).
    assert not (calisma_dizini / "output").exists()


def test_istemde_kayitli_gercek_ad_yakalanir(kimlik_db, sahte_istemci, calisma_dizini):
    """kimlik.db'deki gerçek ad, Türkçe büyük/küçük farkıyla bile yakalanmalı
    (dogrulayici._tr_fold katmanı)."""
    istem = "IŞIK İNŞAAT A.Ş. hesabında yüksek bakiye tespit edildi."

    with pytest.raises(MaskeIhlali):
        uret(istem, "Sistem istemi.", kimlik_db)

    sahte_istemci.assert_not_called()


def test_sistem_istemi_de_taranir(kimlik_db, sahte_istemci, calisma_dizini):
    """Sızıntı taraması yalnız kullanıcı istemini değil sistem istemini de
    kapsamalı — her iki alan da API'ye gider."""
    with pytest.raises(MaskeIhlali):
        uret("Temiz istem.", f"Sistem: {_KAYITLI_VKN}", kimlik_db)

    sahte_istemci.assert_not_called()


# --- temiz istek akışı --------------------------------------------------------


def test_temiz_istem_mock_yanitini_doner(kimlik_db, sahte_istemci, calisma_dizini):
    sonuc = uret("Bulgu paragraflarını redakte et: [MUK-001] dönemi.", "Sistem.", kimlik_db)

    assert sonuc == "REDAKTE EDILMIS METIN"
    sahte_istemci.assert_called_once()
    kwargs = sahte_istemci.call_args.kwargs
    assert kwargs["model"] == "claude-sonnet-5"
    assert kwargs["system"] == "Sistem."
    assert kwargs["messages"][0]["content"] == "Bulgu paragraflarını redakte et: [MUK-001] dönemi."


def test_temiz_istem_denetim_izi_json_yazar(kimlik_db, sahte_istemci, calisma_dizini):
    uret("Temiz istem metni.", "Sistem istemi.", kimlik_db)

    log_dosyalari = list((calisma_dizini / "output" / "llm_log").glob("*.json"))
    assert len(log_dosyalari) == 1

    kayit = json.loads(log_dosyalari[0].read_text(encoding="utf-8"))
    assert kayit["istem"] == "Temiz istem metni."
    assert kayit["sistem"] == "Sistem istemi."
    assert kayit["yanit"] == "REDAKTE EDILMIS METIN"
    assert kayit["model"] == "claude-sonnet-5"


def test_ardisik_cagrilar_ayri_log_dosyalari(kimlik_db, sahte_istemci, calisma_dizini):
    uret("Birinci istem.", "Sistem.", kimlik_db)
    uret("İkinci istem.", "Sistem.", kimlik_db)

    log_dosyalari = list((calisma_dizini / "output" / "llm_log").glob("*.json"))
    assert len(log_dosyalari) == 2


# --- API anahtarı -------------------------------------------------------------


def test_api_anahtari_yoksa_aciklayici_hata(kimlik_db, calisma_dizini, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(RuntimeError) as hata:
        uret("Temiz istem.", "Sistem.", kimlik_db)

    assert "ANTHROPIC_API_KEY" in str(hata.value)


# --- istemler.py ---------------------------------------------------------------


def test_redaksiyon_istemi_paragraflari_icerir():
    paragraflar = ["Birinci bulgu paragrafı.", "İkinci bulgu paragrafı."]

    istem = redaksiyon_istemi(paragraflar)

    assert "Birinci bulgu paragrafı." in istem
    assert "İkinci bulgu paragrafı." in istem


def test_rapor_sistem_istemi_takma_kod_koruma_talimati_icerir():
    """Sistem istemi, [MUK-001]/[KISI-001] takma kod token'larının AYNEN
    korunmasını talimatlamalı — geri-yerleştirme adımı bunlara bağlı."""
    assert "takma kod" in RAPOR_SISTEM_ISTEMI.lower()
    assert "TASLAK" in RAPOR_SISTEM_ISTEMI
