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
