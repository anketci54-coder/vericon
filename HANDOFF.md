# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-17
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**ADIM 4-5** Aşama kapanışı: ChatGPT/Gemini ikinci göz, Fable denetçi, HANDOFF. Başlamadı; kapsam ve kabul ölçütü başlamadan kullanıcıyla yazılır.

## BİTTİ
- Adım 1, 2, 3A, 3B, 4-1 (ayrıntı `docs/history.md`). A=`hudys3-p0` realm `9341458613758425`, B=`vericon-tenant-b-test` realm `9341458641399133` (TRY). A ve B `financial_access_enabled=true` (AGENTS 6b; geri alma: bayrak `false`).
- **Adım 4-2:** `adapt_tenant_envelopes` fail-closed, kod `0fd7254`, `main`=`origin/main`=`4-2-adaptor`, 612 test geçti (`pytest -q`). ChatGPT ve Gemini incelemesi sonrası düzeltmeler: refund `nodes` eksik, `pageInfo` dict değil, dict olmayan satır, kısmi blok = tüm girdi BLOCKED, boş `orders` BLOCKED. Dağıtım yok.
- **Adım 4-3:** kanıt: kullanıcının 17-11 09:55 konsol ölçümü (8 belgede marker yeni numaralarla) ve `invoice_audit.py:800-821` ayrıştırma kuralı (`VERICON_SHOPIFY_ORDER_ID=` marker; çoklu/çelişkili = hata).
- **Adım 4-4** (2026-11-17, kullanıcı kabulü, tek seferlik salt-okunur koşu, yazma 0): adaptör READY; audit 0/8 VERIFIED, hiçbiri sessiz geçmedi. #1001–#1004 fatura yok (beklenen); #1005, #1008 pilot şekil dışı (`BLOCKED_UNSUPPORTED_ORDER_LINES`: kargo satırı 0, SKU yok); #1006 120≠119 ve #1007 çift fatura kasıtlı, doğru yakalandı.
- B test siparişleri #1005–#1008; 8 QBO belge notu güncel. Dağıtım 4-1: `05324c5` (8787–8789, 2026-11-17 08:19 EET).

## BİTMEDİ
- 4-5 (yukarıda).
- IDEAS: pilot şekil sınırı (Adım 7), B test verisi yeniden kurulumu (düşük öncelik); `shopify_read.py` ~331-337 `has_next_page` fail-open (canlı kod, dağıtım gerekir, 4-5 öncesi karar).

## BLOKE
- 16-11 08:29 ve 11:01 callback hatalarının kaynağı: kullanıcıdan teyit (o saatlerde OAuth/bağlantı sayfası açıldı mı).
- Eski CLI `invalid_grant` doğrulanmadı (dış çağrı gerekir).
- Dış kapılar: 2.5 muhasebe politikası, 2.6–2.7 banka/ödeme verisi, 2.8 muhasebeci örneklemi, 4.3 Shopify dağıtım kararı.

## Yapılmayacaklar
- Eski CLI OAuth kurtarma, OAuth URL üretme
- Yeni test yığını, refactor, yeni mimari, yeni doküman
- Profit ve Intelligence kodlaması

Fikir kutusu: `IDEAS.md`. Eski içerik: `docs/history.md`.
