# VERICON

2026-11-13 canlı durum: `36ce87b` kaynak sürümü üç systemd API servisine alınmış checkpoint'ten devam edildi. 8787/8788/8789 active+enabled; kontrollü süreç kaybında otomatik toparlanma 6,3 saniye, health 200 ve anonim auth/finance 401. Kalıcı env 0600, ağsız preflight PASS. Sunucu reboot'u yapılmadı.

Nginx başlıkları, IP başına 5 istek/sn + 10 burst ve callback metadata logu canlıya dağıtıldı. HTTP yönlendirmesindeki callback log açığı sentetik istekle kanıtlandı; rollback ardından HTTP callback de korundu. İzole 502 hata testi ve canlı 301/400/429 kontrollerinde code/state loglara girmiyor; callback yalnız status/upstream/elapsed kaydediyor. Canlı 32 istekte 11 normal ret/21 hız sınırı, beş güvenlik başlığı, sağlık/statik 200. Sağlayıcıya yük gönderilmedi.

Dört `web/` dosyası kaynak/disk/HTTPS olarak birebir; aktif Nginx `deploy/vericon-app.nginx.conf` ile eşit. Git dışı dosyaların uyumu ayrıca ölçüldü; kaynak SHA eşitliği tüm VPS için eşitlik iddiası değildir. Son suite 228 pytest PASS. Güncel madde durumları ve kalan engeller yalnız `TODO.md` ana checklist'indedir; eski kabul testleri yeni sürüm testi diye sunulmaz. Ürün ticari kullanıma hazır değildir.

Rollback kanıtları `/root/vericon-completion-20261113/` içinde korunur. Nginx hatasında önceki config'i geri koy, `nginx -t` ardından yalnız Nginx reload yap. Kod/unit geri dönüşünde çalışan public Auth env ve GÜNCEL `private/` dosyalarını koru; eski boş env veya OAuth token arşivini otomatik geri yükleme. Diğer VPS projelerine dokunma.

Finans sayımı, doğrulanmış RLS/sahiplik/realm bağından sonra `financial_access_enabled=true` veya operatörün açık Sandbox realm listesiyle sınırlıdır. Kurulu env mevcut iki pilotun yalnız sayım iznini taşır; genel finans erişimi açılmadı. Alt-sent kayıtlar ve belirsiz yarım-sent politikası BLOCKED; kayıtlı toplamlar tam eşitlik gerektirir. Muhasebe politikası, banka mutabakatı ve muhasebeci etiketli örneklem beklenir.

Aşama 3 tarihsel kullanıcı kabulü korunur: OTP, sahiplik, QBO revoke/reconnect ve logout testi yeniden istenmez. Bu sürümde tüm endpointlerin gerçek A/B negatif matrisi 4.2 kapsamında hâlâ bloke; geçmiş kabul yeni sürüm testi değildir. Aşama 2.5–2.8 için politika, settlement verisi ve etiketli örneklem beklenir.

`python3 -B benchmark_invoice_audit.py` dış API çağırmadan izole sentetik aritmetiği ölçer. 21 batch, p50/p95/p99, CPU/RSS ve ID oracle içerir; CPU maliyeti yalnız açıkça belirtilen fiyat varsayımıdır, gerçek SaaS faturası değildir. Tam Shopify–QBO ingest kapasitesiyle karıştırılmaz.

**Guncel tek ana plan: [`TODO.md`](TODO.md), 2026-11-07.** VERICON'un kalici 3 ayagi: **Finance** (fatura/odeme/iade/muhasebe denetimi, AKTIF), **Profit** (urun/stok/maliyet ve gercek karlilik, SONRA) ve **Intelligence** (rakip fiyatlari, yeni urun/firsat ve kanitli ticari tavsiyeler, SONRA). Ilk pazar ABD Shopify + QuickBooks Online. Mevcut Finance gelistirme sirasi korunur; diger ayaklarin kodu, paneli veya altyapisi simdilik kurulmaz. Abonelik ucretinin ekonomik faydasi ayrica olculur, tahmini getiri garanti edilmez. Asagidaki tarihli bulgular tarihsel kayittir; eski 'siradaki is' ifadeleri guncel karar degildir.

**Tarihsel durum: 2026-11-03.** Bu bir **Sandbox prototipidir**, satisa hazir SaaS degildir.

