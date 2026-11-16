---
description: Oturumu aç, tek açık işi özetle (iş başlatmaz)
---
AGENTS.md ve HANDOFF.md zaten yüklü. Şunları yap, başka hiçbir şey yapma:
1. `git status --porcelain`, `git log -1 --oneline`, `git fetch` sonrası local ile origin/main SHA'sını karşılaştır.
2. HANDOFF'taki "tek açık iş" için PLAN.md'de yalnızca ilgili aşamayı oku.
3. IDEAS.md'den yalnızca bu aşamaya ait açık fikirleri al.
4. Beş satırı geçmeyen özet ver: tek açık iş, kabul ölçütü, BLOKE olanlar, ilgili fikirler, git durumu (temiz mi, local=origin mi).
5. "Başlayayım mı?" diye sor ve bekle. Onay gelmeden dosya değiştirme, komut çalıştırma, servise dokunma.
