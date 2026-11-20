# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-20
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**Profiller arası çelişki işareti (`receipts_conflicts`). Kabul ölçütü onay bekliyor, KOD YOK.**
Sınıf (her profil, sipariş başına): BOUND = `document_id` dolu (FOUND/AMOUNT_MISMATCH/CURRENCY_OR_TOTAL_UNKNOWN); AMBIG = `BLOCKED_DUPLICATE_*`; NONE = `REVIEW_NO_DOCUMENT`/`BLOCKED_UNBOUND_DOCUMENTS`/`BLOCKED_NO_ORDER_NUMBER`.
Karar: BOUND+BOUND farklı id → `REVIEW_PROFILE_CONFLICT`. BOUND+AMBIG → `REVIEW_PROFILE_AMBIGUOUS` (hangi belge olduğu bilinmiyor, kanıtlanamaz). BOUND+BOUND aynı id, BOUND+NONE (tek profil normal; gerçek bağlayıcı yalnız birini yazar), AMBIG+AMBIG, AMBIG+NONE, NONE+NONE → `NO_CONFLICT` (AMBIG olanlar kendi profilinde zaten BLOCKED). Tanınmayan/eksik durum, id'siz BOUND, sipariş iki profilde eşleşmiyor, aynı id ama farklı durum → `REVIEW_CONFLICT_UNKNOWN` (fail-closed). Çelişki işareti hiçbir mevcut durumu değiştirmez, yalnız bayrak.
Şekil: yeni ayrı anahtar `receipts_conflicts` = `{profiles:["docnumber","marker"], conflict_count, results:[{order, status, docnumber_status, marker_status, docnumber_document_id, marker_document_id, verified:false, cash_received_verified:false, bank_settlement_verified:false}]}`; yalnız bu alanlar (beyaz liste, `_audit_value`), PII yok. `receipts` ve `receipts_marker` AYNEN kalır. Profil bloklarından biri `None` ise `receipts_conflicts: null`. Yeni sorgu/ayar/Supabase alanı YOK; 5 GET /query bütçesi aynı (iki mevcut bağlama sonucundan saf hesap). Yanıt yalnız ek anahtar kadar büyür (~8 satır); `web/`/Nginx değişmez, dağıtım yalnız 8787–8789.
**Kabul (B'nin MEVCUT verisi, yeni veri girilmez):**
| Sipariş | docnumber | marker | Beklenen `status` |
|---|---|---|---|
| #1001 | FOUND(159) | FOUND(166) | REVIEW_PROFILE_CONFLICT |
| #1002 | BLOCKED_DUPLICATE_DOCUMENT_NUMBER | REVIEW_AMOUNT_MISMATCH(163) | REVIEW_PROFILE_AMBIGUOUS |
| #1003 | REVIEW_AMOUNT_MISMATCH(11) | BLOCKED_DUPLICATE_DOCUMENT_REFERENCE | REVIEW_PROFILE_AMBIGUOUS |
| #1004 | REVIEW_NO_DOCUMENT | FOUND(162) | NO_CONFLICT |
| #1005–#1007 | REVIEW_NO_DOCUMENT | REVIEW_NO_DOCUMENT | NO_CONFLICT |
| #1008 | REVIEW_CURRENCY_OR_TOTAL_UNKNOWN(17) | REVIEW_NO_DOCUMENT | NO_CONFLICT |
- `conflict_count`=3 (#1001–#1003). Her satırda verified/cash/bank false.
- `receipts_conflicts` anahtarı çıkarılınca yanıt hash'i AYNI: SHA256 d585b018…f532e, LEN 3985 (`receipts`, `receipts_marker`, `results` değişmez).
- Kod sonrası ve dağıtım öncesi yeni test yazılmaz; gerçek davranış canlı ölçümle kabul edilir (yeni test gerekirse önce sorulur).

## BİTTİ
- **6A-2b marker kabulü** kod `aa563b6` (`receipts_marker`; `receipts` docnumber değişmedi; yeni sorgu yok). Dağıtım 2026-11-20 15:29 +0200: 8787–8789 sırayla, /health 200, oturumsuz audit 401, dış /health 200, 8782–8786 dinlemiyor; yedek yok, nginx değişmedi. Canlı kabul (kullanıcı, B, 16:08 +02:00): anahtarsız hash d585b018…f532e LEN 3985 (receipt girildikten sonra da aynı); marker: #1001 FOUND(166, `not | ` biçimi), #1002 REVIEW_AMOUNT_MISMATCH(163, gid biçimi), #1003 BLOCKED_DUPLICATE_DOCUMENT_REFERENCE, #1004 FOUND(162), #1005–#1008 REVIEW_NO_DOCUMENT; verified/cash/bank hep false; unbound 1. B receipt'leri MKT-1(300), MKT-2(130), MKT-3A/3B(100), MKT-5(216); marker QBO'da "Message displayed on statement" = PrivateNote. #1005–#1007 TRY, receipt'ler USD olduğundan M2/M3/M5 #1001–#1004'e kaydırıldı.
- **PII whitelist** `f229a04`, **6A-2b docnumber** `bbebb7f`, **6A-2a** `dcdb40f`, **6A-1** `78c59c5`, **Adım 5**: ayrıntı `docs/history.md`. A=`hudys3-p0` realm `9341458613758425`, B=`vericon-tenant-b-test` realm `9341458641399133` (TRY). A ve B `financial_access_enabled=true` (AGENTS 6b; geri alma: bayrak `false`).

## BİTMEDİ
- Adım 6 kabul ölçütleri yazılmadı.
- M4 (geçersiz marker `abc`) canlıda bilerek ölçülmedi: yan etkisi taban ölçümü bozar.
- IDEAS: iki profil aynı siparişi farklı receipt'e bağlayabilir (çelişki tespiti yok), pilot şekil sınırı, serbest metin PII (PrivateNote/CustomField, Adım 7 öncesi), `index.html` `style=` CSP (düşük).

## BLOKE
- Receipt ödeme alanı (DepositToAccountRef/PaymentMethodRef/PaymentRefNum): beyaz liste döndürmüyor, bilinmiyor. Bilinene kadar yalnız "belge kaydı var", cash ve banka false.
- Eski CLI `invalid_grant` doğrulanmadı (dış çağrı gerekir).
- Dış kapılar: 2.5 muhasebe politikası, 2.6–2.7 banka/ödeme verisi, 2.8 muhasebeci örneklemi, 4.3 Shopify dağıtım kararı.

## Yapılmayacaklar
- Eski CLI OAuth kurtarma, OAuth URL üretme; yeni test yığını, refactor, yeni doküman; Profit/Intelligence

Fikir kutusu: `IDEAS.md`. Eski içerik: `docs/history.md`.
