---
description: Dağıtım rutini (Nginx + sıralı servis yeniden başlatma + kanıt). Argüman: beklenen commit SHA öneki
argument-hint: <sha>
---
Beklenen commit: $ARGUMENTS. Her sert durak "DUR" ise işlemi bırak, çıktıyı göster, kullanıcıya sor.

**1. Ön kontrol**
- `git pull`, `git log -1 --oneline`. SHA $ARGUMENTS ile başlamıyorsa DUR.
- `git status --porcelain` temiz değilse DUR.
- Dağıtılacak değişikliği özetle: `git diff --stat <önceki dağıtılan>..HEAD` (HANDOFF'taki son dağıtım SHA'sı). Kullanıcıdan "devam" onayı al.

**2. Nginx** (yalnızca deploy/vericon-app.nginx.conf değiştiyse)
- Canlı dosya (`/etc/nginx/sites-enabled/vericon-app.conf`) ile repo dosyasının diff'ini göster. Beklenmeyen fark varsa DUR.
- Yedek: `/root/backup-nginx/vericon-app.conf.<tarih-saat>`. Kopyala, `nginx -t`. Hata varsa yedeği geri koy, DUR.
- Temizse `systemctl reload nginx`, dış `/health` 200 doğrula.
- `web/` dosyaları değiştiyse `/var/www/vericon-app` ile `cmp` karşılaştır ve farkı raporla (kopyalamadan önce sor).

**3. Servisler** (kod değiştiyse; kullanıcıdan ayrıca "yeniden başlat" onayı al, geri alma planını söyle)
- `vericon-api@8787`, `@8788`, `@8789`: SIRAYLA. Her birinden sonra 3 sn bekle, `systemctl is-active`, `curl http://127.0.0.1:<port>/health` = 200. Biri başarısızsa DUR, `journalctl -u <birim> -n 30 --no-pager` göster. Önceki sürüme dönüş yalnızca kullanıcı onayıyla.
- `journalctl` sorgularını birim başına ve zaman sınırlı çalıştır (`--since`, `--no-pager`).

**4. Kanıt**
- Yeni eklenen yol varsa oturumsuz `curl -s -o /dev/null -w "%{http_code}"` ile 401 bekle (önce 403 idi).
- `ss -ltnp`: yalnızca 127.0.0.1:8787-8789 dinliyor, 8782-8786 dinlemiyor.
- Dış `/health` 200.

**5. Kayıt**
- HANDOFF'a tek satır: dağıtım, SHA, saat (sunucunun kendi saati: `date +"%F %T %z"`, TZ değişkeni verilmeden), kanıt, yedek dosya yolu. Eski "canlı eski kod" notunu kaldır. Commit, push (yalnızca HANDOFF), SHA raporla.

Yapma: Supabase'e dokunma, bayrak açma/kapama, dış API çağrısı, kod değişikliği, başka servisler (SMRS, Senal Plastik). Çıktı BİTTİ/BİTMEDİ/BLOKE, en çok 10 satır.
