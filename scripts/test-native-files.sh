#!/bin/sh
# Build-time real I/O regression tests; no GTK display or user's files.
set -eu
base=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
output=$(mktemp -d "${TMPDIR:-/tmp}/oguzdows-native-files-bin-XXXXXX")
trap 'rm -f "$output/test"; rmdir "$output"' EXIT HUP INT TERM
# shellcheck disable=SC2046
cc -std=c11 -O2 -Wall -Wextra -Werror -fstack-protector-strong -D_FORTIFY_SOURCE=2 \
    -fPIE -pie -Wl,-z,relro,-z,now -I"$base/native" \
    $(pkg-config --cflags gtk+-3.0 json-glib-1.0 x11) \
    "$base/tests/native-files.c" "$base/native/ui.c" -o "$output/test" \
    $(pkg-config --libs gtk+-3.0 json-glib-1.0 x11) -lm
"$output/test"