## Urun hedefi
- **Modul A / Fatura Hata Avcisi:** fatura, siparis ve teslimat tutar/miktar uyusmazliklarini kanitlariyla bulmak.
- **Modul B / E-ticaret Hata Dedektoru:** urun, SKU, stok ve fiyat farklarini kanitlariyla bulmak.
- Moduller ayrica, birlikte ise tek panelde satilabilir. Ilk surum kaynak veriyi DEGISTIRMEZ. AI yalnizca yardimci, parasal hesaplar deterministiktir.
- Ilk hedef Shopify + QuickBooks Online kullanan perakendeciler. Aylik fiyatlar 49/69/99 USD sadece arastirilacak hipotezlerdir.

## Kanitlanan gercek davranis
- Shopify deneme magazasi `hudys3-p0.myshopify.com` uygulama v2 (read_products, read_inventory, read_locations) VPS'ye bagli.
- QuickBooks Online Plus **Sandbox** OAuth ile VPS'ye bagli. Tokenlar `private/` icinde yerel sifreli saklanir; gerektiğinde otomatik yenilenir.
- Ortak test SKU `VERICON-TEST-001`: Shopify `available=10`, `on_hand=10`, QBO `QtyOnHand=7`; test farki **3 adet**. Bu gercek musteri hatasi veya parasal kayip kaniti DEGIL.
- `shopify_read.py check` iki API'den sirali okuyup SKU, tek depo, stok alanlari, takip durumu ve 30 sn'lik sorgu zamani farki kontrolu yapar. Paralel/atomik snapshot garantisi yoktur.
- `check-many` sadece acikca secilmis **2-5 SKU** icin calisir; eksik/tekrarlanan/uyusmayan SKU fark uydurmaz (`BLOCKED_*`). Iki gercek ortak SKU ile tam basari henuz kanitlanmadi.
- **Tarihsel kanit:** Saatlik test zamanlayicisinin 2026-11-03 13:00 ve 14:00 EET tetiklemeleri exit=0 idi. Bu yalnizca ayni kontrollu farki tekrarladigindan, gereksiz `root` servisi ve timer kalici olarak devre disi birakildi ve kaldirildi. Mevcut denetim komutla calisir.
- QuickBooks Sandbox'ta `VERICON-TEST-002` (Id 20, QtyOnHand=5) deneme kaydi **olusturuldu**. Shopify'da karsiligi yok. Bu kayit otomatik silinmedi; yeni fixture uretmeyin.
- Fatura, siparis, teslimat ve fiyat denetimi, gercek musteri hatasi, panel, odeme, tenant OAuth, ucretli pilot **henüz yapilmadi**.

## Kaynaklar / dosyalar
- `shopify_read.py`: Shopify salt-okunur stok sorgusu ve tek/coklu SKU Sandbox karsilastirmasi.
- `qbo_oauth.py`: QuickBooks OAuth, guvenli token yenileme, Sandbox Item GET sorgusu, sadece yerel callback.
- `qbo_setup.py`: ilk kurulum veya gecersiz yetkilendirmeyi **yerel SSH tuneli** uzerinden yenilemek icin tutuldu. Saatlik runtime kullanmiyor; silinirse yeniden yetki almak zorlasir.
- `inventory_compare.py`: deterministik miktar hesabi, `UNKNOWN=BLOCK`.
- Yeni VPS servisi veya timer yok: eski gereksiz saatlik deneme servisi hem `/etc/systemd/system` hem GitHub kaynaklarindan kaldirildi. Gerektiginde tek-seferlik CLI okuma yapilir.
- `test_qbo_oauth.py`, `test_shopify_read.py`: testler ve dis API yazma yolu regresyon kontrolleri.
- `AGENTS.md`: muhendislik sinirlari. `TODO.md`: yalniz guncel gorev/karar listesi.
- `private/`: **Git ignore edilmis**, token ve kimlik bilgileri; ASLA GitHub'a koyma, isimlerini/izinlerini koru.

