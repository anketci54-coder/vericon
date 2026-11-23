# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-23
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**`receipts_unbound` kabul ölçütü (YAZILDI, kod yok, kullanıcı onayı bekliyor).** Şimdi: `unbound` yalnız (A) kusurlu belgeleri tutar (`invoice_audit.py:2197` error, `:2202` docnumber'da numarasız, `:2206` marker'sız iade); yanıtta yalnız `unbound_count` (`qbo_oauth.py:986`). (B) kusursuz ama eşleşmeyen satışlar hiçbir listede yok (sessiz); marker profilinde işaretsiz satışlar da öyle; siparişe bağlanmayan iade belgesi de öyle.
- **Şekil (kullanıcı düzeltmesi 2026-11-23):** mevcut bloklara anahtar eklenmez (hash bozulur). Ayrı üst düzey tek anahtar `receipts_unmatched` = `{docnumber:{unbound:[≤50], unmatched_count, unmatched:[≤20], unmatched_truncated}, marker:{...}}`. Alanlar yalnız `document_id, document_kind, reason` (NO_ORDER_MATCH | NO_MARKER; A'da bind durum kodu). `bind_documents_to_orders` sonuçları değişmez; verified/cash/bank false; yeni sorgu yok.
- **Gürültü/boyut:** okuma zaten ≤50 belge/tür (`qbo_oauth.py:573`), fazlası `has_more`=true ile kapanır; tavan 20 satır ≈ 1 KB. Gerçek mağazada B binlerce olursa yalnız sayı büyür.
- **Bütçe:** yeni sorgu yok (5 GET /query aynı), yeni dış çağrı yok. Mevcut anahtarların hiçbiri/yapısı değişmez.
- **Kabul (B, gerçek ölçüm, kullanıcı 2026-11-23):** 12 SalesReceipt (11 no1003, 17 no1008, 38 no1011, 47 no1014, 159 no1001, 160/161 no1002, 162 MKT-1, 163 MKT-2, 164 MKT-3A, 165 MKT-3B, 166 MKT-5; 162–166 ORDER_MARKER, diğerlerinde marker yok) + 1 RefundReceipt (66 no1020, marker yok).
  | profil | unbound (A) | unmatched (B) |
  |---|---|---|
  | docnumber | 66 BLOCKED_REFUND_MARKER_REQUIRED | 7: 38, 47, 162, 163, 164, 165, 166 NO_ORDER_MATCH |
  | marker | 66 aynı | 7: 11, 17, 38, 47, 159, 160, 161 NO_MARKER |
  truncated false; 160/161 (docnumber çift), 164/165 (marker çift) unmatched değil. `receipts_marker`, `receipts_conflicts`, `receipts_unmatched` çıkarılınca hash d585b018…f532e, LEN 3985.

## BİTTİ
- **`receipts_unmatched`** kod `9fe6a9a` dağıtıldı 2026-11-23 10:24 +0200 (sunucu saati): 8787–8789 sırayla, /health 200, oturumsuz audit 401, dış /health 200, yalnız 127.0.0.1:8787–8789 dinliyor (8782–8786 yok); yedek yok, nginx değişmedi. Canlı kabul (B, yukarıdaki tablo) kullanıcıda bekliyor.
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
