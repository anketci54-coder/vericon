# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-16
Son bilinen SHA: `3f6fefe` (disiplin commit öncesi; güncel için `git log -1`)

## Şu an tek açık iş
**ADIM 1: Gerçek durum özeti (salt okunur).**
Kabul ölçütü: Repo taranır, tek sayfada şunlar yazılır: hangi yollar çalışıyor, hangileri çalışmıyor, tenant A/B yolunda sipariş + fatura + ödeme okuyan bir kod yolu var mı. Hiçbir dosya değişmez, hiçbir servis dokunulmaz, hiçbir dış API çağrısı yapılmaz.

## Onaylı karar
A/B kendi Sandbox hesapları için, yalnızca okuma yetkisiyle `financial_access_enabled` açılabilir (kullanıcı onayı 2026-11-16). Kullanımı yalnızca Adım 3'te. Detay: AGENTS.md 6b.

## BİTTİ
- Disiplin dosyaları yazıldı (kullanıcı repoya koyacak)
- Claude Code VPS'e kuruldu

## BİTMEDİ
- Adım 0: dosyaların repoya konması ve commit
- Adım 1: durum özeti

## BLOKE (dış kapılar, kullanıcıdan)
- 2.5 muhasebe politikası onayı
- 2.6–2.7 banka/ödeme sağlayıcısı verisi
- 2.8 muhasebeci etiketli örneklem
- 4.3 Shopify merchant dağıtım kararı

## Yapılmayacaklar
- Eski CLI OAuth kurtarma (`invalid_grant`), OAuth URL üretme
- `financial_access_enabled` kısıtını Adım 3'ten önce açmak
- Yeni test yığını, refactor, yeni mimari, yeni doküman
- Profit ve Intelligence kodlaması

## Fikir kutusu
`IDEAS.md`