## Sinirlar ve guvenlik
- **Dış sistemlerde mutation YASAK:** QuickBooks muhasebe verileri sadece GET `/query` ile okunur. QuickBooks `POST` yalnizca OAuth TOKEN endpointine yapilir. Shopify `POST` token almak veya GraphQL **query** icindir, GraphQL `mutation` YOK.
- **Yetki riski:** Intuit `com.intuit.quickbooks.accounting` OAuth kapsami teknik olarak yazma yetkisi de verir; mevcut kodun GET-only olmasi tokeni salt-okunur yapmaz. Gereksiz `root` saatlik servis silindi. Uretimden once yetki siniri ve guvenli runtime kullanicisi tekrar degerlendirilmeli.
- Shopify istemci-kimlik akisi sadece bu gelistirici magazasi icindir; baska musterinin magazasina kopyalanmaz.
- Sandbox test verisini silme/duzeltme, yeni API izni, musteri verisi veya yeni servis icin ayri gerekce ve onay gerekir.
- Harici Shopify/QBO POST'u topluca yasaklamak dogru degildir: OAuth token ve Shopify GraphQL sorgulari POST gerektirir. Yazma yasagi **veri mutasyonlari** icindir.
- Diger VPS projelerine (DEXBOT/BINBOT/SMRS/Senal) dokunma. Yerel OAuth callback sadece 127.0.0.1:8782; public port veya domain yok.

## Komutlar
```bash
cd /root/vericon
python3 -B shopify_read.py status
python3 -B qbo_oauth.py --saved-setup status
python3 -B shopify_read.py check --sku VERICON-TEST-001
python3 -B shopify_read.py check-many --sku VERICON-TEST-001 --sku VERICON-TEST-002
python3 -B -m pytest -q -p no:cacheprovider test_qbo_oauth.py test_shopify_read.py
```

`check-many` ikinci SKU kaydi Shopify'da bulunmadigi icin kismen engellenmis cikis kodu `2` beklenir. `test_*` sahte HTTP yanitlariyla calisir, bagli API gercegini tek basina kanitlamaz.

**Siradaki karar kapisi:** Fatura satiri ve desteklenen toplam/indirim/vergi matematik kontrolleri Sandbox API'de dogrulandi. Gercek siparis/fatura/teslimat **capraz** denetimi icin Shopify siparis verisi ve onayli kapsam halen yok. Fatura hukuk/mukellefiyet/tax uygunlugu ve ticari hata kanitlanmadan urun basarisi ilan etme. `TODO.md`ye bak.

## Temizlik ve E2E delili (2026-11-03)
- Gereksiz eski `.env.example`, saatlik test service/timer deploy dosyalari ve VPS systemd unitleri temizlendi. OAuth kurtarma betigi, tek seferlik API okuyuculari, guvenlik testleri ve `private/` sakli bilgileri korundu. `__pycache__/` ve `.pytest_cache/` uretilmis dosyalari silindi.
- Test baslangici/sonunda Shopify lokasyon on_hand/available/committed/updatedAt ve QuickBooks Item QtyOnHand/SyncToken/LastUpdatedTime **ayni** okundu. Tekli API kontrolu `TEST_DIFFERENCE`, 10-7=3, okuma araligi 1.163 sn. Ikili CLI: mevcut SKU fark 3 + eksik Shopify SKU `BLOCKED_ITEM_READ`, grup `TEST_BATCH_PARTIAL_BLOCKED`, exit=2 (beklenen).
- Bu, Sandbox okuma ve fark hesaplama akisi icin uctan uca delildir. Uretim, fatura mutabakati, ticari kayip, tum urunler veya tokenin teknik yazma izninin kaldirildigi iddia edilmez.

