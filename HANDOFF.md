# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-18
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**Adım 6A (TASLAK, başlatılmadı; kullanıcı onayı yok).** Kod yok, dal yok.
Kapsam: (1) ortak belge modeli, saf fonksiyon: Invoice/SalesReceipt/CreditMemo/RefundReceipt aynı iç biçime. (2) QBO'dan SalesReceipt ve RefundReceipt okuma: yalnız GET /query, yeni scope yok (doğrula), yeni dış yazma yok. (3) Bağlama profili, istek parametresi, izinli liste: `marker` (VERICON_SHOPIFY_ORDER_ID, varsayılan) ve `docnumber` (QBO belge no = Shopify sipariş no; yalnız tam eşleşme veya tek tanımlı önek). Supabase şeması değişmez. Profil yok / eşleşme belirsiz / aynı numara iki belgede = BLOKE, tahmin yok.
Kabul: sandbox'ta SalesReceipt ve RefundReceipt örnekleriyle doğru eşleşme REVIEW/VERIFIED; numara yok, çakışma, yanlış tutar BLOKE/REVIEW; mevcut Invoice yolu bozulmaz; yazma 0; panel yalnız onaylı alanları gösterir; canlı ölçüm; dağıtım ayrı onay.
Ön koşul (BLOKE): önce gerçek bağlayıcı çıktısı gözlemlenmeli (IDEAS 6A satırı).

## BİTTİ
- Adım 1–4 (ayrıntı `docs/history.md`). A=`hudys3-p0` realm `9341458613758425`, B=`vericon-tenant-b-test` realm `9341458641399133` (TRY). A ve B `financial_access_enabled=true` (AGENTS 6b; geri alma: bayrak `false`).
- **Adım 5 kapandı (2026-11-18).** 5A `0f5155f`, 5B `af1e47e` + dar ekran `4d18934`, hepsi dağıtıldı (ayrıntı `docs/history.md`).
- **5B canlı kabul** (kullanıcı, 2026-11-18 11:50–12:30 EET, tarayıcı): B sayfada kendi mağazası, 8 sipariş, doğrulanan 0, banka doğrulanmadı, salt-okunur, nedenler 4-4 ile uyumlu; A yalnız kendi mağazası ve 4 siparişi. Dar ekran: `.audit-scroll` var, scrollWidth 1265 > clientWidth 314, overflow-x auto, sebep sütunu yatay kaydırarak görüldü.

## BİTMEDİ
- Adım 6 (Güvenilirlik testleri) kabul ölçütleri yazılmadı; 6A taslağı onaylanana kadar bekler.
- IDEAS: pilot şekil sınırı (Adım 7), B test verisi yeniden kurulumu (düşük öncelik), `index.html` eski `style=` nitelikleri CSP'de engelleniyor (düşük öncelik). `shopify_read.py` fail-open satırı kapandı (4-5a); IDEAS'ta işaretlemek kullanıcı kararı.

## BLOKE
- 6A: SalesReceipt/RefundReceipt okumanın mevcut OAuth izniyle çalıştığı kanıtı yok; sandbox test belgelerini kullanıcı elle girecek.
- 16-11 08:29 ve 11:01 callback hatalarının kaynağı: kullanıcı teyidi.
- Eski CLI `invalid_grant` doğrulanmadı (dış çağrı gerekir).
- Dış kapılar: 2.5 muhasebe politikası, 2.6–2.7 banka/ödeme verisi, 2.8 muhasebeci örneklemi, 4.3 Shopify dağıtım kararı.

## Yapılmayacaklar
- Eski CLI OAuth kurtarma, OAuth URL üretme
- Yeni test yığını, refactor, yeni mimari, yeni doküman
- Profit ve Intelligence kodlaması

Fikir kutusu: `IDEAS.md`. Eski içerik: `docs/history.md`.
