# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-24
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**7.2** (PLAN.md Adım 7): müşteri açma için yazılı tek sayfa elle kontrol listesi (Supabase `ownership_verified`, `financial_access_enabled`). Başlamadı; kapsam ve kabul ölçütü başlamadan kullanıcıyla yazılır.
- Önce kullanıcı karar verir: müşteri ekranındaki 3 düğme (Shopify kod x2, Disconnect QuickBooks) kalsın mı.
- İlk pilot 7 gün, elle kapatma (`financial_access_enabled=false`); admin paneli ve ödeme kapsam dışı.

## BİTTİ
- **7.1 İngilizce arayüz:** kodlar `cffd065` (a), `56b3c1e` (b), `ad63780` (c), `4e0c5bd` (d). GitHub=yerel `4e0c5bd` (ls-remote 2026-11-24). Yalnız statik dağıtım, cmp OK, nginx ve servis dokunulmadı; yedekler `/var/www/vericon-app/*.bak-20261124-*`.
- Canlı kanıt (B, kullanıcı, 2026-11-24): tablo İngilizce; conflict_count 3; unmatched 7/7; kusurlu belge 1 (ID 66); oturum ekranı "Verified ✓", "Enabled · Pilot", doğru yeşil kutu; giriş ekranı ve kod sonrası düğme İngilizce; konsolda yalnız favicon 404. Bundle yaması bağımsız doğrulandı (38 değişiklik, kalan Türkçe 0).
- Önceki: receipts_unmatched `9fe6a9a`, receipts_conflicts `9c308a0`, 6A-2b `aa563b6`, PII `f229a04`, docnumber `bbebb7f`, 6A-2a `dcdb40f`, 6A-1 `78c59c5`, Adım 5 (`docs/history.md`).
- A=`hudys3-p0` realm `9341458613758425`, B=`vericon-tenant-b-test` realm `9341458641399133` (TRY). İkisi `financial_access_enabled=true` (AGENTS 6b; geri alma: bayrak `false`).

## BİTMEDİ
- Bayrak `false` dalı (bundle metni) canlıda ölçülmedi; 7.3'te bayrak false/true ölçümüyle.
- `tenant-isolation-check.js` A/B realm ID'leri açıkta (kaldırmak nginx reload onayı ister); `/favicon.ico` 404.
- IDEAS: unbound 50'de sessiz kesiliyor; receipts bölüm başlığı "Status: OK" yanıltıcı; serbest metin PII.
- Adım 6 kabul ölçütleri yazılmadı. M4 (geçersiz marker `abc`) bilerek ölçülmedi.

## BLOKE
- 7.4 token iptali (AGENTS §6 ayrı onay); `app.bundle.js` kaynağı repoda yok (yalnız dizge yaması yapıldı).
- Receipt ödeme alanı beyaz listesi yok; bilinene kadar cash/banka false.
- Eski CLI `invalid_grant` doğrulanmadı (dış çağrı).
- Dış kapılar: 2.5 muhasebe politikası, 2.6–2.7 banka/ödeme verisi, 2.8 muhasebeci örneklemi, 4.3 Shopify dağıtım kararı.

## Yapılmayacaklar
- Eski CLI OAuth kurtarma, OAuth URL üretme; yeni test yığını, refactor, yeni doküman; Profit/Intelligence

Fikir kutusu: `IDEAS.md`. Eski içerik: `docs/history.md`.
