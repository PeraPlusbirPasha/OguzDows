#!/bin/sh
# Hedef mimaride, yalnızca imaj / geliştirme aşamasında C / GTK3 derlemesi.
set -eu
if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo 'Kullanım: build-news.sh ÇIKTI [--test]' >&2
    exit 2
fi
base=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
output=$1
mkdir -p "$(dirname -- "$output")"
if [ "${2:-}" = --test ]; then
    set -- -DOGUZDOWS_NEWS_TEST "-DNEWS_SERVICE=\"$base/tests/news-service-fixture.py\""
elif [ "$#" -eq 1 ]; then
    set --
else
    echo 'Bilinmeyen derleme seçeneği.' >&2
    exit 2
fi
# Ortak tabanın derleyici / ABI varsayılanları: -march=native veya NEON yok.
# shellcheck disable=SC2046
cc -std=c11 -O2 -Wall -Wextra -Werror -fstack-protector-strong -D_FORTIFY_SOURCE=2 \
    -fPIE -pie -Wl,-z,relro,-z,now "$@" \
    $(pkg-config --cflags gtk+-3.0 json-glib-1.0) \
    "$base/native/news.c" -o "$output" \
    $(pkg-config --libs gtk+-3.0 json-glib-1.0)
