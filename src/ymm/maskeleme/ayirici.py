"""Kimlik ayirici: mizan satirlarindaki kisi/firma adlarini [KISI-nnn] token'ina cevirir.

KVKK cekirdegi: kimlik.db, veri.db'den fiziksel olarak AYRI bir SQLite
dosyasidir. Bu modul kendi baglantisini acar (Depo KULLANILMAZ) ve
kimlik_schema.sql'i (CREATE TABLE IF NOT EXISTS) idempotent olarak uygular.

Tespit kurallari (mimar onayli, docs/01-MIMARI.md §4 + task-0.4 brief):
1. Hesap adinda koseli parantez `[...]` varsa, parantez icindeki etiket
   kimlik adayidir (ör. "Ortaklardan Alacaklar [ORTAK-A]" -> gercek_ad="ORTAK-A").
   Bu, YMM ingest sirasinda koseli parantezle isaretleme sozlesmesidir (v1).
2. Hesap adinda 2+ ardisik BUYUK harfli kelime varsa (Turkce karakterler dahil,
   ör. "AHMET YILMAZ"), bu da kimlik adayidir ve tum eslesen dizgi maskelenir.

Token uretimi: ayni gercek ad ayni token'i alir (idempotent -- kimlik.db'de
zaten varsa yeni token uretilmez). Token sirasi deterministik: KISI-001,
KISI-002... ilk gorulme sirasina gore (mevcut db'deki en buyuk numaradan devam eder).
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import replace
from pathlib import Path

from ymm.modeller import MizanSatiri

_KIMLIK_SCHEMA_DOSYASI = Path(__file__).resolve().parent.parent / "db" / "kimlik_schema.sql"

# Koseli parantez icindeki etiket: "... [ETIKET]" -> group(1) = "ETIKET"
_KOSELI_PARANTEZ_REGEX = re.compile(r"\[([^\[\]]+)\]")

# 2+ ardisik BUYUK harfli kelime (Turkce buyuk harfler dahil): "AHMET YILMAZ"
_BUYUK_HARF_AD_REGEX = re.compile(
    r"\b[A-ZÇĞİÖŞÜ]{2,}(?:\s[A-ZÇĞİÖŞÜ]{2,})+\b"
)


def kimlik_ayir(satirlar: list[MizanSatiri], kimlik_db: Path) -> list[MizanSatiri]:
    """Alt hesap adlarindaki koseli parantezli kimlik etiketlerini (veya BUYUK harfli
    ad-soyad dizgilerini) [KISI-nnn] token'ina cevirir, eslemeyi kimlik_db'ye yazar,
    maskelenmis yeni satir listesi doner. Girdi listesi degistirilmez (yeni liste doner).
    """
    kimlik_db.parent.mkdir(parents=True, exist_ok=True)
    baglanti = sqlite3.connect(kimlik_db)
    try:
        baglanti.executescript(_KIMLIK_SCHEMA_DOSYASI.read_text(encoding="utf-8"))

        ad_to_kod: dict[str, str] = {}
        en_buyuk_numara = 0
        for kod, ad in baglanti.execute(
            "SELECT takma_kod, gercek_ad FROM kimlik WHERE tip = 'KISI'"
        ):
            ad_to_kod[ad] = kod
            try:
                numara = int(kod.rsplit("-", 1)[-1])
            except ValueError:
                numara = 0
            en_buyuk_numara = max(en_buyuk_numara, numara)

        sonraki_numara = en_buyuk_numara + 1

        def _token_al(gercek_ad: str) -> str:
            nonlocal sonraki_numara
            if gercek_ad in ad_to_kod:
                return ad_to_kod[gercek_ad]
            token = f"KISI-{sonraki_numara:03d}"
            sonraki_numara += 1
            baglanti.execute(
                "INSERT INTO kimlik (takma_kod, tip, gercek_ad, vkn_tckn) "
                "VALUES (?, 'KISI', ?, NULL)",
                (token, gercek_ad),
            )
            ad_to_kod[gercek_ad] = token
            return token

        yeni_satirlar: list[MizanSatiri] = []
        for satir in satirlar:
            hesap_adi = satir.hesap_adi or ""

            eslesme = _KOSELI_PARANTEZ_REGEX.search(hesap_adi)
            if eslesme is not None:
                gercek_ad = eslesme.group(1)
            else:
                eslesme = _BUYUK_HARF_AD_REGEX.search(hesap_adi)
                gercek_ad = eslesme.group(0) if eslesme is not None else None

            if eslesme is not None and gercek_ad is not None:
                token = _token_al(gercek_ad)
                yeni_hesap_adi = (
                    hesap_adi[: eslesme.start()] + f"[{token}]" + hesap_adi[eslesme.end():]
                )
                yeni_satirlar.append(replace(satir, hesap_adi=yeni_hesap_adi))
            else:
                yeni_satirlar.append(satir)

        baglanti.commit()
        return yeni_satirlar
    finally:
        baglanti.close()
