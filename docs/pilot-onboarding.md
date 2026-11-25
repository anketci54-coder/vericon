# Pilot müşteri açma (operatör için, tek sayfa)

## Önkoşullar
- BLOKE: Gerçek müşteri QBO'su için Intuit üretim anahtarları gerekir (sandbox şirketini müşteri yetkilendiremez). PLAN 7.7.
- BLOKE: Müşterinin Shopify okuma kimliği (client_id/secret) sunucuya nasıl alınır? Sohbete ve Git'e girmez (AGENTS §7). Yöntem kararı 4.3'e bağlı.
- ONAY: AGENTS §6b yalnız A ve B içindir. Yeni tenant için bayrak açmak yeni kullanıcı onayı ister.

## Adımlar
1. Supabase Auth'ta müşterinin e-postasıyla kullanıcı oluştur. Giriş kod iledir ve `shouldCreateUser:false` olduğundan kullanıcı yoksa kod gitmez.
2. Müşteriden iste: Shopify alan adı (`x.myshopify.com`) ve QuickBooks şirket numarası (realm, rakam). Gizli bilgi isteme.
3. `vericon_pilot_connections` satırı: user_id, shop_domain, qbo_realm_id, connection_status=`pilot_linked`, ownership_verified=`false`, financial_access_enabled=`false`.
4. Sunucuda `private/shopify_tenants/<user_id>_<store>.json` (mod 0600) oluştur. Yöntem BLOKE (yukarıda).
5. Müşteri girer, "Generate Shopify ownership code" ile kodu alır, 10 dakika içinde mağazasında `vericon.owner_proof` metafield'ına yazar ve "Verify Shopify code" der.
6. Yanıt "verified" ise `ownership_verified=true` yap. Backend Supabase'e yazmaz, elle yapılır.
7. Müşteri QuickBooks'u yetkilendirir (QBO düğmesi bayrak `false` iken görünür).
8. Aç: `financial_access_enabled=true`. 7 günlük süre başlar, başlangıç tarihini not et.
9. Doğrula: "Run financial audit" 200 döner, tablo İngilizce.

## Kapatma (7. gün veya sorun çıkarsa)
`financial_access_enabled=false`. Servis yeniden başlatma gerekmez. `/tenant/finance/audit` 403 vermeli.

## Açık / doğrulanmadı
- 7.2 kabulü ("yeni test hesabıyla baştan sona uygulanmış") henüz yapılmadı. Adım 4 ve 7 yeni bir tenant için canlıda denenmedi.
- Müşteri bağlantıyı kendi kesemez (Disconnect düğmesi gizli, Intuit'te token iptal eder). Bağlantı kesme yolu PLAN 7.4.

## Müşteriye gidecek (İngilizce, kopyala-gönder)
1. Sign in at app.vericon.site with the code we email you.
2. Click "Generate Shopify ownership code". Paste it into your Shopify store metafield `vericon.owner_proof` within 10 minutes, then click "Verify Shopify code".
3. Authorize QuickBooks when asked. VERICON only reads your data.
4. We will confirm when audit access is open. It runs for 7 days.
