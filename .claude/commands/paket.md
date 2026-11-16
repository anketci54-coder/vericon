---
description: ChatGPT/Gemini için salt-okunur inceleme paketi üretir (dosya yazmaz, yalnızca metin basar)
argument-hint: <dal veya SHA aralığı, örn. main..3b-orders>
---
Yalnızca okuma yap. Çıktıyı tek blok metin olarak bas, dosya yazma, commit atma.
1. HANDOFF.md'den "Şu an tek açık iş" ve Kabul satırını aynen al.
2. `git diff --stat $ARGUMENTS`, sonra `git diff $ARGUMENTS` (en çok 600 satır; fazlaysa yalnız stat + dosya listesi ver ve söyle).
3. `.env`, `private/`, token, secret, gerçek müşteri verisi içeren satır varsa o satırı `[GİZLENDİ]` yaz.
4. Sonuna sabit istek ekle: "Bu diff kabul ölçütünü karşılıyor mu? Tenant izolasyonu, yazma/mutation, PII, sahte test riski var mı? Her bulguya dosya:satır ver. Kanıtsız iddia yazma."
Başka söz yok.
