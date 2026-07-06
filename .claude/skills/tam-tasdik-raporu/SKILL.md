---
name: tam-tasdik-raporu
description: Tam tasdik (KV beyannamesi tasdik) raporu taslağı üretimi — rapor dispozisyonu, bulgu paragraf kalıpları, üslup kuralları, çapraz kontrol ve riskli hesap referansları. Modül C (rapor/) üzerinde çalışırken, şablon yazarken veya bulgu metni üretirken KULLAN.
---

# Tam Tasdik Raporu Üretimi

## 0. Değişmez Çerçeve

- Çıktı HER ZAMAN taslaktır: `TASLAK_` dosya öneki + her sayfada
  "İNCELENMESİ GEREKEN TASLAK — YMM ONAYI GEREKLİDİR" üstbilgisi.
- LLM'e giden veride yalnız takma kodlar (`[MUK-001]`, `[KISI-003]`) bulunur;
  gerçek ad geri-yerleştirme LLM'den SONRA yerelde yapılır.
- LLM görüş/kanaat ÜRETMEZ; sayısal bulguyu kalıp paragrafa döker. Vergi hukuku
  yorumu, "kabul edilebilir/edilemez" hükmü, tasdik görüşü YAZILMAZ — bunlar YMM'nin işi.
  Sonuç bölümü şablonda `[YMM GÖRÜŞÜ — ELLE DOLDURULACAK]` yer tutucusuyla boş bırakılır.

## 1. Rapor Dispozisyonu (iskelet.md.j2 bu sırayı izler)

YMM'nin geçmiş raporları alınana kadar standart dispozisyon:

