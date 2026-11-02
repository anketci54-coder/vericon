# VERICON - Gelistirme kurallari

1. Ana hedef: Shopify ve QuickBooks Online verilerinin bagimsiz, kanitlanabilir, salt-okunur uyusmazlik denetimi. ERP, envanter yoneticisi veya otomatik muhasebe kaydi olusturma projesine donusturme.
2. Once olc, sonra karar ver. Kod degistirmeden once runtime ve kanitli kok nedeni belirle; tek nedensel degisiklik yap, test et, gercek davranisi dogrula.
3. Shopify inventory_quantity ile QuickBooks QtyOnHand alanlarini korlemesine karsilastirma. Lokasyon, rezerve/stokta/mevcut, zaman damgasi ve SKU ayniligi kanitlanmadan fark diye etiketleme.
4. Parasal kurallar (vergi, indirim, iade, para birimi, birim fiyat, yuvarlama) deterministik olmali. AI sonucu tek basina finansal gercek olamaz. Bilinmeyen = incelemeye al.
5. Once QuickBooks Sandbox ve bos Shopify deneme magazasiyla sinirli calis. Gercek musteri verisi, API yetki artisi, canli servis veya veri degisikligi icin ayri onay gerekir.
6. Token, client secret, .env, gercek veriler, fatura ve musteri bilgilerini depoya koyma, loglarda paylasma. Gerekiyorsa mevcut gizli depolama cozumunu kontrollu belirle.
7. Iki AI ayni dosyada paralel degisiklik yapmaz. Degisikliklerin diff'i, test sonucu ve uygulama davranisi ayri dogrulanir.
8. Yeni framework, refactor, servis, konteyner, dokuman, branch veya ek API ancak kanitli ihtiyac varsa acilir.
9. Projeyi diger VPS uygulamalarindan izole tut. BINBOT, DEXBOT, SMRS ve Senal Plastik servislerine dokunma.
10. 'Hazir' veya 'basarili' sadece uctan uca kanitli sonuc icin kullanilir. Halen herhangi bir musteri sonucu dogrulanmadi.
