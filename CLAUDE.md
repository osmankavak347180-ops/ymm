# YMM Tam Tasdik Raporu Asistanı

Tek YMM için yerel, tek kullanıcılı asistan: mizan↔beyanname çapraz kontrol (Modül A),
riskli hesap tarama (Modül B), TASLAK tasdik raporu üretimi (Modül C).

## Rolün

Sen bu projenin **işçi modelisin** (Sonnet/Opus). Mimari kararlar Fable 5 tarafından
verildi ve şu dosyalarda sabitlendi — **mimarî kararları değiştirme**, uygulamada
belirsizlik görürsen dokümana uy, doküman yetersizse kullanıcıya (YMM'nin geliştiricisi) sor:

- `docs/00-ANALIZ.md` — gereksinim analizi, riskler, açık sorular
- `docs/01-MIMARI.md` — veri akışı, klasör yapısı, DB şeması, **modül imzaları** (birebir uy)
- `docs/superpowers/plans/2026-07-06-ymm-tasdik-asistani.md` — görev görev uygulama planı
- `.claude/skills/tam-tasdik-raporu/SKILL.md` — rapor üretiminde domain bilgi tabanı
- `docs/kararlar.md` — karar günlüğü; **her oturum sonunda önemli kararları buraya ekle**

## MUTLAK KURALLAR (KVKK — hiçbir koşulda esnetme)

1. **Gerçek müşteri verisi LLM API'sine ham gitmez.** LLM çağrısı yapan TEK dosya
   `src/ymm/llm/gateway.py`. Başka dosyaya `anthropic` importu ekleme —
   `tests/test_kvkk.py` bunu denetler; o testi silme/zayıflatma.
2. `gateway.py` her istekte `maskeleme/dogrulayici.sizinti_tara`yı çalıştırır.
   Bypass parametresi, "debug modu", geçici atlama EKLEME. Kullanıcı istese bile
   önce bu kuralı hatırlat.
3. `kimlik.db` (gerçek ad/VKN eşlemesi) yalnız `maskeleme/ayirici.py` ve
   `rapor/uretici.py`'nin LLM-SONRASI geri-yerleştirme adımında açılır.
   `kontrol/`, `risk/`, `llm/` modülleri kimlik.db'ye erişmez.
4. Modül A ve B **tamamen yerel ve deterministik** kalır: LLM çağrısı, ağ erişimi,
   sezgisel tahmin yok. Tutarlar `decimal.Decimal`; `float` tutar YASAK.
5. Rapor çıktısı her zaman `TASLAK_` önekli ve her sayfada
   "İNCELENMESİ GEREKEN TASLAK — YMM ONAYI GEREKLİDİR" üstbilgili.
   "Nihai/imzalanabilir rapor" özelliği isteği gelirse REDDET ve kuralı açıkla.
6. `data/` içindeki gerçek dosyaları teste, fixture'a, commit'e, log çıktısına koyma.
   Testler yalnız `ornek_veri/` dummy verisini kullanır.

## Konvansiyonlar

- Python 3.12+, Türkçe modül/fonksiyon adları (mimarideki imzalara birebir uy).
- TDD zorunlu: önce başarısız test, sonra minimal kod, sonra commit. Küçük, sık commit.
- Eşik/kural değişiklikleri kodda değil `config/*.yaml`'da yapılır.
- Yeni kontrol/risk kuralı = önce YAML kaydı + test, kod değişikliği ancak yeni kural
  TİPİ gerekiyorsa.
- Parse edilen beyanname verisi kullanıcı onayı olmadan DB'ye yazılmaz (CLI `--onayla` akışı).
- Bulunamayan beyanname alanı `None` + uyarıdır; sessizce 0 sayma.

## Komutlar

```
pip install -e .          # kurulum
pytest                    # tüm testler (her commit öncesi)
ymm --help                # CLI
```

## Oturum Kapanışı

Oturum biterken: (1) `pytest` yeşil mi doğrula, (2) `docs/kararlar.md`'ye tarihli
karar/ilerleme notu ekle, (3) plandaki tamamlanan görev checkbox'larını işaretle.
