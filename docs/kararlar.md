# Karar Günlüğü

İşçi model her oturum sonunda tarihli not ekler (en yeni üstte).

## 2026-07-08 — Task 3.2 tamamlandı (MUHSGK/GECICI/KV parser'ları) → Faz 3 bitti

Teknik kararlar ve gerekçeleri:
- **Ortak parse gövdesi `ortak.beyanname_alanlari`'na çekildi** (pdf açma →
  ValueError, alan döngüsü, None+warning): 4 parser da bunu çağırır; `kdv.py`
  refactor edilip aynı fonksiyona geçirildi (testler yeşil kaldı, davranış
  aynı — uyarı mesajı biçimi `"{TIP} parse: '{alan}' alanı bulunamadı"`).
- **Alan kümeleri** (kontrol motorunun beklediği adlar DEĞİŞTİRİLEMEZ,
  bkz. config/kontrol_kurallari.yaml): MUHSGK → `brut_ucret_toplam`
  (A-MUHSGK-UCRET) + `gelir_vergisi_kesintisi`; GECICI → `matrah`
  (A-GECICI-KV sol) + `hesaplanan_gecici_vergi`; KV → `matrah`
  (A-GECICI-KV sağ) + `hesaplanan_kurumlar_vergisi`.
- **CLI dönem biçimi tipe göre** (`_beyanname_donem_coz`): KDV1/MUHSGK =
  `YYYY-MM` → AY(sira=ay); GECICI = `YYYY-QN` → CEYREK(sira=N) — ay biçimiyle
  karışmasın diye Q zorunlu; KV = `YYYY` → YILLIK(sira=0, mizanla paylaşılan
  yıllık dönem `donem_bul` üzerinden bulunur). Geçersiz biçim hatası beklenen
  biçimi mesajda gösterir, traceback sızmaz.
- **Onay akışı (R3) tüm tipler için aynı**: `--onayla` yoksa DB'ye hiçbir şey
  yazılmaz (test: MUHSGK onaysız → mükellef bile oluşmaz).
- **Test fixture tekrarı `tests/yardimci_pdf.py`'ye çekildi**
  (`dummy_beyanname_pdf` + `turkce_tutar`, aynı Arial/Türkçe font gerekçesi);
  mevcut test_parser_kdv.py kendi yerel yardımcılarıyla bırakıldı (dokunulmadı).
- Eski `test_yukle_beyanname_tip_kdv1_disinda_desteklenmiyor` testi yeni
  davranışa güncellendi (`tip="XYZ"` → exit 1 + geçerli tipler listelenir).
- **NOT (R3, açık)**: yeni parser'ların `_ALAN_ETIKETLERI` etiketleri de gerçek
  GİB PDF'ine dayanmıyor — ilk gerçek dosyada config'e taşınıp doğrulanacak
  (kdv.py'deki notla aynı).

Durum: 201/201 test yeşil (183 + 12 parser + 6 CLI). RED kanıtı: parser
testleri `ModuleNotFoundError`; CLI testleri eski "yalnız KDV1" reddi ile
exit 1. Faz 3 tamam; sırada Faz 4 (LLM geçidi — gateway.py, KVKK kapısı).

Faz sonu KVKK denetimi (kvkk-denetci): TEMİZ — anthropic importu hiçbir
yerde yok; float yalnız yüzde/oran hesaplarında (tutarlar Decimal); kimlik.db
erişimi yalnız maskeleme/ (parsers/kontrol/risk erişmiyor); test_kvkk.py
bütün; ornek_veri dummy, data/ boş, repoda binary PDF yok.

## 2026-07-07 — Task 3.1 tamamlandı (KDV1 beyanname PDF parser + onay akışı)

Teknik kararlar ve gerekçeleri:
- **KVKK sınırı korundu**: `kdv_parse` yalnızca 4 tutar alanı döner
  (`teslim_hizmet_toplam`, `indirilecek_kdv`, `hesaplanan_kdv`, `matrah`);
  mükellef kimlik bilgisi hiçbir yerde okunmaz/loglanmaz. `ortak.pdf_metni`
  ile çıkarılan tam PDF metni yalnız `kdv_parse` içinde geçici işlenir, hiç
  saklanmaz.
- **`ortak.py`**: `pdf_metni` (pdfplumber) + `etiket_degeri` (etiket bul →
  200 karakterlik pencerede ilk Türk-biçimli tutarı yakala) + `_tutar_normalize`
  (mizan.py'deki fonksiyonun BİREBİR kasıtlı kopyası — import edilmedi, iki
  kopya senkron tutulmalı). Türk tutar regex'i ondalık "," kısmını ZORUNLU
  tutuyor (sıra no / tarih gibi alakasız sayıları tutar sanmamak için).
- **Bulunamayan alan → `None` + `logger.warning`** (sessiz sıfır YASAK) — hem
  parser hem CLI (`BULUNAMADI` sarı hücre) düzeyinde uygulanıyor.
- **CLI `yukle beyanname`**: `--tip` v1'de yalnız `KDV1` kabul eder (diğerleri
  "Task 3.2'de" hatasıyla exit 1). `--donem YYYY-MM` `datetime.strptime` ile
  katı parse edilir. `--onayla` yoksa DB'ye HİÇBİR ŞEY yazılmaz (mükellef bile
  oluşturulmaz), exit 0 + "İncelendi mi?" mesajı. `--onayla` ile: dönem
  (tip=AY, sira=ay) yoksa oluşturulur, `None` alanlar dict'e KONMAZ (kontrol
  motoru zaten `.get()` ile eksik alanı atlıyor).
