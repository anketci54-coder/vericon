# VERICON

Kurallar ve durum, her oturumda otomatik yüklenir. Başka bir şey okuma, tahmin yürütme.

@AGENTS.md
@HANDOFF.md

Plan: `PLAN.md` (yalnızca HANDOFF'taki aşama). Fikir kutusu: `IDEAS.md`. Eski kayıtlar: `docs/history.md` (okunmaz).

## Komutlar
- `/basla` oturumu aç, tek açık işi özetle (iş başlatmaz)
- `/dagit <sha>` dağıtım rutini (yedek, nginx testi, sıralı yeniden başlatma, kanıt)
- `/bitir` HANDOFF güncelle, commit, push, SHA raporla
- `/fikir <metin>` IDEAS.md'ye tek satır ekle, başka bir şey yapma

## Değişmez
- Oturumda tek görev. Kapsam dışı iş, yeni araç/dosya/test: önce sor.
- Rapor dili: BİTTİ / BİTMEDİ / BLOKE. "Ama, fakat, garanti değil" yok.
- Servis yeniden başlatma, Nginx reload, Supabase/bayrak değişikliği, `main`'e push, scope artışı: kullanıcı onayı olmadan yapılmaz.
- Cevaplar kısa. Tekrar, özür, süreç anlatımı yok.
