# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-20
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**Sonraki iş, kullanıcı kararı bekliyor.** (Aday: Adım 6 kabul ölçütleri; başlatılmadı.)

## BİTTİ
- **`receipts_conflicts`** kod `9c308a0` (iki profil çelişki işareti; `receipts`/`receipts_marker`/ana denetim değişmedi; yeni sorgu yok). Dağıtım 2026-11-20 16:50 +0200: 8787–8789 sırayla, /health 200, oturumsuz audit 401, dış /health 200, 8782–8786 dinlemiyor; yedek yok, nginx değişmedi. Canlı kabul (kullanıcı, B, 17:16 +03:00 yerel): anahtarsız hash (receipts_marker ve receipts_conflicts çıkarılınca) d585b018…f532e LEN 3985; conflict_count 3; #1001 REVIEW_PROFILE_CONFLICT (159/166); #1002, #1003 REVIEW_PROFILE_AMBIGUOUS; #1004–#1008 NO_CONFLICT; verified/cash/bank false.
- **6A-2b marker** `aa563b6` (dağıtım 15:29 +0200, canlı kabul 16:08 +02:00; hash d585b018…f532e, unbound 1; ayrıntı `docs/history.md`). **PII whitelist** `f229a04`, **6A-2b docnumber** `bbebb7f`, **6A-2a** `dcdb40f`, **6A-1** `78c59c5`, **Adım 5**: ayrıntı `docs/history.md`. A=`hudys3-p0` realm `9341458613758425`, B=`vericon-tenant-b-test` realm `9341458641399133` (TRY). A ve B `financial_access_enabled=true` (AGENTS 6b; geri alma: bayrak `false`).

## BİTMEDİ
- Adım 6 kabul ölçütleri yazılmadı.
- M4 (geçersiz marker `abc`) canlıda bilerek ölçülmedi: yan etkisi taban ölçümü bozar.
- IDEAS: pilot şekil sınırı, serbest metin PII (PrivateNote/CustomField, Adım 7 öncesi), `index.html` `style=` CSP (düşük).

## BLOKE
- Receipt ödeme alanı (DepositToAccountRef/PaymentMethodRef/PaymentRefNum): beyaz liste döndürmüyor, bilinmiyor. Bilinene kadar yalnız "belge kaydı var", cash ve banka false.
- Eski CLI `invalid_grant` doğrulanmadı (dış çağrı gerekir).
- Dış kapılar: 2.5 muhasebe politikası, 2.6–2.7 banka/ödeme verisi, 2.8 muhasebeci örneklemi, 4.3 Shopify dağıtım kararı.

## Yapılmayacaklar
- Eski CLI OAuth kurtarma, OAuth URL üretme; yeni test yığını, refactor, yeni doküman; Profit/Intelligence

Fikir kutusu: `IDEAS.md`. Eski içerik: `docs/history.md`.
