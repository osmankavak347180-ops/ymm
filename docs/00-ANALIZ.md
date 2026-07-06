# YMM Tam Tasdik Raporu Asistanı — Gereksinim Analizi

> Hazırlayan: Fable 5 (baş mimar rolü). Bu doküman inşa öncesi tek seferlik analizdir.
> İşçi model (Sonnet/Opus) inşa sırasında bu dokümanı bağlam olarak okur, değiştirmez.

## 1. Problem Özeti

Tek YMM için yerel, tek kullanıcılı asistan. Üç iş yükü hedefleniyor:

1. **Mutabakat/çapraz kontrol** (mizan ↔ beyannameler) — bugün elle Excel'de yapılıyor, mekanik ve hataya açık.
2. **Riskli hesap taraması** — dönem karşılaştırmalı, deneyime dayalı; kurallaştırılabilir.
3. **Rapor taslağı yazımı** — standart iskelet + bulgulara göre değişen bulgular bölümü.

Hedef: toplam iş yükünde %50 azalma. Sistem hiçbir zaman nihai rapor üretmez; her çıktı YMM onayı bekleyen taslaktır.

## 2. Teknik Karşılanabilirlik Değerlendirmesi

### Modül A — Çapraz Kontrol Motoru: ✅ Tamamen kural bazlı yapılabilir

Kontroller aritmetik eşitlik/eşleşme + tolerans karşılaştırmasıdır. LLM gereksiz ve **zararlı** (halüsinasyon riski). Kritik tasarım noktaları:

- **Dönem hizalama:** KDV aylık, muhtasar aylık, geçici vergi 3'er aylık kümülatif, KV yıllık. Motor, aylık beyanname verilerini kümülatif toplayıp yıllık mizanla karşılaştırabilmeli. Dönem modeli (yıl + ay/çeyrek) veri katmanında birinci sınıf kavram olmalı.
- **Meşru farklar:** KDV matrahı ≠ net satışlar birebir. Meşru mutabakat kalemleri var: duran varlık satışları (KDV matrahına girer, hasılat değildir), istisna teslimler, iade/iskonto, avans faturaları, vade/kur farkı faturaları, özel matrah şekilleri. Motor bu kalemleri **konfigüre edilebilir mutabakat kalemleri** olarak modellemelidir; aksi halde her mükellefte yalancı pozitif üretir.
- **Tolerans:** Mutlak (TL) + oransal (%) çift eşik, kontrol başına YAML'da ayarlanabilir. Varsayılanları YMM belirler.
- **Sıfır hata payı ilkesi:** Tüm tutar aritmetiği `Decimal` ile yapılmalı, float asla kullanılmamalı. Her kontrol deterministik ve birim testli.

### Modül B — Riskli Hesap Tarayıcı: ✅ Kural bazlı + LLM sadece yorum katmanı

İki tarama tipi:
1. **Statik kural:** belirli hesapların varlığı/bakiyesi kendi başına risk sinyali (131/231 ortaklardan alacaklar → örtülü kazanç/adat; 331/431 → örtülü sermaye testi; 689/679 → KKEG; 100 yüksek kasa → adat; 190 sürekli devreden KDV).
2. **Dönemsel karşılaştırma:** önceki dönem bakiyesine göre anormal artış/azalış (eşik: % değişim + mutlak tutar tabanı — küçük bakiyelerdeki büyük yüzdeler gürültü üretmesin diye ikisi birlikte).

Risk seviyesi (düşük/orta/yüksek) kural konfigürasyonunda tanımlı; kod atar, LLM atamaz. LLM yalnızca Modül C'de bulguyu doğal dile çevirirken devreye girer.

### Modül C — Rapor Taslağı Üretici: ✅ Şablon + kısıtlı LLM

