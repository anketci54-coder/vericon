# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-17
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**ADIM 5 (Panel)** başlamadı. Aşağıdaki TASLAK kullanıcıyla onaylanmadan hiçbir şey yapılmaz.
TASLAK kapsam: pilot müşterinin kendi bağlantısı için salt-okunur denetim sonucunu (sipariş adı, durum kodu, tutar farkı; PII yok) gösteren tek sayfa; veri kalıcı bir çağıran yoldan gelir (adaptör + audit, IDEAS Denetçi 2). Yazma/mutation yok, banka doğrulaması "incelemede" yazılı kalır.
TASLAK kabul: (1) B hesabı oturumla kendi sonucunu görür, A hesabı B'ninkini göremez (403); (2) sonuç sayfası yalnız onaylı alanları basar, PII/token yok; (3) VERIFIED/REVIEW/BLOCKED ayrımı ve nedeni görünür; (4) yazma çağrısı 0; (5) dağıtım ayrı onayla.
BLOKE (taslak için): panelin mevcut durumu/yeri okunmadı; veri kaynağı ve arayüz biçimi kullanıcı kararı.

## BİTTİ
- Adım 1, 2, 3A, 3B, 4-1 (ayrıntı `docs/history.md`). A=`hudys3-p0` realm `9341458613758425`, B=`vericon-tenant-b-test` realm `9341458641399133` (TRY). A ve B `financial_access_enabled=true` (AGENTS 6b; geri alma: bayrak `false`).
- **Adım 4-2:** `adapt_tenant_envelopes` fail-closed, kod `0fd7254`, `main`=`origin/main`=`4-2-adaptor`, 612 test geçti (`pytest -q`). ChatGPT ve Gemini incelemesi sonrası düzeltmeler: refund `nodes` eksik, `pageInfo` dict değil, dict olmayan satır, kısmi blok = tüm girdi BLOCKED, boş `orders` BLOCKED. Dağıtım yok.
- **Adım 4-3:** kanıt: kullanıcının 17-11 09:55 konsol ölçümü (8 belgede marker yeni numaralarla) ve `invoice_audit.py:800-821` ayrıştırma kuralı (`VERICON_SHOPIFY_ORDER_ID=` marker; çoklu/çelişkili = hata).
- **Adım 4-4** (2026-11-17, kullanıcı kabulü, tek seferlik salt-okunur koşu, yazma 0): adaptör READY; audit 0/8 VERIFIED, hiçbiri sessiz geçmedi. #1001–#1004 fatura yok (beklenen); #1005, #1008 pilot şekil dışı (`BLOCKED_UNSUPPORTED_ORDER_LINES`: kargo satırı 0, SKU yok); #1006 120≠119 ve #1007 çift fatura kasıtlı, doğru yakalandı.
- B test siparişleri #1005–#1008; 8 QBO belge notu güncel. Dağıtım 4-1: `05324c5` (2026-11-17 08:19 EET).

- **Adım 4 kapandı.** 4-5: adaptör `start==1` ve `store`/`realm` eşleşmesi şart (kod `ebc9eaa`, 621 test, dağıtım yok: servis adaptörü çağırmıyor). `denetci` bulguları 3, 4 düzeltildi; 1, 2, 5 IDEAS'ta (9 zaten IDEAS Adım 7).
- **Dağıtım 4-5a:** `64066c7` (`shopify_read.py` pageInfo fail-closed), 8787–8789 sırayla yeniden başlatıldı 2026-11-17 13:26 EET. Nginx değişmedi, yedek gerekmedi (son: `/root/backup-nginx/vericon-app.conf.20261116-114739`). Kanıt: 3 birim active, yerel /health 200 ×3, dış /health 200, orders oturumsuz 401, yalnız 127.0.0.1:8787-8789 dinliyor (8782-8786 yok), son 3 dk uyarı logu yok.

## BİTMEDİ
- Adım 5 (yukarıda, taslak onayı bekliyor).
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
