"""KVKK bekci testleri (kalici) — bkz. docs/01-MIMARI.md §6.

1. `anthropic` importu yalniz src/ymm/llm/gateway.py'de olabilir.
2. src/ymm/kontrol/, src/ymm/risk/, src/ymm/llm/ altindaki hicbir dosya:
   (a) ymm.maskeleme.ayirici modulunu IMPORT EDEMEZ -- kimlik.db'ye
       gercekten dokunan (yazan) tek modul budur; herhangi bicimde
       (`import ymm.maskeleme.ayirici`, `from ymm.maskeleme import ayirici`,
       `from ymm.maskeleme.ayirici import kimlik_ayir` -- hepsi dahil)
       import edilmesi izolasyon ihlalidir.
   (b) adinda "kimlik" alt dizgisi gecen HERHANGI baska bir modulu de
       import edemez.
   ymm.maskeleme.dogrulayici importu SERBESTTIR: sizinti_tara/MaskeIhlali
   sozlesmesi salt-okunur bir kontrol katmanidir, kimlik.db'ye yazmaz ve
   adinda "kimlik" ya da "ayirici" gecmez -- yasakli kosullarin hicbirine
   girmez.

   (Onceki surumde bu bekci yalniz import edilen modul ADINDA "kimlik"
   alt dizgisi ariyordu; ancak kimlik.db'ye dokunan gercek modul olan
   ymm.maskeleme.ayirici'nin adinda "kimlik" GECMEZ -- bu da bekcide
   gercek bir delik birakiyordu (Critical-2 bulgusu). Fix: (a) kosulu
   eklendi.)

String arama DEGIL: AST ile Import/ImportFrom dugumleri taranir (yorum
satirindaki yalanci pozitifleri onlemek icin).

Bilinen sinirlama (Minor-4): bu AST bekcileri yalniz STATIK
`import X` / `from X import Y` bicimlerini yakalar. Calisma-zamaninda
modul yukleyen `importlib.import_module("...")` veya `__import__("...")`
cagrilari AST agacinda sadece birer duz fonksiyon cagrisi (ast.Call)
olarak gorunur; bu bekciler bu cagrilarin icindeki string modul adlarini
YORUMLAMAZ / YAKALAMAZ. Dinamik import ile bu bekci atlatilabilir --
bu bilinen ve kabul edilmis bir kapsam disi durumdur (mimar onayli v1).
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC_KOKU = Path(__file__).resolve().parent.parent / "src"


def _py_dosyalari(kok: Path) -> list[Path]:
    return sorted(kok.rglob("*.py"))


def _importlanan_moduller(dosya: Path) -> set[str]:
    """Bir .py dosyasindaki tum import edilen modul adlarini (dotted) doner.

    ImportFrom dugumleri icin hem taban modul (`node.module`) hem de
    `node.module + "." + isim` bicimindeki genisletilmis dotted ad
    eklenir; boylece "from ymm.maskeleme import ayirici" da tipki
    "import ymm.maskeleme.ayirici" gibi "ymm.maskeleme.ayirici" olarak
    yakalanir (from-import kacagi onlenir).
    """
    kaynak = dosya.read_text(encoding="utf-8")
    agac = ast.parse(kaynak, filename=str(dosya))
    moduller: set[str] = set()
    for node in ast.walk(agac):
        if isinstance(node, ast.Import):
            for isim in node.names:
                moduller.add(isim.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                moduller.add(node.module)
                for isim in node.names:
                    moduller.add(f"{node.module}.{isim.name}")
    return moduller


def test_anthropic_importu_sadece_gatewayde_olabilir():
    """anthropic importu bulunan dosyalarin kumesi {"src/ymm/llm/gateway.py"} alt kumesi olmali.

    gateway.py henuz yoksa (bu gorevde), bos kume de gecerlidir (bos kume ⊆ her kume).
    """
    izin_verilen = {"src/ymm/llm/gateway.py"}
    ihlal_eden: set[str] = set()

    for dosya in _py_dosyalari(SRC_KOKU):
        moduller = _importlanan_moduller(dosya)
        if any(m == "anthropic" or m.startswith("anthropic.") for m in moduller):
            goreli_yol = dosya.relative_to(SRC_KOKU.parent).as_posix()
            ihlal_eden.add(goreli_yol)

    assert ihlal_eden <= izin_verilen, (
        f"anthropic importu izin verilenler disinda bulundu: {ihlal_eden - izin_verilen}"
    )


def _kimlik_izolasyon_ihlalleri(kok: Path) -> list[str]:
    """kok altindaki tum .py dosyalarini AST ile tarar, kimlik.db izolasyon
    ihlallerini (aciklayici metin listesi olarak) doner. Bos liste = temiz.

    Parametrik tutulur (kok: Path) ki gercek src/ agacina dokunmadan,
    tmp_path ile sahte dosyalar uzerinde de dogrulanabilsin (RED kaniti).

    Ihlal kosullari:
    (a) modul == "ymm.maskeleme.ayirici" veya bununla baslayan bir alt-yol
        (kimlik.db'ye yazan gercek modul -- herhangi import bicimiyle).
    (b) modul adinda (kucuk harfe cevrilmis) "kimlik" alt dizgisi gecmesi.
    ymm.maskeleme.dogrulayici bu iki kosuldan hicbirine girmedigi icin
    otomatik olarak serbesttir (ozel bir istisna kodu gerekmez).
    """
    ihlaller: list[str] = []
    for dosya in _py_dosyalari(kok):
        for modul in _importlanan_moduller(dosya):
            if modul == "ymm.maskeleme.ayirici" or modul.startswith(
                "ymm.maskeleme.ayirici."
            ):
                ihlaller.append(
                    f"{dosya}: '{modul}' ayirici (kimlik.db yazari) izolasyonunu ihlal ediyor"
                )
            elif "kimlik" in modul.lower():
                ihlaller.append(
                    f"{dosya}: '{modul}' kimlik.db izolasyonunu ihlal ediyor"
                )
    return ihlaller


def test_kontrol_risk_llm_kimlik_modulu_import_etmez():
    """kimlik.db izolasyonu: kontrol/, risk/, llm/ altinda hicbir dosya
    ymm.maskeleme.ayirici'yi (kimlik.db'ye yazan gercek modul, herhangi
    import bicimiyle) veya adinda 'kimlik' gecen baska bir modulu import
    edemez. ymm.maskeleme.dogrulayici importu SERBESTTIR (bkz. modul
    docstring'i / _kimlik_izolasyon_ihlalleri docstring'i)."""
    yasakli_dizin_adlari = ["kontrol", "risk", "llm"]

    for dizin_adi in yasakli_dizin_adlari:
        dizin = SRC_KOKU / "ymm" / dizin_adi
        if not dizin.exists():
            continue
        ihlaller = _kimlik_izolasyon_ihlalleri(dizin)
        assert ihlaller == [], "; ".join(ihlaller)


def test_kimlik_izolasyon_ayirici_import_herhangi_bicimde_yakalanir(tmp_path):
    """Negatif test tekniği: gercek src/ altina dosya yazmadan, tmp_path'te
    sahte bir 'kontrol modulu' olusturup ymm.maskeleme.ayirici'yi from-import
    ile ice aktariyor -- bekci bunu yakalamali (adinda 'kimlik' GECMEDIGI
    halde -- Critical-2'nin tam da yakaladigi delik budur)."""
    sahte = tmp_path / "sahte_kontrol_modulu.py"
    sahte.write_text("from ymm.maskeleme import ayirici\n", encoding="utf-8")

    ihlaller = _kimlik_izolasyon_ihlalleri(tmp_path)

    assert len(ihlaller) == 1
    assert "ayirici" in ihlaller[0]


def test_kimlik_izolasyon_ayirici_dogrudan_import_da_yakalanir(tmp_path):
    """`import ymm.maskeleme.ayirici` bicimi de (from-import olmadan) yakalanmali."""
    sahte = tmp_path / "sahte_risk_modulu.py"
    sahte.write_text("import ymm.maskeleme.ayirici\n", encoding="utf-8")

    ihlaller = _kimlik_izolasyon_ihlalleri(tmp_path)

    assert len(ihlaller) == 1
    assert "ayirici" in ihlaller[0]


def test_kimlik_izolasyon_adinda_kimlik_gecen_modul_yakalanir(tmp_path):
    sahte = tmp_path / "sahte_llm_modulu.py"
    sahte.write_text("import ymm.kimlik_yardimci\n", encoding="utf-8")

    ihlaller = _kimlik_izolasyon_ihlalleri(tmp_path)

    assert len(ihlaller) == 1
    assert "kimlik" in ihlaller[0]


def test_kimlik_izolasyon_dogrulayici_importuna_izin_verir(tmp_path):
    """ymm.maskeleme.dogrulayici (sizinti_tara/MaskeIhlali) importu serbest
    olmali -- ihlal listesi bos donmeli."""
    sahte = tmp_path / "sahte_kontrol_modulu.py"
    sahte.write_text("from ymm.maskeleme import dogrulayici\n", encoding="utf-8")

    ihlaller = _kimlik_izolasyon_ihlalleri(tmp_path)

    assert ihlaller == []
