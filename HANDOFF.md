# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-16
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**ADIM 3A: `GET /tenant/finance/documents`** (Invoice/Payment/CreditMemo, sınırlı sayfa, token dönmez).
Kapılar: `_authorized_tenant_connection` + realm eşleşmesi + `financial_access_enabled=true`. Yalnızca GET `/query`, scope artışı yok, Shopify'a dokunulmaz.
Kabul: A→A 200, A→B 403, B→A 403, oturumsuz 401 (mevcut auth davranışı), bayrak false iken 403.
Her biri ayrı kullanıcı onayıyla: (1) Nginx + middleware izin listesi, (2) servis yeniden başlatma, (3) `/health`, (4) geri alma planı. Bayrak EN SON, kullanıcı tarafından, yalnız bu iki satır için açılır (AGENTS 6b). Geri alma: bayrak `false`.
Kod yazmaya başlamadan önce kullanıcıdan başlama onayı alınır.

## Sonraki, onay bekliyor
**ADIM 3B:** Shopify `read_orders` (scope artışı). PLAN'da ayrı, 3A'dan bağımsız, ayrı onay.

## BİTTİ
- Adım 1: durum özeti, 556 test geçti (normal ağ)
- Adım 2 kapandı. Kanıt: kullanıcı Supabase panelinden okudu; `vericon_pilot_connections` 2 satır: `hudys3-p0` = A, `vericon-tenant-b-test` = B. İkisi `pilot_linked`, `ownership_verified=true`, `financial_access_enabled=false`.
- Kod okuma (2a): tenant yolunda yalnızca `read_tenant_invoice_count` (`qbo_oauth.py:423`); tenant Invoice/Payment/CreditMemo okuyan fonksiyon yok; tenant Shopify yalnızca sahiplik kanıtı, `read_orders` yok (`shopify_read.py:56`).
- B realm = TRY realm: B `9341458641399133` (docs/history.md:117,122), `invoice_audit.py:1713/1718/1765/1812` gömülü TRY realm `9341458641399133`. AYNI QBO şirketi (`Sandbox Company US 32e0`). A realm `9341458613758425`. 3A tenant okuması B'nin tenant token'ını, `read_try_pilot_*` ise ayrı legacy kasa tokenını kullanır; iki yol karıştırılmaz.
- Dağıtım Adım 2 (yalnızca Nginx): `main` = `48d83d5` VPS'te; canlı Nginx = repo (`cmp`), `nginx -t` temiz, reload yapıldı, `/health` 200. Yedek: `/root/backup-nginx/vericon-app.conf.20261116-110809`. `/tenant/finance/documents` servis yeniden başlatılana dek 403 (eski kod middleware).

## BLOKE
- Canlı servisler eski kod: 8787/8788/8789, 2026-11-14 07:46 EET'te başlamış; `qbo_oauth.py` sonradan değişti (`101f5cf`). Yeniden başlatma kullanıcı onayı bekliyor.
- Eski CLI `invalid_grant` doğrulanmadı (dış çağrı gerekir)
- Dış kapılar: 2.5 muhasebe politikası, 2.6–2.7 banka/ödeme verisi, 2.8 muhasebeci örneklemi, 4.3 Shopify dağıtım kararı

## Yapılmayacaklar
- Eski CLI OAuth kurtarma, OAuth URL üretme
- Bayrağı 3A kodu ve dağıtımı bitmeden açmak
- Yeni test yığını, refactor, yeni mimari, yeni doküman
- Profit ve Intelligence kodlaması

Fikir kutusu: `IDEAS.md`. Eski içerik: `docs/history.md`.
