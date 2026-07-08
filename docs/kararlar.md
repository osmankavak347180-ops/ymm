# Karar Günlüğü

İşçi model her oturum sonunda tarihli not ekler (en yeni üstte).

## 2026-07-08 — MUK-002 örnek senaryosu (orkestratör Fable, işçi Sonnet)

- Fable senaryoyu tasarladı (tam mizan satırları + beyanname tutarları +
  beklenen 11 bulgunun kod/seviye/tutar listesi); Sonnet işçi ajan
  `ornek_veri/senaryo_muk002.py` üreticisini yazıp CLI ile yükledi ve koştu.
- Sonuç: 11/11 bulgu beklenenle birebir (Fable DB'den bağımsız doğruladı).
  İlk kez tetiklenen yollar: karşılaştırmalı B-770/B-131-ARTIS (2024 önceki
  yıl mizanı sayesinde) ve A-KDV-HESAPLANAN sapma dalı (%7,6 → yüksek).
- Dashboard'dan gerçek LLM'le TASLAK_MUK-002_2025.docx üretildi ve docx
  içi doğrulandı: [KISI-*] token'ı kalmadı (ORTAK-X yerine yerleşti — LLM
  loglarında yalnız maskeli token var, KVKK zinciri uçtan uca kanıtlı),
  damga + [YMM GÖRÜŞÜ] yer tutucusu mevcut, bulgu tutarları birebir.
- Not: 241 test beklentisi Fable'ın brief'indeki aritmetik hatasıydı;
  gerçek sayı 239 ve suite yeşil (Sonnet raporundaki "uncommitted
  değişiklik" tahmini yanlış — her şey commit'liydi).

## 2026-07-08 — İlk gerçek LLM çağrısı doğrulandı + "Yaldızlı Defter" teması

- Kullanıcı ANTHROPIC_API_KEY'i kendi terminalinde `setx` ile tanımladı
  (anahtar sohbete/koda/repoya girmedi; Streamlit süreci anahtarı Windows
  kayıt defterinden ortam değişkenine aktararak başlatıldı — değer hiç
  görüntülenmedi).
- Uçtan uca GERÇEK doğrulama (tarayıcıdan, dummy maskeli veriyle): Rapor
  sekmesi → claude-sonnet-5 redaksiyonu → tutarlar birebir korunmuş akıcı
  resmi rapor Türkçesi → `output/TASLAK_MUK-001_2025.docx` (39 KB) + iki
  denetim izi JSON'u (`output/llm_log/`, Modül A ve B ayrı çağrılar).
- UI: "Yaldızlı Defter" karanlık teması (koyu mürekkep + altın varak +
  Fraunces; kaşe ışımalı; pill sekmeler). Türkçe uyum düzeltmeleri:
  CSS `text-transform: uppercase` Türkçe İ'yi bozduğu için YASAK (büyük
  harf Python tarafında yazılır); Streamlit yerleşik İngilizce metinleri
  (file uploader) CSS ile Türkçeleştirildi; Material ikon fontu global
  font override'ından istisna tutulmalı (aksi halde ligatürler düz
  İngilizce metne dönüşür); Streamlit 1.59 sekme DOM'u `data-testid=stTab`
  (eski `data-baseweb` seçicileri ölü).

## 2026-07-08 — Uzman YMM tam denetimi + Faz 6 (Streamlit) — v1.1

Kullanıcı talebi: "tüm projeyi uzman YMM gözüyle A'dan Z'ye kontrol et,
eksikleri düzelt, Faz 6'yı ekle." Yapılanlar:

**Düzeltilen boşluklar:**
1. **A-KDV-HESAPLANAN kontrolü eklendi** (YAML-only, yeni kural tipi
   gerekmedi): parser `hesaplanan_kdv` alanını Task 3.1'den beri çıkarıyordu
   ama HİÇBİR kontrol kullanmıyordu. Beyan edilen hesaplanan KDV kümülatif ~
   391 alacak toplamı (tolerans 5.000 TL / %1). Dummy veriye uyumlu değerler
   eklendi (1.000.000 == 1.000.000, bulgu üretmez); sapma senaryosu testte.
2. **CLI traceback sızıntıları kapatıldı** (Faz 2'den beri bilinen borç):
   bozuk xlsx/kolon haritası (`yukle mizan`) ve bozuk JSON/şema dışı dosya
   (`yukle beyanname-ozet`) artık kırmızı mesaj + exit 1.

**Faz 6 — Streamlit (`src/ymm/app.py`):**
- src altında tutuldu ki test_kvkk AST bekçisi anthropic importunu tarasın.
- Mizan yükleme akışı CLI ile aynı ilke: TEK fonksiyonda mizan_oku →
  kimlik_ayir → depo (maskesiz ara yol yok). Beyanname PDF: önizle →
  "Onayla ve kaydet" (R3'ün UI karşılığı; onaysız DB'ye yazılmaz).
- Dönem çözme/parser eşlemesi cli.py'den import edildi (kod tekrarı yok,
  çekirdeğe dokunulmadı). Upload geçici dosyaları finally'de unlink.