- Rapor iskeleti (kapak, genel bilgi, usul incelemeleri, hesap incelemeleri, sonuç) **statik şablon** — LLM iskelet üretmez, sadece bulgular bölümündeki paragrafları maskelenmiş bulgu verisinden yazar.
- Her bulgu tipi için hazır paragraf şablonu (SKILL.md'de) → LLM'in görevi büyük oranda "şablonu veriyle akıcı doldurma". Bu, halüsinasyon yüzeyini küçültür.
- Çıktı `.docx`, her sayfada üstbilgi: **"İNCELENMESİ GEREKEN TASLAK — YMM ONAYI GEREKLİDİR"**; dosya adı `TASLAK_` önekli. Bu, kodda zorunlu, parametreyle kapatılamaz.

## 3. Riskler

| # | Risk | Etki | Azaltım |
|---|------|------|---------|
| R1 | Mizan format çeşitliliği (Luca/Logo/Mikro/ETA farklı Excel yapıları) | Parser kırılır | Kolon haritalama YAML'ı; parser haritaya göre çalışır, formata gömülü varsayım yok |
| R2 | Beyanname PDF'i taranmış görüntü çıkarsa | Metin çıkarılamaz | v1 kapsamı: yalnızca e-beyanname metin-PDF. Taranmışsa kullanıcıya net hata + manuel giriş ekranı (CSV) alternatifi |
| R3 | GİB beyanname PDF yapısı sürüm değişikliği | Alan eşleşmeleri kayar | Beyanname tipi başına ayrı parser + "çıkarılan alanları göster, onayla" adımı; parse sonucu YMM görsel doğrulamadan DB'ye yazılmaz |
| R4 | Yalancı pozitif bolluğu (mutabakat kalemleri modellenmezse) | Güven kaybı, araç terk edilir | Mutabakat kalemi mekanizması + kontrol başına tolerans; ilk dönemlerde eşikler gevşek başlar, YMM geri bildirimiyle sıkılır |
| R5 | Kimlik sızıntısı (LLM'e ham veri) | KVKK ihlali | Tek geçit mimarisi: yalnızca `llm/gateway.py` API çağırır; çağrı öncesi zorunlu sızıntı taraması; kimlik haritası ayrı DB dosyasında, LLM yolunda hiç açılmaz |
| R6 | İşçi modelin maskelemeyi "kolaylık olsun diye" bypass etmesi | KVKK ihlali | CLAUDE.md'de mutlak yasak + mimaride `anthropic` importu tek dosyada + sızıntı testleri CI kapısı |
| R7 | Taslak raporun bitmiş sanılması | Mesleki sorumluluk | Zorunlu taslak damgası (kod seviyesi), "nihai rapor üret" özelliği hiç yok |
| R8 | Hesap planı sapmaları (mükellef alt hesap yapıları farklı) | Kural eşleşmez | Kurallar 3 haneli ana hesap prefix'iyle eşleşir (`770*`), gerekirse mükellefe özel istisna listesi |

## 4. Açık Sorular (YMM'ye sorulacak — inşayı bloklamaz)

1. Gerçek mizan Excel örneği hangi programdan geliyor? (Kolon haritası buna göre doldurulacak; iskelet formata bağımsız.)
2. Beyanname PDF'leri e-beyanname sisteminden mi indiriliyor (metin tabanlı mı)?
3. Geçmiş 2-3 tasdik raporu (anonimleştirilmiş) şablon çıkarımı için verilebilir mi? Verilene kadar SKILL.md'deki genel iskelet kullanılır.
4. Kontrol toleransları: KDV matrahı ↔ net satış farkında hangi mutlak/oransal eşik "bulgu" sayılsın? (Varsayılan: %1 veya 10.000 TL, büyük olan.)
5. Önceki dönem mizanı her mükellef için mevcut mu? (Modül B karşılaştırmalı tarama için gerekli; yoksa yalnızca statik kurallar çalışır.)
6. Muhtasar karşılaştırması MUHSGK toplam brüt ücret üzerinden mi, tahakkuk bazında mı yapılıyor?

## 5. Teknoloji Kararları (gerekçeli)

| Karar | Seçim | Gerekçe |
|-------|-------|---------|
| Dil | Python 3.12+ | pandas/openpyxl/pdfplumber ekosistemi; Windows'ta sorunsuz |
| Excel parse | `openpyxl` + `pandas` | Standart, sağlam |
| PDF parse | `pdfplumber` | e-beyanname metin PDF'lerinde tablo/alan çıkarımı için en pratik |
| Tutar tipi | `decimal.Decimal` | Float yuvarlama hatası kabul edilemez |
| DB | SQLite (2 ayrı dosya: `veri.db` + `kimlik.db`) | Tek kullanıcı, yerel; kimlik haritasının fiziksel ayrımı KVKK katmanını basitleştirir |
| Config | YAML (`config/*.yaml`) | YMM'nin eşik/kural düzenlemesi kod değişikliği gerektirmesin |
| Rapor çıktısı | `python-docx` | YMM Word'de düzenleyecek |
| LLM | Anthropic API, `claude-sonnet-5` (yalnızca Modül C) | Maliyet/kalite dengesi; tek geçit üzerinden |
| Arayüz | v1: CLI (`typer` + `rich` tabloları). v2 (opsiyonel): Streamlit | CLI test edilebilir, hızlı inşa edilir; Streamlit sonradan aynı core'u sarar |
| Test | `pytest`, dummy veri `ornek_veri/` | TDD zorunlu; gerçek veri test fixture'ı olamaz |

## 6. Kapsam Dışı (v1 — YAGNI)

- OCR / taranmış PDF desteği
- Çok kullanıcılı yapı, web deploy, Supabase
- E-imza, GİB entegrasyonu, otomatik beyanname indirme
- Karşıt inceleme tutanağı otomasyonu (v2 adayı)
- Enflasyon düzeltmesi hesaplamaları (v2 adayı — kural motoru genişletilebilir tasarlanacak)
