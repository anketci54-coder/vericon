# VERICON

**Guncel durum: 2026-11-03.** Bu bir **Sandbox prototipidir**, satisa hazir SaaS degildir.

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

**Siradaki tek dogru oncelik:** Mevcut QuickBooks faturasi ve Shopify siparis verisinin salt-okunur kullanilabilirligini olcmek; sonra Modul A icin gercek uyusmazlik kaniti. `TODO.md`ye bak. Gereksiz test fixture, panel veya zamanlayici acma.

## Temizlik ve E2E delili (2026-11-03)
- Gereksiz eski `.env.example`, saatlik test service/timer deploy dosyalari ve VPS systemd unitleri temizlendi. OAuth kurtarma betigi, tek seferlik API okuyuculari, guvenlik testleri ve `private/` sakli bilgileri korundu. `__pycache__/` ve `.pytest_cache/` uretilmis dosyalari silindi.
- Test baslangici/sonunda Shopify lokasyon on_hand/available/committed/updatedAt ve QuickBooks Item QtyOnHand/SyncToken/LastUpdatedTime **ayni** okundu. Tekli API kontrolu `TEST_DIFFERENCE`, 10-7=3, okuma araligi 1.163 sn. Ikili CLI: mevcut SKU fark 3 + eksik Shopify SKU `BLOCKED_ITEM_READ`, grup `TEST_BATCH_PARTIAL_BLOCKED`, exit=2 (beklenen).
- Bu, Sandbox okuma ve fark hesaplama akisi icin uctan uca delildir. Uretim, fatura mutabakati, ticari kayip, tum urunler veya tokenin teknik yazma izninin kaldirildigi iddia edilmez.
