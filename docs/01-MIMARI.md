# YMM Tam Tasdik Raporu Asistanı — Sistem Mimarisi

## 1. Üst Düzey Veri Akışı

```
 Excel mizan          PDF beyannameler
     │                      │
     ▼                      ▼
┌──────────┐        ┌──────────────┐
│ mizan     │        │ beyanname    │      1. AŞAMA: ALIM (ingest)
│ parser    │        │ parser'ları  │      Tamamen yerel. Dış çağrı YOK.
└────┬─────┘        └──────┬───────┘
     │   ┌──────────────┐  │
     └──▶│ KİMLİK AYIRICI│◀─┘              2. AŞAMA: KİMLİK AYRIMI
         │ (maskeleme)   │                 VKN/unvan/ad-soyad → kimlik.db
         └──────┬───────┘                  Anonim veri → veri.db
                ▼
         ┌────────────┐
         │  veri.db   │  (SQLite — yalnız anonim: hesap kodu, tutar, dönem)
         └──────┬─────┘
        ┌───────┴────────┐
        ▼                ▼
┌──────────────┐  ┌──────────────┐
│ MODÜL A      │  │ MODÜL B      │         3. AŞAMA: ANALİZ
│ çapraz       │  │ risk         │         %100 yerel kural motoru.
│ kontrol      │  │ tarayıcı     │         LLM YOK. Decimal aritmetik.
└──────┬───────┘  └──────┬───────┘
       └───────┬─────────┘
               ▼
        bulgular tablosu (veri.db)
               │
               ▼
       ┌───────────────┐
       │ SIZINTI       │                   4. AŞAMA: GÜVENLİK KAPISI
       │ DOĞRULAYICI   │  ← kimlik.db'deki bilinen dizgiler + regex (VKN/TCKN/IBAN)
       └──────┬────────┘     İhlalde: exception, çağrı iptal, log.
              ▼
       ┌───────────────┐
       │ LLM GATEWAY   │  → Anthropic API (yalnızca maskelenmiş bulgu verisi)
       └──────┬────────┘
              ▼
┌────────────────────────┐
│ MODÜL C: rapor taslağı │                 5. AŞAMA: TASLAK ÜRETİM
│ şablon + LLM paragraf  │
└──────────┬─────────────┘
           ▼
   output/TASLAK_<dönem>.docx              6. AŞAMA: İNSAN ONAYI (sistem dışı)
   her sayfada: "İNCELENMESİ GEREKEN       YMM okur, düzeltir, kendi imzasıyla
   TASLAK — YMM ONAYI GEREKLİDİR"          nihai raporu KENDİSİ oluşturur.
```

**Değişmez ilke:** `anthropic` paketi yalnızca `src/llm/gateway.py` içinde import edilir.
Başka hiçbir dosya API çağrısı yapamaz. Gateway her çağrıdan önce sızıntı doğrulayıcıyı
çalıştırır; bu adım parametreyle kapatılamaz.

## 2. Klasör / Dosya Yapısı

