# YMM Tam Tasdik Raporu Asistanı — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mizan/beyanname çapraz kontrolü, riskli hesap taraması ve TASLAK tasdik raporu üreten yerel, tek kullanıcılı Python aracı.

**Architecture:** 3 modül (A: kural bazlı çapraz kontrol, B: kural bazlı risk tarama, C: şablon+LLM taslak). Kimlik verisi ingest'te ayrılır (`kimlik.db`), analiz anonim veride çalışır, LLM'e yalnız maskelenmiş bulgu gider (`gateway.py` tek geçit). Detay: `docs/01-MIMARI.md` — **her göreve başlamadan önce oku.**

**Tech Stack:** Python 3.12+, pandas/openpyxl, pdfplumber, SQLite, typer+rich, jinja2, python-docx, anthropic SDK (yalnız Modül C), pytest.

## Global Constraints

- Tüm tutar aritmetiği `decimal.Decimal`; `float` tutar için YASAK. DB'de Decimal string saklanır.
- `anthropic` importu YALNIZCA `src/ymm/llm/gateway.py` içinde. (`tests/test_kvkk.py` bunu zorlar.)
- Gerçek müşteri verisi test fixture'ı olamaz; testler yalnız `ornek_veri/` dummy verisini kullanır.
- Rapor çıktısı her zaman `TASLAK_` önekli + her sayfada "İNCELENMESİ GEREKEN TASLAK — YMM ONAYI GEREKLİDİR" üstbilgisi. Kapatma parametresi eklenmez.
- Kod dili: Türkçe modül/fonksiyon adları (mimari dokümandaki imzalara birebir uy).
- Her görev TDD: önce başarısız test, sonra minimal implementasyon, sonra commit.
- `data/`, `output/`, `*.db`, `.env` gitignore'da kalır.

---

## Faz 0 — İskelet ve Veri Katmanı

### Task 0.1: Proje iskeleti + pyproject + gitignore

**Files:** Create: `pyproject.toml`, `.gitignore`, `src/ymm/__init__.py`, boş paket dizinleri (mimari dokümandaki ağaç), `ornek_veri/beyanname_ozet.json`

- [ ] `git init`; mimarideki klasör ağacını oluştur
- [ ] `pyproject.toml`: proje adı `ymm-asistan`, bağımlılıklar: pandas, openpyxl, pdfplumber, typer, rich, jinja2, python-docx, pyyaml, anthropic, pytest (dev)
- [ ] `.gitignore`: `data/`, `output/`, `*.db`, `.env`, `__pycache__/`, `.venv/`
- [ ] `pip install -e .` çalışıyor, `pytest` 0 test toplayıp geçiyor
- [ ] Commit: `chore: proje iskeleti`

### Task 0.2: Modeller + veri.db şeması + depo

**Files:** Create: `src/ymm/modeller.py`, `src/ymm/db/schema.sql`, `src/ymm/db/kimlik_schema.sql`, `src/ymm/db/depo.py`; Test: `tests/test_depo.py`

**Interfaces (Produces):**
- `modeller.py`: `@dataclass MizanSatiri(hesap_kodu: str, hesap_adi: str, borc_toplam: Decimal, alacak_toplam: Decimal, borc_bakiye: Decimal, alacak_bakiye: Decimal)`; `Donem(yil: int, tip: str, sira: int)`; `Bulgu(kaynak: str, kontrol_kodu: str, seviye: str, tutar_fark: Decimal | None, yuzde_fark: float | None, detay: dict, mukellef_id: int, yil: int)` (son iki alan DDL'deki NOT NULL kolonlar için — Task 0.2'de eklendi)
- `depo.py`: `class Depo(veri_yolu: Path)` — `mukellef_ekle(takma_kod) -> int`, `donem_ekle(mukellef_id, Donem) -> int`, `mizan_yaz(donem_id, list[MizanSatiri])`, `mizan_oku(donem_id) -> list[MizanSatiri]`, `beyanname_yaz(donem_id, tip, alanlar: dict)`, `beyanname_oku(mukellef_id, tip, yil) -> list[dict]`, `bulgu_yaz(list[Bulgu])`, `bulgular(mukellef_id, yil) -> list[Bulgu]`

