"""LLM geçidi — projede `anthropic` import etmeye yetkili TEK dosya
(Task 4.1; bekçi: tests/test_kvkk.py).

KVKK — MUTLAK KURALLAR (docs/01-MIMARI.md §6, kök CLAUDE.md):
1. Her istekte `maskeleme.dogrulayici.sizinti_tara` ÖNCE çalışır — hem
   kullanıcı istemi hem sistem istemi taranır. Bulgu varsa `MaskeIhlali`
   fırlatılır; API çağrılmaz, istem diske YAZILMAZ (log dosyası kimlik
   sızdırırdı). Bypass parametresi / "debug modu" EKLENMEZ.
2. Bu modül kimlik.db'yi yalnız SALT-OKUNUR sızıntı taraması için
   `dogrulayici`ye geçirir; kendisi açmaz (bekçi: ayirici importu yasak).
3. Temiz isteklerde denetim izi: `output/llm_log/` altına istek+yanıt JSON.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import anthropic

from ymm.maskeleme.dogrulayici import MaskeIhlali, sizinti_tara

_MODEL = "claude-sonnet-5"
_MAX_TOKENS = 16000
_LOG_DIZINI = Path("output/llm_log")


def _istemci_olustur() -> anthropic.Anthropic:
    """anthropic istemcisini kurar. Testler bu fonksiyonu mock'lar —
    gerçek API çağrısı test suite'inde HİÇ yapılmaz."""
    return anthropic.Anthropic()


def _api_anahtari_dogrula() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY ortam değişkeni tanımlı değil. LLM geçidi "
            "anahtarsız çalışamaz — anahtarı tanımlayın (setx ANTHROPIC_API_KEY ...) "
            "veya LLM'siz akışları (kontrol/tara/bulgular) kullanın."
        )


def _denetim_izi_yaz(istem: str, sistem: str, yanit_metni: str) -> None:
    """İstek+yanıtı `output/llm_log/` altına JSON olarak yazar (denetim izi).
    Yalnız sızıntı taramasından GEÇMİŞ (maskeli) metinler buraya ulaşır."""
    _LOG_DIZINI.mkdir(parents=True, exist_ok=True)
    dosya = _LOG_DIZINI / (
        f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.json"
    )
    dosya.write_text(
        json.dumps(
            {
                "zaman": datetime.now().isoformat(),
                "model": _MODEL,
                "sistem": sistem,
                "istem": istem,
                "yanit": yanit_metni,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def uret(istem: str, sistem: str, kimlik_db: Path) -> str:
    """İstemi LLM'e gönderir, yanıt metnini döner (imza: docs/01-MIMARI.md).

    Akış: sızıntı taraması (istem + sistem) -> API anahtarı kontrolü ->
    API çağrısı -> denetim izi -> yanıt. Sızıntı bulunursa `MaskeIhlali`
    fırlatılır ve API HİÇ çağrılmaz.
    """
    bulgular = sizinti_tara(istem, kimlik_db) + sizinti_tara(sistem, kimlik_db)
    if bulgular:
        raise MaskeIhlali(
            f"LLM isteminde maskelenmemiş kimlik bilgisi bulundu "
            f"({len(bulgular)} eşleşme). İstek GÖNDERİLMEDİ. "
            "Veriyi maskeleme akışından (kimlik_ayir) geçirmeden LLM'e göndermeyin."
        )

    _api_anahtari_dogrula()

    istemci = _istemci_olustur()
    yanit = istemci.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=sistem,
        messages=[{"role": "user", "content": istem}],
    )

    yanit_metni = "".join(
        blok.text for blok in yanit.content if getattr(blok, "type", None) == "text"
    )

    _denetim_izi_yaz(istem, sistem, yanit_metni)
    return yanit_metni
