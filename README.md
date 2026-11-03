# VERICON

Durum: Baslangic deposu (2026-11-02). Canli urun veya dogrulanmis hata tespit sistemi yok.

## Hedef
Mevcut yazilimlari degistirmeden e-ticaret ve muhasebe verilerindeki gercek uyusmazliklari kanitlariyla gosteren, yalnizca okuma yetkili bagimsiz denetim araci.

## Ilk kapsam
- Hedef kitle: Shopify + QuickBooks Online kullanan stoklu perakendeciler.
- Modul A: Fatura / siparis / teslimat tutar ve miktar uyusmazligi.
- Modul B: E-ticaret urun / SKU / stok / fiyat uyusmazligi.
- Iki modul bagimsiz satilabilir; ikisini alan tek panelde capraz kontrol gorur.
- Ilk surum veriyi DEGiSTiRMEZ; supheli farklari belge ve kayit dayanaklariyla gosterir.
- AI gerekiyorsa yalnizca belge okuma / aday eslestirme icin; parasal hesaplar deterministik.

## Dogrulanmis mevcut durum (2026-11-02)
- Shopify baglantisi: calisti. Bagli magaza deneme planinda, sorguda 0 urun ve 0 siparis.
- QuickBooks Online Plus sandbox: CompanyInfo HTTP 200 ve Item SKU=VERICON-TEST-001, QtyOnHand=7 API Explorer sonucuyla dogrulandi. VERICON uygulamasinin dogrudan QuickBooks OAuth API erisimi HENUZ kurulmadı.
- 2026-11-03: Shopify bagli deneme magazasinda draft SKU=VERICON-TEST-001 on_hand=10; kontrollu replayde inventory_compare.py 3 adet farki hesapladi, esitlik ve farkli SKU engelleme kontrolleri de gecti. Bu test kaydi, gercek musteri zarari veya canli iki yonlu API baglantisi degildir.
- Ilk fiyat hipotezleri: tek modul 49 USD/ay, iki modul 69 USD/ay, yuksek hacim 99 USD/ay. Talep ve kar dogrulanmadi.
- Rakipler: mevcut mutabakat / stok yazilimlari var; rekabet ustunlugu kanitlanmadi.

## Ilk teknik karar kapisi
Ayni SKU, depo, stok anlami, para birimi ve zaman anini esitlenmis veriler uzerinden uyusmazlik hesapla; gercek hata / yanlis alarm / bilinmeyen ayrimini olc. Ornek veya sandbox veriyle canli musteri faydasi iddia etme.

## Guvenlik
Gercek sifre, OAuth client secret, access/refresh token, musteri kaydi veya kisisel veri GitHub'a koyulmaz. Sandbox disinda degisiklik yapmadan once ayrica onay gerekir. Kod ve servisler henuz baslatilmadi.

Guncel is listesi: TODO.md. Muhendislik kurallari: AGENTS.md.

