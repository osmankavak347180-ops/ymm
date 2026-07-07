"""KV (Kurumlar Vergisi Beyannamesi) PDF'inden TUTAR alanlarının çıkarımı
(Task 3.2).

KVKK — mutlak kural: bu modül mükellef kimlik bilgisi (unvan, VKN, TCKN,
adres) HİÇ ÇIKARMAZ / DÖNDÜRMEZ / SAKLAMAZ. `kv_parse` yalnızca aşağıdaki
tutar alanlarını içeren bir sözlük döner.

NOT (R3 azaltımı): `_ALAN_ETIKETLERI` içindeki etiket metinleri gerçek bir
GİB e-beyanname PDF'ine dayanmıyor. İlk gerçek KV PDF'i alındığında bu
etiketler `config/`e taşınıp YMM ile ekran başında doğrulanacak (bkz.
kdv.py'deki aynı not).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from ymm.parsers.beyanname.ortak import beyanname_alanlari

# alan adı -> olası etiket varyantları (sırayla denenir, ilk eşleşen kazanır).
# `matrah` kontrol motorunun A-GECICI-KV kuralının sağ tarafta beklediği
# alandır (config/kontrol_kurallari.yaml) — adı DEĞİŞTİRİLEMEZ.
_ALAN_ETIKETLERI: dict[str, list[str]] = {
    "matrah": [
        "Kurumlar Vergisi Matrahı",
        "Matrah",
    ],
    "hesaplanan_kurumlar_vergisi": [
        "Hesaplanan Kurumlar Vergisi",
    ],
}


def kv_parse(dosya: Path) -> dict[str, Decimal | None]:
    """Kurumlar vergisi beyanname PDF'ini parse eder.

    Döner: {"matrah": Decimal|None,
            "hesaplanan_kurumlar_vergisi": Decimal|None}

    Bulunamayan alan `None` + uyarı; bozuk PDF'te `ValueError`
    (bkz. `ortak.beyanname_alanlari`).
    """
    return beyanname_alanlari(dosya, _ALAN_ETIKETLERI, "KV")
