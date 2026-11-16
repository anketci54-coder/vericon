# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-16
Son bilinen SHA: `ed72111` (bu güncelleme commit'i için `git log -1`)

## Şu an tek açık iş
**ADIM 2: Ölçüm.** A/B tenant yolundan Shopify siparişi, QBO Invoice ve Payment okunabilir mi; eksik alanlar hangileri. Yeni kod yok. Kullanıcı onayı bekleniyor.

## Onaylı karar
A/B kendi Sandbox hesapları için, yalnızca okuma yetkisiyle `financial_access_enabled` açılabilir (2026-11-16). Kullanımı yalnızca Adım 3'te. Detay: AGENTS.md 6b.

## BİTTİ
- Adım 0: disiplin dosyaları repoda (`ed72111`)
- Adım 1: durum özeti. Kanıt: `systemctl`, `ss`, `cmp`, kod okuma, `python3 -m pytest -q -p no:cacheprovider` = 556 passed (normal ağ, dosya değişikliği 0)
  - Çalışan: servisler 8787/8788/8789 active; 8782–8786 dinlemiyor; Nginx, unit, web dosyaları repo ile aynı; local = origin/main
  - Tenant yolunda yalnızca `/tenant/finance/invoice-count` (COUNT) ve `access-check` var
  - Sipariş + fatura + ödeme okuyan kod tenant'a bağlı DEĞİL: `read_invoices/payments/credit_memos` saved-setup token'ı, `read_try_pilot_*` gömülü TRY realm, `read_shopify_test_orders` gömülü mağaza kullanıyor; hepsi yalnızca CLI. Asıl eksik halka bu.

## BLOKE
- Canlı servisler eski kod: servisler 2026-11-14 07:46 EET'te başlamış, `qbo_oauth.py` 12:46'da (`101f5cf`), `shopify_read.py` 07:47'de (`edd59b5`) değişmiş. Yeniden başlatma gerekir. Kullanıcı onayı bekliyor.
- Eski CLI `invalid_grant` durumu doğrulanmadı (token/dış çağrı gerekir)
- `financial_access_enabled` canlı değeri okunmadı (dış çağrı)
- Dış kapılar: 2.5 muhasebe politikası, 2.6–2.7 banka/ödeme verisi, 2.8 muhasebeci örneklemi, 4.3 Shopify dağıtım kararı

## Yapılmayacaklar
- Eski CLI OAuth kurtarma, OAuth URL üretme
- `financial_access_enabled` kısıtını Adım 3'ten önce açmak
- Yeni test yığını, refactor, yeni mimari, yeni doküman
- Profit ve Intelligence kodlaması

## Fikir kutusu
`IDEAS.md`