## QuickBooks Sandbox OAuth baglanti bileseni (2026-11-03)
- Kod: qbo_oauth.py (yalnizca Sandbox API; GET Item sorgusu). Test: test_qbo_oauth.py.
- Yetenekler: OAuth state+CSRF kontrolu, yetki kodu degisimi, local sifreli token kasasi, token rotasyonu/yenileme ve salt okunur Item sorgusu. Sandbox dogrudan baglanti henuz YAPILMADI.
- Entegrasyonun tamamlanmasi icin: Intuit Developer Development Client ID/Secret, tanimli callback ve kullanicinin bir kez OAuth onayi gerekli. Bunlar yokken kod sadece test edilebilir; servis baslatilmaz.
- SANDBOX icin alan adi satin almak GEREKMIYOR: Intuit, localhost HTTP callback destekliyor. Gelistirme testinde http://localhost:8782/oauth/quickbooks/callback adresi Intuit Development settings icine kaydedilebilir; kullanicinin tarayicisindan VPS localhost portuna SSH-L tüneliyle guvenli ulasim gerekir. Windows SSH tüneli veya yerel agent bagli degilse kisisel OAuth akisi baslatma. Production icin ayri HTTPS zorunludur.
- Onceki ekran goruntusunde Authorization Basic degeri paylasildigi icin Development Client Secret yenilenmelidir. Anahtari asla sohbete veya GitHub'a koyma.
- Ozel konfigurasyon ornegi: .env.example; gercek dosya private/qbo.env olarak chmod 600 ve dizin chmod 700 ile saklanir. Git deposu disinda veya gitignore ile koruma altindadir.
- Gelistirme sunucusunu sadece 127.0.0.1:8782 adresinde uvicorn qbo_oauth:app --host 127.0.0.1 --port 8782 --no-access-log ile calistir. HTTPS ters vekili ileride kurulursa /oauth/quickbooks/callback sorgu dizisini access log'a yazma; auth code sizar. Mevcut Nginx sitelerine dokunulmaz.
- OAuth scope = com.intuit.quickbooks.accounting. Bu scope Intuit tarafinda teknik olarak sadece okuma yetkisi DEGILDIR; bizim adaptorumuz yalnizca GET yapar. Canli muhasebe sirketine baglama.
- Yetkili ortam kurulduktan sonra: python3 qbo_oauth.py auth-url -> Intuit tek seferlik izin -> GET /oauth/quickbooks/callback -> python3 qbo_oauth.py item --name 'VERICON TEST'. Baska islem yapilmaz.
- Not: QuickBooks baglantisi VERICON'a ait olmalidir. Intuit API Explorer'dan alinan gecici token VERICON'un token deposu degildir.

### Tek seferlik yerel kurulum yardimcisi
- qbo_setup.py: Development Client ID/Secret ve Sandbox realm ID'yi terminalde gizlice alir, private/qbo_setup.json dosyasina 0600 yetkisiyle kaydeder. Kodu ve sirri sohbete veya shell history'ye yazma.
- SSH localhost port yonlendirmesi (8782) aktifken OAuth izin linkini acip Intuit onayi verir; sadece localhost'a bagli gecici callback'i kullanir. Yetki bitince ilk VERICON TEST Item sorgusunu okur, sunucuyu kapatir. Bu dosya yayinlanan servis degildir.
- Ilk kurulumdan once, daha once ekran goruntusunde gorunen Development Client Secret rotasyonu/degişimi yetkili Intuit panelinde dogrulanmali. UI rotasyonu desteklemiyorsa hesap yetkilisi tarafindan yeni sandbox uygulamasi veya resmi Intuit destek yolu degerlendirilmeli.
- Bu islemler sadece gelistirme ortaminda kullanilacak; production baglantisi yok.

## QuickBooks baglantisi dogrulama (2026-11-03)
- Kullanici Intuit Sandbox'a bir defa OAuth izni verdi; VPS'de kilitli private klasorden token okuma ve yeni GET /Item dogrulandi.
- Gercek veri: SKU VERICON-TEST-001, Inventory, TrackQtyOnHand=true, QtyOnHand=7. Shopify'da ayni SKU on_hand=10. Fark=3, kasitli test.
- `python3 qbo_oauth.py --saved-setup status` sadece tokenin kayitli olmasini/sona ermesini bildirir; secret yazmaz.
- `python3 qbo_oauth.py --saved-setup item --name 'VERICON TEST'` sandbox Item GET ve gerekli olursa refresh token yenilemesini dener; json sadece secilen Item alanlarini icerir. Bu otomatik servis/cron degildir.
- Callback tuneli kapandi: kodu almaya yarayan gecici portun kapatılması normal; veri okuma icin yeni tunel gerekmez.
- Shopify ChatGPT eklentisi OAuth jetonlari VPS'ye aktarilmaz. Iki kaynagi tek VPS calistiricisindan otomatik okumak icin ayri Shopify yetkilendirmesi hala gerekli.
- Dogrulanan: OAuth saklama + QBO Item canli okuma. Dogrulanmayan: gercek sure dolunca refresh basarisi, Shopify otomasyonu, periyodik isci, musteri kaybi/kar.

