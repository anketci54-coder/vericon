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
