# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-20
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**Adım 6A-2b (ONAYLI, profil `docnumber`, kod yazılıyor, push/dağıtım onay bekler).** Kapsam ve kabul ölçütü `PLAN.md` 6A-2b. Değişiklik: `AUDIT_DOCUMENT_ENTITIES` + receipt'ler, `tenant_finance_audit` çıktısında ayrı `receipts` alanı. Receipt asla verified/cash/bank true üretmez.

## BİTTİ
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