## Shopify VPS baglantisi (2026-11-03)
- Kod: shopify_read.py; cevrimdisi test: test_shopify_read.py. Tek test Shopify magazasi: hudys3-p0.myshopify.com.
- Shopify Dev Dashboard uzerinden VERICON icin kendi magazamiza kurulan bir app gerekir. ChatGPT'nin Shopify plugin baglantisiyla VPS kimlik bilgileri farklidir.
- Mevcut test magazasiyla AYNI Shopify organization icindeyse client_credentials grant kullanilir. Baska bir organization musterisinde kullanmak icin bu akisi yeniden kullanma, ayri onay/dağıtım akisi gerekir.
- Shopify Admin > Settings > Apps > Develop apps > Build apps in Dev Dashboard > Create app > Start from Dev Dashboard.
- App adi: VERICON Audit Test. Yeni version: App URL as default https://shopify.dev/apps/default-app-home, access scopes SADECE read_products,read_inventory,read_locations; Release. Installs > Install app, hudys3-p0.myshopify.com sec ve yetkileri kontrol et.
- Sonra Dev Dashboard > App Settings > Credentials icindeki Client ID ve Secret'i SOHBETE GONDERMEDEN VPS'de interaktif olarak gir: python3 shopify_read.py setup. Bu komut kimlik bilgilerini 0600 izinli private/ dosyasina koyar, konsola veya GitHub'a yazmaz.
- `python3 shopify_read.py stock --sku VERICON-TEST-001`: Iki kaynak degil, sadece Shopify'a sunucudan baglanip stok durumlarini ve konumlari okur.
- `python3 shopify_read.py check --sku VERICON-TEST-001`: Shopify ve QBO Sandbox verilerini iki API'den tek seferlik okur; kontrollu testte 3 farki hesaplamasi beklenir. Bu komut veriyi degistirmez ve servisi devamli calistirmaz.
- 2026-11-03: ChatGPT Shopify baglantisindan ayni SKU icin GraphQL read dogrulandi: on_hand=10, available=10, committed=0, bir konum. VPS uzerinden Shopify API yetkilendirmesi HENUZ YOK.
- Bağımsız musteri verisinde stok anlamini, depo sayisini, rezervleri ve anlik zaman farkini dogrulamadan gercek kayip yorumu yapma. Buradaki fark yapay test verisidir.
- Shopify mağazasi trial planinda; satis icin plana gecmek gerekir, ancak test sirasinda bunu yapma.

### Bagli iki API ile ilk gercek okuma (2026-11-03)
- Geliştirici test magaza hesabi Shopify Dev Dashboard app v2 izinleri: read_products, read_inventory, read_locations. Client credentials sunucu private/ icinde, token API uzerinden alindi.
- VPS Shopify GraphQL sonucunda VERICON-TEST-001: on_hand=10 / available=10 / committed=0, tek konum.
- VPS QBO Sandbox sonucunda VERICON-TEST-001: QtyOnHand=7, Inventory, tracked=true.
- `python3 shopify_read.py check --sku VERICON-TEST-001` bu iki canli API yanitini ayni cagri akisi icinde alip farki 3 olarak dondu (TEST_DIFFERENCE).
- Henuz otomatik zamanlama/servis yok. Shopify testi trial magazada; QuickBooks Sandbox. Bu kasitli fark, ticari zarar kaniti DEGIL.

