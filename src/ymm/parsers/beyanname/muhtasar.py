"""MUHSGK (Muhtasar ve Prim Hizmet Beyannamesi) PDF'inden TUTAR alanlarının
çıkarımı (Task 3.2).

KVKK — mutlak kural: bu modül mükellef/çalışan kimlik bilgisi (unvan, VKN,
TCKN, ad-soyad, adres) HİÇ ÇIKARMAZ / DÖNDÜRMEZ / SAKLAMAZ. `muhsgk_parse`
yalnızca aşağıdaki tutar alanlarını içeren bir sözlük döner.

NOT (R3 azaltımı): `_ALAN_ETIKETLERI` içindeki etiket metinleri gerçek bir
GİB e-beyanname PDF'ine dayanmıyor. İlk gerçek MUHSGK PDF'i alındığında bu
etiketler `config/`e taşınıp YMM ile ekran başında doğrulanacak (bkz.
kdv.py'deki aynı not).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from ymm.parsers.beyanname.ortak import beyanname_alanlari

# alan adı -> olası etiket varyantları (sırayla denenir, ilk eşleşen kazanır).
# `brut_ucret_toplam` kontrol motorunun A-MUHSGK-UCRET kuralının beklediği
# alandır (config/kontrol_kurallari.yaml) — adı DEĞİŞTİRİLEMEZ.
_ALAN_ETIKETLERI: dict[str, list[str]] = {
    "brut_ucret_toplam": [
        "Ücret Ödemeleri Gayrisafi Tutar",
        "Brüt Ücret Toplamı",
    ],
    "gelir_vergisi_kesintisi": [
        "Tevkif Edilen Gelir Vergisi",
        "Gelir Vergisi Kesintisi Toplamı",
    ],
}


def muhsgk_parse(dosya: Path) -> dict[str, Decimal | None]:
    """MUHSGK beyanname PDF'ini parse eder.

    Döner: {"brut_ucret_toplam": Decimal|None,
            "gelir_vergisi_kesintisi": Decimal|None}

    Bulunamayan alan `None` + uyarı; bozuk PDF'te `ValueError`
    (bkz. `ortak.beyanname_alanlari`).
    """
    return beyanname_alanlari(dosya, _ALAN_ETIKETLERI, "MUHSGK")
