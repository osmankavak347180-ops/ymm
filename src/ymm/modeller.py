"""Veri modelleri: Donem, MizanSatiri, Beyanname, Bulgu.

Tutarlar daima ``decimal.Decimal``. ``float`` tutar bu projede yasak.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class MizanSatiri:
    hesap_kodu: str
    hesap_adi: str
    borc_toplam: Decimal
    alacak_toplam: Decimal
    borc_bakiye: Decimal
    alacak_bakiye: Decimal


@dataclass
class Donem:
    yil: int
    tip: str
    sira: int


@dataclass
class Bulgu:
    kaynak: str
    kontrol_kodu: str
    seviye: str
    tutar_fark: Decimal | None
    yuzde_fark: float | None
    detay: dict
    # Not: brief'teki arayüzde bulgu_yaz(list[Bulgu]) mukellef_id/yil'i ayrı
    # parametre olarak almıyor; ancak veri.db şemasında bulgu.mukellef_id ve
    # bulgu.yil NOT NULL. Bu yüzden bu iki alan burada eklendi (detayda
    # verilen 6 alanın sırası/değişmedi, ekleme sona yapıldı). Bkz. rapor.
    mukellef_id: int
    yil: int
