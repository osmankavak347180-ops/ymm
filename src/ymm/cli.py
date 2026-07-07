"""CLI v1 (Task 2.3): `ymm yukle mizan/beyanname-ozet`, `kontrol`, `tara`,
`bulgular` — bkz. docs/01-MIMARI.md §7, .superpowers/sdd/task-2.3-brief.md.

KVKK: bu dosya `anthropic` IMPORT ETMEZ (bkz. tests/test_kvkk.py — o test bu
dosyaya dokunmaz ama ilke aynıdır). `ymm.maskeleme.ayirici` (kimlik.db'ye
yazan TEK modül) yalnızca `yukle mizan` komutunda, tek bir fonksiyon
içindeki akışta kullanılır: mizan_oku -> kimlik_ayir -> depo. Bu adım
ATLANAMAZ -- maskesiz bir ara çıktı/parametre yoktur.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

from ymm.db.depo import Depo
from ymm.kontrol.motor import konfig_yukle, kontrolleri_calistir
from ymm.maskeleme.ayirici import kimlik_ayir
from ymm.modeller import Bulgu, Donem
from ymm.parsers.beyanname.gecici import gecici_parse
from ymm.parsers.beyanname.kdv import kdv_parse
from ymm.parsers.beyanname.kurumlar import kv_parse
from ymm.parsers.beyanname.muhtasar import muhsgk_parse
from ymm.parsers.mizan import mizan_oku
from ymm.risk.seviye import GECERLI_SEVIYELER
from ymm.risk.tarayici import risk_konfig_yukle, riskleri_tara

app = typer.Typer(help="YMM Tam Tasdik Raporu Asistanı — CLI v1 (LLM'siz).")
yukle_app = typer.Typer(help="Veri yükleme komutları (mizan, beyanname özeti).")
app.add_typer(yukle_app, name="yukle")

console = Console()

_VARSAYILAN_VERI_DB = Path("data/veri.db")
_VARSAYILAN_KIMLIK_DB = Path("data/kimlik.db")
_VARSAYILAN_KOLON_HARITASI = Path("config/kolon_haritasi.yaml")
_VARSAYILAN_KONTROL_KONFIG = Path("config/kontrol_kurallari.yaml")
_VARSAYILAN_RISK_KONFIG = Path("config/risk_hesaplari.yaml")

# bulgular çıktı sırası: yüksek -> orta -> düşük.
_SEVIYE_SIRASI = {"yuksek": 0, "orta": 1, "dusuk": 2}

# Task 3.2: beyanname tipi -> (parser, dönem biçimi açıklaması). Dönem
# çözümleme tipi `_beyanname_donem_coz` içindedir (AY/CEYREK/YILLIK).
_BEYANNAME_PARSERLAR = {
    "KDV1": kdv_parse,
    "MUHSGK": muhsgk_parse,
    "GECICI": gecici_parse,
    "KV": kv_parse,
}
_DONEM_BICIMLERI = {
    "KDV1": "YYYY-MM (ör. 2025-03)",
    "MUHSGK": "YYYY-MM (ör. 2025-03)",
    "GECICI": "YYYY-QN (ör. 2025-Q4)",
    "KV": "YYYY (ör. 2025)",
}

_logger = logging.getLogger(__name__)


def _mukellef_id_al_veya_olustur(depo: Depo, takma_kod: str) -> int:
    mukellef_id = depo.mukellef_bul(takma_kod)
    if mukellef_id is None:
        mukellef_id = depo.mukellef_ekle(takma_kod)
    return mukellef_id


def _mukellef_id_al_zorunlu(depo: Depo, takma_kod: str) -> int:
    """`kontrol`/`tara`/`bulgular` gibi salt-okunur komutlarda mükellef yoksa
    yeni oluşturmak yerine anlaşılır hatayla çıkılır (yazma akışı `yukle`
    komutlarına özgüdür)."""
    mukellef_id = depo.mukellef_bul(takma_kod)
    if mukellef_id is None:
        console.print(f"[red]Mükellef bulunamadı: {takma_kod!r}[/red]")
        raise typer.Exit(code=1)
    return mukellef_id


def _detay_kisa(detay: dict) -> str:
    metin = detay.get("aciklama") or detay.get("not") or ""
    metin = str(metin).strip()
    if not metin:
        metin = ", ".join(f"{k}={v}" for k, v in detay.items() if v not in (None, ""))
    if len(metin) > 70:
        metin = metin[:67] + "..."
    return metin


def _bulgu_tablosu_bas(bulgular: list[Bulgu], baslik: str) -> None:
    tablo = Table(title=baslik)
    tablo.add_column("Kaynak")
    tablo.add_column("Kontrol Kodu")
    tablo.add_column("Seviye")
    tablo.add_column("Tutar Fark", justify="right")
    tablo.add_column("Yüzde Fark", justify="right")
    tablo.add_column("Detay")

    for bulgu in bulgular:
        tablo.add_row(
            bulgu.kaynak,
            bulgu.kontrol_kodu,
            bulgu.seviye,
            "-" if bulgu.tutar_fark is None else str(bulgu.tutar_fark),
            "-" if bulgu.yuzde_fark is None else f"{bulgu.yuzde_fark:.2f}",
            _detay_kisa(bulgu.detay),
        )

    if not bulgular:
        console.print(f"[yellow]{baslik}: bulgu yok.[/yellow]")
        return
    console.print(tablo)


@yukle_app.command("mizan")
def yukle_mizan(
    dosya: Path = typer.Argument(..., exists=True, readable=True, help="Mizan Excel dosyası."),
    mukellef: str = typer.Option(..., "--mukellef", help="Mükellef takma kodu (ör. MUK-001)."),
    yil: int = typer.Option(..., "--yil", help="Mizan yılı."),
    harita: Path = typer.Option(
        _VARSAYILAN_KOLON_HARITASI, "--harita", help="Kolon haritası YAML dosyası."
    ),
    veri_db: Path = typer.Option(_VARSAYILAN_VERI_DB, "--veri-db", help="veri.db yolu."),
    kimlik_db: Path = typer.Option(_VARSAYILAN_KIMLIK_DB, "--kimlik-db", help="kimlik.db yolu."),
) -> None:
    """Mizan Excel dosyasını okur, kimlik maskelemesini uygular ve depoya
    yazar. Akış TEK fonksiyonda: mizan_oku -> kimlik_ayir -> depo -- maskeleme
    adımı atlanamaz, ara (maskesiz) çıktı üretilmez.

    Aynı (mükellef, yıl) için YILLIK dönem zaten varsa, eski mizan satırları
    silinip yenisi yazılır (v1 politikası).
    """
    harita_dict = yaml.safe_load(harita.read_text(encoding="utf-8"))

    satirlar = mizan_oku(dosya, harita_dict)
    maskeli_satirlar = kimlik_ayir(satirlar, kimlik_db)

    depo = Depo(veri_db)
    mukellef_id = _mukellef_id_al_veya_olustur(depo, mukellef)

    donem_id = depo.donem_bul(mukellef_id, yil, "YILLIK")
    if donem_id is None:
        donem_id = depo.donem_ekle(mukellef_id, Donem(yil=yil, tip="YILLIK", sira=0))
    else:
        depo.mizan_sil(donem_id)

    depo.mizan_yaz(donem_id, maskeli_satirlar)

    console.print(
        f"[green]{len(maskeli_satirlar)} mizan satırı yüklendi[/green] "
        f"(mükellef={mukellef}, yıl={yil})."
    )


@yukle_app.command("beyanname-ozet")
def yukle_beyanname_ozet(
    dosya: Path = typer.Argument(
        ..., exists=True, readable=True, help="beyanname_ozet.json formatındaki dosya."
    ),
    mukellef: str = typer.Option(..., "--mukellef", help="Mükellef takma kodu (ör. MUK-001)."),
    veri_db: Path = typer.Option(_VARSAYILAN_VERI_DB, "--veri-db", help="veri.db yolu."),
) -> None:
    """`beyanname_ozet.json` formatındaki kayıtları ({"beyannameler": [...]})
    depoya yazar; dönem yoksa oluşturur. Bu, ileride PDF parser çıktısının da
    gireceği yoldur (Task 3.1 PDF akışı bu komuta bağlanacak).
    """
    veri = json.loads(dosya.read_text(encoding="utf-8"))

    depo = Depo(veri_db)
    mukellef_id = _mukellef_id_al_veya_olustur(depo, mukellef)

    # YILLIK (sira=0) dönemler aynı (mükellef, yıl) için PAYLAŞILIR (bkz.
    # tests/test_kontrol_entegrasyon.py -- mizan da aynı YILLIK dönemi
    # kullanır); diğer dönem tipleri (AY/CEYREK) için her kayıt kendi dönemini
    # oluşturur.
    yillik_donem_idler: dict[int, int] = {}
    yazilan = 0

    for kayit in veri["beyannameler"]:
        kayit_yil = kayit["yil"]
        donem_tip = kayit["donem_tip"]
        sira = kayit["sira"]

        if donem_tip == "YILLIK" and sira == 0:
            if kayit_yil not in yillik_donem_idler:
                donem_id = depo.donem_bul(mukellef_id, kayit_yil, "YILLIK")
                if donem_id is None:
                    donem_id = depo.donem_ekle(
                        mukellef_id, Donem(yil=kayit_yil, tip="YILLIK", sira=0)
                    )
                yillik_donem_idler[kayit_yil] = donem_id
            donem_id = yillik_donem_idler[kayit_yil]
        else:
            donem_id = depo.donem_ekle(
                mukellef_id, Donem(yil=kayit_yil, tip=donem_tip, sira=sira)
            )

        depo.beyanname_yaz(donem_id, kayit["tip"], kayit["alanlar"])
        yazilan += 1

    console.print(f"[green]{yazilan} beyanname kaydı yüklendi[/green] (mükellef={mukellef}).")


def _beyanname_donem_coz(tip: str, donem: str) -> tuple[int, str, int]:
    """`--donem` değerini beyanname tipine göre (yil, donem_tip, sira)
    üçlüsüne çözer. Geçersiz biçimde beklenen biçimi söyleyen `ValueError`
    fırlatır (çağıran traceback göstermeden kullanıcıya yansıtır).

    KDV1/MUHSGK: YYYY-MM -> AY(sira=ay); GECICI: YYYY-QN -> CEYREK(sira=N);
    KV: YYYY -> YILLIK(sira=0).
    """
    beklenen = _DONEM_BICIMLERI[tip]
    if tip in ("KDV1", "MUHSGK"):
        try:
            donem_dt = datetime.strptime(donem, "%Y-%m")
        except ValueError:
            raise ValueError(
                f"Geçersiz --donem değeri: {donem!r} (beklenen biçim: {beklenen})"
            ) from None
        return donem_dt.year, "AY", donem_dt.month
    if tip == "GECICI":
        eslesme = re.fullmatch(r"(\d{4})-Q([1-4])", donem)
        if eslesme is None:
            raise ValueError(
                f"Geçersiz --donem değeri: {donem!r} (beklenen biçim: {beklenen})"
            )
        return int(eslesme.group(1)), "CEYREK", int(eslesme.group(2))
    if tip == "KV":
        eslesme = re.fullmatch(r"\d{4}", donem)
        if eslesme is None:
            raise ValueError(
                f"Geçersiz --donem değeri: {donem!r} (beklenen biçim: {beklenen})"
            )
        return int(donem), "YILLIK", 0
    raise ValueError(f"Bilinmeyen beyanname tipi: {tip!r}")


@yukle_app.command("beyanname")
def yukle_beyanname(
    dosya: Path = typer.Argument(..., exists=True, readable=True, help="Beyanname PDF dosyası."),
    tip: str = typer.Option(
        ..., "--tip", help=f"Beyanname tipi ({'/'.join(_BEYANNAME_PARSERLAR)})."
    ),
    donem: str = typer.Option(
        ...,
        "--donem",
        help="Dönem; biçim tipe göre: KDV1/MUHSGK=YYYY-MM, GECICI=YYYY-QN, KV=YYYY.",
    ),
    mukellef: str = typer.Option(..., "--mukellef", help="Mükellef takma kodu (ör. MUK-001)."),
    onayla: bool = typer.Option(
        False,
        "--onayla",
        help="Verilmezse yalnız önizleme yapılır, DB'ye yazılmaz (R3 azaltımı).",
    ),
    veri_db: Path = typer.Option(_VARSAYILAN_VERI_DB, "--veri-db", help="veri.db yolu."),
) -> None:
    """Beyanname PDF'ini (KDV1/MUHSGK/GECICI/KV) parse eder, sonucu rich
    tabloda gösterir. `--onayla` verilmeden DB'ye YAZILMAZ -- YMM önce ekran
    başında inceler (bkz. docs/01-MIMARI.md R3 azaltımı).

    KVKK: yalnızca tutar alanları işlenir; mükellef kimlik bilgisi (unvan,
    VKN, adres) bu akışın hiçbir aşamasında okunmaz/saklanmaz.
    """
    parser = _BEYANNAME_PARSERLAR.get(tip)
    if parser is None:
        console.print(
            f"[red]--tip {tip!r} desteklenmiyor "
            f"(geçerli tipler: {', '.join(_BEYANNAME_PARSERLAR)}).[/red]"
        )
        raise typer.Exit(code=1)

    try:
        yil, donem_tip, sira = _beyanname_donem_coz(tip, donem)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from None

    try:
        alanlar = parser(dosya)
    except ValueError as exc:
        console.print(f"[red]PDF ayrıştırma hatası: {exc}[/red]")
        raise typer.Exit(code=1) from None

    tablo = Table(title=f"{tip} Parse Sonucu — {mukellef} / {donem}")
    tablo.add_column("Alan")
    tablo.add_column("Değer", justify="right")
    for alan, deger in alanlar.items():
        if deger is None:
            tablo.add_row(alan, "[yellow]BULUNAMADI[/yellow]")
        else:
            tablo.add_row(alan, str(deger))
    console.print(tablo)

    if not onayla:
        console.print(
            "[yellow]İncelendi mi? Yazmak için --onayla ile tekrar çalıştırın.[/yellow]"
        )
        raise typer.Exit(code=0)

    depo = Depo(veri_db)
    mukellef_id = _mukellef_id_al_veya_olustur(depo, mukellef)

    donem_id = depo.donem_bul(mukellef_id, yil, donem_tip, sira=sira)
    if donem_id is None:
        donem_id = depo.donem_ekle(mukellef_id, Donem(yil=yil, tip=donem_tip, sira=sira))

    # None dönen alanlar dict'e KONMAZ -- eksik alan konvansiyonu (kontrol
    # motoru `EksikAlanHatasi` exception'ı yakalayıp o kontrolü atlar,
    # bkz. kontrol/motor.py & kontrol/donem.py).
    yazilacak_alanlar = {alan: str(deger) for alan, deger in alanlar.items() if deger is not None}
    depo.beyanname_yaz(donem_id, tip, yazilacak_alanlar)

    console.print(
        f"[green]{tip} beyannamesi kaydedildi[/green] (mükellef={mukellef}, dönem={donem})."
    )


@app.command("kontrol")
def kontrol(
    mukellef: str = typer.Option(..., "--mukellef", help="Mükellef takma kodu."),
    yil: int = typer.Option(..., "--yil", help="Kontrol edilecek yıl."),
    konfig_yolu: Path = typer.Option(
        _VARSAYILAN_KONTROL_KONFIG, "--konfig", help="Kontrol kuralları YAML dosyası."
    ),
    veri_db: Path = typer.Option(_VARSAYILAN_VERI_DB, "--veri-db", help="veri.db yolu."),
) -> None:
    """Modül A (çapraz kontrol) kurallarını çalıştırır, bulguları depoya
    yazar ve rich tablo olarak gösterir."""
    depo = Depo(veri_db)
    mukellef_id = _mukellef_id_al_zorunlu(depo, mukellef)

    try:
        konfig = konfig_yukle(konfig_yolu)
    except ValueError as exc:
        console.print(f"[red]Kontrol konfig hatası: {exc}[/red]")
        raise typer.Exit(code=1) from None

    depo.bulgu_sil(mukellef_id, yil, "A")
    bulgular = kontrolleri_calistir(depo, mukellef_id, yil, konfig)
    depo.bulgu_yaz(bulgular)
    _bulgu_tablosu_bas(bulgular, f"Kontrol Sonuçları (Modül A) — {mukellef} / {yil}")


@app.command("tara")
def tara(
    mukellef: str = typer.Option(..., "--mukellef", help="Mükellef takma kodu."),
    yil: int = typer.Option(..., "--yil", help="Taranacak yıl."),
    konfig_yolu: Path = typer.Option(
        _VARSAYILAN_RISK_KONFIG, "--konfig", help="Risk kuralları YAML dosyası."
    ),
    veri_db: Path = typer.Option(_VARSAYILAN_VERI_DB, "--veri-db", help="veri.db yolu."),
) -> None:
    """Modül B (riskli hesap taraması) kurallarını çalıştırır, bulguları
    depoya yazar ve rich tablo olarak gösterir."""
    depo = Depo(veri_db)
    mukellef_id = _mukellef_id_al_zorunlu(depo, mukellef)

    try:
        konfig = risk_konfig_yukle(konfig_yolu)
    except ValueError as exc:
        console.print(f"[red]Risk konfig hatası: {exc}[/red]")
        raise typer.Exit(code=1) from None

    depo.bulgu_sil(mukellef_id, yil, "B")
    bulgular = riskleri_tara(depo, mukellef_id, yil, konfig)
    depo.bulgu_yaz(bulgular)
    _bulgu_tablosu_bas(bulgular, f"Risk Taraması (Modül B) — {mukellef} / {yil}")


@app.command("bulgular")
def bulgular_komutu(
    mukellef: str = typer.Option(..., "--mukellef", help="Mükellef takma kodu."),
    yil: int = typer.Option(..., "--yil", help="Yıl."),
    seviye: str | None = typer.Option(
        None, "--seviye", help=f"Seviye filtresi ({'/'.join(GECERLI_SEVIYELER)})."
    ),
    veri_db: Path = typer.Option(_VARSAYILAN_VERI_DB, "--veri-db", help="veri.db yolu."),
) -> None:
    """Depodaki bulguları (Modül A + B) rich tabloda gösterir. `--seviye`
    verilirse yalnız o seviye gösterilir. Sıralama: yüksek -> orta -> düşük.
    """
    if seviye is not None and seviye not in GECERLI_SEVIYELER:
        console.print(
            f"[red]Geçersiz --seviye değeri: {seviye!r} "
            f"(geçerli: {', '.join(GECERLI_SEVIYELER)})[/red]"
        )
        raise typer.Exit(code=1)

    depo = Depo(veri_db)
    mukellef_id = _mukellef_id_al_zorunlu(depo, mukellef)

    bulgular = depo.bulgular(mukellef_id, yil)
    if seviye is not None:
        bulgular = [b for b in bulgular if b.seviye == seviye]
    bulgular = sorted(bulgular, key=lambda b: _SEVIYE_SIRASI.get(b.seviye, 99))

    baslik = f"Bulgular — {mukellef} / {yil}"
    if seviye is not None:
        baslik += f" (seviye={seviye})"
    _bulgu_tablosu_bas(bulgular, baslik)


if __name__ == "__main__":
    app()
