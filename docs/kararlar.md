# Karar Günlüğü

İşçi model her oturum sonunda tarihli not ekler (en yeni üstte).

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
