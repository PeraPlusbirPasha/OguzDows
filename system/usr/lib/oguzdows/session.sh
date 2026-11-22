#!/bin/sh
# Tek seferlik oturum kararı; ağ, root ve devamlı arka plan işçisi yoktur.
set -eu
sleep 1
if [ "${OGUZDOWS_SESSION_PREPARED:-0}" != 1 ] && ! python3 /usr/lib/oguzdows/profiles.py --session; then
    echo "OğuzDows kaynak görünümü uygulanamadı; varsayılan opak görünüm korunur." >&2
fi
# Yalnızca ilk girişte uygula; sonraki girişler duvar kâğıdı seçimini korur.
python3 /usr/lib/oguzdows/wallpapers.py --initialize
exit 0
