#!/bin/sh
# Yerel hedef ABI'sinde C11/GTK; evrensel x86 ikili dosyasını ARM'e taşıma.
set -eu
if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo 'Kullanım: build-desktop.sh monitor|hub ÇIKTI [--test]' >&2
    exit 2
fi
base=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
target=$1
output=$2
case "$target" in
    monitor) source=monitor.c; extra="$base/native/metrics.c"; test=OGUZDOWS_MONITOR_TEST ;;
    hub) source=hub.c; extra=; test=OGUZDOWS_HUB_TEST ;;
    *) echo 'İzin verilmeyen yerel masaüstü hedefi.' >&2; exit 2 ;;
esac
if [ "${3:-}" = --test ]; then
    set -- "-D$test" "-DOGUZDOWS_UI_CSS=\"$base/system/usr/share/oguzdows/ui/modern.css\""
elif [ "$#" -eq 2 ]; then
    set --
else
    echo 'Bilinmeyen derleme seçeneği.' >&2
    exit 2
fi
mkdir -p "$(dirname -- "$output")"
# Hedef derleyicinin varsayılanları; ARMv6'da NEON / -march=native yok.
# shellcheck disable=SC2046,SC2086
cc -std=c11 -O2 -Wall -Wextra -Werror -fstack-protector-strong -D_FORTIFY_SOURCE=2 \
    -fPIE -pie -Wl,-z,relro,-z,now "$@" \
    $(pkg-config --cflags gtk+-3.0 json-glib-1.0 gio-unix-2.0) \
    "$base/native/$source" "$base/native/ui.c" $extra -o "$output" \
    $(pkg-config --libs gtk+-3.0 json-glib-1.0 gio-unix-2.0) -lm
