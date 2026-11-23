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

## Checklist (tek kaynak: durum için HANDOFF.md, sıra için bu dosya)
İşaret: [x] bitti (kanıtlı), [ ] açık, [!] bloke. Yalnızca kullanıcı onayıyla işaretlenir.

**Adım 0-3**
- [x] 0 Disiplin kurulumu (AGENTS, PLAN, HANDOFF, IDEAS, komutlar)
- [x] 1 Gerçek durum özeti
- [x] 2 Ölçüm (A/B sipariş + fatura + ödeme okunabiliyor)
- [x] 3A `GET /tenant/finance/documents` canlı (`48d83d5`), izolasyon ölçüldü
- [x] 3B `GET /tenant/shopify/orders` canlı, B→B 200, PII yok (`edf9e15`)

**Adım 4 İlk uçtan uca rapor (KAPANDI 2026-11-17)**
- [x] 4-0 Girdi sözleşmesi farkı çıkarıldı (`audit_order_financial_batch`)
- [x] 4-1a B Shopify mağazası TRY, 4 yeni test siparişi (#1005-#1008, iadeler dahil)
- [x] 4-1b Sipariş sorgusu genişletildi, kod main'de (`05324c5`, 593 test)
- [x] 4-1c Dağıtım: `/dagit 05324c5` (8787-8789 yeniden başlatma, onayla)
- [x] 4-1d Canlı ölçüm: yeni alanlar geliyor mu, sorgu maliyeti hatası yok mu
- [x] 4-1e QBO notları: 8 belgeye yeni sipariş/iade numarası (elle, ayrı onay)
- [x] 4-2 Adaptör: zarf açma, yalnızca SUCCESS iade işlemi, kesilme kontrolü (lineItems/shippingLines hasNextPage, transactions tam 10), para birimi
- [x] 4-3 Tenant belge okuyucu: bağlantı notu (PrivateNote) doğrulaması
- [x] 4-4 İlk uçtan uca denetim: B siparişleri ↔ B QBO belgeleri, yazma çağrısı 0. Kanıt (2026-11-17, gerçek B verisi, yazma 0, 8 sipariş/36 fatura/4 kredi/20 ödeme): #1001–#1004 fatura yok (beklenen, `BLOCKED_ORDER_INVOICE_LINK`); #1005, #1008 pilot şekil dışı (`BLOCKED_UNSUPPORTED_ORDER_LINES`); #1006 toplam 120≠119 (`REVIEW_LINKED_TOTAL_MISMATCH`, kasıtlı); #1007 çift fatura DUP-1003 (`BLOCKED_MULTIPLE_LINKED_INVOICES`, kasıtlı). Hiçbir sipariş sessizce geçmedi, 0/8 VERIFIED.
- [x] 4-5 Aşama kapanışı: fail-closed düzeltmeler (`64066c7` dağıtıldı; adaptör start/store/realm), `denetci` denetimi (BLOKE bulguları 1, 2, 9 IDEAS'ta/Adım 5-7), HANDOFF

**Adım 5 ve sonrası (Adım 4 kapanınca kabul ölçütleri yazılır)**
- [x] 5A Sunucu endpoint'i: GET, salt-okunur, anlık hesap, kayıt yok, yalnız onaylı alanlar, mevcut `_authorized_tenant_connection`, hata 503. Dağıtım `0f5155f`; canlı ölçüm 2026-11-17 17:20–17:30 +02:00: B→B 200/8 sipariş, A→A 200, A→B/B→A/olmayan mağaza 403, oturumsuz 401
- [x] 5B Arayüz: `web/finance-audit.js`, yalnız 5A'yı çağırır. Dağıtım `af1e47e` + dar ekran `4d18934`; canlı kabul 2026-11-18 11:50–12:30 +02:00: B 8 sipariş/doğrulanan 0, A yalnız kendi 4 siparişi, yatay kaydırma ölçüldü. **Adım 5 kapandı.**
- [x] 6A-1 Okuma dilimi: SalesReceipt/RefundReceipt GET /query, beyaz liste. Dağıtım `78c59c5`; canlı kanıt (kullanıcı, B, konsol): documents 200, Invoice 36/Payment 20/CreditMemo 4/SalesReceipt 4/RefundReceipt 1, has_more false, yeni türlerde PII anahtarı yok.
- [x] 6A-2a Ortak belge modeli + docnumber/marker bağlama profili (saf fonksiyon, 3 test, canlı yol değişmedi). Kod `dcdb40f`, dağıtım yok. Ödeme alanı bulgusu: BLOKE (HANDOFF).
- [ ] 6A-2b Receipt'leri audit'e ve uca bağla, canlı ölçüm, dağıtım ayrı onay (TASLAK; önce "gerçek kullanıcı sesi" kapısı, HANDOFF).
  - **6A-2b kapsam (son hal, başlatılmadı):** (1) `AUDIT_DOCUMENT_ENTITIES` SalesReceipt/RefundReceipt'i de okur (6A-1 beyaz listesi değişmez); (2) audit `bind_documents_to_orders` (6A-2a) çağırır; (3) uç ve panel yalnız bağ çıktısındaki onaylı alanları döndürür. Kapsam dışı: ödeme alanı, beyaz liste genişletme, yazma, Profit/Intelligence.
  - **Kabul ölçütü:** (a) receipt satırı hiçbir koşulda VERIFIED, cash true veya bank true üretmez; en iyi sonuç `DOCUMENT_RECORD_FOUND`; (b) B'de aşağıdaki 4 receipt girilince canlı ölçümde beklenen durumlar tabloyla birebir çıkar; (c) yazma çağrısı 0; (d) A yalnız kendi, B yalnız kendi verisi; (e) dağıtım ayrı onay, GitHub=VPS aynı SHA.
  - **Kural (b) ödeme kaydı tanımı: BLOKE.** DepositToAccountRef/PaymentMethodRef/PaymentRefNum receipt'te var mı bilinmiyor (beyaz liste döndürmüyor). Bilinene kadar yalnız "belge kaydı var".
  - **Bağlama profili: BLOKE.** `marker` mı `docnumber` mı (önek var mı) kullanıcı kararı; "gerçek kullanıcı sesi" kapısına bağlı.
  - **Gerçek kullanıcı sesi (2026-11-18, 3 gerçek Reddit konusu okundu):** yöntem sorusu cevaplandı; belge numarası = sipariş numarası mı: belirsiz. Bilinmeyen = BLOKE; docnumber profili bu belirsizlik çözülmeden varsayılan yapılmaz.
  - **Sandbox B elle girilecek SalesReceipt'ler (kaynak: kod + testler + HANDOFF; bilinmeyen = BLOKE).** Sabit: para birimi TRY, vergi 0, TaxCode NON. Kodun beklediği sipariş şekli (`_audit_pilot_line_items`): 1 ürün satırı SKU `VERICON-TEST-001` + 1 kargo satırı başlığı `Standart` (QBO'da kalem `SHIPPING-STANDARD`, adet 1, kargo>0 ise ayrı satır). Bağlama (6A-2a) satır şekline bakmaz, yalnız numara/işaret, toplam ve para birimine bakar; satır şekli yalnız faturadaki pilot doğrulamasında kullanılır, receipt'e uygulanması 6A-2b kararı değil, BLOKE.
    - Uyan/uymayan B siparişleri: #1005–#1008 uymuyor (SKU yok, kargo satırı yok, #1008 1x300 vs 3x100; IDEAS 2026-11-17, PLAN 4-4). #1001–#1004: sipariş toplamı, satırları, kargosu repoda kayıtlı değil, uyup uymadığı BLOKE (canlı/Shopify okuma gerekir, bu oturumda yapılmadı). Aşağıdaki tablo bu yüzden #1001–#1004 üzerine kuruludur; toplam ve satır hücreleri sipariş okunana kadar BLOKE.
    - B'de hâlihazırda 4 SalesReceipt + 1 RefundReceipt var (6A-1 canlı sayım); DocNumber ve işaretleri kayıtlı değil. Docnumber profilinde yeni belgelerle çakışabilir: BLOKE, girişten önce okunmalı.

| # | Sipariş | DocNumber | Toplam | Para | Satırlar | Sınanan durum | Beklenen bağ sonucu |
|---|---|---|---|---|---|---|---|
| R1 | #1001 | `1001` | = sipariş toplamı (BLOKE: değer) | TRY | VERICON-TEST-001 x1 + SHIPPING-STANDARD x1 (sipariş şekline uyuyorsa; BLOKE) | tam eşleşme | `DOCUMENT_RECORD_FOUND` (docnumber profili) |
| R2 | #1002 | `1002` | sipariş toplamı + 1.00 (BLOKE: değer) | TRY | R1 ile aynı | tutar uyuşmaz | `REVIEW_AMOUNT_MISMATCH` |
| R3a | #1003 | `1003` | = sipariş toplamı (BLOKE: değer) | TRY | R1 ile aynı | aynı numara iki belgede | `BLOCKED_DUPLICATE_DOCUMENT_NUMBER` |
| R3b | #1003 | `1003` | R3a ile aynı | TRY | R1 ile aynı | (R3a ile birlikte) | aynı satır |
| - | #1004 | (receipt girilmez) | - | - | - | numara hiç yok | `REVIEW_NO_DOCUMENT` |

    - R3a/R3b: QBO'nun aynı DocNumber'ı kabul edip etmediği (yinelenen numara uyarısı/engeli) bilinmiyor: BLOKE; kabul etmezse bu durum sandbox'ta girilemez, fixture testiyle sınanır.
    - "Numara hiç yok" iki ayrı durumdur: siparişe ait receipt yok (#1004, `REVIEW_NO_DOCUMENT`) ve DocNumber'sız receipt (`BLOCKED_NO_DOCUMENT_NUMBER`). İkincisi sandbox'ta girilebilir mi (QBO otomatik numara verir mi) bilinmiyor: BLOKE; girilmeyecek.
    - `marker` profilinde bu 4 receipt'in hiçbiri bağlanmaz (işaret yok) ve hepsi `REVIEW_NO_DOCUMENT`; marker durumunu sınamak istenirse PrivateNote'a `VERICON_SHOPIFY_ORDER_ID=<id>` elle eklenmesi gerekir (ayrı karar).
- [ ] 6 Güvenilirlik testleri
- [ ] 7 ABD pilot müşteri (kabul ölçütü yazıldı 2026-11-23, onay bekliyor; başlatılmadı)
  - **Karar (kullanıcı, 2026-11-23):** ilk pilot 7 gün; süre elle kapatılır (Supabase `financial_access_enabled=false`; uzatma = bayrağı `true` yapmak). Otomatik süre ve token iptali ilk pilot sonrasına. Kapsam DIŞI: admin paneli (3–5 müşteriden sonra), ödeme/abonelik (Adım 9).
  - **Kabul ölçütü (her madde gerçek davranışla kanıtlanır; BİTTİ/BİTMEDİ/BLOKE):**
    - **7.1** Arayüz tamamen İngilizce (görünür tüm metin, hata mesajları dahil). Bulgular (ana denetim, receipts, receipts_marker, receipts_conflicts, receipts_unmatched) konsolsuz ekranda sade dille görünür; her durum kodunun yanında kısa açıklama. Kanıt: B hesabında gerçek ekran, mevcut canlı veriyle beklenen sonuçlar.
    - **7.2** Müşteri açma: yazılı tek sayfa elle kontrol listesi (Supabase: `ownership_verified`, `financial_access_enabled`), kod gerektirmez. Kanıt: yeni test hesabıyla baştan sona uygulanmış.
    - **7.3** Süre: 7 gün, elle kapatma. Kanıt: bayrak `false` → `/tenant/finance/audit` 403 (daha önce ölçüldü, tekrar ölçülür); `true` → 200.
    - **7.4** Bağlantıyı kesme/veri silme yolu: müşteri için QBO/Shopify tarafında kaldırma talimatı; bizde bağlantı satırı silme prosedürü. Token iptal çağrısı AGENTS §6 "POST yalnız token uç noktası" kuralına aykırı: **BLOKE** (ayrı onay).
    - **7.5** Gizlilik/ToS sayfası: Adım 8'e bağlı. HANDOFF "yeni doküman" yasağı gereği metin üretimi ayrıca açık onay ister.
    - **7.6** Destek e-postası ve geri bildirim yolu arayüzde görünür.
    - **7.7** Dış kapılar (kod değil): Intuit üretim anahtarları/uygulama incelemesi, Shopify dağıtım kararı (4.3), 2.5 muhasebe politikası.
  - **Açık bulgular (BLOKE):** `web/app.bundle.js` minified, kaynağı repoda yok; `index.html:92` "4-2 İzolasyon Testi" düğmesinin işlevi okunmadı; arayüz metinleri şu an Türkçe.
- [ ] 8 Hukuk ve uyumluluk
- [ ] 9 Abonelik ve ödeme
- [ ] 10 Ticari lansman

**Dış kapılar (kod ile çözülmez)**
- [!] 2.5 Muhasebe politikası + izinli örnek
- [!] 2.6-2.7 Banka/ödeme sağlayıcısı verisi
- [!] 2.8 Muhasebeci etiketli örneklem
- [!] 4.3 Shopify dağıtım kararı

**Açık sorular**
- [!] 16-11 08:29 ve 11:01 callback hatalarının kaynağı (kullanıcı teyidi)
- [ ] Eski CLI `invalid_grant`: gerekli mi? Ölç, sonra kapat
- [ ] Claude Code: auto mode kapalı mı, Fable erişimi `/model` ile kontrol
- [ ] OmniRoute: Adım 4 sonrası karar (IDEAS)

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
