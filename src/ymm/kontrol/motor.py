"""Kontrol motoru (MODÜL A): YAML kural konfigürasyonunu okur, kontrolleri
çalıştırır ve Bulgu listesi üretir.

Tamamen yerel/deterministik: LLM çağrısı, ağ erişimi yok. Tüm tutarlar Decimal.
"""

from __future__ import annotations

import json

from ymm.db.depo import Depo
from ymm.kontrol.donem import yillik_kumulatif
from ymm.kontrol.kurallar import formul_degerlendir, karsilastir
from ymm.modeller import Bulgu, MizanSatiri


def _mizan_satirlari_yil_icin(depo: Depo, mukellef_id: int, yil: int) -> list[MizanSatiri]:
    """Mükellefin ilgili yıla ait YILLIK dönem mizanını okur.

    Not (bilinen arayüz sınırı — bkz. task-1.2-report.md "concerns"): Depo,
    (mukellef_id, yil) çiftinden ilgili donem_id'ye doğrudan erişim sağlayan
    bir metod sunmuyor; yalnızca ``mizan_oku(donem_id)`` var. Bu yüzden burada
    Depo'nun genel amaçlı, herkese açık ``baglanti`` (sqlite3 connection)
    özniteliği salt-okunur bir SELECT ile kullanılıyor. depo.py DEĞİŞTİRİLMEDİ
    (bu modülün kapsamı dışında) — yalnızca mevcut public arayüzü tüketiliyor.
    """
    satir = depo.baglanti.execute(
        "SELECT id FROM donem WHERE mukellef_id = ? AND yil = ? AND tip = 'YILLIK'",
        (mukellef_id, yil),
    ).fetchone()
    if satir is None:
        return []
    return depo.mizan_oku(satir[0])


def _beyanname_kayitlari_donemli(
    depo: Depo, mukellef_id: int, yil: int, tip: str
) -> list[dict]:
    """``yillik_kumulatif`` biçimine (``{"donem_tip","sira","alanlar"}``) uygun
    beyanname kayıtları döner.

    Not (bilinen arayüz sınırı — bkz. task-1.2-report.md "concerns"):
    ``depo.beyanname_oku`` yalnızca ``alanlar`` JSON'unu döner (donem_tip/sira
    içermez); ``yillik_kumulatif`` ise eksik dönem tespiti için ikisini de
    bekler. Aynı gerekçeyle burada da ``depo.baglanti`` üzerinden donem.tip /
    donem.sira eklenerek kayıt yeniden sarmalanıyor (depo.py'deki SQL deseninin
    aynısı, yalnızca ek kolonlarla).
    """
    satirlar = depo.baglanti.execute(
        """
        SELECT d.tip, d.sira, b.alanlar
        FROM beyanname b JOIN donem d ON d.id = b.donem_id
        WHERE d.mukellef_id = ? AND b.tip = ? AND d.yil = ?
        ORDER BY d.sira
        """,
        (mukellef_id, tip, yil),
    ).fetchall()
    return [
        {"donem_tip": satir[0], "sira": satir[1], "alanlar": json.loads(satir[2])}
        for satir in satirlar
    ]


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