```
YMM/
├── CLAUDE.md                     # İşçi modelin ana talimatı (bu depoda mevcut)
├── .claude/skills/
│   └── tam-tasdik-raporu/SKILL.md# Rapor üretim bilgi tabanı
├── docs/
│   ├── 00-ANALIZ.md
│   ├── 01-MIMARI.md
│   ├── superpowers/plans/        # Uygulama planları
│   └── kararlar.md               # Oturum sonu karar günlüğü (işçi model yazar)
├── config/
│   ├── kontrol_kurallari.yaml    # Modül A: kontroller, toleranslar, mutabakat kalemleri
│   ├── risk_hesaplari.yaml       # Modül B: hesap listesi, eşikler, risk seviyeleri
│   └── kolon_haritasi.yaml       # Mizan Excel kolon eşlemesi (format adaptasyonu)
├── src/ymm/
│   ├── __init__.py
│   ├── cli.py                    # typer CLI: yukle / kontrol / tara / rapor / bulgular
│   ├── modeller.py               # dataclass'lar: Donem, MizanSatiri, Beyanname, Bulgu
│   ├── db/
│   │   ├── schema.sql            # veri.db şeması
│   │   ├── kimlik_schema.sql     # kimlik.db şeması (ayrı dosya!)
│   │   └── depo.py               # tüm SQL erişimi (repository)
│   ├── parsers/
│   │   ├── mizan.py              # Excel/CSV → MizanSatiri[] (kolon_haritasi.yaml ile)
│   │   └── beyanname/
│   │       ├── ortak.py          # pdfplumber yardımcıları, tutar normalize
│   │       ├── kdv.py            # KDV1 beyannamesi alan çıkarımı
│   │       ├── muhtasar.py       # MUHSGK
│   │       ├── gecici.py         # Geçici vergi
│   │       └── kurumlar.py       # Yıllık KV
│   ├── maskeleme/
│   │   ├── ayirici.py            # ingest sırasında kimlik → kimlik.db, anonim → veri.db
│   │   └── dogrulayici.py        # sızıntı taraması: regex + bilinen dizgi listesi
│   ├── kontrol/                  # MODÜL A
│   │   ├── motor.py              # kural yükle → çalıştır → Bulgu[] üret
│   │   ├── kurallar.py           # kontrol fonksiyonları (kdv_hasilat, muhtasar_ucret, ...)
│   │   └── donem.py              # dönem hizalama/kümülatif toplama yardımcıları
│   ├── risk/                     # MODÜL B
│   │   ├── tarayici.py           # statik + karşılaştırmalı tarama → Bulgu[]
│   │   └── seviye.py             # eşiklerden risk seviyesi hesabı
│   ├── llm/
│   │   ├── gateway.py            # TEK API noktası; doğrulayıcı zorunlu; istek loglama
│   │   └── istemler.py           # prompt şablonları (yalnız anonim alan adları içerir)
│   └── rapor/                    # MODÜL C
│       ├── uretici.py            # iskelet doldurma + LLM paragrafları → docx
│       └── sablonlar/            # jinja2: iskelet + bulgu tipi başına paragraf şablonu
├── ornek_veri/                   # DUMMY veri — testlerin fixture'ı. Gerçek veri ASLA girmez.
│   ├── mizan_2025.xlsx
│   └── beyanname_ozet.json       # PDF parse edilmiş gibi hazır JSON (test kolaylığı)
├── data/                         # GERÇEK müşteri verisi. .gitignore'da. Test kullanamaz.
├── output/                       # Taslak raporlar + llm_log/ (denetim izi)
├── tests/
├── pyproject.toml
└── .gitignore                    # data/, output/, *.db, .env
```

## 3. Veri Modeli (SQLite)

### veri.db — anonim çalışma verisi

```sql
-- Mükellef anonim kimliği: yalnızca takma kod (örn. "MUK-001")
CREATE TABLE mukellef (
    id INTEGER PRIMARY KEY,
    takma_kod TEXT UNIQUE NOT NULL,          -- "MUK-001"; gerçek ad ASLA burada olmaz
    sektor TEXT                              -- analiz bağlamı için genel sektör etiketi
);

CREATE TABLE donem (
    id INTEGER PRIMARY KEY,
    mukellef_id INTEGER REFERENCES mukellef(id),
    yil INTEGER NOT NULL,
    tip TEXT NOT NULL CHECK (tip IN ('YILLIK','CEYREK','AY')),
    sira INTEGER NOT NULL                    -- ay: 1-12, çeyrek: 1-4, yıllık: 0
);

CREATE TABLE mizan (
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

CREATE TABLE beyanname (
    id INTEGER PRIMARY KEY,
    donem_id INTEGER REFERENCES donem(id),
    tip TEXT NOT NULL CHECK (tip IN ('KDV1','MUHSGK','GECICI','KV')),
    alanlar TEXT NOT NULL,                   -- JSON: {"matrah": "1250000.00", ...} Decimal string
    kaynak_dosya_ozeti TEXT                  -- sha256 — hangi PDF'ten geldi (denetim izi)
);

CREATE TABLE bulgu (
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
```

### kimlik.db — kimlik haritası (fiziksel olarak ayrı dosya)

```sql
CREATE TABLE kimlik (
    takma_kod TEXT PRIMARY KEY,              -- "MUK-001", "KISI-003"
    tip TEXT NOT NULL CHECK (tip IN ('MUKELLEF','KISI','FIRMA_DIGER')),
    gercek_ad TEXT NOT NULL,
    vkn_tckn TEXT
);
```

Kurallar:
- `kimlik.db`'ye yalnızca `maskeleme/ayirici.py` ve rapor son adımındaki **yerel** geri-yerleştirme (`rapor/uretici.py` docx yazımı, LLM'den SONRA) erişir.
- `llm/` ve `kontrol|risk/` modülleri `kimlik.db`'yi import dahi etmez.
- Geri-yerleştirme: LLM taslağı `[MUK-001]` token'larıyla döner; docx yazılırken yerelde gerçek adla değiştirilir. Böylece LLM hiçbir zaman gerçek ad görmez ama YMM'nin okuduğu taslak okunaklıdır.

## 4. Modül Arayüzleri (işçi model bu imzalara uyar)

