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


## Modelden bagimsiz devir ve maliyet protokolu (2026-11-12)
- Bu dosya Codex, Claude, Gemini ve diger ajanlar icin ayni kurallari tasir. Tek gorev kaynagi `TODO.md` PDF checklist; yeni liste acma, mevcut [x] isleri yeniden yapma.
- Her oturum basinda `AGENTS.md`, `TODO.md` (ozellikle ilk acik madde ve son kanit), `git status`, `git log -1`, ilgili kodu oku. VPS runtime ile GitHub SHA'yi ayri dogrula. Notion Agent Operating Guide: https://app.notion.com/p/40b467bd97ef815abf37c96427066e48
- Guncel devir (2026-11-13): TODO.md DEVAM kaydi esas. Nginx/systemd dagitimi, otomatik servis toparlanmasi ve refresh hata sogumasi canli; 231 test PASS. Asama 3 tarihsel gercek kullanici kabulunu tekrar acma veya ayni OTP/logout/revoke/scope testlerini yeniden isteme. Siradaki dar kabul PDF 4-2: henuz kapsanmamis endpointlerde iki izinli gercek A/B oturumuyla negatif izolasyon; yeni JWT yoksa BLOKE kaydet, uydurma. 2.5–2.8 politika/banka/orneklem; 4.3–4.5 ticari onboarding/ingest/kapasite eksikleri acik. Secret sizintisi kaniti olmadan rotasyon yapma; eski token arsivini otomatik geri yukleme.
- Model rolleri oneridir, zorunlu API aboneligi degildir: Codex kod degisikligi; Claude bagimsiz diff/guvenlik incelemesi; Gemini uzun dokuman/arastirma; MiMo/Nemotron yalniz olculmus dusuk riskli gorevlerde. Her zaman tek dosya yazari; incelemeciler salt-okunur.
- Gorev devri: (1) gorev ve kabul olcutu (2) mevcut kanit/kok neden (3) degisen dosyalar ve diff (4) test ve gercek API davranisi (5) acik riskler (6) commit SHA ve sonraki tek is. Sir, JWT, token, musteri kaydi veya tam logu devre ekleme.
- Maliyet: API token sayilari olculmediyse tahmin olarak etiketle. Her gercek API gorevinde model, input/output token, cache, USD, sure, tekrar deneme ve dogrulanmis sonuc kaydet; abonelik kullanimi ile API faturalarini karistirma. Ilk API deney butce tavani 20 USD/ay; kullanici onayi olmadan yeni ucretli servis acma.
- Canli servis, OAuth, Supabase politikasi, finansal veri veya musteri yetkisi degisikligi kullanici onayi ve rollback plani gerektirir. CI PASS ticari davranis PASS degildir.
