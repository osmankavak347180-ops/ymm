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


class EksikAlanHatasi(Exception):
    """Bir beyanname kaydında ``alanlar[alan]`` beklenen alan bulunamazsa
    fırlatılır.

    KULLANICIYA/ÇALIŞTIRMAYA YANSIYAN bir çökme DEĞİLDİR — kontrol-içi bir
    sinyaldir. Mimar kararı: "sessiz sıfır yasak, çökme de yasak" — eksik
    alanlı bir kayıt yüzünden kısmi/yanlış bir toplamla sessizce devam etmek
    de, tüm çalıştırmayı ``KeyError`` ile çökertmek de kabul edilemez. Bu
    yüzden çağıran taraf (bkz. ``motor.kontrolleri_calistir``) bu exception'ı
    yakalayıp yalnızca İLGİLİ KONTROLÜ atlar (bulgu üretmez), ``_logger.warning``
    ile nedenini loglar ve diğer kontroller çalışmaya devam eder.
    """


def yillik_kumulatif(beyannameler: list[dict], alan: str) -> tuple[Decimal, list[str]]:
    """Verilen beyanname kayıtlarının ``alanlar[alan]`` değerlerini Decimal toplar.

    İkinci eleman: eksik dönem uyarıları (ör. AY tipinde 12'den az kayıt varsa
    hangi sıraların eksik olduğunu söyleyen mesajlar). Uyarı listesi boş = tam yıl.

    Akış kesilmez: eksik DÖNEM bir exception DEĞİL, dönüş değerinde uyarıdır —
    çağıran taraf (kontrol motoru / rapor) bu uyarıyı loglar/rapora düşer.

    Eksik ALAN farklı bir durumdur: mevcut bir kayıtta ``alanlar[alan]``
    yoksa (config'in beklediği alan kayıtta hiç yoksa) ``EksikAlanHatasi``
    fırlatılır — bkz. o sınıfın docstring'i. Bu, "eksik dönem" (kayıt hiç yok)
    ile "eksik alan" (kayıt var ama alan yok) arasındaki farkı ayırt eder;
    ikincisi kısmi/yanlış bir toplamla sessizce devam etmeye izin vermez.
    """
    if not beyannameler:
        return Decimal("0"), ["Beyanname kaydı bulunamadı — dönem karşılaştırması yapılamadı."]

    toplam = Decimal("0")
    for kayit in beyannameler:
        if alan not in kayit["alanlar"]:
            raise EksikAlanHatasi(
                f"alan eksik: kayıt sira={kayit.get('sira')!r} içinde "
                f"alanlar[{alan!r}] bulunamadı."
            )
        toplam += Decimal(kayit["alanlar"][alan])

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
