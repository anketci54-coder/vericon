# VERICON: Ana Plan

Tek yaşayan plan. Sıra değişirse yalnızca bu dosya güncellenir. Kullanıcı onayı olmadan aşama atlanmaz.

## Hedef
Shopify sipariş → QBO fatura → ödeme/mahsup → mutabakat → kanıtlı uyuşmazlık sonucu. Salt-okunur, yanlış alarmsız, müşteri kayıtlarını değiştirmeden.

Ürün ayakları: **1. Finance (AKTİF)**, 2. Profit (sonra), 3. Intelligence (sonra). Finance ticari kabulü bitmeden Profit ve Intelligence kodlanmaz.

## Akış şeması

```
ADIM 0  Disiplin kurulumu (kod yok)
          ↓
ADIM 1  Gerçek durum özeti (salt okunur)
          ↓
ADIM 2  Ölçüm: A/B tenant yolundan sipariş + fatura + ödeme okunabiliyor mu?
          ↓
ADIM 3  Tek dar düzeltme: tenant bazlı salt-okunur denetim yolu
        (financial_access_enabled yalnız A/B için, onaylı)
          ↓
ADIM 4  İlk gerçek uçtan uca rapor
          ↓
   paralel, kod dışı (kullanıcı): muhasebeci, banka/ödeme verisi, merchant kararı
          ↓
ADIM 5  Panel
ADIM 6  Güvenilirlik testleri
ADIM 7  ABD pilot müşteri
ADIM 8  Hukuk ve uyumluluk
ADIM 9  Abonelik ve ödeme
ADIM 10 Ticari lansman
```

Her adım sonu: `HANDOFF.md` güncellenir, kullanıcı onaylar, ancak sonra sonraki adım başlar. Aşama kapanışında Fable (salt-okunur) bağımsız inceleme yapar.

## Yapıldı (kanıtlı, tekrar yapılmaz)
- Repo, GitHub ve VPS eşit; systemd üç API servisi, Nginx, HTTPS canlı
- Shopify test mağazaları ve QBO Sandbox okuma
- Sipariş-fatura eşleme, duplicate tespiti, tutar farkı, iade/mahsup zinciri (Sandbox)
- Bilinmeyen durum REVIEW/BLOCK
- OTP girişi, oturum, Shopify sahiplik (A/B)
- A/B izolasyonu: kendi 200, çapraz 403 (fatura sayımı uçları)
- `write_orders` izni kaldırıldı; kota, rate limit, OAuth state sertleştirmeleri
- Yerel fixture ingest ve benchmark (sentetik, müşteri doğruluğu değil)

## Yapılması gerekip yapılmayan
- Tenant bağlantısı üzerinden uçtan uca finans denetimi. Şu an tenant yolunda yalnızca fatura sayımı var. **Asıl eksik halka.**
- Eski CLI `invalid_grant` borcu. Önce gerekli mi ölçülür, otomatik kurtarma yok.
- Root yerine özel runtime kullanıcısı, HSTS, readiness izleme, kilitli bağımlılık kurulumu

## Dış kapılar (kullanıcıdan veya dışarıdan)
| Kapı | Gerekli |
|---|---|
| 2.5 | İşletme/muhasebeci onaylı belge politikası + izinli örnek |
| 2.6–2.7 | Banka veya ödeme sağlayıcısı settlement verisi |
| 2.8 | Muhasebeci etiketli örneklem |
| 4.3 | Shopify dağıtım türü, app redirect/scope, dış merchant test kurulumu |

Bunlar kod ile çözülmez. Ajan bu maddeleri BLOKE olarak tutar, uydurma kanıt üretmez.

## Adımların kabul ölçütleri

**ADIM 0 Disiplin kurulumu**
Kabul: AGENTS, PLAN, HANDOFF, IDEAS repoda; eski TODO.md `docs/history.md`'ye taşındı; commit atıldı.

**ADIM 1 Gerçek durum özeti**
Kabul: Ajan repoyu salt-okunur tarar ve tek sayfada yazar: çalışan yollar, çalışmayan yollar, tenant finans yolu var mı. Dosya değişikliği 0.

**ADIM 2 Ölçüm**
Kabul: A/B tenant yolundan Shopify siparişi, QBO Invoice ve Payment okunabilir mi; eksik alanlar hangileri. Sonuç BİTTİ/BLOKE olarak yazılır. Yeni kod yok.

**ADIM 3 Tek dar düzeltme**
Kabul: Yalnız A/B için, yalnız okuma, scope artışı yok; mevcut `financial_access_enabled` kısıtı bu iki hesap için kaldırılır. Çapraz erişim hâlâ 403. Geri alma yolu yazılı.

**ADIM 4 İlk uçtan uca rapor**
Kabul: A veya B Sandbox için sipariş → fatura → ödeme → sonuç raporu gerçek API verisiyle üretilir; yazma çağrısı 0; banka doğrulaması yoksa ödeme kısmı açıkça incelemede.

Adım 5 ve sonrası için kabul ölçütleri, Adım 4 kapanınca ayrı yazılır.

## Başlangıç sırası özeti
Adım 0 → 1 → 2 → (onay) → 3 → 4 → paralel dış kapılar → 5…10.
