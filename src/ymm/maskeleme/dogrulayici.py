"""Sizinti dogrulayici: LLM'e giden metinde kimlik bilgisi kaldi mi kontrol eder.

Iki katman:
1. Regex: VKN (10 hane), TCKN (11 hane), IBAN (TR + 24 hane).
2. kimlik.db'deki tum gercek_ad ve vkn_tckn dizgileri (case-insensitive,
   Turkce I/i buyuk-kucuk donusumune dikkat: casefold() kullanilir --
   naif .lower()/.upper() Turkce'de "I" <-> "i" eslemesini hatali yapar).

Not (bilinen sinirlama): Python'un casefold()'u genel Unicode kurallarini
uygular; Turkce'ye ozgu "I" (noktasiz buyuk) <-> "ı" (noktasiz kucuk) ve
"İ" (noktali buyuk) <-> "i" (noktali kucuk) ayrimini lokal olarak
cozmez -- bu proje kapsaminda (mimar onayli v1 sozlesmesi) casefold()
yeterli kabul edilmistir; tam Turkce lokal-farkinda karsilastirma
kapsam disidir.

Bu modulde raise eden yer YOKTUR; MaskeIhlali'yi gateway (Task 4.1) kullanir.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

_VKN_REGEX = re.compile(r"\b\d{10}\b")
_TCKN_REGEX = re.compile(r"\b\d{11}\b")
_IBAN_REGEX = re.compile(r"\bTR\d{24}\b")


class MaskeIhlali(Exception):
    """LLM'e gonderilecek metinde maskelenmemis kimlik bilgisi bulundugunda
    gateway (Task 4.1) tarafindan firlatilir. Bu dosyada raise edilmez."""


def sizinti_tara(metin: str, kimlik_db: Path) -> list[str]:
    """Metinde VKN/TCKN/IBAN veya kimlik.db'deki bilinen gercek ad/vkn-tckn
    dizgilerinden biri var mi tarar. Bos liste = temiz. Eslesen ham
    dizgilerin listesini doner (bos olmayan liste = sizinti var demektir).
    """
    sonuclar: list[str] = []

    sonuclar.extend(_TCKN_REGEX.findall(metin))
    sonuclar.extend(_VKN_REGEX.findall(metin))
    sonuclar.extend(_IBAN_REGEX.findall(metin))

    if kimlik_db.exists():
        baglanti = sqlite3.connect(kimlik_db)
        try:
            kayitlar = baglanti.execute(
                "SELECT gercek_ad, vkn_tckn FROM kimlik"
            ).fetchall()
        finally:
            baglanti.close()

        metin_cf = metin.casefold()
        for gercek_ad, vkn_tckn in kayitlar:
            if gercek_ad and gercek_ad.casefold() in metin_cf:
                sonuclar.append(gercek_ad)
            if vkn_tckn and vkn_tckn.casefold() in metin_cf:
                sonuclar.append(vkn_tckn)

    return sonuclar
