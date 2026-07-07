"""Risk seviyesi: geçerli seviye kümesi + doğrulama.

Statik kurallarda (Task 2.1) risk seviyesini KOD hesaplamaz — seviye doğrudan
``config/risk_hesaplari.yaml``'da kural yazarınca atanır (sezgisel/istatistiksel
tahmin YOK, bkz. .claude/agents/risk-tarama.md). Bu modül yalnızca o sabit
değerin geçerli kümede olduğunu (fail-fast) doğrular. Karşılaştırmalı kurallar
(ör. yüzde değişim eşikleri) için eşik tabanlı seviye hesabı ileride buraya
eklenebilir; v1'de yalnızca doğrulama vardır.
"""

from __future__ import annotations

GECERLI_SEVIYELER = ("dusuk", "orta", "yuksek")


def seviye_dogrula(seviye: str, baglam: str = "") -> str:
    """``seviye``'nin ``GECERLI_SEVIYELER`` içinde olduğunu doğrular ve aynen
    döner; değilse ``ValueError`` fırlatır (fail-fast, Modül A konvansiyonu).

    ``baglam``: hata mesajına eklenecek isteğe bağlı bağlam bilgisi (ör. hangi
    kural kodu için doğrulandığı).
    """
    if seviye not in GECERLI_SEVIYELER:
        ek = f" ({baglam})" if baglam else ""
        raise ValueError(
            f"Bilinmeyen seviye değeri: {seviye!r}{ek} (geçerli: {GECERLI_SEVIYELER})"
        )
    return seviye
