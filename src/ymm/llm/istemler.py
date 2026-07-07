"""Modül C rapor üretimi için LLM istem şablonları (Task 4.1).

KVKK: bu modül `anthropic` IMPORT ETMEZ (bekçi: tests/test_kvkk.py) ve
kimlik bilgisine dokunmaz — istemler yalnız MASKELİ ([MUK-001]/[KISI-001]
takma kodlu) paragraf metinleriyle doldurulur.
"""

from __future__ import annotations

RAPOR_SISTEM_ISTEMI = (
    "Sen bir Yeminli Mali Müşavir (YMM) tam tasdik raporu redaktörüsün. "
    "Sana verilen kalıp bulgu paragraflarını akıcı, resmi Türkçe ile "
    "birleştirip redakte edersin.\n"
    "KURALLAR:\n"
    "1. Köşeli parantezli takma kod token'larını ([MUK-001], [KISI-001] "
    "gibi) AYNEN koru — değiştirme, çevirme, çıkarma. Bu takma kod "
    "token'ları sonradan yerel bir adımda gerçek değerlerle değiştirilecek.\n"
    "2. Tutarları ve yüzdeleri AYNEN aktar; yeni sayı üretme, yuvarlama.\n"
    "3. Paragraflarda olmayan hiçbir bulgu/iddia EKLEME.\n"
    "4. Metin bir TASLAK rapora girecektir; kesin hüküm bildiren ifadeler "
    "yerine tespit dilini kullan (\"tespit edilmiştir\", \"görülmektedir\")."
)


def redaksiyon_istemi(paragraflar: list[str]) -> str:
    """Kalıp bulgu paragraflarını tek redaksiyon istemine dönüştürür."""
    numarali = "\n\n".join(
        f"[Paragraf {i}]\n{p}" for i, p in enumerate(paragraflar, start=1)
    )
    return (
        "Aşağıdaki kalıp bulgu paragraflarını, sıralarını koruyarak akıcı ve "
        "resmi bir rapor bölümü hâlinde birleştir ve redakte et:\n\n"
        f"{numarali}"
    )