- **`Depo.donem_bul` genişletildi** (kapsam dışı ama zorunlu düzeltme):
  önceki imza `(mukellef_id, yil, tip)` aynı yılın farklı AY dönemlerini
  (sira=1..12) ayırt edemiyordu — `sira: int | None = None` parametresi
  eklendi (geriye dönük uyumlu, `sira=None` eski davranış). Bu olmadan aylık
  KDV1 kayıtları yanlış/belirsiz döneme yazılabilirdi.
- **Fixture'lar reportlab ile üretiliyor** (`tests/test_parser_kdv.py`,
  `tests/test_cli.py`), repoya binary PDF girmiyor. Türkçe özel karakterler
  (ş, ğ, ı, İ, ö, ü, ç) reportlab'in gömülü Helvetica/WinAnsi fontunda
  düzgün basılmadığından testlerde Windows'un yerleşik `arial.ttf`'i Unicode
  font olarak kaydedildi (proje zaten Windows'a özgü tek-makine aracı).
- **NOT (R3 azaltımı, açık kaldı)**: `_ALAN_ETIKETLERI` içindeki etiket
  metinleri gerçek bir GİB e-beyanname PDF'ine dayanmıyor — ilk gerçek dosya
  geldiğinde etiketler `config/`e taşınıp YMM ile ekran başında doğrulanmalı.

Durum: 180/180 test yeşil (162 + 18 yeni: 8 parser + 2 depo(`donem_bul` sira) +
8 CLI). RED kanıtı: `kdv.py`/`ortak.py` yokken `ModuleNotFoundError`; CLI
komutu yokken `SystemExit(2)`; `donem_bul(sira=...)` yokken `TypeError`.

## 2026-07-07 — Faz 2 tamamlandı (Modül B + CLI v1 — LLM'siz kullanılabilir ilk sürüm)

Teknik kararlar ve gerekçeleri:
- **Modül B statik kurallar** (8 adet): bakiye_var (131/231 yüksek, 331/431 orta) ve bakiye_esik_ustu (689>10k orta, 679>10k düşük, 100>50k orta, 190>100k düşük). Tam eşitlik = eşik içi (bulgu yok, Modül A konvansiyonu). Hesap eşleşme mantığı kontrol/'dan import edilmedi (modül izolasyonu — bilinçli kopya).
- **Karşılaştırmalı tarama**: yuzde_degisim, payda önceki dönem; taban muafiyeti (cari < taban → gürültü filtresi); önceki=0 + cari>taban → "yeni bakiye" bulgusu (yüzde yok); önceki YILLIK dönem yoksa karşılaştırmalılar atlanır + warning (bulgu tablosu kirletilmez). B-770-ARTIS (%40/250k/orta), B-131-ARTIS (%50/100k/yüksek).
- **CLI v1** (typer + rich): yukle mizan / yukle beyanname-ozet / kontrol / tara / bulgular --seviye. Entry point `ymm` (pyproject scripts). Yükleme akışı tek fonksiyonda mizan_oku→kimlik_ayir→depo — maskeleme atlanamaz (denetçi doğruladı: depoya yazan tek çağrı noktası, ham satır yolu yok).
- **Mükerrer bulgu önlendi**: kontrol/tara, yazmadan önce kendi kaynağının (A/B) eski bulgularını siler — tekrar çalıştırma güvenli, diğer modülün bulguları korunur.
- **Aynı dönem mizan tekrar yüklemesi**: eski satırlar silinir (mizan_sil).
- beyanname-ozet JSON yolu, ileride PDF parser çıktısının gireceği ortak kapı olarak tasarlandı (Faz 3 buna bağlanacak).
- Bilinen sertleştirme ihtiyacı (Faz 3+ öncesi değerlendirilecek): bozuk JSON/kolon haritası hatalarında ham traceback sızıyor (ValueError dışı yollar).

Durum: 162/162 test yeşil. ARA TESLİM: araç LLM'siz uçtan uca çalışıyor (`ymm yukle mizan` → `kontrol` → `tara` → `bulgular`). Kullanıcı talimatıyla durmadan Faz 3'e devam ediliyor; YMM'nin 6 açık sorusu (docs/00-ANALIZ.md §4) hâlâ bekliyor.

## 2026-07-07 — Faz 1 tamamlandı (Modül A: çapraz kontrol motoru)

Teknik kararlar ve gerekçeleri:
- **Hesap değeri konvansiyonu**: değer = borç bakiyesi > 0 ise borç, değilse alacak bakiyesi; formül işaretleri açık ("600 + 601 - 610"). Ana hesap TAM eşleşme önceliği → alt hesap çifte sayımı önlenir.
- **Katı formül sözdizimi**: bozuk formül ("600 ++ 601", "600 601", sarkan operatör) ValueError; config yüklemede TÜM formüller + enum alanları (sol.donem/sag.kaynak/sag.deger_tipi) ön-doğrulanır (`konfig_yukle` = fail-fast giriş noktası — CLI bunu kullanmalı).
- **Sessiz sıfır yasak, çökme yasak**: mizanda eşleşmeyen formül terimleri detay["eslesmeyen_hesaplar"]a; beyanname kaydında eksik alan → o kontrol ATLANIR (kısmi toplam yok) + logger.warning.
- **Tolerans AND kuralı**: bulgu için mutlak VE oransal eşik ikisi de aşılmalı; tam eşitlik tolerans içi. yuzde_fark paydası = sağ taraf.
- **Motor genişletmeleri** (geriye uyumlu): sol.donem=son_ceyrek, sag.kaynak=beyanname (beyanname↔beyanname karşılaştırma), sag.deger_tipi=bakiye|borc_toplam|alacak_toplam. Beyanname-sağ + mutabakat_kalemleri kombinasyonu config'de reddedilir.
- **4 kontrol aktif**: A-KDV-HASILAT (dummy: 100k fark, %2, orta), A-MUHSGK-UCRET (400k, %50, yüksek — "770" formülü v1 dummy varsayımı, gerçek mükellefte güncellenecek), A-GECICI-KV (5k, %0.83, orta), A-KDV-INDIRIM (varsayılan uyumlu).
- **Depo genişledi**: donem_bul + beyanname_oku_donemli — motor'daki ham SQL temizlendi, repository ilkesi korundu.
- Bilinen teknik borç: _GECERLI_DEGER_TIPLERI sabiti motor.py + kurallar.py'de tekrar (bilinçli izolasyon).

Durum: 108/108 test yeşil.

## 2026-07-06 — Faz 0 tamamlandı (orkestratör: Fable 5, implementer: Sonnet sub-agent'lar)

Teknik kararlar ve gerekçeleri:
- **Python 3.12 sabitlendi** (`py -3.12`): PATH'teki `python` güvenilmez (başka ortama işaret ediyor); uv-yönetimli 3.11 PEP 668 korumalı olduğundan standart 3.12 kurulumuna geçildi, plan gereksinimi de buydu.
- **`Bulgu` dataclass'ına `mukellef_id`+`yil` eklendi**: DDL'deki NOT NULL kolonlar gerektiriyordu; plan güncellendi.
- **JSON serileştirmede `default=str`** (depo.py): detay/alanlar dict'lerine ham Decimal düşerse TypeError yerine tam hassasiyetli string.
- **Çifte sayım önlemi (Faz 1-2'ye direktif)**: formül değerlendirici önce 3 haneli ana hesap satırını kullanır, yoksa prefix alt hesap toplamı — dummy mizanda 131 ve 131.01 aynı bakiyeyi taşıyor.
- **Türkçe kimlik eşleme `_tr_fold`** (İ→i, I→ı + casefold, iki tarafa): düz `casefold()` "IŞIK"/"Işık" eşleşmesini kaçırıyordu (kanıtlanmış sızıntı yalancı negatifi). ASCII-I çift yönü çözülemiyor — bilinen sınır.
- **KVKK bekçi testleri AST tabanlı** (test_kvkk.py): anthropic importu yalnız gateway.py'de; kontrol/risk/llm modülleri `ymm.maskeleme.ayirici` ve "kimlik" içeren modülleri import edemez (dogrulayici serbest). Dinamik importlar kapsam dışı (dokümante).
- **IBAN regex boşluk toleranslı**; maskeleme katmanları sıralı uygulanıyor (bracket + BÜYÜK harf birlikte).
- **Kimlik tespiti v1 sözleşmesi**: köşeli parantez etiketi + 2+ ardışık BÜYÜK harfli kelime; dummy veride gerçekçi ad kullanılmıyor.

Durum: 43/43 test yeşil. Sub-agent tanımları `.claude/agents/` altında (bu oturumda hot-load edilemedi, sonraki oturumlarda aktif; şimdilik tanım gömülerek general-purpose ile çalıştırılıyor).

## 2026-07-06 — Mimari (Fable 5)

- Blueprint tamamlandı: `docs/00-ANALIZ.md`, `docs/01-MIMARI.md`, uygulama planı,
  kök `CLAUDE.md`, `.claude/skills/tam-tasdik-raporu/SKILL.md`.
- Temel kararlar: Python + SQLite (veri.db/kimlik.db fiziksel ayrım), CLI v1
  (Streamlit opsiyonel v2), tek LLM geçidi (`gateway.py`) + zorunlu sızıntı taraması,
  Decimal aritmetik, YAML tabanlı kural/eşik konfigürasyonu, zorunlu TASLAK damgası.
- YMM'den beklenen girdiler (docs/00-ANALIZ.md §4): gerçek mizan örneği, e-beyanname
  PDF örneği, geçmiş 2-3 anonim rapor, tolerans tercihleri, önceki dönem mizanları.
