# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-18
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**ADIM 5B (arayüz) TASLAK, onay bekliyor. Başlatılmadı.**
5B kapsam: yeni tek düz JS dosyası `web/finance-audit.js` (bağımlılık yok, derleme yok, `tenant-isolation-check.js` kalıbı: localStorage'daki Supabase oturumundan `Bearer`). Yalnız `GET /tenant/finance/audit?store=` çağırır; başka uç, POST, yazma yok. `index.html`'e bir düğme + sonuç alanı + bir `<script defer>` satırı. Nginx deploy kopyasına `location = /finance-audit.js` statik bloğu (dağıtımda). Gösterilen: mağaza, adaptör durumu, genel durum, kontrol edilen/doğrulanan sayısı, sipariş başına sipariş adı + durum kodu + `verified` + tutar/fark, `blocked` listesi, sabit "Banka mutabakatı doğrulanmadı" ve "Salt-okunur" ibaresi. Değerler `textContent` ile yazılır (`innerHTML` yok). Sonuç tarayıcıda saklanmaz.
5B kabul: (1) B oturumunda düğme → 8 sipariş satırı, her birinde durum kodu, VERIFIED görünmez (B pilot şeklinde değil), eksik satır yok; (2) A oturumu kendi sonucunu görür, B'yi göremez (yalnız kendi `store`'u gönderilir); (3) oturumsuz/401 → "Oturum gerekli", 403 → "Erişim yok", 503 → `Retry-After` varsa bekleme mesajı, yoksa "Denetim şu an yapılamadı"; hiçbir hata boş tablo veya "doğrulandı" göstermez; (4) yanıtta olmayan alan uydurulmaz, beyaz liste dışı alan gösterilmez; (5) ağ izinde yalnız GET `/tenant/finance/audit` (yazma 0); (6) `bank_settlement_verified` her zaman "doğrulanmadı"; (7) suit geçer, sunucu kodu değişmez; (8) dağıtım ayrı onayla (`/dagit`: dosya kopyası `/var/www/vericon-app`, Nginx yedek + test + reload).
Açık soru (onayda): `store` değeri sayfada nereden alınır (mevcut bağlantı durumu yanıtı mı, elle giriş mi).

## BİTTİ
- Adım 1–4 (ayrıntı `docs/history.md`). A=`hudys3-p0` realm `9341458613758425`, B=`vericon-tenant-b-test` realm `9341458641399133` (TRY). A ve B `financial_access_enabled=true` (AGENTS 6b; geri alma: bayrak `false`).
- **Dağıtım 5A:** `0f5155f` (`GET /tenant/finance/audit`, Nginx bloğu), 2026-11-17 17:18 EET; 8787–8789 sırayla yeniden başlatıldı. Kanıt: 3 birim active, /health 200 ×3, dış /health 200, audit oturumsuz 401. Nginx yedek: `/root/backup-nginx/vericon-app.conf.20261117-171430`.
- **Dağıtım 5B (statik):** `af1e47e` (`web/finance-audit.js`, `index.html`, Nginx `location = /finance-audit.js`), 2026-11-18 EET; servis yeniden başlatılmadı (sunucu kodu değişmedi). Kanıt: cmp ok ×2, nginx -t ok + reload, dış /health 200, /finance-audit.js 200, audit oturumsuz 401, 8787–8789 dinliyor ve active. Nginx yedek: `/root/backup-nginx/vericon-app.conf.20261118-092239`; eski index.html: `/root/backup-nginx/index.html.20261118-092239`. Kalan: 5B tarayıcı kabulü (kullanıcı).
- **Adım 5A kapandı** (kullanıcı canlı ölçümü, 2026-11-17 17:20–17:30 EET, konsol): B→B 200, 8 sipariş, hepsi `BLOCKED_ORDER_INVOICE_LINK`, `read_only: true`, `bank_settlement_verified: false`, alan listesi beyaz liste ile aynı; A→A 200; A→B 403; B→A 403; olmayan mağaza 403; oturumsuz 401.

- **Dağıtım 5B dar ekran (statik):** `4d18934` (`web/finance-audit.js`, `web/style.css`), 2026-11-18 12:21 EET; servis/Nginx dokunulmadı. Kanıt: cmp ok ×3, dış /health 200, /finance-audit.js 200, /style.css 200, audit oturumsuz 401, 8787–8789 dinliyor, 8782–8786 yok. Eski dosyalar: `/root/backup-nginx/finance-audit.js.20261118-122110`, `/root/backup-nginx/style.css.20261118-122110`. Kalan: dar ekran tarayıcı doğrulaması (kullanıcı), sonra 5B ve Adım 5 kapanışı.

## BİTMEDİ
- 5B onayı (yukarıdaki taslak + açık soru).
- IDEAS: pilot şekil sınırı (Adım 7), B test verisi yeniden kurulumu (düşük öncelik). `shopify_read.py` fail-open satırı kapandı (4-5a); IDEAS'ta işaretlemek kullanıcı kararı.

## BLOKE
- 16-11 08:29 ve 11:01 callback hatalarının kaynağı: kullanıcı teyidi.
- Eski CLI `invalid_grant` doğrulanmadı (dış çağrı gerekir).
- Dış kapılar: 2.5 muhasebe politikası, 2.6–2.7 banka/ödeme verisi, 2.8 muhasebeci örneklemi, 4.3 Shopify dağıtım kararı.

## Yapılmayacaklar
- Eski CLI OAuth kurtarma, OAuth URL üretme
- Yeni test yığını, refactor, yeni mimari, yeni doküman
- Profit ve Intelligence kodlaması

Fikir kutusu: `IDEAS.md`. Eski içerik: `docs/history.md`.
