# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-16
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**ADIM 2: Ölçüm.** A/B tenant yolundan Shopify siparişi, QBO Invoice ve Payment okunabilir mi; eksik alanlar hangileri. Yeni kod yok.
2a (kod okuma) BİTTİ. 2b (Supabase SELECT) BLOKE, aşağıda.

## Onaylı karar
A/B kendi Sandbox hesapları için, yalnızca okuma yetkisiyle `financial_access_enabled` açılabilir (2026-11-16). Kullanımı yalnızca Adım 3'te. Detay: AGENTS.md 6b.

## BİTTİ
- Adım 0: disiplin dosyaları repoda (`ed72111`)
- Adım 1: durum özeti. Kanıt: `systemctl`, `ss`, `cmp`, kod okuma, `python3 -m pytest -q -p no:cacheprovider` = 556 passed (normal ağ, dosya değişikliği 0)
  - Çalışan: servisler 8787/8788/8789 active; 8782–8786 dinlemiyor; Nginx, unit, web dosyaları repo ile aynı; local = origin/main
  - Tenant yolunda yalnızca `/tenant/finance/invoice-count` (COUNT) ve `access-check` var
  - Sipariş + fatura + ödeme okuyan kod tenant'a bağlı DEĞİL: `read_invoices/payments/credit_memos` saved-setup token'ı, `read_try_pilot_*` gömülü TRY realm, `read_shopify_test_orders` gömülü mağaza kullanıyor; hepsi yalnızca CLI. Asıl eksik halka bu.

- Adım 2a: kod okuma. Tenant QBO token deposu ve OAuth var (`qbo_oauth.py:236-331`), tenant Invoice/Payment/CreditMemo okuyan fonksiyon yok (yalnız `read_tenant_invoice_count`, `:423`). Tenant Shopify yalnızca sahiplik kanıtı: `REQUIRED_SCOPES` içinde `read_orders` yok (`shopify_read.py:56`); `save_tenant_setup` üretimde çağrılmıyor.

## BLOKE
- Adım 2b: `vericon_pilot_connections` SELECT, publishable key (anon) ile HTTP 401, PostgREST kodu 42501 (permission denied). Tablo anon'a kapalı, yalnızca oturum açmış kullanıcı JWT'si ile okunuyor (RLS). Satır sayısı ve `financial_access_enabled` değeri BİLİNMİYOR. Kimden ne lazım: sen, ya A/B kullanıcı JWT'sini ver (token sohbete girmez, yerel dosya/ortam değişkeni olarak) ya da kimlik bilgisi gerektirmeyen başka bir okuma yolu onayla (ör. Supabase panelinden satırları sen kontrol et). Service-role anahtarı aranmadı, kullanılmadı.
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