## Modul A / Fatura Hata Avcisi: ilk kanitli okuma (2026-11-03)
- Mevcut QuickBooks Plus Sandbox `SELECT COUNT(*) FROM Invoice` => **31**, `SELECT * FROM Invoice STARTPOSITION 1 MAXRESULTS 100` => **31** kayit; 60 `SalesItemLineDetail`, 31 `SubTotalLineDetail`, 2 `DiscountLineDetail`, para birimi USD. Salt-okunur `GET /query`, veri mutasyonu YOK.
- Shopify ChatGPT baglantisi `list_orders(first=1)` => **0 siparis** (bu baska uygulama yetkisi). VERICON'un VPS Shopify app'i GraphQL `orders(first:1)` sorgusunda HTTP 200 / GraphQL `ACCESS_DENIED` verdi; `read_orders` yetkisi YOK. Bu nedenle faturayi Shopify siparisi/teslimatla gercekten eslestirdigimizi SOYLEME. Scope yetkisi genisletilmedi.
- `invoice_audit.py`: Modul A. `python3 -B invoice_audit.py` QBO'dan en cok 100 faturayi **salt okunur** alir; COUNT/tekil ID dogrular. USD urun satiri Qty x UnitPrice/Amount, tek SubTotalLineDetail ile urun satirlari toplami, desteklenen tek yuzde indirimi, TaxLine Amount/TotalTax ve NetAmountTaxable x TaxPercent, son TotalAmt hesabini **ayri** kontrol eder. Yuvarlamada 1 sentlik farki kabul etmez. Eksik veya desteklenmeyen alan `BLOCKED_*`; hesap uyumsuzlugu `REVIEW_*`. Verginin mevzuata uygunlugu, indirimin is kurali, gercek kayip ve Shopify/teslimat eslesmesi DENETLENMEZ.
- Gercek QuickBooks Sandbox E2E: 31 faturada 60 satis satiri; **59 satir hesaplanabildi ve 0 fark**, 29 fatura `LINE_AMOUNTS_MATCH`; iki fatura **bloklandi**: ID 27'de Qty ve UnitPrice alanlari YOK, ID 42'de yalniz ara toplam var, urun satiri YOK. 0 fatura `REVIEW_LINE_AMOUNT`. Bu 29 faturanin toplam/vergi/odeme/siparis uyumunun dogrulandigi anlamina GELMEZ.
- `test_invoice_audit.py`: satir ve toplam/indirim/vergi aritmetigi, 1-sent sapma, eksik/karmaşık satiri engelleme, GET-only ve eksik/tekrarlanan sayfalama testleri. `private/`, tokenlar, yeni urunler, faturalar ve zamanlayicilar degistirilmedi.
- **Karar kapisi:** Shopify siparisleri 0 ve VERICON app `read_orders` yetkisi yok. Yeni siparis veya fatura olusturma, API scope genisletme, otomatik servis ve hazir SaaS iddiasi YOK. Gercek siparis/fatura/teslimat eslesmesini ancak gercek veri ile ve uygun onayli kapsamda kanitla.

## Modul A / Toplam, indirim ve vergi ic tutarlilik kontrolu (2026-11-03)
- Intuit Invoice API `TotalAmt` kalem/indirim/vergi toplamidir; `TxnTaxDetail.TotalTax` ve `TaxLineDetail.NetAmountTaxable/TaxPercent` farkli alanlardir. Ayrintilar: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/invoice
- Gercek Sandbox okuma: **31 fatura, 30 ara toplam satir tutarliligi, 2 yuzde indirimi, 17 vergi satiri matrah/oran carpimi, 30 fatura toplam bilesen tutarliligi**. 16 faturada 17 tax-line denetlendi; 15 faturada vergi kaydi sifir ve vergi satiri yok (vergi uygulanmamasi dogru mu TEST EDILMEDI). 0 REVIEW; 1 fatura (ID 42) urun satiri olmayan ara toplam nedeniyle TOTAL BLOCKED. ID 27 miktar ve fiyat eksik oldugu icin urun satiri BLOCKED; kayitli satir Amount ve toplam matematiksel olarak eslesiyor, satir hesabinin tam oldugu iddia edilmez.
- Indirimler: fatura 49 (5%), 39 (10%), indirim duzeyleri matematiksel uyumlu. Komplike sepet vergisi, vergiden once/sonra islem sirasi, sabit indirim, ara subtotal gruplanmasi, cok para birimi ve vergi yasaligi **UNKNOWN=BLOCK**, hata veya kayip ilan edilmez.
- 47 lokal test + tek-seferlik gercek QBO API sonuclarina gore durum; kaynak veride yazma/mutation, yeni servis, test verisi veya izin genislemesi YOK.

