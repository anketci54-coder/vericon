# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-18
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**Adım 6A-2b (HAZIRLIK TAMAM, başlatılmadı; onay yok). Kod yok.** Kapsam, kabul ölçütü ve B'ye elle girilecek 4 SalesReceipt listesi `PLAN.md` 6A-2b altında (son hal).
**Bloke kalanlar:** ödeme kaydı tanımı (receipt ödeme alanı bilinmiyor, yalnız "belge kaydı var"); bağlama profili (`marker`/`docnumber`); #1001–#1004 sipariş toplam/satırları repoda yok (okuma gerekir); B'deki mevcut 4 SalesReceipt + 1 RefundReceipt'in DocNumber/işareti bilinmiyor; QBO aynı DocNumber'ı kabul ediyor mu bilinmiyor.
**Gerçek kullanıcı sesi kapısı:** 3 gerçek Reddit konusu okundu (2026-11-18); yöntem sorusu cevaplandı; belge numarası = sipariş numarası mı belirsiz, bilinmeyen = BLOKE. Kullanıcı kararı: devam, atla veya daha fazla konuş. Karar yok, 6A-2b başlamaz.

## BİTTİ
- **6A-2a kapandı** (`dcdb40f`, main'de, dağıtım yok, canlı yolda çağıran yok): `normalize_document`, `bind_documents_to_orders`, 3 test, suit 638. Kurallar (a) RefundReceipt/CreditMemo yalnız refund marker, (b) tutar eşleşirse yalnız `DOCUMENT_RECORD_FOUND`, (c) yalnız baştaki `#`, tek önek.
- 16-11 08:29 ve 11:01 callback hataları kapandı: kaynak belirlenemedi, kullanıcı hatırlamıyor (2026-11-18).
- **6A-1 kapandı** (`78c59c5` dağıtıldı 2026-11-18 15:16 +02:00, sunucu saati, journalctl 8789 başlama 15:16:14). Canlı kanıt (kullanıcı, B, konsol, 2026-11-18 15:24 +02:00, Bükreş saati): documents 200, Invoice 36/Payment 20/CreditMemo 4/SalesReceipt 4/RefundReceipt 1, has_more false; yeni türlerde PII yok. Eski 3 türde BillEmail/BillAddr/ShipAddr/FreeFormAddress/CustomerMemo/CustomerRef dönüyor (IDEAS, yüksek öncelik, Adım 7 öncesi).
- Adım 1–4 (ayrıntı `docs/history.md`). A=`hudys3-p0` realm `9341458613758425`, B=`vericon-tenant-b-test` realm `9341458641399133` (TRY). A ve B `financial_access_enabled=true` (AGENTS 6b; geri alma: bayrak `false`).
- **Adım 5 kapandı (2026-11-18).** 5A `0f5155f`, 5B `af1e47e` + dar ekran `4d18934`, hepsi dağıtıldı (ayrıntı `docs/history.md`).
- **5B canlı kabul** (kullanıcı, 2026-11-18 11:50–12:30 +02:00, tarayıcı): B sayfada kendi mağazası, 8 sipariş, doğrulanan 0, banka doğrulanmadı, salt-okunur, nedenler 4-4 ile uyumlu; A yalnız kendi mağazası ve 4 siparişi. Dar ekran: `.audit-scroll` var, scrollWidth 1265 > clientWidth 314, overflow-x auto, sebep sütunu yatay kaydırarak görüldü.

## BİTMEDİ
- Adım 6 (Güvenilirlik testleri) kabul ölçütleri yazılmadı; 6A-2b kapısı geçilene kadar bekler.
- IDEAS: pilot şekil sınırı (Adım 7), B test verisi yeniden kurulumu (düşük öncelik), `index.html` eski `style=` nitelikleri CSP'de engelleniyor (düşük öncelik). `shopify_read.py` fail-open satırı kapandı (4-5a); IDEAS'ta işaretlemek kullanıcı kararı.

## BLOKE
- Receipt ödeme alanı: BLOKE. DepositToAccountRef, PaymentMethodRef ve PaymentRefNum repoda (kod, fixture, belge) hiç geçmiyor; canlı yolda da görünmez, çünkü `RECEIPT_ROW_FIELDS` beyaz listesi bunları döndürmüyor ve canlı kanıtta (15:24 +02:00) yalnız PII yokluğu doğrulandı, alan adları kaydedilmedi. Bu alanların sandbox receipt'inde olup olmadığı bilinmiyor; öğrenmek beyaz liste değişikliği ve canlı ölçüm ister. Bilinene kadar yalnız "belge kaydı var", cash ve banka false.
- Eski CLI `invalid_grant` doğrulanmadı (dış çağrı gerekir).
- Dış kapılar: 2.5 muhasebe politikası, 2.6–2.7 banka/ödeme verisi, 2.8 muhasebeci örneklemi, 4.3 Shopify dağıtım kararı.

## Yapılmayacaklar
- Eski CLI OAuth kurtarma, OAuth URL üretme
- Yeni test yığını, refactor, yeni mimari, yeni doküman
- Profit ve Intelligence kodlaması

Fikir kutusu: `IDEAS.md`. Eski içerik: `docs/history.md`.
