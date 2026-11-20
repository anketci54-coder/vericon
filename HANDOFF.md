# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-20
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**Sonraki iş, kullanıcı kararı bekliyor.** (Aday: Adım 6 kabul ölçütleri; başlatılmadı.)

## BİTTİ
- **PII whitelist (Invoice/Payment/CreditMemo)** kod `f229a04`, dağıtım 2026-11-20 14:28 +0200 (8787–8789 sırayla, /health 200, oturumsuz audit 401, dış /health 200, 8782–8786 dinlemiyor). Canlı kabul (kullanıcı, B, 14:40 +02:00): `/tenant/finance/audit` hash'i değişmedi (SHA256 d585b018…f532e, LEN 3985, HTTP 200); `/tenant/finance/documents` 5 türde yasaklı alan yok, CustomerRef.name yok, alan listeleri whitelist'le birebir (Invoice 36, Payment 20, CreditMemo 4, SalesReceipt 7, RefundReceipt 1 satır).
- **6A-2b** (`bbebb7f`, dağıtım + canlı kabul 2026-11-20), **6A-2a** (`dcdb40f`), **6A-1** (`78c59c5`), **Adım 5**: ayrıntı `docs/history.md`. A=`hudys3-p0` realm `9341458613758425`, B=`vericon-tenant-b-test` realm `9341458641399133` (TRY). A ve B `financial_access_enabled=true` (AGENTS 6b; geri alma: bayrak `false`).

## BİTMEDİ
- Adım 6 kabul ölçütleri yazılmadı; 6A-2b sonrası.
- IDEAS: pilot şekil sınırı, serbest metin PII (PrivateNote/CustomField, Adım 7 öncesi), `index.html` `style=` CSP (düşük).

## BLOKE
- Receipt ödeme alanı (DepositToAccountRef/PaymentMethodRef/PaymentRefNum): beyaz liste döndürmüyor, bilinmiyor. Bilinene kadar yalnız "belge kaydı var", cash ve banka false.
- Eski CLI `invalid_grant` doğrulanmadı (dış çağrı gerekir).
- Dış kapılar: 2.5 muhasebe politikası, 2.6–2.7 banka/ödeme verisi, 2.8 muhasebeci örneklemi, 4.3 Shopify dağıtım kararı.

## Yapılmayacaklar
- Eski CLI OAuth kurtarma, OAuth URL üretme; yeni test yığını, refactor, yeni doküman; Profit/Intelligence

Fikir kutusu: `IDEAS.md`. Eski içerik: `docs/history.md`.
