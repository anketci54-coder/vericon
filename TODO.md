# VERICON - Tek is listesi (2026-11-02)

## Simdi (kapsam sabit)
- [x] QuickBooks Sandbox Item sorgusu dogrulandi: Item Id=19, SKU=VERICON-TEST-001, Type=Inventory, TrackQtyOnHand=true, QtyOnHand=7. Cikti kullanicinin Intuit API Explorer oturumundan geldi; VERICON uygulamasinin dogrudan OAuth baglantisi HALA YOK.
- [x] Shopify test magazasi verisini salt-okunur sorgula: 0 urun / 0 siparis (2026-11-02 dogrulamasi). Veri uydurma, kayitlari degistirme.
- [x] VERICON-TEST-001 kontrollu test replay: Shopify API on_hand=10, QBO kullanicinin API Explorer QueryResponse QtyOnHand=7, ayni SKU, fark=3. inventory_compare.py deterministik kod ile 3 farki hesapliyor; esit stokta 0, farkli SKU icin BLOCK. Bu gercek musteri kaybi veya canli entegrasyon kaniti degildir.
- [x] QBO Sandbox OAuth bir defa yetkilendirildi, tokenlar private/ icinde, VPS GET Item tekrar basarili: VERICON-TEST-001 QtyOnHand=7. Ek localhost tuneli gerekmiyor; servis halen baslatilmadi. Tokenin suresi dolunca otomatik refresh CANLI olarak henuz olculmedi.
- [x] Shopify VERICON Audit Test v2 kurulu; read_products/read_inventory/read_locations scope verildi. Gelistirme kimlik bilgileri private/ icinde. 2026-11-03 VPS uzerinden API ile ayni SKU icin on_hand=10, available=10, committed=0 okundu. QBO Sandbox Item QtyOnHand=7 VPS API ile okundu; shopify_read.py check ile delta=3 ve TEST_DIFFERENCE elde edildi. Kurulu ve BAGLI iki test kaynakli tek seferlik sorgu dogrulandi. Bunun gercek musteri hatasi veya saatlik otomatik tarama oldugu ileri surulmez.
- [ ] Ilk sonraki teknik karar: stok alanlarinin gercek ticari semantigini ve zaman farkini dogrula; baglantilari cron/service ile otomatiklestirmeden once tek-dongu snapshot kalitesini olc. Token yenilemesini gercek vade sonunda dogrula.
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
