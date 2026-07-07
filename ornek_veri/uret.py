"""Dummy mizan_2025.xlsx ureticisi.

Deterministik: her calistirmada AYNI dosyayi uretir (tutarlar bu dosyada
sabit listeye yazilidir, rastgelelik yoktur).

ANKOR degerler (sonraki fazlarin -- T1.1/T1.2/T2.1/T2.2 -- testleri bu
sayilara dayanir; DEGISTIRME):
    600 Yurtici Satislar        alacak_bakiye = 5.000.000,00
    770 Genel Yonetim Giderleri borc_bakiye   =   800.000,00
    131 Ortaklardan Alacaklar   borc_bakiye   =   150.000,00
    689 Diger Olagandisi Gider  borc_bakiye   =    45.000,00
        ve Zararlar (KKEG)

KVKK notu: alt hesap adlarinda gercek kisi/firma adi KULLANILMAZ; notr
etiketler ("ORTAK-A", "TEDARIKCI-B") kullanilir -- dummy veride bile
gercek kimlik olmamali.

Mizan tutarliligi: tum satirlarin (ana + alt hesap) borc_toplam toplami
alacak_toplam toplamina, borc_bakiye toplami da alacak_bakiye toplamina
esittir (bkz. _denge_dogrula). Uretim sirasinda bu esitlik dogrulanir;
bozulursa AssertionError firlatilir.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

BASLIKLAR = [
    "Hesap Kodu",
    "Hesap Adı",
    "Borç Toplam",
    "Alacak Toplam",
    "Borç Bakiye",
    "Alacak Bakiye",
]

# (hesap_kodu, hesap_adi, borc_toplam, alacak_toplam, borc_bakiye, alacak_bakiye)
# Not: her satir tek tarafli bakiye tasir (borc_bakiye XOR alacak_bakiye sifir
# degildir) -- 331/601/610/690 disinda; bu uc hesap bilincli olarak bakiyesiz
# (donem ici hareket olup net sifir, ya da hic hareket olmayan) sekilde
# tutulmustur.
MIZAN_SATIRLARI: list[tuple[str, str, Decimal, Decimal, Decimal, Decimal]] = [
    ("100", "Kasa", Decimal("30000.00"), Decimal("0.00"), Decimal("30000.00"), Decimal("0.00")),
    ("102", "Bankalar", Decimal("250000.00"), Decimal("0.00"), Decimal("250000.00"), Decimal("0.00")),
    ("120", "Alıcılar", Decimal("2645000.00"), Decimal("0.00"), Decimal("2645000.00"), Decimal("0.00")),
    ("131", "Ortaklardan Alacaklar", Decimal("150000.00"), Decimal("0.00"), Decimal("150000.00"), Decimal("0.00")),  # ANKOR
    ("131.01", "Ortaklardan Alacaklar [ORTAK-A]", Decimal("150000.00"), Decimal("0.00"), Decimal("150000.00"), Decimal("0.00")),
    ("153", "Ticari Mallar", Decimal("450000.00"), Decimal("0.00"), Decimal("450000.00"), Decimal("0.00")),
    ("191", "İndirilecek KDV", Decimal("120000.00"), Decimal("0.00"), Decimal("120000.00"), Decimal("0.00")),
    ("253", "Tesis, Makine ve Cihazlar", Decimal("2500000.00"), Decimal("0.00"), Decimal("2500000.00"), Decimal("0.00")),
    ("257", "Birikmiş Amortismanlar (-)", Decimal("0.00"), Decimal("100000.00"), Decimal("0.00"), Decimal("100000.00")),
    ("320", "Satıcılar", Decimal("0.00"), Decimal("350000.00"), Decimal("0.00"), Decimal("350000.00")),
    ("320.01", "Satıcılar [TEDARIKCI-B]", Decimal("0.00"), Decimal("150000.00"), Decimal("0.00"), Decimal("150000.00")),
    ("331", "Ortaklara Borçlar", Decimal("80000.00"), Decimal("80000.00"), Decimal("0.00"), Decimal("0.00")),
    ("360", "Ödenecek Vergi ve Fonlar", Decimal("0.00"), Decimal("80000.00"), Decimal("0.00"), Decimal("80000.00")),
    ("391", "Hesaplanan KDV", Decimal("0.00"), Decimal("1000000.00"), Decimal("0.00"), Decimal("1000000.00")),
    ("500", "Sermaye", Decimal("0.00"), Decimal("1000000.00"), Decimal("0.00"), Decimal("1000000.00")),
    ("570", "Geçmiş Yıllar Karları", Decimal("0.00"), Decimal("250000.00"), Decimal("0.00"), Decimal("250000.00")),
    ("600", "Yurtiçi Satışlar", Decimal("0.00"), Decimal("5000000.00"), Decimal("0.00"), Decimal("5000000.00")),  # ANKOR
    ("601", "Yurtdışı Satışlar", Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00")),
    ("610", "Satıştan İadeler (-)", Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00")),
    ("649", "Diğer Olağan Gelir ve Karlar", Decimal("0.00"), Decimal("50000.00"), Decimal("0.00"), Decimal("50000.00")),
    ("679", "Diğer Olağandışı Gelir ve Karlar", Decimal("0.00"), Decimal("10000.00"), Decimal("0.00"), Decimal("10000.00")),
    ("689", "Diğer Olağandışı Gider ve Zararlar", Decimal("45000.00"), Decimal("0.00"), Decimal("45000.00"), Decimal("0.00")),  # ANKOR
    ("690", "Dönem Karı veya Zararı", Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00")),
    ("720", "Direkt İşçilik Giderleri", Decimal("320000.00"), Decimal("0.00"), Decimal("320000.00"), Decimal("0.00")),
    ("730", "Genel Üretim Giderleri", Decimal("180000.00"), Decimal("0.00"), Decimal("180000.00"), Decimal("0.00")),
    ("740", "Hizmet Üretim Maliyeti", Decimal("120000.00"), Decimal("0.00"), Decimal("120000.00"), Decimal("0.00")),
    ("760", "Pazarlama Satış Dağıtım Giderleri", Decimal("230000.00"), Decimal("0.00"), Decimal("230000.00"), Decimal("0.00")),
    ("770", "Genel Yönetim Giderleri", Decimal("800000.00"), Decimal("0.00"), Decimal("800000.00"), Decimal("0.00")),  # ANKOR
]


# 2024 (onceki donem) dummy mizani -- Task 2.2 karsilastirmali risk taramasi
# icin girdi. 2025 listesinin bir kopyasidir; yalnizca iki satir degistirildi
# (denge otomatik korunur cunku ayni tutar bir borc kaleminden dusulup ayni
# tutar bir alacak kaleminden dusuldu):
#   770 Genel Yonetim Giderleri: 800.000,00 -> 500.000,00 (ANKOR, -300.000)
#   600 Yurtici Satislar       : 5.000.000,00 -> 4.700.000,00 (-300.000)
# 2025'e gore: 770 %60 artis (500.000 -> 800.000, esik %40) -> B-770-ARTIS
# orta bulgu bekleniyor (bkz. tests/test_risk_karsilastirma.py).
MIZAN_SATIRLARI_2024: list[tuple[str, str, Decimal, Decimal, Decimal, Decimal]] = [
    ("100", "Kasa", Decimal("30000.00"), Decimal("0.00"), Decimal("30000.00"), Decimal("0.00")),
    ("102", "Bankalar", Decimal("250000.00"), Decimal("0.00"), Decimal("250000.00"), Decimal("0.00")),
    ("120", "Alıcılar", Decimal("2645000.00"), Decimal("0.00"), Decimal("2645000.00"), Decimal("0.00")),
    ("131", "Ortaklardan Alacaklar", Decimal("150000.00"), Decimal("0.00"), Decimal("150000.00"), Decimal("0.00")),
    ("131.01", "Ortaklardan Alacaklar [ORTAK-A]", Decimal("150000.00"), Decimal("0.00"), Decimal("150000.00"), Decimal("0.00")),
    ("153", "Ticari Mallar", Decimal("450000.00"), Decimal("0.00"), Decimal("450000.00"), Decimal("0.00")),
    ("191", "İndirilecek KDV", Decimal("120000.00"), Decimal("0.00"), Decimal("120000.00"), Decimal("0.00")),
    ("253", "Tesis, Makine ve Cihazlar", Decimal("2500000.00"), Decimal("0.00"), Decimal("2500000.00"), Decimal("0.00")),
    ("257", "Birikmiş Amortismanlar (-)", Decimal("0.00"), Decimal("100000.00"), Decimal("0.00"), Decimal("100000.00")),
    ("320", "Satıcılar", Decimal("0.00"), Decimal("350000.00"), Decimal("0.00"), Decimal("350000.00")),
    ("320.01", "Satıcılar [TEDARIKCI-B]", Decimal("0.00"), Decimal("150000.00"), Decimal("0.00"), Decimal("150000.00")),
    ("331", "Ortaklara Borçlar", Decimal("80000.00"), Decimal("80000.00"), Decimal("0.00"), Decimal("0.00")),
    ("360", "Ödenecek Vergi ve Fonlar", Decimal("0.00"), Decimal("80000.00"), Decimal("0.00"), Decimal("80000.00")),
    ("391", "Hesaplanan KDV", Decimal("0.00"), Decimal("1000000.00"), Decimal("0.00"), Decimal("1000000.00")),
    ("500", "Sermaye", Decimal("0.00"), Decimal("1000000.00"), Decimal("0.00"), Decimal("1000000.00")),
    ("570", "Geçmiş Yıllar Karları", Decimal("0.00"), Decimal("250000.00"), Decimal("0.00"), Decimal("250000.00")),
    ("600", "Yurtiçi Satışlar", Decimal("0.00"), Decimal("4700000.00"), Decimal("0.00"), Decimal("4700000.00")),
    ("601", "Yurtdışı Satışlar", Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00")),
    ("610", "Satıştan İadeler (-)", Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00")),
    ("649", "Diğer Olağan Gelir ve Karlar", Decimal("0.00"), Decimal("50000.00"), Decimal("0.00"), Decimal("50000.00")),
    ("679", "Diğer Olağandışı Gelir ve Karlar", Decimal("0.00"), Decimal("10000.00"), Decimal("0.00"), Decimal("10000.00")),
    ("689", "Diğer Olağandışı Gider ve Zararlar", Decimal("45000.00"), Decimal("0.00"), Decimal("45000.00"), Decimal("0.00")),
    ("690", "Dönem Karı veya Zararı", Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), Decimal("0.00")),
    ("720", "Direkt İşçilik Giderleri", Decimal("320000.00"), Decimal("0.00"), Decimal("320000.00"), Decimal("0.00")),
    ("730", "Genel Üretim Giderleri", Decimal("180000.00"), Decimal("0.00"), Decimal("180000.00"), Decimal("0.00")),
    ("740", "Hizmet Üretim Maliyeti", Decimal("120000.00"), Decimal("0.00"), Decimal("120000.00"), Decimal("0.00")),
    ("760", "Pazarlama Satış Dağıtım Giderleri", Decimal("230000.00"), Decimal("0.00"), Decimal("230000.00"), Decimal("0.00")),
    ("770", "Genel Yönetim Giderleri", Decimal("500000.00"), Decimal("0.00"), Decimal("500000.00"), Decimal("0.00")),  # ANKOR
]


def _denge_dogrula(satirlar: list[tuple[str, str, Decimal, Decimal, Decimal, Decimal]]) -> None:
    toplam_borc = sum((s[2] for s in satirlar), start=Decimal("0"))
    toplam_alacak = sum((s[3] for s in satirlar), start=Decimal("0"))
    toplam_borc_bakiye = sum((s[4] for s in satirlar), start=Decimal("0"))
    toplam_alacak_bakiye = sum((s[5] for s in satirlar), start=Decimal("0"))

    assert toplam_borc == toplam_alacak, (
        f"Mizan dengede degil: borc toplam={toplam_borc} alacak toplam={toplam_alacak}"
    )
    assert toplam_borc_bakiye == toplam_alacak_bakiye, (
        f"Mizan dengede degil: borc bakiye={toplam_borc_bakiye} "
        f"alacak bakiye={toplam_alacak_bakiye}"
    )


def uret(hedef: Path | None = None) -> Path:
    """Deterministik dummy mizan_2025.xlsx uretir; var olan dosyanin uzerine yazar."""
    _denge_dogrula(MIZAN_SATIRLARI)

    hedef = hedef or (Path(__file__).parent / "mizan_2025.xlsx")

    wb = Workbook()
    ws = wb.active
    ws.title = "Mizan 2025"
    ws.append(BASLIKLAR)

    for hesap_kodu, hesap_adi, borc_toplam, alacak_toplam, borc_bakiye, alacak_bakiye in MIZAN_SATIRLARI:
        ws.append(
            [
                hesap_kodu,
                hesap_adi,
                float(borc_toplam),
                float(alacak_toplam),
                float(borc_bakiye),
                float(alacak_bakiye),
            ]
        )

    hedef.parent.mkdir(parents=True, exist_ok=True)
    wb.save(hedef)
    return hedef


def uret_2024(hedef: Path | None = None) -> Path:
    """Deterministik dummy mizan_2024.xlsx uretir (onceki donem karsilastirma
    girdisi, Task 2.2); var olan dosyanin uzerine yazar. Testler bu dosyayi
    degil, dogrudan ``MIZAN_SATIRLARI_2024`` sabitini kullanir."""
    _denge_dogrula(MIZAN_SATIRLARI_2024)

    hedef = hedef or (Path(__file__).parent / "mizan_2024.xlsx")

    wb = Workbook()
    ws = wb.active
    ws.title = "Mizan 2024"
    ws.append(BASLIKLAR)

    for hesap_kodu, hesap_adi, borc_toplam, alacak_toplam, borc_bakiye, alacak_bakiye in MIZAN_SATIRLARI_2024:
        ws.append(
            [
                hesap_kodu,
                hesap_adi,
                float(borc_toplam),
                float(alacak_toplam),
                float(borc_bakiye),
                float(alacak_bakiye),
            ]
        )

    hedef.parent.mkdir(parents=True, exist_ok=True)
    wb.save(hedef)
    return hedef


if __name__ == "__main__":
    yol = uret()
    print(f"Uretildi: {yol}")
    print(f"Satir sayisi: {len(MIZAN_SATIRLARI)}")

    yol_2024 = uret_2024()
    print(f"Uretildi: {yol_2024}")
    print(f"Satir sayisi: {len(MIZAN_SATIRLARI_2024)}")
