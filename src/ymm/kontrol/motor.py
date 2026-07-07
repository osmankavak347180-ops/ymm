"""Kontrol motoru (MODÜL A): YAML kural konfigürasyonunu okur, kontrolleri
çalıştırır ve Bulgu listesi üretir.

Tamamen yerel/deterministik: LLM çağrısı, ağ erişimi yok. Tüm tutarlar Decimal.
"""

from __future__ import annotations

import logging
from decimal import Decimal
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
    tek listede döner — hem ön-doğrulama hem eşleşmeyen-hesap taraması için.

    Task 1.3: ``sag.kaynak == "beyanname"`` olan kontrollerde sağ tarafın
    formülü YOKTUR (mizan formülü değil, doğrudan beyanname alanı okunur) —
    bu durumda yalnızca mutabakat kalemi formülleri (varsa) taranır.
    """
    formuller: list[str] = []
    if "formul" in kontrol["sag"]:
        formuller.append(kontrol["sag"]["formul"])
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


def _tek_donem_kaydi_degeri(
    kayitlar: list[dict], alan: str, donem_tip: str, sira: int
) -> tuple[Decimal, list[str]]:
    """``kayitlar`` içinden yalnız ``(donem_tip, sira)`` eşleşen TEK kaydın
    ``alanlar[alan]`` değerini döner — KÜMÜLATİF TOPLAMA YAPMAZ (bkz.
    ``yillik_kumulatif`` ile farkı: A-GECICI-KV'de yalnız 4. dönem/son çeyrek
    kaydı gerekir, 4 çeyreğin toplamı değil).

    Eşleşen kayıt yoksa ``(Decimal("0"), [uyarı])`` döner — ``yillik_kumulatif``
    ile aynı "akış kesilmez" ilkesi: eksik kayıt exception değil, uyarıdır.
    """
    eslesenler = [
        k for k in kayitlar if k["donem_tip"] == donem_tip and k["sira"] == sira
    ]
    if not eslesenler:
        return Decimal("0"), [
            f"Eksik dönem: {donem_tip} sıra {sira} kaydı bulunamadı."
        ]
    return Decimal(eslesenler[-1]["alanlar"][alan]), []


def _sol_tutar_hesapla(
    depo: Depo, mukellef_id: int, yil: int, sol: dict
) -> tuple[Decimal, list[str]]:
    """Kontrolün sol (beyanname) tarafını ``sol["donem"]`` seçimine göre
    hesaplar. Varsayılan ("yillik_kumulatif" ya da alan belirtilmemişse)
    Task 1.2'deki davranışla birebir aynıdır — geriye dönük uyumlu.

    Task 1.3 eklentisi: ``"son_ceyrek"`` — GECICI beyannamesinden yalnız 4.
    dönem (sira=4) kaydını alır, KÜMÜLATİF TOPLAMAZ (bkz. A-GECICI-KV).
    """
    kayitlar = _beyanname_kayitlari_donemli(depo, mukellef_id, yil, sol["tip"])
    donem_secimi = sol.get("donem", "yillik_kumulatif")

    if donem_secimi == "yillik_kumulatif":
        return yillik_kumulatif(kayitlar, sol["alan"])
    if donem_secimi == "son_ceyrek":
        return _tek_donem_kaydi_degeri(kayitlar, sol["alan"], donem_tip="CEYREK", sira=4)
    raise ValueError(f"Bilinmeyen sol.donem değeri: {donem_secimi!r}")


def _sag_tutar_beyanname(
    depo: Depo, mukellef_id: int, yil: int, sag: dict
) -> tuple[Decimal, list[str]]:
    """Kontrolün sağ tarafı bir BEYANNAME ise (``sag.kaynak == "beyanname"``,
    Task 1.3 — ör. A-GECICI-KV'de KV beyannamesi) ``sag["tip"]``/``sag["alan"]``
    üzerinden ``yillik_kumulatif`` ile okur. Tek kayıtlı (YILLIK, sira=0) bir
    beyanname tipi için de doğru çalışır — kümülatif toplam tek kaydın kendisi
    olur.
    """
    kayitlar = _beyanname_kayitlari_donemli(depo, mukellef_id, yil, sag["tip"])
    return yillik_kumulatif(kayitlar, sag["alan"])


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

        sol_tutar, sol_uyarilari = _sol_tutar_hesapla(depo, mukellef_id, yil, sol)

        if sag.get("kaynak", "mizan") == "beyanname":
            # Task 1.3: sağ taraf da bir beyanname olabilir (ör. A-GECICI-KV
            # için KV beyannamesi) — mizan formülü/mutabakat kalemi kavramı
            # bu durumda yok.
            sag_tutar, sag_uyarilari = _sag_tutar_beyanname(depo, mukellef_id, yil, sag)
            formul_metni = None
        else:
            deger_tipi = sag.get("deger_tipi", "bakiye")
            sag_tutar = formul_degerlendir(sag["formul"], mizan_satirlari, deger_tipi)
            for kalem in kontrol.get("mutabakat_kalemleri") or []:
                sag_tutar += formul_degerlendir(kalem["formul"], mizan_satirlari, deger_tipi)
            sag_uyarilari = []
            formul_metni = sag["formul"]

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
            "formul": formul_metni,
            "aciklama": kontrol.get("aciklama", ""),
            "eksik_donem_uyarilari": sol_uyarilari + sag_uyarilari,
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
