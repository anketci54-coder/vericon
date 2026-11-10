# VERICON - Gelistirme kurallari

1. Ana hedef: Shopify ve QuickBooks Online verilerinin bagimsiz, kanitlanabilir, salt-okunur uyusmazlik denetimi. ERP, envanter yoneticisi veya otomatik muhasebe kaydi olusturma projesine donusturme.
2. Once olc, sonra karar ver. Kod degistirmeden once runtime ve kanitli kok nedeni belirle; tek nedensel degisiklik yap, test et, gercek davranisi dogrula.
3. Shopify inventory_quantity ile QuickBooks QtyOnHand alanlarini korlemesine karsilastirma. Lokasyon, rezerve/stokta/mevcut, zaman damgasi ve SKU ayniligi kanitlanmadan fark diye etiketleme.
4. Parasal kurallar (vergi, indirim, iade, para birimi, birim fiyat, yuvarlama) deterministik olmali. AI sonucu tek basina finansal gercek olamaz. Bilinmeyen = incelemeye al.
5. Once QuickBooks Sandbox ve bos Shopify deneme magazasiyla sinirli calis. Gercek musteri verisi, API yetki artisi, canli servis veya veri degisikligi icin ayri onay gerekir.
6. Token, client secret, .env, gercek veriler, fatura ve musteri bilgilerini depoya koyma, loglarda paylasma. Gerekiyorsa mevcut gizli depolama cozumunu kontrollu belirle.
7. Iki AI ayni dosyada paralel degisiklik yapmaz. Degisikliklerin diff'i, test sonucu ve uygulama davranisi ayri dogrulanir.
8. Yeni framework, refactor, servis, konteyner, dokuman, branch veya ek API ancak kanitli ihtiyac varsa acilir.
9. Projeyi diger VPS uygulamalarindan izole tut. SMRS ve Senal Plastik servislerine dokunma.
10. 'Hazir' veya 'basarili' sadece uctan uca kanitli sonuc icin kullanilir. Halen herhangi bir musteri sonucu dogrulanmadi.

11. Dis sistemde urun, stok, item, fatura, siparis olusturma/guncelleme/silme islemleri KAPALI. QBO REST istegi sadece GET `/query`; POST yalniz Intuit OAuth token endpointine. Shopify POST yalnizca OAuth token ve `query` GraphQL; `mutation` kullanma. Eger gercek is ihtiyaci varsa ayri onay karari almadan yazma yolu acma.
12. Silmeden once runtime referanslarini kanitla; `private/` ve OAuth yetki-kurtarma kodunu koru. GitHub ve VPS ayni SHA olmadan bitmis ilan etme.

13. Ticari urune kadar TEK CANLI CHECKLIST `TODO.md` icindeki `Ticari urune kadar ana checklist` bolumudur. Tamamlanan gorevi ancak test + gercek davranis kaniti sonrasi `[x]` yap. Her tamamlanan dar adimda ilgili TODO/README kaydini guncelle, diff/test/canli kontrol yap, VPS commit + GitHub push ve local/remote SHA eslesmesini raporla. Bir adim bloke ise tik atma; gerekce ve sonraki tek isi yaz.
14. Canli web dosyalari `/var/www/vericon-app` ve Nginx ayarlari Git disindaysa deployment drift'i ayri belirt; kaynak SHA eslesmesini tum VPS dosyalari eslesiyor diye sunma. Gizli dosyalari ve tokenleri Git'e alma.
