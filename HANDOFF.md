# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-23
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**Adım 7 kabul ölçütü ONAYLANDI (2026-11-23); uygulama başlamadı.** Sıradaki tek iş: kullanıcı hangi maddeyle başlanacağını seçer (PLAN.md Adım 7).
- İlk pilot 7 gün, elle kapatma (`financial_access_enabled=false`); admin paneli ve ödeme kapsam dışı.
- Ölçütler 7.1–7.7: İngilizce arayüz, müşteri açma listesi, süre/403, silme yolu, ToS, destek, dış kapılar.
- BLOKE: 7.4 token iptali (AGENTS §6), app.bundle.js kaynağı yok, "4-2 İzolasyon Testi" düğmesi okunmadı, arayüz Türkçe.

## BİTTİ
- **Adım 7 kabul ölçütü** onaylandı ve `PLAN.md`'ye yazıldı (2026-11-23, kullanıcı); kod yok.
- **documents/audit hata dalı envanteri** (2026-11-23, yalnız okuma, kod değişmedi): satır 612 (`QueryResponse.get(entity, [])`) anahtar yoksa boş sayfa → audit'te REVIEW_NO_DOCUMENT, sahte VERIFIED yok; sıkılaştırma yapılmadı (gerçek QBO sıfır-sonuç gövdesi ölçülmedi). Ayrıntı `docs/history.md`.
- **`receipts_unmatched`** `9fe6a9a`, dağıtım 2026-11-23 10:24 +0200, canlı kabul B 10:27 (hash d585b018…f532e LEN 3985; docnumber 7, marker 7 unmatched; unbound [66]); ayrıntı `docs/history.md`.
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
