"""Kontrol motoru (MODÜL A): YAML kural konfigürasyonunu okur, kontrolleri
çalıştırır ve Bulgu listesi üretir.

Tamamen yerel/deterministik: LLM çağrısı, ağ erişimi yok. Tüm tutarlar Decimal.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from ymm.db.depo import Depo
from ymm.kontrol.donem import yillik_kumulatif
from ymm.kontrol.kurallar import (
    formul_degerlendir,
    formul_terimlerini_ayikla,
    hesap_eslesir,
    karsilastir,
)
from ymm.modeller import Bulgu, MizanSatiri

_logger = logging.getLogger(__name__)


def _mizan_satirlari_yil_icin(depo: Depo, mukellef_id: int, yil: int) -> list[MizanSatiri]:
    """Mükellefin ilgili yıla ait YILLIK dönem mizanını okur.

    Katman ayrımı: tüm SQL erişimi ``Depo`` üzerinden — bu fonksiyon yalnızca
    ``Depo.donem_bul`` + ``Depo.mizan_oku`` public metodlarını çağırır,
    ``depo.baglanti``'ya doğrudan erişim ya da motor.py'de ham SQL YOKTUR.
    """
    donem_id = depo.donem_bul(mukellef_id, yil, "YILLIK")
    if donem_id is None:
        return []
    return depo.mizan_oku(donem_id)


def _beyanname_kayitlari_donemli(
    depo: Depo, mukellef_id: int, yil: int, tip: str
) -> list[dict]:
    """``yillik_kumulatif`` biçimine (``{"donem_tip","sira","alanlar"}``) uygun
    beyanname kayıtları döner — ``Depo.beyanname_oku_donemli`` public metodu
    üzerinden (bkz. yukarıdaki katman ayrımı notu)."""
    return depo.beyanname_oku_donemli(mukellef_id, tip, yil)


def _kontrol_formulleri(kontrol: dict) -> list[str]:
    """Bir kontrol kaydındaki tüm formülleri (sağ taraf + mutabakat kalemleri)
    tek listede döner — hem ön-doğrulama hem eşleşmeyen-hesap taraması için."""
    formuller = [kontrol["sag"]["formul"]]
    formuller.extend(kalem["formul"] for kalem in kontrol.get("mutabakat_kalemleri") or [])
    return formuller


def _formulleri_dogrula(konfig: dict) -> None:
    """``konfig["kontroller"]`` içindeki TÜM formülleri ayrıştırmayı dener
    (fail fast). Bozuk sözdizimli bir formül varsa ``formul_terimlerini_ayikla``
    ``ValueError`` fırlatır; bu, config yükleme anında (kontrol çalıştırma
    zamanını beklemeden) reddedilir."""
    for kontrol in konfig.get("kontroller", []):
        for formul in _kontrol_formulleri(kontrol):
            formul_terimlerini_ayikla(formul)


def konfig_yukle(yol: str | Path) -> dict:
    """``config/kontrol_kurallari.yaml`` (veya eşdeğer) dosyasını okur ve
    yükleme anında tüm formülleri ön-doğrular.

    Bozuk formüllü bir config, ilk kontrol çalıştırıldığında değil, burada
    (açılışta) ``ValueError`` ile reddedilir — "sıfır hata payı" katmanı için
    fail-fast garantisi.
    """
    konfig = yaml.safe_load(Path(yol).read_text(encoding="utf-8"))
    _formulleri_dogrula(konfig)
    return konfig


def _eslesmeyen_hesaplari_bul(
    kontrol: dict, mizan_satirlari: list[MizanSatiri]
) -> list[str]:
    """Kontroldeki formüllerde geçen ama mizanda hiçbir satırla eşleşmeyen
    hesap kodlarını (sırayı koruyarak, tekrarsız) döner.

    Sessiz sıfır katkısının uyarı izi: ``hesap_degeri`` eşleşme yoksa da
    sessizce ``Decimal(0)`` döndüğü için (bilinmeyen/yanlış yazılmış hesap
    kodu formülü sonuçsuz etkiler), bu bulguya dönüşmese bile ayrı bir iz
    olarak taşınır.
    """
    eslesmeyenler: list[str] = []
    for formul in _kontrol_formulleri(kontrol):
        for _isaret, terim in formul_terimlerini_ayikla(formul):
            if not hesap_eslesir(terim, mizan_satirlari) and terim not in eslesmeyenler:
                eslesmeyenler.append(terim)
    return eslesmeyenler


def kontrolleri_calistir(
    depo: Depo, mukellef_id: int, yil: int, konfig: dict
) -> list[Bulgu]:
    """``konfig["kontroller"]`` listesindeki (config/kontrol_kurallari.yaml
    şeması) her kontrolü çalıştırır ve tolerans dışı kalanlar için Bulgu üretir.
    """
    bulgular: list[Bulgu] = []
    mizan_satirlari = _mizan_satirlari_yil_icin(depo, mukellef_id, yil)

    for kontrol in konfig.get("kontroller", []):
        sol = kontrol["sol"]
        sag = kontrol["sag"]

        kayitlar = _beyanname_kayitlari_donemli(depo, mukellef_id, yil, sol["tip"])
        sol_tutar, eksik_uyarilari = yillik_kumulatif(kayitlar, sol["alan"])

        sag_tutar = formul_degerlendir(sag["formul"], mizan_satirlari)
        for kalem in kontrol.get("mutabakat_kalemleri") or []:
            sag_tutar += formul_degerlendir(kalem["formul"], mizan_satirlari)

        eslesmeyen_hesaplar = _eslesmeyen_hesaplari_bul(kontrol, mizan_satirlari)
        if eslesmeyen_hesaplar:
            # Bulguya dönüşmese bile uyarı izi kalsın (sessiz sıfır katkısı).
            _logger.warning(
                "Kontrol %s: formülde mizanda eşleşmeyen hesap kodu/kodları var: %s",
                kontrol["kod"],
                eslesmeyen_hesaplar,
            )

        sonuc = karsilastir(
            sol_tutar, sag_tutar, kontrol["tolerans"], kontrol["seviye_esikleri"]
        )
        if sonuc is None:
            continue

        tutar_fark, yuzde_fark, seviye = sonuc
        detay = {
            "sol_tutar": str(sol_tutar),
            "sag_tutar": str(sag_tutar),
            "formul": sag["formul"],
            "aciklama": kontrol.get("aciklama", ""),
            "eksik_donem_uyarilari": eksik_uyarilari,
            "eslesmeyen_hesaplar": eslesmeyen_hesaplar,
        }
        bulgular.append(
            Bulgu(
                kaynak="A",
                kontrol_kodu=kontrol["kod"],
                seviye=seviye,
                tutar_fark=tutar_fark,
                yuzde_fark=yuzde_fark,
                detay=detay,
                mukellef_id=mukellef_id,
                yil=yil,
            )
        )

    return bulgular
