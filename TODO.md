# VERICON - Ana plan (6 Kasim 2026)

## Hedef ve degismez kurallar
ABD Shopify + QuickBooks Online isletmeleri icin mevcut entegrasyonlari DEGISTIRMEDEN, salt-okunur ve kanitli muhasebe uyusmazlik denetimi. Ilk is akisi yalniz her Shopify Order icin ayri QBO Invoice ve acik Shopify Order ID referansi. SalesReceipt, toplu JournalEntry, payout muhasebesi, kur ve ulke vergisi v1 disinda.

Olc -> kanit -> tek dar degisiklik -> diff -> test -> gercek Sandbox davranisi -> VPS/GitHub SHA. Test gecmesi musteri basarisi degildir. Bilinmeyen = BLOCK/REVIEW; gercek para kaybi veya banka tahsilati kanitsiz ilan edilmez. Yeni mimari, servis, otomatik finansal yazma, panel ve yan moduller yok. Onceki ayrintili denetim gunlukleri Git tarihinde sakli; tekrar arastirma yapma.

## Tek is sirasi
- [x] **1. Kod kapsam olcumu:** Shopify/QBO okuma ve denetim yollari incelendi. Kanitlanmis sinirlar belirlendi.
- [x] **2. ABD muhasebe kapsami:** Yalniz ayri Invoice eslestirmesi v1 kapsaminda. Musterinin gercek muhasebe politikasinin onayi halen GEREKLI.
- [ ] **3. Duplicate Detector:** Acik Shopify Order ID'yi paylasan farkli QBO Invoice'lar yalniz inceleme adayi. Gercek Sandbox: 32 fatura, 1 acik Shopify referansi, 0 ortak referansli aday. Ayni tutar duplicate kaniti degil. Gercek pozitif vaka henuz YOK; dogrulama 6. asamadaki onayli coklu Sandbox testinde.
- [ ] **4. Missing Transaction Detector:** Politika + referans + tam fatura snapshot'i + gecmis senkron penceresi kaniti olmadan alarm KAPALI. `--pilot-batch` sonucu `BLOCKED_ACCOUNTING_METHOD_UNVERIFIED`, 0 aday. Gercek musteri politikasi ve pozitif vaka henuz YOK; dogrulama 6. asamada.
- [ ] **5. Evidence Report [SIMDI]:** MEVCUT raporu olc. Siparis/fatura ID, tutar, para birimi, neden, kaynak kanit, bilinmeyen ve inceleme durumunu kontrol et. Yalniz kanitlanan eksigi duzelt; yeni modül yazma.
- [ ] **6. Coklu Sandbox E2E:** Gercek API'de birden fazla bagimsiz siparis, fatura, iade ve kasitli hata sinamasi. Harici kayit olusturma/degistirme icin ayri onay gerekir. 3-4'teki pozitif kanit da burada arastirilir.
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
