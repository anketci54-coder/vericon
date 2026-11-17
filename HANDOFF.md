# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-16
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**ADIM 4-0** (PLAN.md Adım 4 hazırlığı; kapsam ve kabul ölçütü başlamadan kullanıcıyla yazılır). Başlamadı.

## BİTTİ
- Adım 1, Adım 2 (A=`hudys3-p0` realm `9341458613758425`, B=`vericon-tenant-b-test` realm `9341458641399133` = TRY realm; tenant ve legacy token yolları ayrı).
- **Adım 3A kapandı.** Kod `48d83d5`, Nginx + 8787–8789 yeniden başlatma yapıldı. Kanıt (2026-11-16 11:17–11:24 EET, kullanıcı panelden ölçtü): A bayrak `false` iken A→A 403; B→B 200 (ilk sayfa Invoice 5, Payment 5, CreditMemo 4); A→A 200 (5, 5, 1); A→B 403; B→A 403; oturumsuz 401.
- Bayraklar: A ve B `financial_access_enabled=true` (kullanıcı, Supabase paneli, AGENTS 6b). Geri alma: ilgili satırda bayrak `false`; servis yeniden başlatma gerekmez.
- RLS: `vericon_pilot_connections` yalnızca SELECT politikası ve yetkisi; kullanıcı bayrağı değiştiremez (kullanıcı panelden doğruladı).
- Shopify kimlik dosyası (yalnız ad listelendi): `private/shopify_tenants/` içinde B (`vericon-tenant-b-test.myshopify.com`) ve A (`hudys3-p0.myshopify.com`, 3B-A ile yazıldı). A→A orders 200 ölçüldü.
- 8787 `QBO_OAUTH_CALLBACK_FAILURE`: 50 kayıt, hepsi `ValueError`. 13-11: 36 `state_validation_failure` (3 patlama × 12, aynı saniye) + 5 `other_failure` (her biri servis restartından 3–4 sn sonra). 14-11: 6 (5 other, 1 state). 16-11: 08:29 1 state, 11:01 2 other. Hepsi Nginx üzerinden geldi (callback durum logunda 50 upstream 400 + 63 adet 429 + 1 adet 200). Callback logu IP/zaman tutmuyor; ana access.log'da 13-11 13:46'ya kadarki callback çağrıları VPS'in kendi IP'sinden (curl/python-requests). Ajan oturum kayıtlarında 16-11 08:29 ve 11:01'e denk gelen callback çağrısı yok.


- **Adım 3B kapandı.** Kod `edf9e15` (main'de), dağıtım 11:47 EET. Canlı ölçüm 2026-11-16 (kullanıcı): B→B `/tenant/shopify/orders` 200, 4 sipariş, USD, PII yok; A→A 200 (onaylandı). Çapraz store 403, bayrak false 403, `first` aralığı 400, oturumsuz 401 kapı testinde BİTTİ.
- 3B-0, 3B-A, 3B dağıtım ayrıntısı (11:47 EET, yedek `/root/backup-nginx/vericon-app.conf.20261116-114739`) `docs/history.md` sonunda.
- **Dağıtım 4-1:** kod `05324c5`, 8787–8789 yeniden başlatıldı 2026-11-17 08:19 EET (Nginx değişmedi, yedek gerekmedi; son yedek `/root/backup-nginx/vericon-app.conf.20261116-114739`). Kanıt: 3 birim active, /health 200, dış /health 200, orders oturumsuz 401, yalnız 127.0.0.1:8787-8789 dinliyor.
- B Shopify mağazası USD'ye çevrildi. B'de 4 test siparişi: #1001 $216 (iade $100), #1002 $120, #1003 $100, #1004 $300 (iade 2×$100).

## BLOKE
- 16-11 08:29 ve 11:01 callback hatalarının kaynağı: IP/zaman kaydı yok, kanıtla belirlenemiyor. Kullanıcı o saatlerde OAuth/bağlantı sayfası açtı mı, kullanıcıdan teyit.
- Eski CLI `invalid_grant` doğrulanmadı (dış çağrı gerekir).
- Dış kapılar: 2.5 muhasebe politikası, 2.6–2.7 banka/ödeme verisi, 2.8 muhasebeci örneklemi, 4.3 Shopify dağıtım kararı.

## Yapılmayacaklar
- Eski CLI OAuth kurtarma, OAuth URL üretme
- Yeni test yığını, refactor, yeni mimari, yeni doküman
- Profit ve Intelligence kodlaması

Fikir kutusu: `IDEAS.md`. Eski içerik: `docs/history.md`.
