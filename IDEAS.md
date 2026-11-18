# IDEAS: Fikir Kutusu

Kural: Buraya yalnızca not düşülür. Hiçbir fikir kullanıcı onayı olmadan işe dönüşmez.
Biçim: `- [ ] YYYY-MM-DD | fikir | ilgili aşama (PLAN adım no)`
Aşama kapanışında ilgili fikirler için karar: yap / ertele / çöpe at.

## Açık
- [ ] 2026-11-16 | Disiplin kuralı: tüm ajan oturumları HANDOFF.md ile başlar ve biter | Adım 0
- [ ] 2026-11-18 | **YÜKSEK ÖNCELİK, gerçek müşteri verisinden önce:** /tenant/finance/documents eski 3 türde (Invoice, Payment, CreditMemo) ham `SELECT *` döndürüyor; canlı kanıt: BillEmail, BillAddr, ShipAddr, FreeFormAddress, CustomerMemo, CustomerRef anahtarları dönüyor. Beyaz liste (receipt kalıbı, `RECEIPT_ROW_FIELDS`) uygulanmalı | Adım 7 öncesi (güncellendi, ilk kayıt 2026-11-16)
- [ ] 2026-11-16 | documents hata dalı testleri (401→409, 429, 5xx, Fault, has_more) | Adım 6
- [ ] 2026-11-17 | shopify_read.py ~331-337: pageInfo/hasNextPage eksikse has_next_page=False üretiyor (fail-open); eksikse hata veya True olmalı. Canlı kod, dağıtım gerekir | Adım 4-5 öncesi
- [ ] 2026-11-17 | Audit pilot şekil sınırı: yalnız tek ürün (SKU VERICON-TEST-001) + tek kargo satırı; gerçek müşteri için kapsam genişletme kararı, muhasebe politikası (dış kapı 2.5) gerekir | Adım 7
- [ ] 2026-11-17 | B test siparişleri #1005-#1008 pilot şekline uymuyor (SKU yok, kargo satırı yok, #1008 1x300 vs faturada 3x100); doğrulanmış (VERIFIED) canlı örnek istenirse test verisi yeniden kurulmalı (düşük öncelik) | Adım 4-5 sonrası
- [ ] 2026-11-17 | Denetçi 2: adapt_tenant_envelopes'u çağıran kalıcı yol yok (4-4 heredoc'la koşuldu, repoda üreten kod yok); rapor üretimi için kalıcı çağıran gerekir | Adım 5
- [ ] 2026-11-17 | Denetçi 5 (BİTTİ notu): tenant izolasyonu (store/realm RLS tek satır, ownership_verified, financial_access_enabled) kanıtlandı; pilot istisnası belge okumada yok. Her yeni tenant yolunda aynı koşullar yeniden kontrol edilir | Adım 7
- [ ] 2026-11-18 | index.html'deki eski style= nitelikleri CSP tarafından engelleniyor (Adım 5 kapsamı dışı, düşük öncelik) | Adım 5 sonrası
- [ ] 2026-11-18 | Adım 6A adayı: (1) denetim yalnız Invoice/Payment/CreditMemo okuyor, gerçek mağazalarda yaygın SalesReceipt/RefundReceipt yok; (2) bağlama kuralı VERICON_SHOPIFY_ORDER_ID işaretine bağlı, gerçek bağlayıcılar (MyWorks: sipariş numarası belge numarası olur) bunu yazmıyor; (3) önce gerçek bağlayıcı çıktısı gözlemlenmeli. Başlatılmadı | Adım 6A
