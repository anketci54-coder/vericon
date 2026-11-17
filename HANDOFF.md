# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-17
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**ADIM 5A (sunucu endpoint'i)** ONAYLI (2026-11-17), dal `5a-audit-endpoint`. Dağıtım yok, Nginx'e dokunulmaz.
5A kapsam: tek `GET` endpoint `/tenant/finance/audit?store=` (`store` zorunlu, orders rotasıyla aynı), yanıtta `read_only: true`, salt-okunur. İstek anında `read_tenant_orders` + `read_tenant_documents` → `adapt_tenant_envelopes(store=, realm=)` → `audit_order_financial_batch`; sonuç kaydedilmez. Yetki mevcut `_authorized_tenant_connection` + `store`/`realm` eşleşmesi + `financial_access_enabled` ile (orders/documents rotalarıyla aynı). Yanıt yalnız onaylı alanlar: sipariş adı, durum kodu, `verified`, tutar/fark, adaptör durumu, `bank_settlement_verified=false`. Her hata 503 (mevcut kalıp). Yeni Nginx bloğu gerekir (dağıtımda).
5A kabul: (1) B oturumu kendi sonucunu görür: B canlıda tüm siparişlerin BLOCKED çıkması başarısızlık değil; beklenen HTTP 200, 8 sipariş, her birinde durum kodu ve neden, hiçbiri sessizce eksik değil, VERIFIED beklenmiyor (B pilot şeklinde değil); (2) A oturumu B'nin `store`/`realm`'ini isterse 403; (3) oturumsuz 401; (4) yanıtta PII/token/`user_id` yok (alan listesi testle sabit); (5) yazma çağrısı 0 (yalnız GET/query, mutation yok); (6) bozuk/eksik veri BLOCKED, hata 503; (7) tüm suit geçer; (8) dağıtım ayrı onayla (`/dagit`, Nginx yedek + reload).
BLOKE: canlı ölçüm (1)-(3) yalnız dağıtım sonrası ve kullanıcı oturumlarıyla; Nginx bloğu dağıtım adımında ayrı onay.
Sıradaki: **5B** (arayüz: yeni düz JS dosyası, bağımlılık yok, yalnız 5A'yı çağırır; `PLAN.md` maddesi).

## BİTTİ
- Adım 1, 2, 3A, 3B, 4-1 (ayrıntı `docs/history.md`). A=`hudys3-p0` realm `9341458613758425`, B=`vericon-tenant-b-test` realm `9341458641399133` (TRY). A ve B `financial_access_enabled=true` (AGENTS 6b; geri alma: bayrak `false`).
- **Adım 4-2:** `adapt_tenant_envelopes` fail-closed, kod `0fd7254`, `main`=`origin/main`=`4-2-adaptor`, 612 test geçti (`pytest -q`). ChatGPT ve Gemini incelemesi sonrası düzeltmeler: refund `nodes` eksik, `pageInfo` dict değil, dict olmayan satır, kısmi blok = tüm girdi BLOCKED, boş `orders` BLOCKED. Dağıtım yok.
- **Adım 4-3:** kanıt: kullanıcının 17-11 09:55 konsol ölçümü (8 belgede marker yeni numaralarla) ve `invoice_audit.py:800-821` ayrıştırma kuralı (`VERICON_SHOPIFY_ORDER_ID=` marker; çoklu/çelişkili = hata).
- **Adım 4-4** (2026-11-17, kullanıcı kabulü, tek seferlik salt-okunur koşu, yazma 0): adaptör READY; audit 0/8 VERIFIED, hiçbiri sessiz geçmedi. #1001–#1004 fatura yok (beklenen); #1005, #1008 pilot şekil dışı (`BLOCKED_UNSUPPORTED_ORDER_LINES`: kargo satırı 0, SKU yok); #1006 120≠119 ve #1007 çift fatura kasıtlı, doğru yakalandı.
- B test siparişleri #1005–#1008; 8 QBO belge notu güncel. Dağıtım 4-1: `05324c5` (2026-11-17 08:19 EET).

- **Adım 4 kapandı.** 4-5: adaptör `start==1` ve `store`/`realm` eşleşmesi şart (kod `ebc9eaa`, 621 test, dağıtım yok: servis adaptörü çağırmıyor). `denetci` bulguları 3, 4 düzeltildi; 1, 2, 5 IDEAS'ta (9 zaten IDEAS Adım 7).
- **Dağıtım 4-5a:** `64066c7` (`shopify_read.py` pageInfo fail-closed), 8787–8789 sırayla yeniden başlatıldı 2026-11-17 13:26 EET. Nginx değişmedi, yedek gerekmedi (son: `/root/backup-nginx/vericon-app.conf.20261116-114739`). Kanıt: 3 birim active, yerel /health 200 ×3, dış /health 200, orders oturumsuz 401, yalnız 127.0.0.1:8787-8789 dinliyor (8782-8786 yok), son 3 dk uyarı logu yok.

## BİTMEDİ
- 5A taslağı (yukarıda), sonra 5B.
- IDEAS: pilot şekil sınırı (Adım 7), B test verisi yeniden kurulumu (düşük öncelik). `shopify_read.py` fail-open satırı kapandı (4-5a); IDEAS'ta işaretlemek kullanıcı kararı.

## BLOKE
- 16-11 08:29 ve 11:01 callback hatalarının kaynağı: kullanıcıdan teyit (o saatlerde OAuth/bağlantı sayfası açıldı mı).
- Eski CLI `invalid_grant` doğrulanmadı (dış çağrı gerekir).
- Dış kapılar: 2.5 muhasebe politikası, 2.6–2.7 banka/ödeme verisi, 2.8 muhasebeci örneklemi, 4.3 Shopify dağıtım kararı.

## Yapılmayacaklar
- Eski CLI OAuth kurtarma, OAuth URL üretme
- Yeni test yığını, refactor, yeni mimari, yeni doküman
- Profit ve Intelligence kodlaması

Fikir kutusu: `IDEAS.md`. Eski içerik: `docs/history.md`.
