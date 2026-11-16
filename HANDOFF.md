# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-16
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**ADIM 3B: `GET /tenant/shopify/orders?store=&first=`** (dal `3b-orders`, main'e birleşmedi). Scope artışı yok (3B-0: B'de `read_orders` var).
Kabul: B→B 200 (yalnız sipariş no, createdAt, currency, toplam/vergi/indirim, ödeme durumu, iade, işlem tutarı; müşteri adı/e-posta/adres/telefon ve token yok); çapraz store 403; bayrak false 403; `first` 1–25 dışı 400; kimlik dosyası yok (A) → 503, veri yok; oturumsuz 401. Yalnız GraphQL `query`, `read_orders` ayrı kontrol, `REQUIRED_SCOPES` değişmez.
Kod + HTTP kapı testi BİTTİ, main = `edf9e15`. Dağıtım BİTTİ. Kalan tek iş: canlı B→B ölçümü (ayrı kullanıcı onayıyla).

## BİTTİ
- Adım 1, Adım 2 (A=`hudys3-p0` realm `9341458613758425`, B=`vericon-tenant-b-test` realm `9341458641399133` = TRY realm; tenant ve legacy token yolları ayrı).
- **Adım 3A kapandı.** Kod `48d83d5`, Nginx + 8787–8789 yeniden başlatma yapıldı. Kanıt (2026-11-16 11:17–11:24 EET, kullanıcı panelden ölçtü): A bayrak `false` iken A→A 403; B→B 200 (ilk sayfa Invoice 5, Payment 5, CreditMemo 4); A→A 200 (5, 5, 1); A→B 403; B→A 403; oturumsuz 401.
- Bayraklar: A ve B `financial_access_enabled=true` (kullanıcı, Supabase paneli, AGENTS 6b). Geri alma: ilgili satırda bayrak `false`; servis yeniden başlatma gerekmez.
- RLS: `vericon_pilot_connections` yalnızca SELECT politikası ve yetkisi; kullanıcı bayrağı değiştiremez (kullanıcı panelden doğruladı).
- Shopify kimlik dosyası (yalnız ad listelendi): `private/shopify_tenants/` içinde 1 dosya, B (`vericon-tenant-b-test.myshopify.com`). A için dosya yok.
- 8787 `QBO_OAUTH_CALLBACK_FAILURE`: 50 kayıt, hepsi `ValueError`. 13-11: 36 `state_validation_failure` (3 patlama × 12, aynı saniye) + 5 `other_failure` (her biri servis restartından 3–4 sn sonra). 14-11: 6 (5 other, 1 state). 16-11: 08:29 1 state, 11:01 2 other. Hepsi Nginx üzerinden geldi (callback durum logunda 50 upstream 400 + 63 adet 429 + 1 adet 200). Callback logu IP/zaman tutmuyor; ana access.log'da 13-11 13:46'ya kadarki callback çağrıları VPS'in kendi IP'sinden (curl/python-requests). Ajan oturum kayıtlarında 16-11 08:29 ve 11:01'e denk gelen callback çağrısı yok.

- 3B-0 (2026-11-16, tek client_credentials isteği, yalnız B): HTTP 200, scope = read_inventory, read_locations, read_orders, read_products. B'de `read_orders` zaten verili; scope artışı gerekmiyor. `REQUIRED_SCOPES` değişmedi.
- **Dağıtım 3B** (2026-11-16 11:47 EET, kod `edf9e15`): Nginx diff yalnız `/tenant/shopify/orders` bloğu; yedek `/root/backup-nginx/vericon-app.conf.20261116-114739`; `nginx -t` temiz, reload; dış /health 200. 8787→8788→8789 sırayla restart, her biri active + yerel /health 200. Oturumsuz GET orders: önce 404, sonra 401; POST 403. Dinleyen: 8787–8789 (+ 8771 Senal Plastik, dokunulmadı).
- **3B-A** (2026-11-16, kullanıcı onayı): legacy kasa mağazası `hudys3-p0` doğrulandı; `save_tenant_setup` ile A dosyası yazıldı (`private/shopify_tenants/ab87c520-…_hudys3-p0.myshopify.com.json`, 0600, + store lock); B dosyasına dokunulmadı. Tek client_credentials isteği HTTP 200, scope = read_inventory, read_locations, read_orders, read_products (`read_orders` var).

## BLOKE
- 16-11 08:29 ve 11:01 callback hatalarının kaynağı: IP/zaman kaydı yok, kanıtla belirlenemiyor. Kullanıcı o saatlerde OAuth/bağlantı sayfası açtı mı, kullanıcıdan teyit.
- Eski CLI `invalid_grant` doğrulanmadı (dış çağrı gerekir).
- Dış kapılar: 2.5 muhasebe politikası, 2.6–2.7 banka/ödeme verisi, 2.8 muhasebeci örneklemi, 4.3 Shopify dağıtım kararı.

## Yapılmayacaklar
- Eski CLI OAuth kurtarma, OAuth URL üretme
- Yeni test yığını, refactor, yeni mimari, yeni doküman
- Profit ve Intelligence kodlaması

Fikir kutusu: `IDEAS.md`. Eski içerik: `docs/history.md`.
