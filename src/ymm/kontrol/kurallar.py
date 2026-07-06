"""Kontrol kuralları: mizan formül değerlendirici + tolerans/seviye karşılaştırması.

Mutlak kurallar (bkz. .claude/agents/capraz-kontrol.md): tamamen yerel/deterministik,
tüm tutarlar Decimal, eşikler kodda değil config/kontrol_kurallari.yaml'da.
"""

from __future__ import annotations

import re
from decimal import Decimal

from ymm.modeller import MizanSatiri

# "+600", "-610", boşluklu "600 + 601 - 610" gibi ifadelerdeki işaret+terim çiftleri.
_TERIM_DESENI = re.compile(r"([+-])([A-Za-z0-9_.]+)")


def _satir_degeri(satir: MizanSatiri) -> Decimal:
    """Hesap değeri konvansiyonu: borç bakiyesi > 0 ise borç bakiyesi, değilse
    alacak bakiyesi (mutlak/aktif taraf bakiyesi)."""
    return satir.borc_bakiye if satir.borc_bakiye > 0 else satir.alacak_bakiye


def hesap_degeri(satirlar: list[MizanSatiri], hesap_kodu: str) -> Decimal:
    """Bir hesap kodunun (ör. "600") mizan değeri.

    Çifte sayım önlemi: önce TAM EŞLEŞEN ana hesap satırı aranır; varsa yalnız
    o kullanılır ve alt hesaplar ("600.01" gibi) YOK SAYILIR. Ana hesap satırı
    yoksa, ``hesap_kodu + "."`` ile başlayan alt hesaplar toplanır.
    """
    ana_hesaplar = [s for s in satirlar if s.hesap_kodu == hesap_kodu]
    if ana_hesaplar:
        return sum((_satir_degeri(s) for s in ana_hesaplar), Decimal("0"))

    alt_hesaplar = [s for s in satirlar if s.hesap_kodu.startswith(hesap_kodu + ".")]
    return sum((_satir_degeri(s) for s in alt_hesaplar), Decimal("0"))


def formul_degerlendir(formul: str, satirlar: list[MizanSatiri]) -> Decimal:
    """"600 + 601 + 602 - 610" gibi bir formülü mizan satırlarına göre hesaplar.

    Her terim ``hesap_degeri`` ile çözülür (ana hesap önceliği + prefix toplamı
    uygulanır), sonra formüldeki işaretine göre toplanır/çıkarılır. Tek terimli
    işaretli ifadeler (ör. "+679", "-610") mutabakat kalemi formülleri için de
    kullanılır — aynı fonksiyon.
    """
    ifade = formul.replace(" ", "")
    if ifade and ifade[0] not in "+-":
        ifade = "+" + ifade

    toplam = Decimal("0")
    for isaret, terim in _TERIM_DESENI.findall(ifade):
        deger = hesap_degeri(satirlar, terim)
        toplam += deger if isaret == "+" else -deger
    return toplam


def karsilastir(
    sol_tutar: Decimal,
    sag_tutar: Decimal,
    tolerans: dict,
    seviye_esikleri: dict,
) -> tuple[Decimal, float, str] | None:
    """Sol (beyanname) ile sağ (mizan) tutarını karşılaştırır.

    Tolerans kuralı: bulgu üretilmesi için mutlak VE oransal eşiğin İKİSİ DE
    aşılmalı; biri aşılmazsa ``None`` (bulgu yok) döner.

    yuzde_fark = |sol - sağ| / |sağ| * 100 (mizan tarafı referans/payda alınır).

    Döner: (tutar_fark, yuzde_fark, seviye) ya da tolerans içindeyse ``None``.
    """
    fark = sol_tutar - sag_tutar
    mutlak_fark = abs(fark)

    if sag_tutar == 0:
        yuzde_fark = 0.0 if mutlak_fark == 0 else float("inf")
    else:
        yuzde_fark = float(mutlak_fark / abs(sag_tutar) * 100)

    mutlak_esik = Decimal(str(tolerans["mutlak"]))
    oransal_esik = float(tolerans["oransal"])

    if mutlak_fark <= mutlak_esik or yuzde_fark <= oransal_esik:
        return None

    yuksek_esik = float(seviye_esikleri["yuksek"])
    orta_esik = float(seviye_esikleri["orta"])
    if yuzde_fark >= yuksek_esik:
        seviye = "yuksek"
    elif yuzde_fark >= orta_esik:
        seviye = "orta"
    else:
        seviye = "dusuk"

    return mutlak_fark.quantize(Decimal("0.01")), yuzde_fark, seviye