## 2026-11-03 stok semantigi duzeltmesi
- Shopify `on_hand` fiziksel toplamdir: available + committed + reserved + damaged + safety_stock + quality_control. QuickBooks `Item.QtyOnHand` dokumanda "available for sale" olarak tanimlanir.
- Bu nedenle VERICON farki icin Shopify `available` ile QBO `QtyOnHand` karsilastirilir; Shopify `on_hand` ayrica kanit olarak korunur. Committed/reserved stokun varligi otomatik kayip kaniti degildir.
- Tek depo ve SKU kanitlanmadan, zaman farkini ve stok hareketlerini denetlemeden ticari kayip raporlanmaz. Kontrollu test `VERICON-TEST-001` icin iki API'den Shopify available=10, QBO QtyOnHand=7, delta=3.
- Kaynak: Shopify inventory quantities states; QuickBooks Item API reference.

## Sandbox-saatlik deneme (2026-11-03)
- Yalnizca VERICON-TEST-001 kontrollu SKU; saatlik, GET yalnizca okuma. systemd unit kaynaklari: deploy/vericon-sandbox-scan.service ve deploy/vericon-sandbox-scan.timer.
- Kullanicinin gercek stok ve muhasebe kayitlarini degistirmez, panel/uyari/odeme servisi degildir. Test sonucu TEST_DIFFERENCE sadece kurgusal SKU farkidir.
- Shopify available ile QBO QtyOnHand karsilastirilir; on_hand raporlanir. Iki okuma arasindaki zaman farki 30 saniyeyi asarsa BLOCKED_SNAPSHOT_TIME_GAP doner; bu kapinin ticari gecerliligi henuz olculmedi.
- Acilis yetkisi root private dizini icindir, kimlik bilgileri ve OAuth jetonlari GitHub veya systemd unit dosyalarina yazilmaz. OAuth refresh kodu once gercek Sandbox token degisimiyle kontrol edildi; refresh token her seferinde degismek zorunda degil.
- Kontrol: systemctl status vericon-sandbox-scan.timer; journalctl -u vericon-sandbox-scan.service -n 15 --no-pager. Durdur: systemctl disable --now vericon-sandbox-scan.timer.

## Saatlik kontrollu deneme: durum (2026-11-03)
- Tek SKU read-only systemd oneshot manuel olarak basariyla calistirildi; iki kaynakli sonuc TEST_DIFFERENCE delta=3; QBO QtyOnHand=7, Shopify available=10, query read gap 0.917 sn.
- Systemd timer aktif/enable; ilk planli calisma 2026-11-03 13:00 EET. Zamanlayicinin gelecekte otomatik basarisi henuz gozlenmedi.
- Terminal veya tarayici acik tutmak gerekmez. Sadece tek test SKU; otomatik stok duzeltme, mesaj ve gercek musteri raporu YOK.
- `systemctl status vericon-sandbox-scan.timer` ve `journalctl -u vericon-sandbox-scan.service -n 20 --no-pager` ile gercek sonuc okunabilir.
- `systemctl disable --now vericon-sandbox-scan.timer` ile otomasyon aninda kapatilir. Kullanilmayan baska projelere dokunulmadi.

## Ilk zamanlanmis gercek calisma ve SKU aramasi (2026-11-03)
- systemd timer ilk otomatik tetikleme 13:00:04 EET; servis 13:00:06 EET basarili cikis (Result=success, ExecMainStatus=0). Iki API result: Shopify available=10, QBO QtyOnHand=7, kontrollu fark=3, read_gap=1.166 saniye.
- Intuit Item API `Sku` alaninin filterable oldugu dogrulandi ve Sandbox API `SELECT * FROM Item WHERE Sku = 'VERICON-TEST-001'` sorgusu 200 OK + tek Item sonucunu verdi. Kontrol kodu artik QuickBooks urun adini sabitlemez, dogrudan istenilen SKU ile sorgular. Tekilleşmeyen SKU BLOCK olur.
- Bu tek-SKU test kontrolunun calismasini dogrular; envanterde ticari dogruluk, diger SKUlar, musteri bazli yanlis alarm ve finansal etki henuz dogrulanmadi. Timer hala ayni test SKU ile saatlik calisir.
