# IDEAS: Fikir Kutusu

Kural: Buraya yalnızca not düşülür. Hiçbir fikir kullanıcı onayı olmadan işe dönüşmez.
Biçim: `- [ ] YYYY-MM-DD | fikir | ilgili aşama (PLAN adım no)`
Aşama kapanışında ilgili fikirler için karar: yap / ertele / çöpe at.

## Açık
- [ ] 2026-11-16 | Disiplin kuralı: tüm ajan oturumları HANDOFF.md ile başlar ve biter | Adım 0
- [x] 2026-11-18 | Eski 3 tür PII (Invoice/Payment/CreditMemo ham SELECT *): KAPANDI, whitelist `f229a04`, canlı kabul 2026-11-20 14:40 | Adım 7 öncesi
- [ ] 2026-11-16 | envanter yapıldı (2026-11-23): 18 dal, KAPALI 6, KANITSIZ-GÜVENLİ 11 (hepsi hata kodu verip durur), KANITSIZ-RİSKLİ 1, satır 612 anahtar yoksa boş sayfa → REVIEW_NO_DOCUMENT; gerçek QBO sıfır-sonuç gövdesi ölçülmedi, ölçülene kadar kod değişmez | Adım 6
- [ ] 2026-11-17 | shopify_read.py ~331-337: pageInfo/hasNextPage eksikse has_next_page=False üretiyor (fail-open); eksikse hata veya True olmalı. Canlı kod, dağıtım gerekir | Adım 4-5 öncesi
- [ ] 2026-11-17 | Audit pilot şekil sınırı: yalnız tek ürün (SKU VERICON-TEST-001) + tek kargo satırı; gerçek müşteri için kapsam genişletme kararı, muhasebe politikası (dış kapı 2.5) gerekir | Adım 7
- [ ] 2026-11-17 | B test siparişleri #1005-#1008 pilot şekline uymuyor (SKU yok, kargo satırı yok, #1008 1x300 vs faturada 3x100); doğrulanmış (VERIFIED) canlı örnek istenirse test verisi yeniden kurulmalı (düşük öncelik) | Adım 4-5 sonrası
- [ ] 2026-11-17 | Denetçi 2: adapt_tenant_envelopes'u çağıran kalıcı yol yok (4-4 heredoc'la koşuldu, repoda üreten kod yok); rapor üretimi için kalıcı çağıran gerekir | Adım 5
- [ ] 2026-11-17 | Denetçi 5 (BİTTİ notu): tenant izolasyonu (store/realm RLS tek satır, ownership_verified, financial_access_enabled) kanıtlandı; pilot istisnası belge okumada yok. Her yeni tenant yolunda aynı koşullar yeniden kontrol edilir | Adım 7
- [x] 2026-11-18 | index.html'deki eski style= nitelikleri CSP tarafından engelleniyor: ÇÖZÜLDÜ (2026-11-24) | Adım 5 sonrası
- [ ] 2026-11-18 | Adım 6A adayı: (1) denetim yalnız Invoice/Payment/CreditMemo okuyor, gerçek mağazalarda yaygın SalesReceipt/RefundReceipt yok; (2) bağlama kuralı VERICON_SHOPIFY_ORDER_ID işaretine bağlı, gerçek bağlayıcılar (MyWorks: sipariş numarası belge numarası olur) bunu yazmıyor; (3) önce gerçek bağlayıcı çıktısı gözlemlenmeli. Başlatılmadı | Adım 6A
- [ ] 2026-11-18 | Callback hata logunda IP/zaman kaydı yok; hata tekrar ederse kaynak belirlenemez (düşük öncelik, kod değişikliği yok) | Adım 7 sonrası
- [ ] 2026-11-20 | Numara eşleştirmesi (docnumber profili) QBO'da "Custom transaction numbers" gerektirir; aksi hâlde DocNumber otomatik sıralı olur ve marker şart | Adım 6A-2b
- [x] 2026-11-20 | Eşleşmeyen receipt listesi: KAPANDI, `receipts_unmatched` `9fe6a9a`, canlı kabul 2026-11-23 | Adım 6
- [ ] 2026-11-20 | `PrivateNote`/`CustomField` serbest metin, bağlama işareti için gerekli; PII riski kalıyor (whitelist yalnız alan adını sınırlar, içeriği değil) | Adım 7 öncesi
- [x] 2026-11-20 | docnumber/marker profil çelişkisi: KAPANDI, `receipts_conflicts` `9c308a0`, canlı kabul 2026-11-20 | Adım 6
- [ ] 2026-11-20 | M4 (geçersiz marker `abc`, unbound+1 ve iki profilde BLOCKED_UNBOUND_DOCUMENTS) canlıda ölçülmedi; taban ölçümü bozar | Adım 6A-2b
- [ ] 2026-11-23 | `receipts_unmatched.unbound` listesi 50'de sessizce kesiliyor, truncated bayrağı yok | Adım 6
- [ ] 2026-11-23 | tenant-isolation-check.js hâlâ A/B realm ID'lerini taşıyor ve Nginx'ten servis ediliyor; iptal işleyicisini ayrı dosyaya taşı, eski dosyayı ve nginx location'ı kaldır (nginx reload ayrı onay) | Adım 7.1
- [x] 2026-11-23 | ÇÖZÜLDÜ `4e0c5bd` (2026-11-24) | "Musteri veri erisimi: Kapali · Pilot" (index.html:76, :96, app.bundle.js /auth/me tenant_authorized=false mesajlari) bayragi true olan B'de yanlis; access-check financial_access_enabled donduruyor; cozum: notr metin veya bayraga gore guncelleme | Adim 7.1
- [ ] 2026-11-24 | receipts bölüm başlığı 'Status: OK / Receipts were matched to orders' yanıltıcı, 8 siparişin 4'ünde belge yok | Adım 7
- [ ] 2026-11-25 | Ownership mesajı ('This store is already verified.') stilsiz düz yazı çıkıyor; tenant-shopify-code alanına sınıf ver | Adım 7
- [ ] 2026-11-25 | Pilot mağaza (A) tenant ownership düğmesine basarsa backend 409 döner ve ekranda yanıltıcı 'not authorized' mesajı çıkar | Adım 7
- [ ] 2026-11-25 | tenant-isolation-check.js: script etiketi 7.2-0 ile index.html'den kalktı, dosya ve nginx location duruyor; dosyayı sil, location'ı kaldır (nginx reload ayrı onay) | Adım 7
