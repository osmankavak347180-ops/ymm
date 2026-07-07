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

    return bulgular
