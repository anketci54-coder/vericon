# VERICON - Tek guncel is listesi (2026-11-03)

## Simdiki karar
- [x] Shopify ve QuickBooks Sandbox VPS baglantisi, OAuth token yenilemesi, tek test SKU sorgusu ve eski saatlik 13:00/14:00 EET tetiklemeleri dogrulandi. Kontrol farki: 10 - 7 = 3. Gercek musteri hatasi DEGIL. Degeri olmayan saatlik test timer/servisi temizlendi; sadece tek seferlik CLI kaldi.
- [x] `check-many` sinirli 2-5 SKU icin guvenli; Shopify'da ikinci ortak SKU yok. QuickBooks Sandbox'a gecmiste `VERICON-TEST-002` (Id 20, QtyOnHand=5) **yazildi**, Shopify'da yok. Yeni test kaydi olusturma.
- [x] Kod/statik API denetimi: QBO muhasebe `/query` sadece GET; POST yalnizca OAuth; Shopify POST yalniz token ve GraphQL query. Olası genislemelerde dis veri mutasyonunu engelleyen regresyon testleri var. QBO OAuth **kapsami** yaziya uygun yetki de tasir.
- [x] Reponun eski/celiskili tarihi notlari tek guncel README/TODO'ya indirildi. Gerekli OAuth kurtarma `qbo_setup.py` korundu. Kullanilmayan `.env.example`, gereksiz tek-SKU test timer/servisi (VPS ve repo), cache dosyalari temizlendi. Tokenlar ve dis sistem kayitlari degistirilmedi.

## Sirada / KAPILAR
- [x] **Modul A ilk veri kapisi:** QBO Sandbox 31 Invoice (60 satis satiri), 4 SalesReceipt. Shopify test magazasi 0 order; VERICON VPS Shopify `orders` GraphQL ACCESS_DENIED (`read_orders` yok). Kapsam genisletilmedi, test siparisi yazilmadi.
- [x] **Modul A canli aritmetik:** QBO GET ile 31 fatura. 59/60 urun satiri hesaplanabilir, 29 fatura satir kontrolu tam, 2 satir denetimi BLOCKED (27 eksik miktar/birim fiyat, 42 urun satiri yok). Ayrica 30 subtotal eslesmesi, 2 yuzde indirimi dogru, 17 vergi matrah/oran satiri tutarli, 30 fatura toplam bilesen eslesmesi. Toplam icin ID 42 BLOCKED (subtotal kaynagi yok). 15 vergisiz fatura: verginin hukuki dogrulugu bilinmiyor. 0 REVIEW. 47 yerel test ve gercek Sandbox okuma. Vergi hukuku / indirim hak edisi / Shopify-siparis eslesmesi DEGIL.
- [ ] **Modul A sonraki karar kapisi:** Shopify siparisleri yok ve VPS scope erisimi de engelli. Fatura-siparis-teslimat carpraz hata tespiti icin veri/izin varligini musteri pilotunda kanitlamadan yeni yetki alma, siparis uydurma veya devam ettigini iddia etme.
- [x] **Modul B fiyat/urun ilk karar kapisi:** Shopify own-store GraphQL `price=100.00`, `shop.currencyCode=TRY`, `product.status=DRAFT`; QBO Sandbox Item `UnitPrice=100` ve `/preferences` `CurrencyPrefs.MultiCurrencyEnabled=false, HomeCurrency=USD`. Esit gorunen sayi, ESIT fiyat degil. Mevcut `shopify_read.py check` sonucu `catalog_price_check.status=BLOCKED_PRICE_CURRENCY_MISMATCH`, sayisal fiyat farki URETMEZ. QBO para birimi bilinmiyorsa da engeller. Gercek API okuma ve 51 offline test ile dogrulandi.
- [ ] **Modul B sonraki kapisi:** Isletmenin ayni fiyat politikasi, para birimi, fiyat listesi/vergi dahil-haric ve aktif urun anlami dogrulanmadan fiyat uyusmazligi alarmini ACMA. Yeni FX kur uretme, Shopify/QBO fiyatini degistirme, yeni urun acma.
- [ ] Ilk gercek hatanin kaniti: kaynak kayitlar, SKU/kalem, zaman, miktar, fiyat, vergi/iskonto, eslesme guveni ve yanlis alarm; bilinmeyen=BLOCK.
- [ ] Gercek musteri faydasi ve odeme istegi (49/69/99 hipotezi) dogrulanmadan panel, tahsilat veya tum stok taramasi baslatma.
- [ ] Uretimden once QBO tam OAuth yazma yetkisi riskini giderilebilirlik acisindan degerlendir ve yalnizca gerekirse asgari yetkili servis kullanicisi tasarla. Gereksiz root oneshot zaten kaldirildi. Mevcut Sandbox baglantisini bozma.
- [ ] Tekrar bir runtime degisikligi yapilirsa: tek degisiklik, offline test, API gercek davranisi, systemd durum/timer, VPS-GitHub SHA, gerekli rollback dogrula.

## Ertelendi
- Yeni alana ad, fiyatlandirma, yeni agent/framework/servis, gereksiz script/dokuman ve coklu musterili OAuth. Talep kaniti yokken yapma.
