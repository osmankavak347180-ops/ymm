"""Beyanname PDF parser'ları için ortak yardımcılar (Task 3.1).

KVKK — kritik: `pdf_metni` ile çıkarılan tam PDF metni HİÇBİR YERDE
loglanmaz/saklanmaz; yalnızca çağıran (ör. `kdv.kdv_parse`) tarafından
geçici olarak işlenip atılır. Bu dosyanın hiçbir fonksiyonu mükellef kimlik
bilgisi (unvan, VKN, TCKN, adres) çıkarmaz/döndürmez -- yalnızca etiket
bazlı TUTAR arama sağlar.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pdfplumber

_logger = logging.getLogger(__name__)

# Türk biçimli tutar: binlik ayırıcı "." (opsiyonel, grup grup) + ondalık
# ayırıcı "," + iki (veya daha fazla) haneli kuruş kısmı. Beyanname
# tutarları GİB PDF'lerinde daima ondalık kuruş haneli göründüğünden ","
# kısmı ZORUNLU tutulur -- aksi halde sıra no / tarih gibi alakasız
# sayılar yanlışlıkla tutar sanılabilir.
_TUTAR_RE = re.compile(r"-?(?:\d{1,3}(?:\.\d{3})+|\d+),\d+")


def pdf_metni(dosya: Path) -> str:
    """PDF dosyasının tüm sayfalarındaki metni çıkarıp birleştirir.

    KVKK: dönüş değeri (tam PDF metni) çağıran tarafından yalnızca geçici
    işleme için kullanılmalı -- loglanmamalı, dosyaya yazılmamalı, DB'ye
    ham olarak konmamalıdır.
    """
    parcalar: list[str] = []
    with pdfplumber.open(dosya) as pdf:
        for sayfa in pdf.pages:
            parcalar.append(sayfa.extract_text() or "")
    return "\n".join(parcalar)


def _tutar_normalize(deger: object) -> Decimal:
    """Değeri Decimal'e çevirir.

    NOT: bu fonksiyon `parsers/mizan.py::_tutar_normalize` ile BİREBİR AYNI
    normalize konvansiyonunu uygular (Türk biçimi "1.234.567,89" ->
    Decimal("1234567.89")). Modüller arası gereksiz bağımlılık yaratmamak
    için import EDİLMEDİ, kasıtlı olarak kopyalandı -- iki kopya arasında
    davranış farkı çıkarsa bu bir bug'dır, ikisi birden güncellenmeli.

    - Boş (None) veya boş string -> Decimal("0")
    - Sayısal değer (int/float) -> `Decimal(str(deger))` üzerinden.
    - String -> Türk biçimi normalize edilir: "1.234.567,89" ->
      "1234567.89" (binlik "." kaldırılır, ondalık "," -> ".")
    """
    if deger is None:
        return Decimal("0")
    if isinstance(deger, Decimal):
        return deger
    if isinstance(deger, bool):
        raise ValueError(f"Gecersiz tutar degeri (bool): {deger!r}")
    if isinstance(deger, (int, float)):
        return Decimal(str(deger))
    if isinstance(deger, str):
        metin = deger.strip()
        if not metin:
            return Decimal("0")
        metin = metin.replace(".", "").replace(",", ".")
        try:
            return Decimal(metin)
        except InvalidOperation as exc:
            raise ValueError(f"Gecersiz tutar degeri: {deger!r}") from exc
    raise ValueError(f"Desteklenmeyen tutar tipi: {type(deger)!r} ({deger!r})")


def beyanname_alanlari(
    dosya: Path,
    alan_etiketleri: dict[str, list[str]],
    beyanname_tipi: str,
) -> dict[str, Decimal | None]:
    """Beyanname PDF'inden `alan_etiketleri`ndeki tüm TUTAR alanlarını
    çıkarır — tüm beyanname parser'larının ortak gövdesi (Task 3.2).

    Bulunamayan alan `None` olur (sessiz sıfır YASAK) ve bir uyarı loglanır.
    PDF açılamıyorsa / geçerli bir PDF değilse anlaşılır bir `ValueError`
    fırlatır (çağıran -- CLI -- bunu traceback göstermeden kullanıcıya
    yansıtmalıdır).

    KVKK: yalnızca `alan_etiketleri`nde tanımlı tutar alanları döner;
    PDF metni geçici işlenip atılır, loglanmaz/saklanmaz.
    """
    try:
        metin = pdf_metni(dosya)
    except Exception as exc:  # pdfplumber/pdfminer'ın attığı çeşitli hatalar
        raise ValueError(f"PDF okunamadı ({dosya.name}): {exc}") from exc

    sonuc: dict[str, Decimal | None] = {}
    for alan, etiketler in alan_etiketleri.items():
        deger = etiket_degeri(metin, etiketler)
        if deger is None:
            _logger.warning(
                "%s parse: %r alanı bulunamadı (dosya=%s)",
                beyanname_tipi,
                alan,
                dosya.name,
            )
        sonuc[alan] = deger
    return sonuc


def etiket_degeri(metin: str, etiketler: list[str]) -> Decimal | None:
    """`metin` içinde `etiketler` listesindeki ilk eşleşen etiketi arar;
    etiketin hemen ardından (aynı satırda/devamındaki pencerede) rastlanan
    ilk Türk biçimli tutarı Decimal'e çevirip döner.

    Hiçbir etiket bulunamazsa veya etiket bulunup ardından tutar
    yakalanamazsa `None` döner -- çağıran bunu "sessiz sıfır" SAYMAMALI,
    kullanıcıya/uyarı loguna yansıtmalıdır.
    """
    for etiket in etiketler:
        idx = metin.find(etiket)
        if idx == -1:
            continue
        pencere = metin[idx + len(etiket) : idx + len(etiket) + 200]
        eslesme = _TUTAR_RE.search(pencere)
        if eslesme is not None:
            return _tutar_normalize(eslesme.group())
    return None