- TASLAK damgası her sayfada `st.warning` ile sabit. Bulgu tablosu seviye
  renkli (yüksek kırmızı/orta turuncu/düşük gri), seviye filtreli; rapor
  sekmesi taslak_uret + docx download_button (MaskeIhlali/anahtar hatası
  st.error ile). streamlit opsiyonel bağımlılık: `pip install -e ".[ui]"`.
- Testler `streamlit.testing.v1.AppTest` ile headless (sunucu/LLM yok).

**Uzman YMM boşluk analizi — YMM ONAYı BEKLEYEN aday kurallar (eklenMEdi;
tolerans/eşik tercihi YMM'nin — gürültü üretmemek için onaysız eklenmedi):**
- Karşılaştırmalı risk adayları (YAML-only eklenebilir): B-120-ARTIS
  (Alıcılar), B-320-ARTIS (Satıcılar), B-780-ARTIS (finansman giderleri
  artışı — örtülü sermaye/finansman gider kısıtlaması işareti).
- Statik risk adayları (YAML-only): 296/297 geçici hesaplar bakiye_var,
  136/336 diğer çeşitli alacak/borç eşik üstü, 159 verilen sipariş avansları.
- Kontrol adayı (motor DESTEKLER, YAML-only): A-GECICI-690 — 4. dönem geçici
  vergi matrahı ~ mizan 690 dönem kârı; matrah ≠ ticari kâr (KKEG/istisna
  farkı) olduğundan tolerans mutlaka YMM ile belirlenmeli.
- Yeni kural TİPİ gerektirenler (v2 adayı): amortisman tutarlılığı (257
  birikmiş amortisman değişimi ↔ 770/730/740 amortisman payları — mizan↔mizan
  karşılaştırması motorda yok), örtülü sermaye oran testi (331 bakiye > 3×
  dönem başı öz sermaye — çok-hesap oran kuralı yok), KV beyannamesi zengin
  alanları (ticari bilanço kârı, KKEG toplamı, geçmiş yıl zararları,
  istisnalar — gerçek GİB PDF etiketleri gelmeden parser'a eklenmesi R3
  riskini büyütür).
- Rapor tarafı: II. USUL bölümüne "verilen/eksik beyanname listesi" özeti
  (şu an yalnız A bulgularının eksik dönem uyarıları akıyor) v1.1 sonrası
  iyileştirme adayı.

Durum: 235/235 test yeşil (227 + 2 kontrol + 3 CLI sertleştirme + 3 app).
Kapanış KVKK denetimi (kvkk-denetci, 10 madde): TEMİZ — anthropic yalnız
gateway'de (app.py dahil yeniden tarandı); float tutar yok; kimlik.db
izolasyonu sağlam (app.py yalnız parametre geçirir, sqlite açmaz); damga ve
TASLAK_ öneki sabit; dummy veri temiz; upload geçici dosyaları unlink'li;
test_kvkk 6/6.

## 2026-07-08 — Faz 5 tamamlandı (Modül C: rapor taslağı) → **v1 TAMAM**

Task 5.1 (metin katmanı) kararları:
- **12 j2 şablonu** SKILL.md §1-2'den: `iskelet.md.j2` (dispozisyon +
  [ELLE DOLDURULACAK]/[YMM GÖRÜŞÜ] yer tutucuları + baş/son damga) + bulgu
  kalıpları (A-KDV-HASILAT, A-MUHSGK-UCRET, A-GECICI-KV, B-131/331/689/100/190,
  ortak `bulgu_b_artis.j2`). Eşleşmeyen kod → kaynak bazlı `bulgu_a_genel.j2` /
  `bulgu_b_genel.j2` (yeni kural tipi rapora girmeden düşmez).
- **Tutarlar KODDA Türk biçimine çevrilir** (`tutar_bicimle`: 1.234.567,89 TL);
  LLM'e daima hazır biçimli string gider, LLM sayı üretmez/yuvarlamaz.
- **Yanıt doğrulaması (SKILL.md §4)**: kalıplardaki TÜM Türk biçimli tutarlar
  yanıtta birebir yoksa redaksiyon REDDEDİLİR, kalıp paragraflar redaksiyonsuz
  kullanılır (güvenli geri düşüş; bypass bayrağı yok). Bulgusuz modülde LLM
  hiç çağrılmaz.
- **Redaksiyon modül başına ayrı çağrı** (A → III.2, B → III.3): tek birleşik
  çağrı bölümlere geri ayrıştırılamazdı.
- **`geri_yerlestir` LLM-SONRASI yerel adım**: kimlik.db salt-okunur, yalnız
  bu fonksiyonda açılır (mimari kural 3 izni). Eşleşmeyen token AYNEN kalır
  (sessiz silme yok — YMM taslakta takma kodu görür).
- Eksik dönem uyarıları (A bulgu detayları) II. USUL bölümüne akar.

