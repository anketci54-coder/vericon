# VERICON - Tek guncel is listesi (2026-11-03)

## Simdiki karar
- [x] Shopify ve QuickBooks Sandbox VPS baglantisi, OAuth token yenilemesi, tek test SKU sorgusu ve eski saatlik 13:00/14:00 EET tetiklemeleri dogrulandi. Kontrol farki: 10 - 7 = 3. Gercek musteri hatasi DEGIL. Degeri olmayan saatlik test timer/servisi temizlendi; sadece tek seferlik CLI kaldi.
- [x] `check-many` sinirli 2-5 SKU icin guvenli; Shopify'da ikinci ortak SKU yok. QuickBooks Sandbox'a gecmiste `VERICON-TEST-002` (Id 20, QtyOnHand=5) **yazildi**, Shopify'da yok. Yeni test kaydi olusturma.
- [x] Kod/statik API denetimi: QBO muhasebe `/query` sadece GET; POST yalnizca OAuth; Shopify POST yalniz token ve GraphQL query. Olası genislemelerde dis veri mutasyonunu engelleyen regresyon testleri var. QBO OAuth **kapsami** yaziya uygun yetki de tasir.
- [x] Reponun eski/celiskili tarihi notlari tek guncel README/TODO'ya indirildi. Gerekli OAuth kurtarma `qbo_setup.py` korundu. Kullanilmayan `.env.example`, gereksiz tek-SKU test timer/servisi (VPS ve repo), cache dosyalari temizlendi. Tokenlar ve dis sistem kayitlari degistirilmedi.

## Sirada / KAPILAR
- [x] **Modul A ilk veri kapisi:** QBO Sandbox 31 Invoice (60 satis satiri), 4 SalesReceipt. Shopify test magazasi 0 order; VERICON VPS Shopify `orders` GraphQL ACCESS_DENIED (`read_orders` yok). Kapsam genisletilmedi, test siparisi yazilmadi.
- [x] **Modul A ilk gercek davranis:** `invoice_audit.py` ile QBO GET sadece fatura kalemi Qty x UnitPrice / Amount kontrolu. 31 faturada **29 LINE_AMOUNTS_MATCH**, **2 BLOCKED** (ID27 alan eksik, ID42 urun satiri yok), 0 REVIEW, **59 satir test edilebilir**. Bu toplam/vergi/teslimat/Shopify eslesmesi DEGIL. 38 testli (sabit kontrol).
- [ ] **Modul A sonraki karar kapisi:** Shopify siparisleri yok ve VPS scope erisimi de engelli. Fatura-siparis-teslimat carpraz hata tespiti icin veri/izin varligini musteri pilotunda kanitlamadan yeni yetki alma, siparis uydurma veya devam ettigini iddia etme.
- [ ] **Modul B**: SKU/stok disinda fiyat/urun kaydi semantigini ve olasi yalanci pozitifleri olc. Sirf test icin yeni urun uretme.
- [ ] Ilk gercek hatanin kaniti: kaynak kayitlar, SKU/kalem, zaman, miktar, fiyat, vergi/iskonto, eslesme guveni ve yanlis alarm; bilinmeyen=BLOCK.
- [ ] Gercek musteri faydasi ve odeme istegi (49/69/99 hipotezi) dogrulanmadan panel, tahsilat veya tum stok taramasi baslatma.
- [ ] Uretimden once QBO tam OAuth yazma yetkisi riskini giderilebilirlik acisindan degerlendir ve yalnizca gerekirse asgari yetkili servis kullanicisi tasarla. Gereksiz root oneshot zaten kaldirildi. Mevcut Sandbox baglantisini bozma.
- [ ] Tekrar bir runtime degisikligi yapilirsa: tek degisiklik, offline test, API gercek davranisi, systemd durum/timer, VPS-GitHub SHA, gerekli rollback dogrula.

## Ertelendi
- Yeni alana ad, fiyatlandirma, yeni agent/framework/servis, gereksiz script/dokuman ve coklu musterili OAuth. Talep kaniti yokken yapma.
