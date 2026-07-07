"""KDV1 (Katma Değer Vergisi) beyannamesi PDF'inden TUTAR alanlarının
çıkarımı (Task 3.1).

KVKK — mutlak kural: bu modül mükellef kimlik bilgisi (unvan, VKN, TCKN,
adres) HİÇ ÇIKARMAZ / DÖNDÜRMEZ / SAKLAMAZ. `kdv_parse` yalnızca aşağıdaki
4 tutar alanını içeren bir sözlük döner; PDF metninin tamamı hiçbir yerde
loglanmaz (bkz. `ortak.pdf_metni` docstring'i).

NOT (R3 azaltımı): `_ALAN_ETIKETLERI` içindeki etiket metinleri gerçek bir
GİB e-beyanname PDF'ine dayanmıyor -- proje bu görev sırasında henüz örnek
gerçek dosyaya sahip değil. İlk gerçek KDV1 PDF'i alındığında bu etiketler
`config/`e taşınıp YMM ile ekran başında doğrulanacak (bkz.
.superpowers/sdd/task-3.1-brief.md).
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from ymm.parsers.beyanname.ortak import beyanname_alanlari

# alan adı -> olası etiket varyantları (sırayla denenir, ilk eşleşen kazanır).
_ALAN_ETIKETLERI: dict[str, list[str]] = {
    "teslim_hizmet_toplam": [
        "Teslim ve Hizmetlerin Karşılığını Teşkil Eden Bedel",
        "Teslim ve Hizmet Bedeli",
    ],
    "indirilecek_kdv": [
        "İndirilecek KDV",
        "Bu Döneme Ait İndirilecek KDV",
    ],
    "hesaplanan_kdv": [
        "Hesaplanan KDV",
        "Toplam Hesaplanan KDV",
    ],
    "matrah": [
        "Vergiye Tabi İşlemler Toplamı",
        "Matrah",
    ],
}


def kdv_parse(dosya: Path) -> dict[str, Decimal | None]:
    """KDV1 beyanname PDF'ini parse eder.

    Döner: {"teslim_hizmet_toplam": Decimal|None, "indirilecek_kdv": Decimal|None,
            "hesaplanan_kdv": Decimal|None, "matrah": Decimal|None}

    Bulunamayan alan `None` olur (sessiz sıfır YASAK) ve bir uyarı loglanır;
    bozuk PDF'te `ValueError` (bkz. `ortak.beyanname_alanlari`).
    """
    return beyanname_alanlari(dosya, _ALAN_ETIKETLERI, "KDV1")
