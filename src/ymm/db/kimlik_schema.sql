-- kimlik.db şeması (docs/01-MIMARI.md §3) — kimlik haritası, fiziksel olarak ayrı dosya.
-- Yalnızca maskeleme/ayirici.py ve rapor son adımındaki yerel geri-yerleştirme erişir.

CREATE TABLE IF NOT EXISTS kimlik (
    takma_kod TEXT PRIMARY KEY,              -- "MUK-001", "KISI-003"
    tip TEXT NOT NULL CHECK (tip IN ('MUKELLEF','KISI','FIRMA_DIGER')),
    gercek_ad TEXT NOT NULL,
    vkn_tckn TEXT
);