## Modul B / Fiyat para birimi korumasi (2026-11-03)
- Bugunku **gercek VPS API** kaniti (iki dogrudan baglanti, yeni yazma yetkisi YOK): Shopify `VERICON-TEST-001` draft varyant fiyati `100.00` **TRY** (`productVariant.price`, `shop.currencyCode`); QBO Sandbox Inventory Item `UnitPrice=100`, `/preferences` `CurrencyPrefs.MultiCurrencyEnabled=false` ve `HomeCurrency=USD`. Shopify stok available=10, QBO QtyOnHand=7, kontrollu test farki=3.
- **Kritik:** 100 TRY ve 100 USD fiyat farki olarak hesaplanamaz ve esit fiyat diye de onaylanamaz. `shopify_read.py check` raporuna `catalog_price_check` eklendi; durum `BLOCKED_PRICE_CURRENCY_MISMATCH`. Fiyatlari cevirmek veya dogrulanmamis kur varsaymak YASAK.
- QBO para birimi belirsiz/multicurrency ise `BLOCKED_QBO_CURRENCY_UNKNOWN`, eksik fiyat alanlari `BLOCKED_PRICE_FIELDS_MISSING`; para birimi ayni ama Shopify urunu taslaksa `BLOCKED_PRODUCT_NOT_ACTIVE`; diger durumlarda ticari fiyat politikasi dogrulanmadigindan `BLOCKED_PRICE_POLICY_UNVERIFIED`. **Her durumda fiyat alarmini acmiyoruz; bu asamada fiyat PnL/kayip kaniti yok.**
- Yeni QBO istegi sadece `GET /preferences` (salt okunur); Shopify GraphQL'e ayni `query` icinde `shop.currencyCode`, varyant `price` ve `product.status` eklendi. Var olan `inventory_compare.py` stok hesabi degistirilmedi.
- Shopify referans: https://shopify.dev/docs/api/admin-graphql/2026-10/objects/ProductVariant (varyant price magazanin varsayilan para birimi). Yalniz QBO HomeCurrency sabit ve multicurrency kapaliyken para birimi tespiti yapildi; gercek musteride bu garanti DEGIL. 51 offline test + iki API'den tek-seferlik E2E okuma dogrulandi.

## Modul A: baglantisallik / fatura-odeme grafi (2026-11-03)
- **Problem:** Tek faturaya iki odeme, kismi odeme veya alacak dekontu mahsuplasmasi uygulanabilir. Payment.TotalAmt'yi her faturaya eklemek nakit ve bakiye uydurabilir. Intuit API kaynagi: https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/Payment ; fatura baglari: https://developer.intuit.com/docs/api/accounting/invoice.
- Yeni graph DB, kutuphane, servis veya dosya **YOK**. Mevcut `invoice_audit.py` 100 kayit sinirli `GET Payment` ile Invoice `LinkedTxn[Payment]` ↔ `Payment.Line.LinkedTxn[Invoice]` cift yonlu **tipli baglanti** olusturur. ID tekilligi, endpoint mevcudiyeti, USD para birimi, tekik Payment.Line miktari ve Invoice `TotalAmt - Balance = SUM(uygulanan Payment.Line.Amount)` karsilastirilir. Eksik/yinelenen/tek tarafli bag, bilinmeyen para birimi, eksik veri veya fark **BLOCKED**; finansal zarar ilani YOK.
- Gercek QBO Sandbox sonucu: **31 Invoice node / 16 Payment node / 16 cift yonlu dogrulanan Invoice-Payment edge**; 14 faturada odeme bagi var; 2 faturada 2 ayri odeme; 3 fatura (ID 13,16,67) halen kismi bakiyeli. 16 bagda karsilikli fark 0 ve fatura bakiyesi hesap aykiriligi 0.
- **Ozel risk:** Payment ID 74 `TotalAmt=0` olmasina ragmen fatura 71'e 100 USD uygular; Payment.Line icinde bir de `CreditMemo` ID73 bagi vardir. Bu, **nakte esit degildir**. `credit_memo_related_payment_ids=[74]` diye kaydedilir. CreditMemo'nun kendisi, gercek banka hareketi ve nakit tahsilat miktari ayrica teyit edilmedi.
- Sonuc `payment_graph.status=GRAPH_LINKS_VERIFIED` sadece **QBO icindeki bu belirli belge/odeme/bakiye baglarini** dogrular. Shopify siparisi, teslimat, gercek odeme tahsilati, tahsilatin banka hesaba yatmasi ve yasal fatura dogrulugu halen **NOT_VERIFIED**.
- 59 offline test + tek seferlik gercek QBO GET Invoice/Payment sorgusu. Sadece `invoice_audit.py` ve `test_invoice_audit.py` davranisi genisledi; yeni izin, dis sistem mutation, zamanlayici ve diger proje degisikligi yok.

