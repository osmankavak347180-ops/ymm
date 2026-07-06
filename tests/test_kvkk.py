"""KVKK bekci testleri (kalici) — bkz. docs/01-MIMARI.md §6.

1. `anthropic` importu yalniz src/ymm/llm/gateway.py'de olabilir.
2. src/ymm/kontrol/, src/ymm/risk/, src/ymm/llm/ altindaki hicbir dosya
   'kimlik' kelimesini iceren bir modulu import etmemeli (kimlik.db izolasyonu).

String arama DEGIL: AST ile Import/ImportFrom dugumleri taranir (yorum
satirindaki yalanci pozitifleri onlemek icin).
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC_KOKU = Path(__file__).resolve().parent.parent / "src"


def _py_dosyalari(kok: Path) -> list[Path]:
    return sorted(kok.rglob("*.py"))


def _importlanan_moduller(dosya: Path) -> set[str]:
    """Bir .py dosyasindaki tum import edilen modul adlarini (dotted) doner."""
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


def test_kontrol_risk_llm_kimlik_modulu_import_etmez():
    """kimlik.db izolasyonu: kontrol/, risk/, llm/ altinda 'kimlik' iceren modul importu yasak."""
    yasakli_dizin_adlari = ["kontrol", "risk", "llm"]

    for dizin_adi in yasakli_dizin_adlari:
        dizin = SRC_KOKU / "ymm" / dizin_adi
        if not dizin.exists():
            continue
        for dosya in _py_dosyalari(dizin):
            moduller = _importlanan_moduller(dosya)
            for modul in moduller:
                assert "kimlik" not in modul.lower(), (
                    f"{dosya}: '{modul}' kimlik.db izolasyonunu ihlal ediyor "
                    f"({dizin_adi}/ altinda 'kimlik' iceren modul import edilemez)"
                )
