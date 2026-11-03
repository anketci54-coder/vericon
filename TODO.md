# VERICON - Tek is listesi (2026-11-02)

## PLAN RESET / KANIT DENETIMI (2026-11-03 14:00 EET)
- [x] Baslangic hedefi AGENTS.md + README.md ile karsilastirildi: birbiriyle iliskili iki ticari modül (Fatura Hata Avcisi ve E-ticaret Hata Dedektoru). Teknik stok POC alt hedef, urunun kendisi DEGIL.
- [x] Asil sapma: tek test SKU'suna asiri odaklanma, gereksiz saatlik deneme, ikinci SKU fixture arayisi; fatura/siparis/fiyat uyusmazliklari, gercek hatanin yanlis alarmdan ayrimi ve musteri degeri henüz yok. 29 kod testi = ticari kanit degil.
- [x] Canli okuma: Shopify test mağazasinda sadece VERICON-TEST-001 var. QBO Sandbox'ta VERICON-TEST-001 (Id 19, QtyOnHand 7) ve 2026-11-03'te OLUSTURULAN VERICON-TEST-002 (Id 20, QtyOnHand 5) var. Ikincisi Shopify'da YOK. Onceki 'write islemi yok' notu ARTIK GUNCEL DEGIL; QBO test Item yazildi, daha fazla veri yazma YAPMA.
- [x] `systemd` saatlik tek-SKU test timer active; ilk otomatik 13:00 EET exit=0, sonraki zaman 14:00 EET. Bu timer urun/abonelik/cozum degil. Prod/gercek musteri taramasi yok. Servis root kullanicisi ile calisiyor; production oncesi asgari yetkiler gerekir.
- [x] Intuit `com.intuit.quickbooks.accounting` OAuth izni API tarafinda yazmaya da elverislidir; kodun kendi okuma disiplini Shopify read scopes ile ayni guvenlik garantisi DEGIL. Izinleri ve servis izolasyonunu production gate olmadan genisletme.
- [ ] ANA ONCELIK 1: Test SKUlarini cogaltmak yerine mevcut veri kaynaklarindan siparis/fatura/teslimat kayitlarinin gercekte mevcut olup olmadigini salt-okunur olc ve Modül A için en kucuk kanitli hata senaryosunu belirle. Gerekli yeni scope varsa once incele, otomatik isteme.
- [ ] ANA ONCELIK 2: Modül B icin SKU/stok disinda fiyat/urun uyusmazligi gerekliyse belge ve alan semantigini olc; veri yokken sirf test icin ek urun yazma.
- [ ] ANA ONCELIK 3: Gercek musteriye saglanan ek fayda ve odeme istegi dogrulanmadan panel, abonelik, fiyatlandirma, tam envanter crawler veya ikinci timer KURMA.
- [ ] Bu denetim artik karar kapisidir. Yeni gercek veri yazma, test fixture veya servis degisikligi KAPALI. Is bitince README/TODO guncelle + git SHA VPS=GitHub dogrula.

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
- [ ] **Karar kapisi / gecersiz onceki varsayim**: 2026-11-03 13:52 EET sonrasi QBO Sandbox'a VERICON-TEST-002 (Id 20, QtyOnHand=5) YAZILDI; Shopify'da ayni SKU halen YOK. Iki ortak SKU kaniti yok. Iki sistemde daha fazla test urunu olusturulmasi ertelendi; is ticari modullere ve veri kalitesine donduruluyor.
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
