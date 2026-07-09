# YMM Tam Tasdik Raporu Asistanı

Tek bir Yeminli Mali Müşavir (YMM) için **yerel, tek kullanıcılı** bir asistan.
Bulut hizmeti değildir; sunucusuz, tamamen bu bilgisayarda çalışır ve gerçek
müşteri verisi hiçbir zaman repoda veya bir bulut servisinde tutulmaz.

Üç modülden oluşur:

- **Modül A — Çapraz Kontrol:** mizan ile beyannameler (KDV, muhtasar/SGK,
  geçici vergi, kurumlar vergisi) arasındaki tutarları kural bazlı,
  deterministik olarak karşılaştırır.
- **Modül B — Riskli Hesap Taraması:** örtülü kazanç/sermaye, KKEG gibi
  bilinen risk sinyali taşıyan hesapları ve dönemsel anormal değişimleri
  statik kurallarla tarar.
- **Modül C — TASLAK Tasdik Raporu Üretimi:** bulgulardan `.docx` biçiminde
  bir rapor **taslağı** üretir. Üretilen dosya her zaman incelenmesi gereken
  bir taslaktır, imzalanabilir nihai rapor değildir.

Modül A ve B tamamen yerel/deterministiktir, ağa çıkmaz. Yalnızca Modül C,
bulguları doğal dile çevirmek için isteğe bağlı olarak Anthropic (Claude)
API'sini kullanır.

## Gereksinimler

- **Python 3.12+**
  - Windows: `py -3.12`
  - macOS/Linux: `python3.12`
- **git**

## Kurulum

```bash
git clone https://github.com/osmankavak347180-ops/ymm.git
cd ymm
py -3.12 -m pip install -e ".[dev]"
```

(macOS/Linux'ta `py -3.12` yerine `python3.12` kullanın.)

## Çalıştırma

### Streamlit arayüzü

```bash
py -3.12 -m streamlit run src/ymm/app.py
```

### CLI

```bash
py -3.12 -m ymm.cli --help
```

> Not: `py -3.12 -m ymm --help` **çalışmaz** (paketin bir `__main__.py`'si
> yok); doğru kullanım yukarıdaki gibi `ymm.cli` modülünü hedeflemektir.
> Kurulum sonrası PATH'e eklenen `ymm` komutu da (`ymm --help`) aynı CLI'yi
> çağırır.

CLI'nin sunduğu komutlar (`ymm.cli` içinden doğrulanmıştır):

| Komut | Açıklama |
|---|---|
| `yukle mizan` | Mizan Excel dosyasını okur, kimlik maskelemesi uygular, depoya yazar. |
| `yukle beyanname-ozet` | `beyanname_ozet.json` biçimindeki beyanname özetlerini depoya yazar. |
| `yukle beyanname` | Beyanname PDF'ini ayrıştırır; `--onayla` verilmeden depoya **yazmaz**, önce önizleme gösterir. |
| `kontrol` | Modül A çapraz kontrol kurallarını çalıştırır. |
| `tara` | Modül B riskli hesap taramasını çalıştırır. |
| `bulgular` | Depodaki tüm bulguları (Modül A + B) listeler. |
| `rapor` | Modül C: bulgulardan `TASLAK_` önekli `.docx` rapor taslağı üretir (Anthropic API anahtarı gerektirir). |

## Test verisi ile uçtan uca akış

Testler ve deneme çalıştırmaları **yalnızca** `ornek_veri/` altındaki uydurma
(dummy) verilerle yapılır — gerçek müşteri verisi asla kullanılmaz. Repo
kökünden çalıştırın:

```bash
py -3.12 -m ymm.cli yukle mizan ornek_veri/mizan_2025.xlsx --mukellef TEST-001 --yil 2025
py -3.12 -m ymm.cli yukle beyanname-ozet ornek_veri/beyanname_ozet.json --mukellef TEST-001
py -3.12 -m ymm.cli kontrol --mukellef TEST-001 --yil 2025
py -3.12 -m ymm.cli tara --mukellef TEST-001 --yil 2025
py -3.12 -m ymm.cli bulgular --mukellef TEST-001 --yil 2025
```

Bu akış sırasıyla: mizanı yükler (kimlik bilgisi maskelenerek `data/kimlik.db`
ve `data/veri.db` içine ayrılır), beyanname özetlerini yükler, Modül A
kontrollerini ve Modül B taramasını çalıştırıp bulguları terminalde tablo
olarak gösterir. `data/` ve `*.db` dosyaları `.gitignore` ile repodan
hariç tutulmuştur; bu komutlar sonrasında oluşan dosyaları silmekten
çekinmeyin.

Rapor taslağı üretmek isterseniz (isteğe bağlı, `ANTHROPIC_API_KEY` gerekir):

```bash
py -3.12 -m ymm.cli rapor --mukellef TEST-001 --yil 2025
```

## Testler

```bash
py -3.12 -m pytest
```

239 test içerir; hepsi yeşil olmalıdır. Testler gerçek veri veya gerçek API
çağrısı yapmaz.

## ÖNEMLİ UYARILAR

> - **Gerçek müşteri verisi bu repoda yoktur ve hiçbir kanaldan
>   paylaşılmaz.** `data/` klasörü `.gitignore` ile hariç tutulur; testler
>   yalnızca `ornek_veri/` altındaki uydurma verilerle çalışır (KVKK).
> - Üretilen rapor çıktıları her zaman `TASLAK_` önekli olur ve her
>   sayfada "İNCELENMESİ GEREKEN TASLAK — YMM ONAYI GEREKLİDİR" üstbilgisi
>   taşır. Araç **nihai/imzalanabilir rapor üretmez**; YMM incelemesi ve
>   onayı zorunludur.
> - LLM (Anthropic Claude API) kullanımı **isteğe bağlıdır** ve yalnızca
>   Modül C'de (`rapor` komutu / `src/ymm/llm/gateway.py`) devreye girer.
>   `ANTHROPIC_API_KEY` tanımlı olmadan Modül A (`kontrol`) ve Modül B
>   (`tara`) tamamen çalışır; yalnızca `rapor` komutu anahtar olmadan hata
>   verir. Projede `anthropic` paketini içe aktaran tek dosya
>   `src/ymm/llm/gateway.py`'dir.

## Lisans / Durum

Bu, tek bir YMM için hazırlanmış özel bir projedir. İzinsiz dağıtılamaz,
kopyalanamaz veya üçüncü taraflarla paylaşılamaz.