- [ ] Başarısız test: geçici SQLite'a `MizanSatiri` yaz/oku round-trip; Decimal değer `Decimal("1234.56")` olarak aynen dönmeli (string saklama doğrulaması)
- [ ] `schema.sql` mimari dokümandaki DDL ile; `Depo` implementasyonu
- [ ] Testler geçiyor → Commit: `feat: veri modeli ve depo katmanı`

### Task 0.3: Dummy mizan üretici + mizan parser

**Files:** Create: `src/ymm/parsers/mizan.py`, `config/kolon_haritasi.yaml`, `ornek_veri/uret.py` (dummy xlsx üretir), `ornek_veri/mizan_2025.xlsx`; Test: `tests/test_mizan_parser.py`

**Interfaces (Produces):** `mizan_oku(dosya: Path, harita: dict) -> list[MizanSatiri]` — harita YAML'dan: `{hesap_kodu: "A", hesap_adi: "B", borc_toplam: "C", ...}` kolon harfleri veya başlık adları.

- [ ] `ornek_veri/uret.py`: tutarlı dummy mizan üret (600=5.000.000, 770=800.000, 131=150.000 bakiyeli, 689=45.000 vb. — Faz 1-2 testleri bu sayılara dayanacak, script'e sabit yaz)
- [ ] Başarısız test: xlsx oku → satır sayısı ve `hesap_kodu=="600"` satırının `alacak_bakiye == Decimal("5000000.00")` doğrula
- [ ] Parser: openpyxl ile oku, haritaya göre kolonları eşle, tutarları `Decimal`e çevir (binlik ayraç/virgül normalize), boş satır atla
- [ ] Testler geçiyor → Commit: `feat: mizan parser + dummy veri`

### Task 0.4: Kimlik ayırıcı (maskeleme temeli)

**Files:** Create: `src/ymm/maskeleme/ayirici.py`, `src/ymm/maskeleme/dogrulayici.py`; Test: `tests/test_maskeleme.py`, `tests/test_kvkk.py`

**Interfaces (Produces):**
- `kimlik_ayir(satirlar, kimlik_db: Path) -> list[MizanSatiri]` — alt hesap adlarındaki kişi/firma adlarını `[KISI-nnn]` token'ına çevirir, eşlemeyi kimlik.db'ye yazar
- `sizinti_tara(metin: str, kimlik_db: Path) -> list[str]` — VKN (10 hane), TCKN (11 hane), IBAN (TR+24 hane) regex + kimlik.db'deki tüm `gercek_ad`/`vkn_tckn` dizgileri; eşleşme listesi döner
- `class MaskeIhlali(Exception)`

- [ ] Başarısız testler: (1) `"131.01 AHMET YILMAZ"` → `"131.01 [KISI-001]"` ve kimlik.db'de eşleme; (2) `sizinti_tara("VKN 1234567890 ...")` boş dönmemeli; (3) temiz metin boş dönmeli
- [ ] `test_kvkk.py`: `src/` ağacında `gateway.py` dışında `anthropic` importu ara — bulursa FAIL (bu test kalıcı KVKK bekçisi)
- [ ] Implementasyon; testler geçiyor → Commit: `feat: kimlik ayırıcı + sızıntı doğrulayıcı + KVKK bekçi testi`

## Faz 1 — MODÜL A: Çapraz Kontrol Motoru

### Task 1.1: Dönem yardımcıları + beyanname dummy verisi

**Files:** Create: `src/ymm/kontrol/donem.py`, `ornek_veri/beyanname_ozet.json`; Test: `tests/test_donem.py`

**Interfaces (Produces):** `yillik_kumulatif(beyannameler: list[dict], alan: str) -> Decimal` — aylık/çeyreklik beyanname alanlarını yıllık toplar; eksik dönem varsa `EksikDonem` uyarısı listeler.

- [ ] `beyanname_ozet.json`: 12 aylık KDV1 (teslim_hizmet_toplam aylık ~416.666 → yıllık 5.000.000'a yakın ama kasıtlı 4.900.000 topla — kontrol bulgu üretsin), 12 MUHSGK, 4 GECICI, 1 KV dummy kaydı
- [ ] Başarısız test: 12 kaydın kümülatifi beklenen `Decimal` toplam; 11 kayıtla `EksikDonem` uyarısı
- [ ] Implementasyon; commit: `feat: dönem hizalama yardımcıları`

### Task 1.2: Kontrol motoru + ilk kontrol (A-KDV-HASILAT)

**Files:** Create: `src/ymm/kontrol/motor.py`, `src/ymm/kontrol/kurallar.py`, `config/kontrol_kurallari.yaml`; Test: `tests/test_kontrol_kdv.py`

**Interfaces (Produces):** `kontrolleri_calistir(depo: Depo, mukellef_id: int, yil: int, konfig: dict) -> list[Bulgu]`. Mizan formül değerlendirici: `"600 + 601 - 610"` → prefix eşleşmeli bakiye toplamı (`600*` tüm alt hesaplar dahil).

- [ ] Başarısız test (dummy sayılarla): net satışlar 5.000.000, KDV kümülatif 4.900.000 → fark 100.000, %2.0 → `Bulgu(kontrol_kodu="A-KDV-HASILAT", seviye="orta", tutar_fark=Decimal("100000.00"))`; tolerans içi senaryoda bulgu YOK
- [ ] YAML'daki `tolerans` (mutlak VE oransal — ikisi de aşılırsa bulgu) ve `seviye_esikleri` mantığını uygula; `mutabakat_kalemleri` mekanizmasını kur (formül sonucuna ekle/düş)
- [ ] Commit: `feat: kontrol motoru + KDV hasılat kontrolü`

### Task 1.3: Muhtasar ve geçici vergi kontrolleri

**Files:** Modify: `src/ymm/kontrol/kurallar.py`, `config/kontrol_kurallari.yaml`; Test: `tests/test_kontrol_muhtasar.py`, `tests/test_kontrol_gecici.py`

- [ ] `A-MUHSGK-UCRET`: MUHSGK kümülatif brüt ücret ↔ mizan `"720 + 730 + 740 + 760 + 770"` içindeki ücret alt hesapları (v1: YAML'da ücret hesap listesi açıkça verilir, varsayılan `770.01` benzeri dummy yapıya göre)
- [ ] `A-GECICI-KV`: 4. dönem geçici vergi matrahı ↔ KV beyannamesi matrahı (tolerans dar: mutlak 1.000 TL)
- [ ] `A-KDV-INDIRIM`: yıllık indirilecek KDV toplamı ↔ 191 hesap borç toplamı (bonus, aynı motorla — yeni kod gerekmiyorsa yalnız YAML)
- [ ] Her kontrol için pozitif (bulgu üretir) + negatif (tolerans içi, bulgu yok) test; commit: `feat: muhtasar ve geçici vergi kontrolleri`

## Faz 2 — MODÜL B: Riskli Hesap Tarayıcı

### Task 2.1: Statik kurallar

**Files:** Create: `src/ymm/risk/tarayici.py`, `src/ymm/risk/seviye.py`, `config/risk_hesaplari.yaml`; Test: `tests/test_risk_statik.py`

**Interfaces (Produces):** `riskleri_tara(depo: Depo, mukellef_id: int, yil: int, konfig: dict) -> list[Bulgu]`

- [ ] YAML'a statik kurallar: 131/231 (bakiye_var→yuksek), 331/431 (bakiye_var→orta, not: örtülü sermaye), 689 (bakiye>esik→orta), 679 (bakiye>esik→dusuk), 100 (bakiye>esik→orta, kasa adat), 190 (yıl sonu bakiye>esik→dusuk)
- [ ] Başarısız test: dummy mizanda 131=150.000 → `B-131-ORTAK, seviye=yuksek` bulgusu; 331 bakiyesiz → bulgu yok
- [ ] Commit: `feat: statik risk taraması`

### Task 2.2: Önceki dönem karşılaştırması

**Files:** Modify: `src/ymm/risk/tarayici.py`, `ornek_veri/uret.py` (2024 dummy mizanı ekle); Test: `tests/test_risk_karsilastirma.py`

- [ ] Kural: `yuzde_degisim` — önceki yıl bakiyesine göre % değişim eşiği + `esik_mutlak_taban` (taban altı bakiyelerde yüzde bakılmaz). Önceki dönem verisi yoksa bulgu üretme, `detay`a "önceki dönem yok" notu düşen tek bilgi bulgusu üret
- [ ] Test: 770 2024=500.000 → 2025=800.000 (%60 artış, eşik %40) → `B-770-ARTIS, seviye=orta`
- [ ] Commit: `feat: dönemsel karşılaştırmalı risk taraması`

### Task 2.3: CLI v1 (yukle/kontrol/tara/bulgular)

**Files:** Create: `src/ymm/cli.py`; Test: `tests/test_cli.py` (typer `CliRunner`)

- [ ] Komutlar: `yukle mizan`, `kontrol`, `tara`, `bulgular` (rich tablo, `--seviye` filtre). `yukle` akışı: parser → `kimlik_ayir` → depo (maskeleme atlanamaz — akış tek fonksiyonda)
- [ ] Uçtan uca test: dummy xlsx yükle → kontrol+tara → `bulgular` çıktısında A-KDV-HASILAT ve B-131-ORTAK görünüyor
- [ ] Commit: `feat: CLI v1 — bu noktada araç LLM'siz kullanılabilir durumda` ← **ara teslim: YMM'ye gösterilecek ilk sürüm**

## Faz 3 — Beyanname PDF Parser'ları

### Task 3.1: KDV1 parser + onay akışı

**Files:** Create: `src/ymm/parsers/beyanname/ortak.py`, `.../kdv.py`; Modify: `cli.py` (`yukle beyanname`); Test: `tests/test_parser_kdv.py`

- [x] `ornek_veri/` için basit metin-PDF fixture üret (reportlab ile dummy KDV beyanname sayfası — gerçek GİB PDF'i repoya girmez) — fixture'lar test dosyalarında (`tests/test_parser_kdv.py`, `tests/test_cli.py`) `tmp_path`'e üretiliyor, repoya binary PDF girmedi
- [x] `kdv_parse(pdf: Path) -> dict` — etiket bazlı arama ("Teslim ve Hizmetlerin Karşılığını Teşkil Eden Bedel" vb.), tutar normalize. Bulunamayan alan → `None` + uyarı; sessiz sıfır YASAK
- [x] CLI akışı: parse sonucu tablo halinde gösterilir, `--onayla` olmadan DB'ye yazılmaz (R3 azaltımı)
- [x] Commit: `feat: KDV beyanname parser + onay akışı`
- [ ] **NOT:** Gerçek e-beyanname PDF'i alındığında etiketler `config/`e taşınarak adapte edilir; ilk gerçek dosyada YMM ile ekran başında doğrulama yap (v1'de henüz gerçek PDF alınmadı — açık kalmalı)

### Task 3.2: MUHSGK / Geçici / KV parser'ları

**Files:** Create: `.../muhtasar.py`, `.../gecici.py`, `.../kurumlar.py`; Test: her biri için ayrı test dosyası

- [x] Aynı desen: etiket bazlı çıkarım + fixture PDF + onay akışı. Kod tekrarını `ortak.py`'ye çek (`beyanname_alanlari` ortak gövde; kdv.py de buna geçirildi. CLI dönem biçimi tipe göre: AY=YYYY-MM, CEYREK=YYYY-QN, YILLIK=YYYY)
- [x] Commit: `feat: kalan beyanname parser'ları`

## Faz 4 — LLM Geçidi (KVKK kapısı)

### Task 4.1: gateway.py + istemler

**Files:** Create: `src/ymm/llm/gateway.py`, `src/ymm/llm/istemler.py`; Test: `tests/test_gateway.py` (API mock'lanır — testte gerçek çağrı YOK)

**Interfaces (Produces):** `uret(istem: str, sistem: str, kimlik_db: Path) -> str`

- [x] Başarısız testler: (1) istemde `"1234567890"` (kimlik.db'de kayıtlı VKN) → `MaskeIhlali` raise, API mock'u ÇAĞRILMADI; (2) temiz istem → mock yanıtı döner, `output/llm_log/` altına istek+yanıt json yazıldı
- [x] Model: `claude-sonnet-5`, `ANTHROPIC_API_KEY` env'den; anahtar yoksa açıklayıcı hata
- [x] Commit: `feat: LLM geçidi — zorunlu sızıntı taraması + denetim izi`

## Faz 5 — MODÜL C: Rapor Taslağı

### Task 5.1: Şablon iskeleti + bulgu paragrafları

**Files:** Create: `src/ymm/rapor/uretici.py`, `src/ymm/rapor/sablonlar/iskelet.md.j2`, `.../bulgu_*.j2`; Test: `tests/test_rapor.py`

- [x] Şablon yapısı ve paragraf kalıpları: `.claude/skills/tam-tasdik-raporu/SKILL.md`'den al (**bu görevi yapmadan SKILL.md'yi oku**)
- [x] Akış: bulguları oku → her bulgu tipi için j2 paragraf şablonunu veriyle doldur → LLM'e "bu kalıp paragrafları akıcı, resmi Türkçe ile birleştir/redakte et" istemi (gateway üzerinden) → dönen metinde `[MUK-001]` token'larını kimlik.db'den YERELDE geri yerleştir
- [x] Test (LLM mock): 2 bulgulu senaryoda üretilen ara metin her iki kontrol kodunun tutarlarını içeriyor; token geri-yerleştirme çalışıyor
- [x] Commit: `feat: rapor taslak üretici (metin katmanı)`

### Task 5.2: DOCX çıktı + taslak damgası

**Files:** Modify: `src/ymm/rapor/uretici.py`; Test: `tests/test_docx.py`

- [x] python-docx: her sayfa üstbilgisinde "İNCELENMESİ GEREKEN TASLAK — YMM ONAYI GEREKLİDİR" (kalın, kırmızı), dosya adı `output/TASLAK_MUK-001_2025.docx`
- [x] Test: üretilen docx'i aç, section header'da damga metnini doğrula; dosya adı önekini doğrula
- [x] `ymm rapor` CLI komutunu bağla; uçtan uca dummy akışı çalıştır
- [x] Commit: `feat: TASLAK damgalı docx çıktı` ← **v1 tamam** ✅ (2026-07-08, 227/227 test)

## Faz 6 (opsiyonel, YMM talep ederse) — Streamlit sarmalayıcı

- [ ] `app.py`: yükleme ekranı, bulgu tablosu (seviye renkli), rapor indirme butonu. Core'a dokunma.

---

## Self-Review Notları (mimar)

- Spec kapsama: Modül A→Faz 1, B→Faz 2, C→Faz 4-5, maskeleme→Task 0.4+4.1, KVKK zorlaması→test_kvkk.py + tek geçit, esnek parser→kolon_haritasi.yaml + etiket-config. ✅
- Bilinçli sapma: writing-plans "her adımda tam kod" ister; kullanıcı brief'i "kod yazma" dedi. Plan, sözleşmeleri (imza + test beklentisi + dummy sayılar) sabitler, gövdeyi işçi modele bırakır.
- Dummy sayılar görevler arası tutarlı: 600=5.000.000 (T0.3) ↔ KDV kümülatif 4.900.000 (T1.1) ↔ %2 fark bulgusu (T1.2); 131=150.000 (T0.3) ↔ B-131 bulgusu (T2.1); 770: 2024=500.000/2025=800.000 (T2.2). `ornek_veri/uret.py` bu sayıları sabit üretmeli.
