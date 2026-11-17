# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-17
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**ADIM 4-2** (PLAN.md Adım 4; kapsam ve kabul ölçütü başlamadan kullanıcıyla yazılır). Başlamadı.

## BİTTİ
- Adım 1, Adım 2 (A=`hudys3-p0` realm `9341458613758425`, B=`vericon-tenant-b-test` realm `9341458641399133` = TRY realm; tenant ve legacy token yolları ayrı).
- Adım 3A, 3B kapandı; ayrıntı `docs/history.md` sonunda. 8787 callback hata dökümü de orada.
- Bayraklar: A ve B `financial_access_enabled=true` (kullanıcı, Supabase paneli, AGENTS 6b). Geri alma: ilgili satırda bayrak `false`; servis yeniden başlatma gerekmez.
- RLS: `vericon_pilot_connections` yalnızca SELECT politikası ve yetkisi; kullanıcı bayrağı değiştiremez (kullanıcı panelden doğruladı).
- Shopify kimlik dosyası (yalnız ad listelendi): `private/shopify_tenants/` içinde B (`vericon-tenant-b-test.myshopify.com`) ve A (`hudys3-p0.myshopify.com`, 3B-A ile yazıldı). A→A orders 200 ölçüldü.

- **Dağıtım 4-1:** kod `05324c5`, 8787–8789 yeniden başlatıldı 2026-11-17 08:19 EET (Nginx değişmedi, yedek gerekmedi; son yedek `/root/backup-nginx/vericon-app.conf.20261116-114739`). Kanıt: 3 birim active, /health 200, dış /health 200, orders oturumsuz 401, yalnız 127.0.0.1:8787-8789 dinliyor.
- B Shopify mağazası TRY. B'de test siparişleri #1005–#1008. QBO'daki 8 belge notu yeni numaralarla güncellendi (kullanıcı, 2026-11-17 09:55).
- **Adım 4-1 kapandı.** Canlı sorgu ölçümü (kullanıcı): 8 sipariş, PII yok, sorgu maliyeti hatası yok.

## BLOKE
- 16-11 08:29 ve 11:01 callback hatalarının kaynağı: IP/zaman kaydı yok, kanıtla belirlenemiyor. Kullanıcı o saatlerde OAuth/bağlantı sayfası açtı mı, kullanıcıdan teyit.
- Eski CLI `invalid_grant` doğrulanmadı (dış çağrı gerekir).
- Dış kapılar: 2.5 muhasebe politikası, 2.6–2.7 banka/ödeme verisi, 2.8 muhasebeci örneklemi, 4.3 Shopify dağıtım kararı.

## Yapılmayacaklar
- Eski CLI OAuth kurtarma, OAuth URL üretme
- Yeni test yığını, refactor, yeni mimari, yeni doküman
- Profit ve Intelligence kodlaması

Fikir kutusu: `IDEAS.md`. Eski içerik: `docs/history.md`.
