"""Dönem hizalama / kümülatif toplama yardımcıları (MODÜL A).

Beyanname kayıtları ``{"tip", "yil", "donem_tip", "sira", "alanlar"}`` biçiminde
dict'lerdir (bkz. ``ornek_veri/beyanname_ozet.json``). ``alanlar`` içindeki
tutarlar Decimal string olarak saklanır (ör. ``"408333.33"``).
"""

from __future__ import annotations

from decimal import Decimal

# donem_tip -> bir yılda beklenen dönem sayısı ve geçerli sıra kümesi.
_BEKLENEN_SIRALAR: dict[str, list[int]] = {
    "AY": list(range(1, 13)),
    "CEYREK": list(range(1, 5)),
    "YILLIK": [0],
}


def yillik_kumulatif(beyannameler: list[dict], alan: str) -> tuple[Decimal, list[str]]:
    """Verilen beyanname kayıtlarının ``alanlar[alan]`` değerlerini Decimal toplar.

    İkinci eleman: eksik dönem uyarıları (ör. AY tipinde 12'den az kayıt varsa
    hangi sıraların eksik olduğunu söyleyen mesajlar). Uyarı listesi boş = tam yıl.

    Akış kesilmez: eksik dönem bir exception DEĞİL, dönüş değerinde uyarıdır —
    çağıran taraf (kontrol motoru / rapor) bu uyarıyı loglar/rapora düşer.
    """
    if not beyannameler:
        return Decimal("0"), ["Beyanname kaydı bulunamadı — dönem karşılaştırması yapılamadı."]

    toplam = sum(
        (Decimal(kayit["alanlar"][alan]) for kayit in beyannameler),
        Decimal("0"),
    )

    donem_tip = beyannameler[0]["donem_tip"]
    beklenen = _BEKLENEN_SIRALAR.get(donem_tip)
    if beklenen is None:
        # Bilinmeyen dönem_tip: eksik kontrolü yapılamaz, yalnızca toplam döner.
        return toplam, []

    mevcut_siralar = {kayit["sira"] for kayit in beyannameler}
    eksik_siralar = sorted(set(beklenen) - mevcut_siralar)

    uyarilar = [
        f"Eksik dönem: {donem_tip} sıra {sira} kaydı bulunamadı."
        for sira in eksik_siralar
    ]

    return toplam, uyarilar