```python
# parsers/mizan.py
def mizan_oku(dosya: Path, harita: KolonHaritasi) -> list[MizanSatiri]: ...

# maskeleme/ayirici.py
def kimlik_ayir(satirlar: list[MizanSatiri]) -> AyrimSonucu:
    """Kimlik dizgilerini kimlik.db'ye yazar, anonim satırları döner."""

# maskeleme/dogrulayici.py
def sizinti_tara(metin: str) -> list[SizintiBulgusu]:
    """Boş liste = temiz. VKN/TCKN/IBAN regex + kimlik.db bilinen dizgileri."""

# kontrol/motor.py  (MODÜL A)
def kontrolleri_calistir(mukellef_id: int, yil: int, kurallar: KontrolKonfig) -> list[Bulgu]: ...

# risk/tarayici.py  (MODÜL B)
def riskleri_tara(mukellef_id: int, yil: int, konfig: RiskKonfig) -> list[Bulgu]: ...

# llm/gateway.py
def uret(istem: str, sistem: str) -> str:
    """TEK API noktası. Önce sizinti_tara(istem+sistem); bulgu varsa MaskeIhlali raise.
    İstek+yanıt output/llm_log/'a yazılır."""

# rapor/uretici.py  (MODÜL C)
def taslak_uret(mukellef_id: int, yil: int) -> Path:
    """Bulguları okur, şablonu doldurur, LLM paragrafları alır (gateway üzerinden),
    kimlik geri-yerleştirir, TASLAK damgalı docx üretir."""
```

## 5. Konfigürasyon Sözleşmeleri

```yaml
# config/kontrol_kurallari.yaml — Modül A örneği
kontroller:
  - kod: A-KDV-HASILAT
    aciklama: "KDV beyannameleri kümülatif matrah ~ gelir tablosu net satışlar"
    sol:                       # beyanname tarafı
      kaynak: beyanname
      tip: KDV1
      alan: teslim_hizmet_toplam
      donem: yillik_kumulatif  # 12 aylık beyannameler toplanır
    sag:                       # mizan tarafı
      kaynak: mizan
      formul: "600 + 601 + 602 - 610 - 611 - 612"
    mutabakat_kalemleri:       # meşru farklar (mizandan otomatik eklenir/düşülür)
      - ad: duran_varlik_satisi
        formul: "+679_duran_varlik"   # işçi model YMM ile netleştirir
    tolerans:
      mutlak: "10000.00"       # TL
      oransal: 1.0             # %
    seviye_esikleri:           # tolerans aşımı → seviye
      orta: 1.0                # %1-5 arası → orta
      yuksek: 5.0              # >%5 → yüksek
```

```yaml
# config/risk_hesaplari.yaml — Modül B örneği
statik:
  - kod: B-131-ORTAK
    hesap_prefix: "131"
    kural: bakiye_var          # bakiye > 0 ise bulgu
    seviye: yuksek
    not: "Ortaklardan alacak — örtülü kazanç/adatlandırma riski (KVK 13)"
karsilastirmali:
  - kod: B-770-ARTIS
    hesap_prefix: "770"
    kural: yuzde_degisim
    esik_yuzde: 40
    esik_mutlak_taban: "250000.00"   # bu tutarın altındaki bakiyelerde yüzde bakılmaz
    seviye: orta
```

## 6. KVKK Zorlama Noktaları (mimariye gömülü, atlanamaz)

1. **Fiziksel ayrım:** kimlik.db ayrı dosya; LLM yolu üzerindeki hiçbir modül ona bağlanmaz.
2. **Tek geçit:** `anthropic` importu yalnız `gateway.py`'de. Test: `tests/test_kvkk.py` tüm kaynak ağacını tarar, başka import bulursa FAIL.
3. **Zorunlu sızıntı taraması:** gateway her istekte `sizinti_tara` çalıştırır; bypass parametresi yok.
4. **Denetim izi:** her LLM istek/yanıtı `output/llm_log/` altında zaman damgalı saklanır — YMM ne gönderildiğini her an görebilir.
5. **Taslak damgası:** docx üstbilgisi + dosya adı öneki kodda sabit.
6. **Git hijyeni:** `data/`, `output/`, `*.db`, `.env` gitignore'da; `ornek_veri/` yalnız dummy.

## 7. Arayüz (v1 CLI)

```
ymm yukle mizan <dosya.xlsx> --mukellef MUK-001 --yil 2025
ymm yukle beyanname <dosya.pdf> --tip KDV1 --donem 2025-03   # parse sonucu ekranda onaya sunulur
ymm kontrol --mukellef MUK-001 --yil 2025                    # Modül A → bulgu tablosu
ymm tara --mukellef MUK-001 --yil 2025                       # Modül B → bulgu tablosu
ymm bulgular --mukellef MUK-001 --yil 2025 [--seviye yuksek]
ymm rapor --mukellef MUK-001 --yil 2025                      # Modül C → output/TASLAK_....docx
```

Streamlit v2: aynı `src/ymm` core'unu sarar; core'da UI bağımlılığı sıfır tutulur.
