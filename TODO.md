# VERICON - Tek is listesi (2026-11-02)

## Simdi (kapsam sabit)
- [x] QuickBooks Sandbox Item sorgusu dogrulandi: Item Id=19, SKU=VERICON-TEST-001, Type=Inventory, TrackQtyOnHand=true, QtyOnHand=7. Cikti kullanicinin Intuit API Explorer oturumundan geldi; VERICON uygulamasinin dogrudan OAuth baglantisi HALA YOK.
- [x] Shopify test magazasi verisini salt-okunur sorgula: 0 urun / 0 siparis (2026-11-02 dogrulamasi). Veri uydurma, kayitlari degistirme.
- [x] VERICON-TEST-001 kontrollu test replay: Shopify API on_hand=10, QBO kullanicinin API Explorer QueryResponse QtyOnHand=7, ayni SKU, fark=3. inventory_compare.py deterministik kod ile 3 farki hesapliyor; esit stokta 0, farkli SKU icin BLOCK. Bu gercek musteri kaybi veya canli entegrasyon kaniti degildir.
- [x] QBO Sandbox OAuth bir defa yetkilendirildi, tokenlar private/ icinde, VPS GET Item tekrar basarili: VERICON-TEST-001 QtyOnHand=7. Ek localhost tuneli gerekmiyor; servis halen baslatilmadi. Tokenin suresi dolunca otomatik refresh CANLI olarak henuz olculmedi.
- [x] Shopify VERICON Audit Test v2 kurulu; read_products/read_inventory/read_locations scope verildi. Gelistirme kimlik bilgileri private/ icinde. 2026-11-03 VPS uzerinden API ile ayni SKU icin on_hand=10, available=10, committed=0 okundu. QBO Sandbox Item QtyOnHand=7 VPS API ile okundu; shopify_read.py check ile delta=3 ve TEST_DIFFERENCE elde edildi. Kurulu ve BAGLI iki test kaynakli tek seferlik sorgu dogrulandi. Bunun gercek musteri hatasi veya saatlik otomatik tarama oldugu ileri surulmez.
- [x] Stok alanlari: Shopify on_hand yerine available / QBO QtyOnHand (available for sale) kiyasina gecildi; ayrilmis stok yanlis alarma yol acmasin diye 21 testle kontrol edildi.
- [x] Sandbox OAuth zorunlu token yenilemesini canli Intuit endpointinde test ettik: yeni access token geldi, sifreli depo guncellendi, Item 7 tekrar okundu (refresh token degismedi).
- [x] Iki canli API snapshot okuma farkini olctuk: 0.927 sn, MAX=30 sn guard eklendi ve 23 test gecti. Ticari semantik, stok hareketleri ve muhasebe esaslari henuz dogrulanmadi.
- [x] Systemd oneshot vericon-sandbox-scan.service manuel canli API cagrisi OK, Result=success/exit=0, TEST_DIFFERENCE=3, read_gap_seconds=0.917. Timer enabled+active ve ilk gelecek calisma 2026-11-03 13:00 EET olarak dogrulandi; ilk zamanlanmis calismanin gercek gerceklesmesi HENUZ dogrulanmadi.
- [x] Ilk saatlik otomatik tetikleme: 2026-11-03 13:00:04 EET (systemd LastTrigger), exit=0/Result=success, TEST_DIFFERENCE=3, Shopify available=10, QBO QtyOnHand=7, read_gap=1.166sn; sonraki tetikleme 14:00 EET. Ayrica QuickBooks Item SKU sorgusu resmî filterable alanla yapildi ve gercek Sandbox API den 200 + tek Item QtyOnHand=7 alindi. Kod artik SKUya gore ariyor; 25 test ve ayri tek-seferlik API kontrolden gecti.
- [x] Acikca secilmis 2–5 SKU icin salt okunur `python3 shopify_read.py check-many --sku SKU1 --sku SKU2` eklendi; tekilleştirme, gecersiz SKU, karisik sonuc ve bloke testleri var. 29 test gecti. Gercek VPS API denemesinde mevcut test SKU fark=3; bulunmayan ikinci SKU `BLOCKED_ITEM_READ`, hatali stok farki uretilmedi. Bu iki farkli mevcut urunun basarili kiyaslandigi anlamina GELMEZ.
- [ ] Saatlik kontrolun daha sonraki tetiklemelerini ve beklenmeyen degisimleri gozle; iki AYRI gercek Shopify+QBO SKU olmadan tum urun taramasini baslatma. Stok kapsami, fiyat/muhasebe, yalanci pozitif kanitini ayri olc.
- [x] **Gercek API preflight (2026-11-03)**: QBO Sandbox `SELECT * FROM Item` => 19 Item, SKU dolu sadece `VERICON-TEST-001` (Inventory, QtyOnHand=7). Shopify `productVariants(first:100)` => toplam 1 varyant, hasNextPage=false, SKU `VERICON-TEST-001` (tracked). Ortak SKU adedi=1. `check-many --sku VERICON-TEST-001 --sku VERICON-TEST-002`: TEST_DIFFERENCE=3 + BLOCKED_ITEM_READ (ikinci icin **delta URETILMEDI**), exit=2 beklenen. 29 test gecti. Bu, iki farkli mevcut SKU icin basarili kiyaslama kaniti DEGIL.
- [ ] **Karar kapisi:** Iki gercek, birbirinden farkli, iki sistemde de takip edilen ortak SKU olmadan `check-many` icin ikinci basarili gercek API senaryosu kanitlanamaz. Veri ekleme/write islemi yok, mevcut tek SKU timer degismedi. Kontrollu ikinci test urunu ancak ayri onay/guvenli test ortami karariyla olusturulabilir.
- [ ] Uretime gecis icin coklu-SKU, urun adi disinda Item eslestirme, butun konumlar, veri zamani ve ticari is akisi farklarini ayri kanitla. Mevcut kontrol YALNIZ test SKU.
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
