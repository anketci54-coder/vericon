# HANDOFF (en fazla yarım sayfa)

Güncelleme: 2026-11-25
Son bilinen SHA: `git log -1` (bu dosyayı içeren commit)

## Şu an tek açık iş
**7.2 kabulü** (PLAN.md Adım 7): kontrol listesi yazıldı (`docs/pilot-onboarding.md`), "yeni test hesabıyla baştan sona uygulanmış" kanıtı YOK. PARK: iki engel kullanıcı kararı bekliyor (aşağıda BLOKE). Karar gelmeden başlanmaz.
- İlk pilot 7 gün, elle kapatma (`financial_access_enabled=false`); admin paneli ve ödeme kapsam dışı.

## BİTTİ
- **7.1 İngilizce arayüz** kapandı (`cffd065`, `56b3c1e`, `ad63780`, `4e0c5bd`); B canlı kabul 2026-11-24. Ayrıntı `docs/history.md`.
- **7.2-0** `eab8a1f`: `tenant-isolation-check.js` script etiketi `index.html`'den kalktı; "Disconnect QuickBooks" gizli (düğme Intuit'te refresh token iptal eder, `qbo_oauth.py:295-313`; tıklanırsa A/B bağlantısı kopar).
- **7.2-0b** `2f6f7a3`: ownership bölümü düzeltildi. `/shopify/ownership/*` yalnız pilot mağaza (`STORE`) içindir, yeni mağaza için `/tenant/shopify/ownership/*` kullanılır; artık yalnız tenant bölümü görünür. B canlı: "This store is already verified.", konsol temiz. Bundle değişikliği bağımsız doğrulandı (bayt bayt).
- **7.2-a** `c5b66a5`: `docs/pilot-onboarding.md` (30 satır, operatör adımları + müşteriye İngilizce blok).
- A=`hudys3-p0` realm `9341458613758425`, B=`vericon-tenant-b-test` realm `9341458641399133` (TRY). İkisi `financial_access_enabled=true` (AGENTS 6b; geri alma: bayrak `false`).

## BİTMEDİ
- 7.2 kabulü: yeni (C) tenant ile Adım 4 ve 7 canlıda denenmedi.
- Bayrak `false` dalı (bundle metni) canlıda ölçülmedi; 7.3'te bayrak false/true ölçümüyle.
- `tenant-isolation-check.js` dosyası ve nginx location duruyor, A/B realm ID'leri hâlâ erişilebilir (kaldırmak nginx reload onayı ister); `/favicon.ico` 404.
- Adım 6 kabul ölçütleri yazılmadı. M4 bilerek ölçülmedi.

## BLOKE
- C tenant için: AGENTS §6b'ye yeni onay (yalnız A ve B); Shopify tenant kimliğinin sunucuya alınma yöntemi (sır sohbete/Git'e girmez, 4.3).
- 7.4 token iptali ve müşteri bağlantı kesme yolu (AGENTS §6 ayrı onay); `app.bundle.js` kaynağı repoda yok.
- Gerçek müşteri QBO: Intuit üretim anahtarları (7.7). Receipt ödeme alanı beyaz listesi yok.
- Eski CLI `invalid_grant` doğrulanmadı. Dış kapılar: 2.5, 2.6–2.7, 2.8, 4.3.

## Yapılmayacaklar
- Eski CLI OAuth kurtarma, OAuth URL üretme; yeni test yığını, refactor, yeni doküman; Profit/Intelligence

Fikir kutusu: `IDEAS.md`. Eski içerik: `docs/history.md`.
