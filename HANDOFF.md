# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-18
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**Adım 6A-1 (yalnız okuma dilimi): kod bitti, dağıtılmadı.** `qbo_oauth.py`: `TENANT_DOCUMENT_ENTITIES` ve sorgu izin listesine SalesReceipt/RefundReceipt eklendi; bu iki tür beyaz liste alanlarıyla döner (PII yok), bozuk sayfa ValueError. Suit 635 geçti. Yan etki: `/tenant/finance/audit` artık 5 GET /query yapıyor (denetim mantığı değişmedi, adaptör yeni türleri yok sayar). Dağıtım ayrı onay (`/dagit`).
Sırada kalan 6A: (1) ortak belge modeli, (3) bağlama profili (`marker` varsayılan, `docnumber` tam eşleşme/tek önek; belirsiz/çakışma = BLOKE), kabul: sandbox örnekleri, Invoice yolu bozulmaz, yazma 0, panel onaylı alanlar, canlı ölçüm. Bağlama profili belge numarası ayarına dayanır, gözlem yapılmadı, bilinmeyen = BLOKE.

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
