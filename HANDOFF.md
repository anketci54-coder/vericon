# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-20
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**Adım 6 sonraki alt adım: kullanıcı kararı bekliyor.** Kabul ölçütleri yazılmadı; karar gelmeden başlanmaz.

## BİTTİ
- **6A-2b kapandı** (kod `bbebb7f`, dağıtım 2026-11-20 13:37 +0200 sunucu saati; 8787–8789 sırayla, /health 200, oturumsuz audit 401). Canlı kabul (kullanıcı, B, 13:41 +02:00): HTTP 200, profil docnumber; #1001 `DOCUMENT_RECORD_FOUND`(159); #1002 `BLOCKED_DUPLICATE_DOCUMENT_NUMBER`; #1003 `REVIEW_AMOUNT_MISMATCH`(11); #1004–#1007 `REVIEW_NO_DOCUMENT`; #1008 `REVIEW_CURRENCY_OR_TOTAL_UNKNOWN`(17); verified/cash/bank false; unbound_count=1 (RefundReceipt 1020, marker yok: `invoice_audit.py:2206`).
- **6A-2a** (`dcdb40f`, main): `normalize_document`, `bind_documents_to_orders`; dağıtım yok.
- **6A-1** (`78c59c5`, dağıtıldı 2026-11-18) ve **Adım 5** (`0f5155f`, `af1e47e`, `4d18934`) kapandı; ayrıntı `docs/history.md`. A=`hudys3-p0` realm `9341458613758425`, B=`vericon-tenant-b-test` realm `9341458641399133` (TRY). A ve B `financial_access_enabled=true` (AGENTS 6b; geri alma: bayrak `false`).
- **B ölçümü 2026-11-20** (kullanıcı): sipariş/receipt değerleri ve para birimleri `docs/history.md`. Receipt para birimi BLOKE'si kapandı: Id11,17,159,160,161 USD. QBO yinelenen DocNumber'ı kabul ediyor.
- **Kod okuması:** `BLOCKED_UNSUPPORTED_ORDER_LINES` (`invoice_audit.py:1446`) yalnız Invoice yolunda, bağ+para birimi+toplam sonrası; bağlama satıra bakmaz.

## BİTMEDİ
- Adım 6 kabul ölçütleri yazılmadı; 6A-2b sonrası.
- IDEAS: eski 3 türde PII (yüksek, Adım 7 öncesi), pilot şekil sınırı, `index.html` `style=` CSP (düşük).

## BLOKE
- Receipt ödeme alanı (DepositToAccountRef/PaymentMethodRef/PaymentRefNum): beyaz liste döndürmüyor, bilinmiyor. Bilinene kadar yalnız "belge kaydı var", cash ve banka false.
- Eski CLI `invalid_grant` doğrulanmadı (dış çağrı gerekir).
- Dış kapılar: 2.5 muhasebe politikası, 2.6–2.7 banka/ödeme verisi, 2.8 muhasebeci örneklemi, 4.3 Shopify dağıtım kararı.

## Yapılmayacaklar
- Eski CLI OAuth kurtarma, OAuth URL üretme; yeni test yığını, refactor, yeni doküman; Profit/Intelligence

Fikir kutusu: `IDEAS.md`. Eski içerik: `docs/history.md`.
