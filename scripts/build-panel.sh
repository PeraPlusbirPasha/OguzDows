#!/bin/sh
# Native target-ABI Xfce component and event observer. No compiler at login.
set -eu
if [ "$#" -ne 1 ]; then
    echo 'Kullanım: build-panel.sh HEDEF_KÖK' >&2
    exit 2
fi
base=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
root=$1
libdir=$(pkg-config --variable=libdir libxfce4panel-2.0)
mkdir -p "$root$libdir/xfce4/panel/plugins" "$root/usr/lib/oguzdows"
# shellcheck disable=SC2046
cc -std=c11 -O2 -Wall -Wextra -Werror -Wno-deprecated-declarations \
    -fstack-protector-strong -D_FORTIFY_SOURCE=2 -fPIC -shared -Wl,-z,relro,-z,now \
    $(pkg-config --cflags libxfce4panel-2.0 libwnck-3.0 libxfconf-0 gio-unix-2.0 x11) \
    "$base/native/tasks.c" -o "$root$libdir/xfce4/panel/plugins/liboguzdows-tasks.so" \
    $(pkg-config --libs libxfce4panel-2.0 libwnck-3.0 libxfconf-0 gio-unix-2.0 x11) -lm
# shellcheck disable=SC2046
cc -std=c11 -O2 -Wall -Wextra -Werror -fstack-protector-strong -D_FORTIFY_SOURCE=2 \
    -fPIE -pie -Wl,-z,relro,-z,now \
    $(pkg-config --cflags libxfconf-0 gio-2.0 json-glib-1.0) \
    "$base/native/accent-watch.c" -o "$root/usr/lib/oguzdows/oguzdows-accent-watch" \
    $(pkg-config --libs libxfconf-0 gio-2.0 json-glib-1.0)
