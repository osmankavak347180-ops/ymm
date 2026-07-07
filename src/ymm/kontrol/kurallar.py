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

# Formülün TAMAMININ (boşluklar atıldıktan, gerekirse baştaki '+' eklendikten
# sonra) işaret+terim çiftlerinin ardışık tekrarından oluştuğunu doğrulamak
# için: fullmatch başarısız olursa formülde tüketilmeyen/sarkan/geçersiz bir
# parça vardır (bkz. formul_terimlerini_ayikla docstring'i).
_IFADE_DESENI = re.compile(r"(?:[+-][A-Za-z0-9_.]+)+")

# ORİJİNAL formülün doğrulanması (space removal ÖNCESİ): boşluklara SADECE
# operatörlerin çevresinde izin verir. Çıplak boşluklar (operatörsüz terimler
# arasında) "600 601" gibi reddedilir. Örnek: "600+601", "600 + 601", " 600 ",
# "-600", "+ 600 + 601" geçer; "600 601", "600  601", "600 601 - 610" fails.
_ORIJINAL_FORMUL_DESENI = re.compile(
    r"^\s*[+-]?\s*[A-Za-z0-9_.]+(?:\s*[+-]\s*[A-Za-z0-9_.]+)*\s*$"
)


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


def hesap_eslesir(hesap_kodu: str, satirlar: list[MizanSatiri]) -> bool:
    """``hesap_kodu`` mizanda (ana hesap ya da ``hesap_kodu + "."`` önekli alt
    hesap olarak) en az bir satırla eşleşiyor mu?

    ``hesap_degeri`` hiç eşleşme yoksa da sessizce ``Decimal("0")`` döner
    (toplama-nötr); bu, formüldeki bir hesap kodunun mizanda hiç bulunmaması
    ile gerçekten sıfır bakiyeli olması arasındaki farkı gizler. Çağıran taraf
    (bkz. ``motor.kontrolleri_calistir``) sessiz-sıfır durumunu ayırt etmek ve
    uyarı izi bırakmak için bu yardımcıyı kullanır.
    """
    return any(
        s.hesap_kodu == hesap_kodu or s.hesap_kodu.startswith(hesap_kodu + ".")
        for s in satirlar
    )


def formul_terimlerini_ayikla(formul: str) -> list[tuple[str, str]]:
    """Bir mizan formülünü ``(isaret, hesap_kodu)`` çiftlerine ayırır.

    Kabul edilen sözdizimi::

        FORMUL     ::= TERIM+
        TERIM      ::= ("+" | "-") HESAP_KODU
        HESAP_KODU ::= [A-Za-z0-9_.]+   (ör. "600", "600.01", "679")

    Boşluklar SADECE operatörlerin çevresinde izin verilir; çıplak boşluklar
    (ör. "600 601") reddedilir. Formül baştaki işaretsizse (ör. "600 + 601")
    bir "+" varsayılır — yani ilk terim de ``TERIM`` biçimine tamamlanır.

    Doğrulama:
    1. ORİJİNAL girdiye ``_ORIJINAL_FORMUL_DESENI`` uygulanır (space removal
       ÖNCESİ): çıplak boşluklar veya diğer sözdizimi hataları reddedilir.
    2. Geçerse, boşluklar kaldırılır ve ``_IFADE_DESENI`` ile tam tüketim
       doğrulanır (fazladan operatör, tanınmayan karakter, boş formül).

    Bilinerek reddedilen (önceden sessizce yanlış sonuç üreten) örnekler:
    ``"600 ++ 601"`` (fazladan "+"), ``"600 -- 601"`` (matematiksel yanlışlık),
    ``"600 + 601 -"`` (sarkan operatör), ``"600 & 601"`` (bilinmeyen operatör),
    ``"600 601"`` (çıplak boşluk — BUG FIX: artık ValueError).
    """
    # Doğrulama 1: ORİJİNAL formüle operatör etrafında boşluk kuralını uygula
    if _ORIJINAL_FORMUL_DESENI.fullmatch(formul) is None:
        raise ValueError(
            f"Geçersiz formül sözdizimi: {formul!r} "
            f"(çıplak boşluklar veya hatalı biçim)"
        )

    ifade = formul.replace(" ", "")
    if not ifade:
        raise ValueError(f"Boş formül: {formul!r}")
    if ifade[0] not in "+-":
        ifade = "+" + ifade

    # Doğrulama 2: Tam tüketim
    if _IFADE_DESENI.fullmatch(ifade) is None:
        kismi_eslesme = _IFADE_DESENI.match(ifade)
        sorunlu_kisim = ifade[kismi_eslesme.end():] if kismi_eslesme else ifade
        raise ValueError(
            f"Geçersiz formül sözdizimi: {formul!r} "
            f"(tüketilemeyen/sorunlu kısım: {sorunlu_kisim!r})"
        )

    return _TERIM_DESENI.findall(ifade)


def formul_degerlendir(formul: str, satirlar: list[MizanSatiri]) -> Decimal:
    """"600 + 601 + 602 - 610" gibi bir formülü mizan satırlarına göre hesaplar.

    Önce ``formul_terimlerini_ayikla`` ile formülün TAMAMININ geçerli
    işaret+terim çiftlerinden oluştuğu doğrulanır (aksi halde ``ValueError``).
    Her terim ``hesap_degeri`` ile çözülür (ana hesap önceliği + prefix toplamı
    uygulanır), sonra formüldeki işaretine göre toplanır/çıkarılır. Tek terimli
    işaretli ifadeler (ör. "+679", "-610") mutabakat kalemi formülleri için de
    kullanılır — aynı fonksiyon.
    """
    toplam = Decimal("0")
    for isaret, terim in formul_terimlerini_ayikla(formul):
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
