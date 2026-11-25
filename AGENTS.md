# VERICON: Ajan Kuralları (değişmez)

Bu dosya yalnızca değişmeyen kuralları taşır. Durum bilgisi `HANDOFF.md`, plan `PLAN.md` içindedir. Buraya durum notu yazılmaz.

## 1. Amaç
ABD Shopify + QuickBooks Online işletmeleri için bağımsız, kanıtlı, **salt-okunur** muhasebe uyuşmazlık denetimi. ERP, stok yöneticisi veya otomatik muhasebe kaydı üreten bir sisteme dönüşmeyecek.

## 2. Oturum başlangıcı (sırayla, başka dosya okunmaz)
1. `AGENTS.md`
2. `HANDOFF.md`
3. `PLAN.md` içinde yalnızca HANDOFF'taki aşama
4. `git status` ve `git log -1`
5. İlgili kod

`docs/history.md` ve eski `TODO.md` okunmaz. Kullanıcı açıkça isterse okunur.

## 3. Tek görev kuralı
- Oturumda tek görev. Görev ve kabul ölçütü `HANDOFF.md` içinde yazılıdır.
- Kabul ölçütü dışındaki dosyaya, araca, teste, belgeye dokunulmaz.
- Görev bitince dur, `HANDOFF.md` güncelle, kullanıcıya raporla. Sonraki göreve kullanıcı onayı olmadan geçilmez.

## 4. Dur ve sor
Şu durumlarda işlem yapmadan önce kullanıcıya sorulur:
- Kapsam dışı dosya, yeni araç, yeni kütüphane, yeni test türü, refactor, yeni servis, branch veya doküman gerekiyorsa
- Kanıt yoksa veya bir şey belirsizse (tahmin yürütülmez)
- Yetki, scope, OAuth, canlı servis, Supabase politikası veya finansal veri değişecekse
- Kullanıcıdan ekran görüntüsü veya elle işlem istenecekse. Önce neden gerektiği ve ajanın kendi başına yapamadığı yazılır.

## 5. Rapor dili
Her madde şu üç etiketten biriyle raporlanır:
- **BİTTİ:** Hangi kanıtla doğrulandı (komut, çıktı, SHA).
- **BİTMEDİ:** Ne kaldı, sıradaki tek iş.
- **BLOKE:** Kimden ne lazım. Tek satır.

"Ama, fakat, ancak, garanti değil" ile yumuşatılmış yarım sonuç yazılmaz. Bilinmeyen bir şey BLOKE olarak yazılır. Rapor kısa tutulur, test sayısı övünme konusu yapılmaz.

## 6. Salt-okunur ve dış sistem kuralları
- Dış sistemde ürün, stok, fatura, sipariş oluşturma/güncelleme/silme KAPALI.
- QBO: yalnızca GET `/query`. POST yalnızca Intuit OAuth token endpoint'ine.
- Shopify: yalnızca OAuth token ve `query` GraphQL. `mutation` yok.
- Gerçek müşteri verisi, yeni API yetkisi, scope artırımı, canlı servis değişikliği için ayrı onay gerekir.
- Parasal kurallar deterministiktir (vergi, indirim, iade, para birimi, yuvarlama). AI çıktısı tek başına finansal gerçek sayılmaz. Bilinmeyen = incele (REVIEW/BLOCK).
- Shopify `inventory_quantity` ile QBO `QtyOnHand` körlemesine karşılaştırılmaz.

## 6b. Onaylı karar (2026-11-16, kullanıcı)
A/B kendi Sandbox hesapları için, yalnızca okuma yetkisiyle `financial_access_enabled` açılabilir. Sınırlar: yalnız A ve B, yalnız GET/query, scope artmaz, başka tenant yok. Geri alma: bayrağı tekrar `false` yap. Bu onay yalnızca `PLAN.md` Adım 2 ölçümü sonrasında, Adım 3'te kullanılır.

