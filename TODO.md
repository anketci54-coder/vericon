# VERICON - Tek is listesi (2026-11-02)

## Simdi (kapsam sabit)
- [ ] QuickBooks Sandbox Item sorgusunu 200 OK + gercek QueryResponse.Item ile dogrula. Intuit tarayicisinda CompanyInfo HTTP 200 goruldu; ancak kullanicinin Intuit OAuth oturumu VPS/ChatGPT baglantisi degil. Kullaniciya tekrar Account sayfasi uzerinden sorgu yaptirma; resmi Item API Query an item hazir ornek SELECT * FROM Item maxresults 2 yeterli.
- [x] Shopify test magazasi verisini salt-okunur sorgula: 0 urun / 0 siparis (2026-11-02 dogrulamasi). Veri uydurma, kayitlari degistirme.
- [ ] Iki kaynak icin eslesebilir ayni SKU/tarih/lokasyon/para birimi verilerini olustur veya uygun test kaydiyla eslestir.
- [ ] Salt-okunur karsilastirmada bulunan fark, yanlis alarm ve belirsiz kayit sayilarini raporla.
- [ ] Ucretli urun kararindan once rakipten ek faydayi ve gercek musteri odeme istegini olc.

## DAHA SONRA - simdi yapma
- [ ] Claude Code/Codex icin token ve tekrar optimizasyonunu degerlendir (TokenEconomizer ve gerekirse Claude-Mem / Aider). Ilk is: repo lisansi, guvenlik, kurulum davranisi ve mevcut araclarin ozellikleriyle cakismayi kontrol et.
- [ ] Degisiklik yapmadan ayni sinirli kodlama gorevinde taban olcum al (token, maliyet, sure, tekrar, gercek dogruluk). Sonra yalnizca izole test ortaminda tek optimizasyonu karsilastir. Etki yoksa KURMA.
- [ ] Claude Pro / ChatGPT Plus / API harcamalarini yalnizca gercek kullanim ihtiyacina gore belirle.
- [ ] Alan adi / marka tescilini ayrica incele; domain SATIN ALMA.
- [ ] Gercek veri dogrulamasindan once VPS servisi, panel, odeme veya canli entegrasyon ACMA.

## Karar bekleyen
- Fiyatlar 49/69/99 USD sadece hipotez; satis ve hizmet maliyeti olculmedi.
- Shopify QuickBooks ortak kullanici ve ayrica ucretli denetim isteyen musteri sayisi bilinmiyor.
