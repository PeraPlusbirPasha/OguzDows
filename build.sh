#!/usr/bin/env bash
# OğuzDows • Akıncı — canlı sistem ve kurulum ISO'su
# Kullanım: sudo ./build.sh [amd64|i386]
# Yalnızca yapılandırma üretmek için: ./build.sh [amd64|i386] --configure-only
set -euo pipefail

usage() {
  printf 'Kullanım: %s [amd64|i386] [--configure-only]\n' "$0"
}

ARCH=amd64
CONFIGURE_ONLY=false
ARCH_GIVEN=false
for arg in "$@"; do
  case "$arg" in
    amd64|i386)
      if "$ARCH_GIVEN"; then usage >&2; exit 2; fi
      ARCH="$arg"
      ARCH_GIVEN=true
      ;;
    --configure-only) CONFIGURE_ONLY=true ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WORK="$ROOT/build-$ARCH"
case "$ARCH" in
  amd64) SUITE=trixie; FLAVOUR=amd64; BOOTLOADERS=syslinux,grub-efi ;;
  i386) SUITE=bookworm; FLAVOUR=686-pae; BOOTLOADERS=syslinux ;;
esac

for tool in python3 lb; do
  command -v "$tool" >/dev/null 2>&1 || {
    printf 'Eksik araç: %s. README.md içindeki derleme hazırlığına bakın.\n' "$tool" >&2
    exit 1
  }
done
if ! "$CONFIGURE_ONLY" && [ "$(id -u)" -ne 0 ]; then
  echo 'ISO derlemek için sudo ile çalıştırın.' >&2
  exit 1
fi
# Bağlı bir chroot'u veya önceki derleme günlüklerini hiçbir zaman rm -rf ile silme.
if [ -e "$WORK" ]; then
  printf 'Çalışma dizini zaten var: %s\nÖnce README.md içindeki güvenli temizleme adımlarını uygulayın.\n' "$WORK" >&2
  exit 1
fi
mkdir -p "$WORK"
cd "$WORK"

BOOTAPPEND="$(python3 "$ROOT/scripts/configure.py" --print-boot-args)"
lb config \
  --distribution "$SUITE" \
  --architectures "$ARCH" \
  --linux-flavours "$FLAVOUR" \
  --archive-areas 'main contrib non-free non-free-firmware' \
  --bootloaders "$BOOTLOADERS" \
  --binary-images iso-hybrid \
  --debian-installer none \
  --uefi-secure-boot disable \
  --apt-recommends false \
  --firmware-chroot true \
  --firmware-binary true \
  --iso-volume OGUZDOWS \
  --iso-application OguzDows \
  --iso-publisher OguzDows \
  --memtest none \
  --bootappend-live "$BOOTAPPEND"

python3 "$ROOT/scripts/configure.py" --arch "$ARCH" --output "$WORK/config"
if "$CONFIGURE_ONLY"; then
  printf 'OğuzDows %s yapılandırması hazır: %s\nISO henüz derlenmedi.\n' "$ARCH" "$WORK"
  exit 0
fi

lb build 2>&1 | tee build.log
mapfile -d '' ISOS < <(find . -maxdepth 1 -type f -name '*.iso' -print0)
if [ "${#ISOS[@]}" -ne 1 ]; then
  echo 'Tek bir ISO bulunamadı. Çalışma dizinindeki build.log dosyasını inceleyin.' >&2
  exit 1
fi
python3 "$ROOT/scripts/verify-iso.py" "${ISOS[0]}" --arch "$ARCH"
mv -- "${ISOS[0]}" "$ROOT/OguzDows-$ARCH.iso"
(cd "$ROOT" && sha256sum "OguzDows-$ARCH.iso" > "OguzDows-$ARCH.iso.sha256")
printf 'Hazır: %s/OguzDows-%s.iso\n' "$ROOT" "$ARCH"
