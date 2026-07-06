-- veri.db şeması (docs/01-MIMARI.md §3) — yalnız anonim çalışma verisi.
-- CREATE TABLE IF NOT EXISTS: Depo.__init__ her bağlantıda idempotent uygular.

-- Mükellef anonim kimliği: yalnızca takma kod (örn. "MUK-001")
CREATE TABLE IF NOT EXISTS mukellef (
    id INTEGER PRIMARY KEY,
    takma_kod TEXT UNIQUE NOT NULL,          -- "MUK-001"; gerçek ad ASLA burada olmaz
    sektor TEXT                              -- analiz bağlamı için genel sektör etiketi
);

CREATE TABLE IF NOT EXISTS donem (
    id INTEGER PRIMARY KEY,
    mukellef_id INTEGER REFERENCES mukellef(id),
    yil INTEGER NOT NULL,
    tip TEXT NOT NULL CHECK (tip IN ('YILLIK','CEYREK','AY')),
    sira INTEGER NOT NULL                    -- ay: 1-12, çeyrek: 1-4, yıllık: 0
);

CREATE TABLE IF NOT EXISTS mizan (
    id INTEGER PRIMARY KEY,
    donem_id INTEGER REFERENCES donem(id),
    hesap_kodu TEXT NOT NULL,                -- "770", "770.01" (alt hesap)
    hesap_adi TEXT,                          -- standart hesap planı adı (kimlik içermez;
                                             -- ayirici.py alt hesap adlarındaki kişi/firma
                                             -- adlarını maskeler: "131.01 [KISI-003]")
    borc_toplam TEXT NOT NULL,               -- Decimal string olarak saklanır
    alacak_toplam TEXT NOT NULL,
    borc_bakiye TEXT NOT NULL,
    alacak_bakiye TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS beyanname (
    id INTEGER PRIMARY KEY,
    donem_id INTEGER REFERENCES donem(id),
    tip TEXT NOT NULL CHECK (tip IN ('KDV1','MUHSGK','GECICI','KV')),
    alanlar TEXT NOT NULL,                   -- JSON: {"matrah": "1250000.00", ...} Decimal string
    kaynak_dosya_ozeti TEXT                  -- sha256 — hangi PDF'ten geldi (denetim izi)
);

CREATE TABLE IF NOT EXISTS bulgu (
    id INTEGER PRIMARY KEY,
    mukellef_id INTEGER REFERENCES mukellef(id),
    yil INTEGER NOT NULL,
    kaynak TEXT NOT NULL CHECK (kaynak IN ('A','B')),
    kontrol_kodu TEXT NOT NULL,              -- "A-KDV-HASILAT", "B-131-ORTAK"
    seviye TEXT NOT NULL CHECK (seviye IN ('dusuk','orta','yuksek')),
    tutar_fark TEXT,                         -- Decimal string
    yuzde_fark REAL,
    detay TEXT NOT NULL,                     -- JSON: ilgili hesaplar, beyanname kalemleri
    durum TEXT NOT NULL DEFAULT 'acik'       -- acik / ymm_inceledi / kapatildi
      CHECK (durum IN ('acik','ymm_inceledi','kapatildi'))
);
