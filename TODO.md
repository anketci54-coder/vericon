# VERICON - Ana plan (6 Kasim 2026)

## Hedef ve degismez kurallar
ABD Shopify + QuickBooks Online isletmeleri icin mevcut entegrasyonlari DEGISTIRMEDEN, salt-okunur ve kanitli muhasebe uyusmazlik denetimi. Ilk is akisi yalniz her Shopify Order icin ayri QBO Invoice ve acik Shopify Order ID referansi. SalesReceipt, toplu JournalEntry, payout muhasebesi, kur ve ulke vergisi v1 disinda.

Olc -> kanit -> tek dar degisiklik -> diff -> test -> gercek Sandbox davranisi -> VPS/GitHub SHA. Test gecmesi musteri basarisi degildir. Bilinmeyen = BLOCK/REVIEW; gercek para kaybi veya banka tahsilati kanitsiz ilan edilmez. Yeni mimari, servis, otomatik finansal yazma, panel ve yan moduller yok. Onceki ayrintili denetim gunlukleri Git tarihinde sakli; tekrar arastirma yapma.

## Kalici buyuk resim: 3 ana urun ayagi (2026-11-07 karar)
- **1. VERICON Finance [AKTIF]:** Shopify -> QBO siparis, fatura, tahsilat/odeme kayitlari, iade, mahsup, duplicate/missing ve kanitli fark denetimi. Mevcut yazilimi degistirmeden inceleme; banka tahsilati harici kanit olmadan dogrulanmis sayilmaz.
- **2. VERICON Profit [SONRA]:** Urun/SKU, stok, alis maliyeti, satis fiyati, komisyon, kargo, iade, reklam gideri ve gercek katki/net karlilik. Gider/kur/vergi/maliyet verisi eksikse kar uydurma; operasyon ve stok farklarini ticari kayip saymadan once dogrula.
- **3. VERICON Intelligence [SONRA]:** Rakiplerin benzer AYNI urunleri hangi fiyata sundugu (urun eslesme guveni, tarih, kaynak, stok/kargo/vergi ayrimi), talep ve yeni urun firsatlari, fiyat/urun karmasi senaryolari, istatistiksel tahmin ve gercek sonraki sonuc olcumu. Tavsiye ve tahmini kazanci gerceklesmis kazanc gibi sunma. Kaynak verisi edinme hukuku, kapsami, guncelligi ve maliyetini once arastir.
- **Birlesik deger onerisi:** Finansal hatayi bul + gercek kar marjini anla + yeni firsati delille goster. Müşteri faydasi = kanitlanmis tasarruf/ek kar ayri; saptanmis fark ve potansiyel firsat AYRI. Ornek $69/ay abonelik yalniz fiyat/ROI hipotezidir, getiri garantisi DEGIL. Uc ayak ileride tek panelde, gerekirse ayri paketler; pazara giris ABD Shopify + QuickBooks Online.
- **Degismez sira:** Aktif Finance 12 asamali asagidaki plani BITMEDEN Profit veya Intelligence kodlamasi BASLATMA. Bu iki ayak unutulmayacak ama simdilik urun karari olarak tutulacak; gerekli veri, birim maliyet, musteri talebi ve dogruluk kaniti sonraki karar kapilaridir. Yeni paralel proje, servis veya yol haritasi acma.
- **Buyuk hacim ilkesi (tasarim hedefi, uygulanmis degil):** API'den fatura basina tekrar tekrar okumak yerine uygun toplu/artimli veri okuma; sadece degisen kayitlari kontrol; fatura bazli bagimsiz sonuc, tenant izolasyonu. 350 bin fatura/2 milyon satir senaryosu kapasite SINAVI degildir. Kuyruk/worker/Redis/Kafka ancak fatura/s, API kotasi, bellek, gecikme ve maliyet olculup gercek ihtiyac kanitlanirsa secilir. Pytest sayisi her islemde calisan kontrol sayisi DEGIL.

## Tek is sirasi
- [x] **1. Kod kapsam olcumu:** Shopify/QBO okuma ve denetim yollari incelendi. Kanitlanmis sinirlar belirlendi.
- [x] **2. ABD muhasebe kapsami:** Yalniz ayri Invoice eslestirmesi v1 kapsaminda. Musterinin gercek muhasebe politikasinin onayi halen GEREKLI.
- [ ] **3. Duplicate Detector:** Acik Shopify Order ID'yi paylasan farkli QBO Invoice'lar yalniz inceleme adayi. Gercek Sandbox: 32 fatura, 1 acik Shopify referansi, 0 ortak referansli aday. Ayni tutar duplicate kaniti degil. Gercek pozitif vaka henuz YOK; dogrulama 6. asamadaki onayli coklu Sandbox testinde.
- [ ] **4. Missing Transaction Detector:** Politika + referans + tam fatura snapshot'i + gecmis senkron penceresi kaniti olmadan alarm KAPALI. `--pilot-batch` sonucu `BLOCKED_ACCOUNTING_METHOD_UNVERIFIED`, 0 aday. Gercek musteri politikasi ve pozitif vaka henuz YOK; dogrulama 6. asamada.
- [x] **5. Evidence Report:** Mevcut rapora Shopify Order GID ve QBO Invoice ID eklendi; mahsup dogrulamasi ile odeme/tahsilat dogrulamasi ayrildi. `offsets_verified=true` iken `payment_status=REVIEW_QBO_PAYMENT_RECORDS` oldugunda genel rapor `REVIEW_PAYMENT_UNVERIFIED`, `verified=false`, `review_required=true`; 0 TRY yalniz mahsup farkidir. Gercek Sandbox #1001 / Invoice 145 ile dogrulandi, 132 test ayni sayida gecti. Banka settlement kanitlanmadi.
- [ ] **6. Coklu Sandbox E2E [SIMDI]:** Gercek API'de birden fazla bagimsiz siparis, fatura, iade ve kasitli hata sinamasi. Harici kayit olusturma/degistirme icin ayri onay gerekir. 3-4'teki pozitif kanit da burada arastirilir.
- [ ] **7. Payout farki [KOSULLU]:** Yalniz yeterli banka/odeme saglayici verisi ve musteri talebi kanitlanirsa.
- [ ] **8. Ticari guvenlik:** Tenant bazli OAuth, veri izolasyonu, asgari yetki.
- [ ] **9. Tek panel:** Ancak dogru ve anlasilir rapor dogrulanirsa.
- [ ] **10. ABD pilot:** 5-10 isletme/muhasebeciyle dogruluk, yanlis alarm ve fayda olcumu.
- [ ] **11. Abonelik:** Odeme istegi olculdukten sonra; $19-29/ay sadece hipotez.
- [ ] **12. Diger ulkeler [ERTELENDI]:** Kur, vergi ve coklu para birimi icin ayrica kanit gerekir.

## Son dogrulanmis temel
- Calisan temel kod: commit `e0b30bc` (TODO sadeleştirmesi kodu degistirmez).
- Shopify test Order #1001 ↔ QBO Invoice #1038: 216 TRY, 100 TRY iade/mahsup, 116 TRY bakiye; banka tahsilati DOGRULANMADI.
- 132/132 yerel pytest; coklu senaryolar sentetik, gercek Sandbox'ta yalniz bir eslesen siparis var. Gercek musteri basarisi KANITLANMADI.
- `private/` OAuth anahtarlari ve geri alma yollari korunur. Eski ayrintili test ve karar kayitlari Git history'de; yeni dokuman olusturma.