### CreditMemo referans kontrolu (2026-11-03)
- QBO Sandbox CreditMemo ID73: USD 100, Balance=0. Payment ID74: TotalAmt=0; Invoice71'e 100 uygulama ve CreditMemo73'e 100 referans var. Payment/Invoice/CreditMemo musteri kimlikleri ayni. Bunlar gercek API `GET /query` ile okundu.
- `invoice_audit.py` artik mevcut graf uzerinde (ayri DB olmadan) 100 kayit limitli CreditMemo GET yapar; Payment.Line.CreditMemo endpoint ID, musteri, para birimi, uygulanan tutarin memo TotalAmt'yi asmamasi kontrolleri ile `credit_memo_endpoints_verified=True` diyebilir. **Bu sadece tek tarafli referans+endpoint dogrulamasidir; CreditMemo kendi tarafindan karsilikli link bildirmiyor, banka/nakit tahsilati ve kredi mahsup kaynagi tumuyle kanitlanmis DEGIL.**
- Canli sonuc: `GRAPH_LINKS_VERIFIED`, 16 fatura/odeme bagi, 1 CreditMemo referansi ve endpointi gecerli; `cash_received_verified=False`, `shopify_order_links_verified=False`. 62 offline test ve dogrudan QBO sorgusu; stok ve fiyat kontrolu korunuyor. Yeni dosya, servis, yetki veya dis sistem veri yazimi YOK.


## Modul A / Tedarikci faturasi ↔ satin alma siparisi kaniti (2026-11-03)
- Salt-okunur GET /query: QuickBooks Sandbox PurchaseOrder sayisi **3**, Bill sayisi **15**.
- Yalniz PO **125** -> Bill **126** acik baglanti tasiyor: ayni vendor/para birimi (USD), 2 adet eslesen kalem, miktar, birim maliyet ve toplam **205 USD**. Denetimde **0 fark**.
- Diger 2 PO'nun Bill bagi yok; bunlar hata diye raporlanmaz (NOT_CHECKED_NO_BILL_LINK). Kismi faturalar, desteklenmeyen satirlar ve bir faturanin birden cok PO'ya baglanmasi konservatif engellenir.
- Bu **tek kaynak Sandbox iki-belge karsilastirmasidir**; teslimatin fiilen yapildigi, fatura kaydinin hukuken dogru oldugu, odemenin bankadan gectigi veya Shopify siparisiyle eslestirildigi anlamina GELMEZ.
- invoice_audit.py, test_invoice_audit.py icinde uygulandi: **70 yerel test** ve yeni API sorgusunun gercek yaniti ile dogrulandi. Yeni dosya, servis, zamanlayici, yeni scope veya veri mutasyonu olusturulmadi.

### 2026-11-10 pilot güvenlik devri (güncel)
- Kaynak durum/iş sırası: `TODO.md` Aşama 8 (2026-11-10). Eski tarihli bölümler tarihsel kanıttır; güncel durumu geçersiz kılmaz.
- Supabase gerçek OTP girişi ve QBO OAuth Sandbox kullanıcı/realm eşleşmesi PASS. Shopify uygulaması kurulu, API mağaza kimliği PASS; **Shopify kullanıcısına bağlı sahiplik ispatı BEKLİYOR**. `ownership_verified=false`, `financial_access_enabled=false`; ticari müşteri veri endpoint'i AÇMA.
- HTTPS pilot runtime: `/var/www/vericon-app` (giriş HTML/JS Git dışında), Nginx `app.vericon.site` -> localhost:8785 QBO FastAPI. QBO kimlik bilgileri ve tokenler `private/` altında; GitHub'a KESİNLİKLE gönderme. Runtime portu kalıcı servis yöneticisiyle henüz sabitlenmedi; process restart dayanıklılığı ayrıca doğrulanmalı.
- Shopify mevcut `client_credentials` ve `write_orders` scope'u: pilot API çalışıyor, ancak salt-okunur asgari yetki hedefi için daha sonra güvenli kapsam daraltma gerekli. Mevcut mağaza veya QBO tokenini izinsiz değiştirme.
- Test: 139 pytest PASS; gerçek QBO CompanyInfo HTTP 200, Shopify shop GraphQL PASS. Gerçek iki müşteri izolasyonu ve Shopify kullanıcı sahipliği PASS DEĞİL.
