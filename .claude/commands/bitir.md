---
description: Oturumu kapat, HANDOFF güncelle, commit ve push et, SHA raporla
---
1. HANDOFF.md'yi güncelle: yapılan iş BİTTİ'ye (kanıtla), kalanlar BİTMEDİ/BLOKE'ye, tek açık iş, son durum. 40 satırı geçirme; eski ayrıntıyı docs/history.md sonuna taşı.
2. Çalışma ağacında HANDOFF/IDEAS/docs dışında kodla ilgisiz değişiklik varsa DUR ve göster.
3. Commit at (kısa, ne yapıldığını söyleyen mesaj).
4. Push: yalnızca mevcut dala. `main` üzerindeysen yalnızca HANDOFF.md, IDEAS.md ve docs değişikliği push edilir; kod değişikliği main'e gidiyorsa onay iste.
5. `git ls-remote` ile local ve origin SHA'sını raporla. BİTTİ/BİTMEDİ/BLOKE biçiminde, en çok 8 satır.
