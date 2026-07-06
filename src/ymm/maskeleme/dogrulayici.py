"""Sizinti dogrulayici: LLM'e giden metinde kimlik bilgisi kaldi mi kontrol eder.

Iki katman:
1. Regex: VKN (10 hane), TCKN (11 hane), IBAN (TR + 24 hane, boslukla
   gruplanmis "TR12 3456 ..." bicimi de dahil -- bkz. Important-3 fix).
2. kimlik.db'deki tum gercek_ad ve vkn_tckn dizgileri (case-insensitive,
   Turkce'ye ozgu I/i buyuk-kucuk donusumu icin `_tr_fold` kullanilir).

Duzeltme (Critical-1): Python'un ham casefold()'u Turkce'ye ozgu "I"
(noktasiz buyuk) <-> "ı" (noktasiz kucuk) ve "İ" (noktali buyuk) <->
"i" (noktali kucuk) ayrimini lokal olarak cozmuyordu -- ornegin db'de
"Işık İnşaat", metinde "IŞIK İNŞAAT" gecince eslesme KACIYORDU (sizinti
yakalanamiyordu). `_tr_fold` once Turkce'ye ozgu I/i donusumunu yapar,
sonra casefold() uygular; karsilastirmanin HER IKI tarafina da (db
degeri + taranan metin) uygulanir.

Bu modulde raise eden yer YOKTUR; MaskeIhlali'yi gateway (Task 4.1) kullanir.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

_VKN_REGEX = re.compile(r"\b\d{10}\b")
_TCKN_REGEX = re.compile(r"\b\d{11}\b")
# IBAN: TR + 2 kontrol hanesi + 22 hane, 4'erli gruplar arasinda opsiyonel
# bosluk toleransiyla ("TR12 3456 7890 1234 5678 9012 34" VE bitisik
# "TR12345678901234567890123 4" ikisi de eslesir -- Important-3 fix).
_IBAN_REGEX = re.compile(r"\bTR\d{2}(?:\s?\d{4}){5}\s?\d{2}\b")


def _tr_fold(s: str) -> str:
    """Turkce'ye ozgu buyuk/kucuk harf donusumunu cozup casefold uygular.

    Once "İ" -> "i" ve "I" -> "ı" donusumu yapilir (Turkce lokaline ozgu
    esleme), ardindan genel `casefold()` uygulanir. Boylece "IŞIK İNŞAAT"
    ile "Işık İnşaat" gibi ciftler dogru eslesir (Critical-1 fix).
    """
    return s.replace("İ", "i").replace("I", "ı").casefold()


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

        metin_tr = _tr_fold(metin)
        for gercek_ad, vkn_tckn in kayitlar:
            if gercek_ad and _tr_fold(gercek_ad) in metin_tr:
                sonuclar.append(gercek_ad)
            if vkn_tckn and _tr_fold(vkn_tckn) in metin_tr:
                sonuclar.append(vkn_tckn)

    return sonuclar