1. **Kapak** — rapor sayısı/tarihi, YMM kimlik bloğu, mükellef bloğu (takma kod
   token'ları), tasdik sözleşmesi tarih/sayısı, inceleme dönemi
2. **I. GENEL BİLGİ** — unvan, faaliyet konusu, ticaret sicil, ortaklık yapısı,
   sermaye, muhasebeden sorumlu kişi/meslek mensubu, yasal defterler ve tasdik
   bilgileri, çalışan sayısı. (Çoğu alan veri setinde yok → `[ELLE DOLDURULACAK]`
   yer tutucusu bırak; UYDURMA.)
3. **II. USUL İNCELEMELERİ** — defter tasdikleri, kayıt nizamı (VUK 215-219),
   beyannamelerin verilme/ödenme durumu. Sistem verisi: hangi beyannamelerin
   yüklendiği/eksik olduğu (`EksikDonem` uyarıları buraya).
4. **III. HESAP İNCELEMELERİ** — raporun gövdesi; alt yapısı:
   - III.1 Bilanço ve gelir tablosunun mizanla uyumu
   - III.2 Çapraz kontrol sonuçları (Modül A bulguları — kontrol başına paragraf)
   - III.3 Riskli/incelemeye alınan hesaplar (Modül B bulguları — hesap başına paragraf)
   - III.4 Dönem sonucu ve matrah ilişkisi (geçici vergi ↔ KV mutabakatı)
   - III.5 KKEG, istisna ve indirimler `[ELLE DOLDURULACAK — sistem yalnız 689/679
     kaynaklı KKEG adaylarını listeler]`
5. **IV. SONUÇ** — `[YMM GÖRÜŞÜ — ELLE DOLDURULACAK]`
6. **Ekler listesi**

## 2. Bulgu Paragraf Kalıpları (bulgu tipi → j2 şablonu)

Genel kalıp deseni: *[ne karşılaştırıldı] + [iki tarafın tutarı] + [fark tutar/%]
+ [olası meşru nedenler — yalnız listelenir, hükme bağlanmaz] + [incelenmesi önerilir cümlesi]*.

### A-KDV-HASILAT
> Dönem içinde verilen KDV beyannamelerinde beyan edilen teslim ve hizmet bedelleri
> toplamı {kdv_toplam} TL olup, gelir tablosunda yer alan net satışlar tutarı
> {net_satis} TL'dir. İki tutar arasında {fark} TL ({yuzde}%) fark tespit edilmiştir.
> Farkın; duran varlık satışları, istisna kapsamındaki teslimler, iade ve iskontolar
> ile fatura dönem kaymalarından kaynaklanıp kaynaklanmadığının incelenmesi gerekmektedir.

### A-MUHSGK-UCRET
> Muhtasar ve prim hizmet beyannamelerinde beyan edilen ücret ödemeleri toplamı
> {muhsgk_toplam} TL, yasal defter kayıtlarında ücret giderlerinin izlendiği
> {hesap_listesi} hesaplarının toplamı {mizan_toplam} TL'dir. {fark} TL tutarındaki
> farkın; tahakkuk-ödeme dönem farkları ve kıdem/izin karşılıkları yönünden
> incelenmesi gerekmektedir.

### A-GECICI-KV
> Dördüncü geçici vergi dönemi matrahı {gecici_matrah} TL iken kurumlar vergisi
> beyannamesinde beyan edilen matrah {kv_matrah} TL'dir. {fark} TL farkın dönem sonu
> işlemleri (karşılıklar, amortisman farkları, KKEG düzeltmeleri) ile açıklanabilirliği
> kontrol edilmelidir.

### B-131-ORTAK (yüksek)
> {hesap_kodu} Ortaklardan Alacaklar hesabında dönem sonu itibarıyla {bakiye} TL
> bakiye bulunmaktadır. Söz konusu bakiye için KVK md. 13 kapsamında emsaline uygun
> faiz hesaplanıp hesaplanmadığı (adatlandırma) ve hesaplanan faiz üzerinden KDV
> yönünden işlem yapılıp yapılmadığı incelenmelidir.

### B-331-ORTAK (orta)
> {hesap_kodu} Ortaklara Borçlar hesabındaki {bakiye} TL bakiyenin, dönem başı öz
> sermayenin üç katını aşıp aşmadığı (KVK md. 12 örtülü sermaye) ve aşan kısma isabet
> eden finansman giderleri yönünden değerlendirilmesi gerekmektedir.

### B-689-KKEG (orta)
> 689 Diğer Olağandışı Gider ve Zararlar hesabında izlenen {bakiye} TL'nin içeriği
> itibarıyla kanunen kabul edilmeyen gider niteliğinde olup olmadığı ve beyannamede
> KKEG olarak dikkate alınıp alınmadığı incelenmelidir.

### B-100-KASA (orta)
> Kasa hesabının dönem sonu bakiyesi {bakiye} TL olup işletme büyüklüğüne göre yüksek
> görünmektedir. Kasa mevcudunun fiilen bulunup bulunmadığı ve yüksek bakiyenin
> adatlandırma gerektirip gerektirmediği değerlendirilmelidir.

### B-190-DEVREDEN (düşük)
> Devreden KDV tutarı {bakiye} TL'dir. Devreden KDV'nin kaynağı ve indirim
> hesaplarının dönemsel uyumu gözden geçirilmelidir.

### B-*-ARTIS (karşılaştırmalı)
> {hesap_adi} ({hesap_kodu}) hesabının bakiyesi önceki dönemde {onceki} TL iken cari
> dönemde {cari} TL'ye yükselmiş olup değişim oranı %{yuzde}'dir. Artışın
> nedenlerinin belgeleriyle birlikte incelenmesi gerekmektedir.

Yeni bulgu tipi eklenirse: aynı desenle kalıp yaz, bu dosyaya ekle, j2 şablonunu oluştur.

## 3. Üslup Kuralları (LLM redaksiyon istemine gömülür)

- Resmi rapor Türkçesi; edilgen/üçüncü şahıs ("tespit edilmiştir", "incelenmesi gerekmektedir").
- Kesin hüküm YOK: "hatalıdır" değil "incelenmesi gerekmektedir"; "kaçırılmıştır" değil
  "fark tespit edilmiştir".
- Tutar biçimi: `1.234.567,89 TL` (Türk biçimi — biçimlendirme kodda yapılır, LLM'e
  hazır biçimli string verilir; LLM sayı ÜRETMEZ/yuvarlamaz).
- Mevzuat atıfları yalnız kalıplardaki kadar; LLM yeni madde numarası eklemez.
- Bulgular seviye sırasıyla dizilir: yüksek → orta → düşük.

## 4. LLM İstem Stratejisi (Modül C)

- Sistem istemi: rol (YMM rapor redaktörü) + üslup kuralları (§3) + "verilen sayı ve
  kalıpların DIŞINA çıkma, yeni olgu/mevzuat ekleme" kısıtı.
- Kullanıcı istemi: doldurulmuş kalıp paragraflar (j2 çıktısı) + "akıcı, tekrarsız,
  aynı üslupta redakte et; sıralamayı ve tüm sayıları aynen koru".
- LLM'e HAM bulgu JSON'u değil, doldurulmuş kalıp verilir — halüsinasyon yüzeyi küçülür.
- Yanıt doğrulaması (kodda): yanıt, girdideki tüm tutar string'lerini birebir içermeli;
  içermiyorsa yanıt reddedilir ve kalıp paragraflar redaksiyonsuz kullanılır (güvenli geri düşüş).

## 5. Çıktı Öncesi Kontrol Listesi (taslak_uret her çağrıda)

- [ ] Tüm `acik` bulgular rapora girdi mi? (bulgu sayısı == paragraf sayısı)
- [ ] Yanıttaki tutarlar girdiyle birebir aynı mı? (§4 doğrulaması)
- [ ] `[KISI-*]`/`[MUK-*]` token'ları geri-yerleştirildi mi? (docx'te token kalmamalı)
- [ ] `[ELLE DOLDURULACAK]` yer tutucuları duruyor mu? (silinmemeli — YMM görecek)
- [ ] Üstbilgi damgası her section'da var mı? Dosya adı `TASLAK_` önekli mi?
- [ ] Eksik dönem uyarıları (II. bölüm) rapora yansıdı mı?

## 6. Geçmiş Rapor Adaptasyonu (ileride)

YMM anonimleştirilmiş geçmiş rapor verdiğinde: dispozisyonu ve kalıp cümleleri o
raporlardan çıkar, §1-2'yi güncelle, j2 şablonlarını yeniden üret. Şablon değişikliği
= bu SKILL.md'nin de güncellenmesi demektir; ikisi birlikte commit edilir.