## 6c. Onaylı karar (2026-11-25, kullanıcı)
7.2 kabulü için tek bir test tenant'ı "C" oluşturulabilir ve yalnız kullanıcının kendi oluşturduğu test hesaplarıyla (kendi Supabase kullanıcısı, kendi Shopify geliştirme/test mağazası, kendi QBO Sandbox şirketi) `financial_access_enabled` açılabilir. Sınırlar: yalnız C, yalnız GET/query, scope artmaz, gerçek müşteri verisi yok, başka tenant yok. C'nin kullanıcı kimliği, mağaza alan adı ve realm'i C oluşturulunca HANDOFF'a yazılır; bu maddede yazılı olmayan hiçbir hesap için bayrak açılmaz. Shopify tenant kimliği (client_id/secret) sohbete ve Git'e girmez; kullanıcı kendi eliyle sunucuya koyar. Geri alma: C satırında bayrağı `false` yap. Bu onay yalnız PLAN 7.2 kabul denemesinde kullanılır.

## 7. Gizli bilgi
Token, client secret, `.env`, JWT, gerçek müşteri kaydı, fatura ve tam log Git'e, sohbete veya devir notuna girmez. Sızıntı kanıtı olmadan rotasyon yapılmaz. Eski token arşivi otomatik geri yüklenmez.

## 8. Koruma listesi (dokunma)
- `private/` ve OAuth yetki-kurtarma kodu
- Çalışan A/B tenant bağlantıları (revoke etme, silme)
- SMRS ve Senal Plastik servisleri, diğer VPS uygulamaları
- Eski portlar 8782–8786 (kullanılmadığı kanıtlanmadan silme/durdurma yok)
- `/var/www/vericon-app` ve Nginx dosyaları Git dışındaysa drift ayrıca belirtilir

## 9. Yasaklı tekrarlar
- Geçersiz refresh token tekrar denenmez. Eski CLI `invalid_grant` kurtarması için OAuth URL tekrar tekrar üretilmez.
- Başka tenant token'ı legacy dosyaya kopyalanmaz.
- Tarihsel OTP/logout/revoke/izolasyon kabulleri yeniden istenmez.
- OAuth code/state/query loglanmaz.

## 10. Değişiklik disiplini
Ölç → kanıtlı kök neden → tek nedensel değişiklik → diff → test → gerçek davranış → commit → push. Test geçmesi tek başına ürün kabulü değildir; kabul ölçütü gerçek davranıştır.
- Yeni test yalnızca kanıtlı bir hatayı yakalamak için yazılır.
- GitHub ve VPS aynı SHA olmadan iş bitti denmez.
- Her adımda README güncellenmez. Yalnızca davranış değiştiyse güncellenir.

## 11. Fikir kutusu
Kullanıcı "fikir: ..." yazarsa tek satır `IDEAS.md` dosyasına eklenir (tarih, fikir, ilgili aşama). Başka hiçbir şey yapılmaz, iş başlatılmaz. Oturum başında yalnızca mevcut aşamaya ait fikirler listelenir. Aşama kapanışında kalan fikirler için kullanıcıya sorulur: yap, ertele, çöpe at.

## 12. Oturum sonu
`HANDOFF.md` güncellenir: tek açık iş, son SHA, BİTTİ/BLOKE değişiklikleri. Yarım sayfayı geçmez. Eski içerik `docs/history.md` içine taşınır.

## 13. Model rolleri ve maliyet
- Tek dosya yazarı: Claude Code ana ajanı (Sonnet; plan modunda Opus, `opusplan`). Paralel yazar yok. Haiku yalnızca kısa okuma/listeleme.
- Baş denetçi: Fable, salt-okunur (`denetci` ajanı), yalnızca aşama kapanışında. API kredisinden (yaklaşık 3-4 USD), abonelikle karıştırılmaz.
- ChatGPT Pro: salt-okunur ikinci göz. Girdi: `/paket` çıktısı (diff + kabul ölçütü). Repo'ya, VPS'e, token'a erişmez.
- Gemini Pro: araştırma (Shopify/QBO dokümanı, vergi/iade kuralı, uzun metin özeti). Kod yazmaz, karar vermez.
- Dış modellerin çıktısı kanıt değildir. Bulgu, Claude Code komut çıktısıyla doğrulanınca BİTTİ olur. Çelişkide kanıt karar verir, kullanıcı onaylar.
- Dış modele `.env`, `private/`, token, gerçek müşteri verisi verilmez.
- ChatGPT/Gemini paketleri 1 aylıktır (2026-11 sonu). Sonunda bu satırlar gözden geçirilir.
- Onaysız yeni ücretli servis, yeni CLI, yeni yönlendirici açılmaz.
- Token ve maliyet ölçülmediyse "tahmin" diye etiketlenir.
