#!/bin/sh
# Tek seferlik oturum kararı; ağ, root ve devamlı arka plan işçisi yoktur.
set -eu
sleep 1
if [ "${OGUZDOWS_SESSION_PREPARED:-0}" != 1 ] && ! python3 /usr/lib/oguzdows/profiles.py --session; then
    echo "OğuzDows kaynak görünümü uygulanamadı; varsayılan opak görünüm korunur." >&2
fi
# Eksik stok PrintScreen bağları tamamlanır; kişisel ekran aracı korunur.
if ! /usr/bin/python3 -I /usr/lib/oguzdows/desktop_shortcuts.py --session; then
    echo "OğuzDows PrintScreen kısayolları tamamlanamadı; klavye ayarları korundu." >&2
fi
# Yalnızca ilk girişte uygula; sonraki girişler duvar kâğıdı seçimini korur.
python3 /usr/lib/oguzdows/wallpapers.py --initialize
# Tek sıralı uzlaştırıcı: profil / galeri ile iki autostart yarışıp cam
# temasını veya kompozitör seçimini karşılıklı geri ezmez.
if ! /usr/bin/python3 -I /usr/lib/oguzdows/desktop_center.py --effects-session; then
    echo "OğuzDows ortak tercihleri uzlaştırılamadı; masaüstü oturumu korunuyor." >&2
fi
/usr/bin/python3 -I /usr/lib/oguzdows/accent.py --session
exit 0
