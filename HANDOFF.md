# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-23
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**Sonraki iş, kullanıcı kararı bekliyor.**

## BİTTİ
- **`receipts_unmatched`** kod `9fe6a9a`, dağıtım 2026-11-23 10:24 +0200 (sunucu saati): 8787–8789 sırayla, active, /health 200, oturumsuz audit 401, dış /health 200, yalnız 127.0.0.1:8787–8789 dinliyor; yedek yok, nginx değişmedi.
  Canlı kabul (B, 2026-11-23 10:27 yerel, kullanıcı): anahtarsız hash (receipts_marker, receipts_conflicts, receipts_unmatched çıkarılınca) d585b018…f532e LEN 3985; docnumber unmatched 7 (38,47,162–166 NO_ORDER_MATCH); marker unmatched 7 (11,17,38,47,159,160,161 NO_MARKER); unbound iki profilde [66 BLOCKED_REFUND_MARKER_REQUIRED]; truncated false; alanlar document_id/document_kind/reason.
- **`receipts_conflicts`** `9c308a0` (dağıtım 2026-11-20, canlı kabul 17:16; ayrıntı `docs/history.md`).
- **6A-2b marker** `aa563b6`, **PII whitelist** `f229a04`, **6A-2b docnumber** `bbebb7f`, **6A-2a** `dcdb40f`, **6A-1** `78c59c5`, **Adım 5**: ayrıntı `docs/history.md`. A=`hudys3-p0` realm `9341458613758425`, B=`vericon-tenant-b-test` realm `9341458641399133` (TRY). A ve B `financial_access_enabled=true` (AGENTS 6b; geri alma: bayrak `false`).

## BİTMEDİ
- Adım 6 kabul ölçütleri yazılmadı.
- M4 (geçersiz marker `abc`) canlıda bilerek ölçülmedi: yan etkisi taban ölçümü bozar.
- IDEAS: `receipts_unmatched.unbound` 50'de sessiz kesiliyor, pilot şekil sınırı, serbest metin PII (Adım 7 öncesi), `index.html` `style=` CSP (düşük).

## BLOKE
- Receipt ödeme alanı (DepositToAccountRef/PaymentMethodRef/PaymentRefNum): beyaz liste döndürmüyor, bilinmiyor. Bilinene kadar yalnız "belge kaydı var", cash ve banka false.
- Eski CLI `invalid_grant` doğrulanmadı (dış çağrı gerekir).
- Dış kapılar: 2.5 muhasebe politikası, 2.6–2.7 banka/ödeme verisi, 2.8 muhasebeci örneklemi, 4.3 Shopify dağıtım kararı.

## Yapılmayacaklar
- Eski CLI OAuth kurtarma, OAuth URL üretme; yeni test yığını, refactor, yeni doküman; Profit/Intelligence

Fikir kutusu: `IDEAS.md`. Eski içerik: `docs/history.md`.