Task 5.2 (docx + CLI) kararları:
- `taslak_uret(depo, mukellef_id, yil, *, kimlik_db, takma_kod, cikti_dizini)`
  — mimarideki imza korunup bağımlılıklar diğer modüllerdeki desenle açık
  parametre yapıldı. Dosya adı `TASLAK_{takma_kod}_{yil}.docx`.
- Damga her section üstbilgisinde kalın + RGBColor(0xC0,0,0); gövde başı/sonu
  blockquote olarak da basılır. Markdown→docx dönüştürücü kasıtlı dar alt
  küme (yalnız iskeletin ürettiği yapılar).
- CLI `ymm rapor`: MaskeIhlali ve RuntimeError (anahtar yok) traceback'siz,
  exit 1. Uçtan uca dummy akış testi: yukle mizan → tara → rapor.
- **PowerShell notu**: çift tırnak içeren commit mesajları here-string'le
  bozuluyor — mesaj dosyaya yazılıp `git commit -F` kullanıldı.

Durum: 227/227 test yeşil (222 + 5 docx). **v1 tamam**: `ymm yukle mizan →
kontrol → tara → rapor` uçtan uca çalışıyor; LLM'siz akışlar anahtarsız,
`rapor` için `ANTHROPIC_API_KEY` ortam değişkeni gerekli (koda/repoya anahtar
girmez). Faz sonu KVKK denetimi (kvkk-denetci): TEMİZ — anthropic yalnız
gateway'de; kimlik.db yalnız geri_yerlestir'de LLM-sonrası salt-okunur;
damga/TASLAK_ kaldırılamaz; doğrulama bypass'sız; repoda docx/db sızıntısı yok.

Açık işler (v1 sonrası): YMM'nin 6 açık sorusu (docs/00-ANALIZ.md §4) ve
gerçek veri girdileri bekleniyor (gerçek mizan, gerçek GİB PDF'i → etiketler
config'e taşınacak, geçmiş anonim raporlar → SKILL.md dispozisyon güncellemesi,
tolerans tercihleri). Faz 6 (Streamlit) opsiyonel — YMM talep ederse.

## 2026-07-08 — Task 4.1 tamamlandı (LLM geçidi) → Faz 4 bitti

Teknik kararlar ve gerekçeleri:
- **`gateway.uret(istem, sistem, kimlik_db)`** mimarideki imzayla birebir.
  Akış sırası: sızıntı taraması (istem + SİSTEM — ikisi de API'ye gittiği
  için ikisi de taranır) → anahtar kontrolü → API → denetim izi.
- **İhlalli istem diske YAZILMAZ**: `MaskeIhlali` durumunda log dosyası da
  oluşturulmaz — ihlalli istemi loglamak kimliği diske sızdırmak olurdu
  (test bunu `output/` dizininin hiç oluşmadığını doğrulayarak sabitler).
- **Denetim izi**: temiz isteklerde `output/llm_log/{zaman}-{uuid8}.json`
  (zaman, model, sistem, istem, yanıt; `ensure_ascii=False`). Log yolu
  görelidir; testler `monkeypatch.chdir(tmp_path)` ile repo ağacını korur.
- **Mock stratejisi**: testler `gateway._istemci_olustur`'u monkeypatch'ler —
  suite HİÇBİR gerçek API çağrısı yapmaz; `ANTHROPIC_API_KEY` yoksa
  açıklayıcı `RuntimeError` (LLM'siz akışlara yönlendiren mesajla).
- **Model `claude-sonnet-5` sabit** (mimari karar; claude-api skill ile
  ID'nin geçerli güncel model olduğu doğrulandı). `max_tokens=16000`.
- **`istemler.py`**: `RAPOR_SISTEM_ISTEMI` (takma kod token'ları AYNEN korunur
  — geri-yerleştirme buna bağlı; tutarlar aynen; bulgu eklenmez; TASLAK/tespit
  dili) + `redaksiyon_istemi(paragraflar)` (numaralı birleştirme). Modül C
  (Task 5.1) bu ikisini gateway üzerinden kullanacak.
- kimlik.db'ye gateway doğrudan DOKUNMAZ — yalnız `dogrulayici.sizinti_tara`ya
  Path geçirir (bekçi test_kvkk: ayirici importu yasak, dogrulayici serbest).

Durum: 210/210 test yeşil (201 + 9: 7 gateway + 2 istemler). RED kanıtı:
`ModuleNotFoundError: ymm.llm.gateway`. Faz 4 tamam; sırada Faz 5
(Modül C — rapor taslağı; SKILL.md okunarak başlanacak).

Faz sonu KVKK denetimi (kvkk-denetci): TEMİZ — anthropic yalnız gateway.py;
istem+sistem her istekte taranıyor, bypass yok; gateway kimlik.db'yi doğrudan
açmıyor; ihlalli istem loglanmıyor; testler mock'lu (gerçek çağrı yok), dummy
veri; float yalnız yüzde hesaplarında.

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
