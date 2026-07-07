"""Risk tarayıcı (MODÜL B): statik risk kurallarını ``config/risk_hesaplari.yaml``
konfigürasyonundan okur, mükellefin YILLIK dönem mizanına uygular ve Bulgu
listesi üretir.

Mutlak kurallar (bkz. .claude/agents/risk-tarama.md): tamamen yerel/deterministik
— LLM çağrısı, ağ erişimi, ``anthropic`` importu YOK; tüm tutarlar
``decimal.Decimal``; risk seviyesini KOD değil config (YAML) atar.

Modül izolasyonu (Task 2.1 mimar kararı): ``kontrol/kurallar.py``'deki hesap
eşleştirme mantığı buraya İMPORT EDİLMEZ. Aşağıdaki ``_hesap_degeri`` /
``_hesap_adi`` fonksiyonları ``kontrol/kurallar.py::hesap_degeri`` ile AYNI
KONVANSİYONU uygular (ana hesap TAM eşleşirse öncelik — alt hesaplar yok
sayılır, çifte sayma yok; ana hesap yoksa "prefix." önekli alt hesaplar
toplanır) ama bilinçli olarak bağımsız bir kopyadır.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

from ymm.db.depo import Depo
from ymm.modeller import Bulgu, MizanSatiri
from ymm.risk.seviye import seviye_dogrula

_logger = logging.getLogger(__name__)

# risk_konfig_yukle fail-fast doğrulaması: bilinmeyen kural tipi burada
# reddedilir (Modül A'daki enum ön-doğrulaması konvansiyonuyla tutarlı).
_GECERLI_KURAL_TIPLERI = ("bakiye_var", "bakiye_esik_ustu")

# Task 2.2 — önceki dönem karşılaştırmalı kural tipleri.
_GECERLI_KARSILASTIRMALI_KURAL_TIPLERI = ("yuzde_degisim",)


def _bakiye(satir: MizanSatiri) -> Decimal:
    """Hesap değeri konvansiyonu: borç bakiyesi > 0 ise borç bakiyesi, değilse
    alacak bakiyesi (bkz. modül docstring'i — kontrol/kurallar.py ile aynı
    konvansiyon, bağımsız kopya)."""
    return satir.borc_bakiye if satir.borc_bakiye > 0 else satir.alacak_bakiye


def _ana_hesaplar(satirlar: list[MizanSatiri], hesap_prefix: str) -> list[MizanSatiri]:
    return [s for s in satirlar if s.hesap_kodu == hesap_prefix]


def _alt_hesaplar(satirlar: list[MizanSatiri], hesap_prefix: str) -> list[MizanSatiri]:
    return [s for s in satirlar if s.hesap_kodu.startswith(hesap_prefix + ".")]


def _hesap_degeri(satirlar: list[MizanSatiri], hesap_prefix: str) -> Decimal:
    """``hesap_prefix``'in mizan değeri: ana hesap TAM eşleşirse yalnız o
    kullanılır (alt hesaplar yok sayılır — çifte sayma yok); ana hesap yoksa
    "prefix." önekli alt hesaplar toplanır. Hiç eşleşme yoksa ``Decimal("0")``.
    """
    ana_hesaplar = _ana_hesaplar(satirlar, hesap_prefix)
    if ana_hesaplar:
        return sum((_bakiye(s) for s in ana_hesaplar), Decimal("0"))

    alt_hesaplar = _alt_hesaplar(satirlar, hesap_prefix)
    return sum((_bakiye(s) for s in alt_hesaplar), Decimal("0"))


def _hesap_adi(satirlar: list[MizanSatiri], hesap_prefix: str) -> str | None:
    """Detay için hesap adı: ana hesap TAM eşleşirse onun adı, yoksa ilk alt
    hesabın adı; hiç eşleşme yoksa ``None``."""
    ana_hesaplar = _ana_hesaplar(satirlar, hesap_prefix)
    if ana_hesaplar:
        return ana_hesaplar[0].hesap_adi
    alt_hesaplar = _alt_hesaplar(satirlar, hesap_prefix)
    if alt_hesaplar:
        return alt_hesaplar[0].hesap_adi
    return None


def risk_konfig_yukle(yol: str | Path) -> dict:
    """``config/risk_hesaplari.yaml`` (veya eşdeğer) dosyasını okur ve yükleme
    anında ön-doğrular (fail-fast, Modül A ``kontrol/motor.py::konfig_yukle``
    ile aynı konvansiyon): bilinmeyen kural tipi, geçersiz seviye ya da
    ``bakiye_esik_ustu`` için Decimal'e çevrilemeyen ``esik`` — hepsi burada
    ``ValueError`` ile reddedilir, çalışma zamanına bırakılmaz.
    """
    konfig = yaml.safe_load(Path(yol).read_text(encoding="utf-8"))

    for kural in konfig.get("statik", []):
        kod = kural.get("kod")
        tip = kural.get("kural")
        if tip not in _GECERLI_KURAL_TIPLERI:
            raise ValueError(
                f"Kural {kod!r}: bilinmeyen kural tipi: {tip!r} "
                f"(geçerli: {_GECERLI_KURAL_TIPLERI})"
            )

        seviye_dogrula(kural.get("seviye"), baglam=f"kural {kod!r}")

        if tip == "bakiye_esik_ustu":
            esik = kural.get("esik")
            try:
                Decimal(str(esik))
            except (InvalidOperation, TypeError):
                raise ValueError(
                    f"Kural {kod!r}: esik Decimal'e çevrilemiyor: {esik!r}"
                ) from None

    for kural in konfig.get("karsilastirmali", []):
        kod = kural.get("kod")
        tip = kural.get("kural")
        if tip not in _GECERLI_KARSILASTIRMALI_KURAL_TIPLERI:
            raise ValueError(
                f"Kural {kod!r}: bilinmeyen kural tipi: {tip!r} "
                f"(geçerli: {_GECERLI_KARSILASTIRMALI_KURAL_TIPLERI})"
            )

        seviye_dogrula(kural.get("seviye"), baglam=f"kural {kod!r}")

        esik_yuzde = kural.get("esik_yuzde")
        if isinstance(esik_yuzde, bool) or not isinstance(esik_yuzde, (int, float)):
            raise ValueError(
                f"Kural {kod!r}: esik_yuzde sayı olmalı: {esik_yuzde!r}"
            )

        esik_mutlak_taban = kural.get("esik_mutlak_taban")
        try:
            Decimal(str(esik_mutlak_taban))
        except (InvalidOperation, TypeError):
            raise ValueError(
                f"Kural {kod!r}: esik_mutlak_taban Decimal'e çevrilemiyor: "
                f"{esik_mutlak_taban!r}"
            ) from None

    return konfig


def _bulgu_uretir_mi(deger: Decimal, kural: dict) -> bool:
    """Kural tipine göre bulgu üretilip üretilmeyeceğine karar verir.

    Eşik karşılaştırması KATI (``>``): değer == esik tam eşitlik durumunda
    tolerans İÇİNDE sayılır, bulgu ÜRETİLMEZ (Modül A "tam eşitlik tolerans
    içi" konvansiyonuyla tutarlı).
    """
    tip = kural["kural"]
    if tip == "bakiye_var":
        return deger > 0
    # "bakiye_esik_ustu" — risk_konfig_yukle ile önceden doğrulanmıştır.
    esik = Decimal(str(kural["esik"]))
    return deger > esik


def _karsilastirma_bulgu_uret(
    kural: dict, cari: Decimal, onceki: Decimal, mukellef_id: int, yil: int
) -> Bulgu | None:
    """Tek bir ``karsilastirmali`` kuralı (``yuzde_degisim``) cari/önceki
    dönem değerlerine uygular; tetiklenirse ``Bulgu`` döner, tetiklenmezse
    ``None`` (bkz. mimar kararları — Task 2.2 raporu).

    - Önceki dönem değeri 0 ise yüzde tanımsızdır: yalnız cari, tabanı KATI
      (``>``) aşıyorsa "yeni oluşan yüksek bakiye" bulgusu üretilir
      (``yuzde_fark=None``).
    - Önceki dönem değeri 0 değilse: cari, tabanın ALTINDAYSA (``<``, taban
      dahil değil — cari == taban değerlendirilir) yüzdeye hiç bakılmaz,
      bulgu üretilmez. Aksi halde değişim yüzdesi hesaplanır; eşiği KATI
      (``>``) aşarsa bulgu üretilir.
    """
    hesap_prefix = kural["hesap_prefix"]
    esik_mutlak_taban = Decimal(str(kural["esik_mutlak_taban"]))
    tutar_fark = abs(cari - onceki)

    if onceki == 0:
        if cari <= esik_mutlak_taban:
            return None
        detay = {
            "hesap_kodu": hesap_prefix,
            "cari": str(cari),
            "onceki": str(onceki),
            "yon": "artis",
            "esik_yuzde": kural["esik_yuzde"],
            "esik_mutlak_taban": esik_mutlak_taban,
            "not": "yeni oluşan yüksek bakiye",
        }
        return Bulgu(
            kaynak="B",
            kontrol_kodu=kural["kod"],
            seviye=kural["seviye"],
            tutar_fark=tutar_fark,
            yuzde_fark=None,
            detay=detay,
            mukellef_id=mukellef_id,
            yil=yil,
        )

    if cari < esik_mutlak_taban:
        return None

    yuzde_fark = float(tutar_fark / onceki * 100)
    esik_yuzde = float(kural["esik_yuzde"])
    if yuzde_fark <= esik_yuzde:
        return None

    yon = "artis" if cari > onceki else "azalis"
    detay = {
        "hesap_kodu": hesap_prefix,
        "cari": str(cari),
        "onceki": str(onceki),
        "yon": yon,
        "esik_yuzde": kural["esik_yuzde"],
        "esik_mutlak_taban": esik_mutlak_taban,
        "not": kural.get("not"),
    }
    return Bulgu(
        kaynak="B",
        kontrol_kodu=kural["kod"],
        seviye=kural["seviye"],
        tutar_fark=tutar_fark,
        yuzde_fark=yuzde_fark,
        detay=detay,
        mukellef_id=mukellef_id,
        yil=yil,
    )


def riskleri_tara(depo: Depo, mukellef_id: int, yil: int, konfig: dict) -> list[Bulgu]:
    """``konfig["statik"]`` listesindeki her statik risk kuralını mükellefin
    ilgili yıla ait YILLIK dönem mizanına uygular ve tetiklenen kurallar için
    ``Bulgu`` üretir.

    Dönem bulunamazsa (mizan henüz yüklenmemiş) çökme yerine boş liste döner
    ve ``_logger.warning`` ile iz bırakır (motor.py'deki "çökme yasak, sessiz
    sıfır de yasak" ilkesiyle tutarlı — burada iz bırakılan tek şey uyarıdır).
    """
    donem_id = depo.donem_bul(mukellef_id, yil, "YILLIK")
    if donem_id is None:
        _logger.warning(
            "Mükellef %s için %s yılı YILLIK dönem bulunamadı; risk taraması atlandı.",
            mukellef_id,
            yil,
        )
        return []

    satirlar = depo.mizan_oku(donem_id)
    bulgular: list[Bulgu] = []

    for kural in konfig.get("statik", []):
        hesap_prefix = kural["hesap_prefix"]
        deger = _hesap_degeri(satirlar, hesap_prefix)

        if not _bulgu_uretir_mi(deger, kural):
            continue

        detay = {
            "hesap_kodu": hesap_prefix,
            "hesap_adi": _hesap_adi(satirlar, hesap_prefix),
            "kural": kural["kural"],
            "not": kural.get("not"),
        }
        if kural["kural"] == "bakiye_esik_ustu":
            detay["esik"] = Decimal(str(kural["esik"]))

        bulgular.append(
            Bulgu(
                kaynak="B",
                kontrol_kodu=kural["kod"],
                seviye=kural["seviye"],
                tutar_fark=deger,
                yuzde_fark=None,
                detay=detay,
                mukellef_id=mukellef_id,
                yil=yil,
            )
        )

    karsilastirmali_kurallar = konfig.get("karsilastirmali", [])
    if karsilastirmali_kurallar:
        onceki_donem_id = depo.donem_bul(mukellef_id, yil - 1, "YILLIK")
        if onceki_donem_id is None:
            _logger.warning(
                "Mükellef %s için %s yılı önceki dönem (%s) YILLIK mizanı "
                "bulunamadı; karşılaştırmalı risk taraması atlandı.",
                mukellef_id,
                yil,
                yil - 1,
            )
        else:
            onceki_satirlar = depo.mizan_oku(onceki_donem_id)
            for kural in karsilastirmali_kurallar:
                hesap_prefix = kural["hesap_prefix"]
                cari = _hesap_degeri(satirlar, hesap_prefix)
                onceki = _hesap_degeri(onceki_satirlar, hesap_prefix)
                bulgu = _karsilastirma_bulgu_uret(kural, cari, onceki, mukellef_id, yil)
                if bulgu is not None:
                    bulgular.append(bulgu)

    return bulgular
