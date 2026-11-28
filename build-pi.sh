#!/bin/bash
# Raspberry Pi SD/USB imajı; PC ISO akışını değiştirmez.
set -euo pipefail
usage() {
    cat <<'EOF'
Kullanım: ./build-pi.sh armhf|arm64 [--configure-only]
  armhf  ARMv6 uyumlu kullanıcı alanı: Zero / 1 / 2 / 3 / 4 (Pi 5 değil)
  arm64  Zero 2 W / Pi 2 rev1.2 / 3 / 4 / 5
  --configure-only  Root, ağ ve derleme araçları olmadan dosyaları hazırla.
Gerçek derleme root + Linux, loop/mount ve QEMU gerektirir.
armhf derleme hostu 4 KiB sayfalı olmalı; arm64 bu koşulla kısıtlanmaz.
EOF
}
if [ "$#" -eq 1 ] && [[ "$1" == --help || "$1" == -h ]]; then usage; exit 0; fi
if [ "$#" -lt 1 ] || [ "$#" -gt 2 ] || [[ ! "$1" =~ ^(armhf|arm64)$ ]]; then usage >&2; exit 2; fi
ARCH=$1
CONFIGURE_ONLY=false
if [ "$#" -eq 2 ]; then
    [ "$2" = --configure-only ] || { usage >&2; exit 2; }
    CONFIGURE_ONLY=true
fi
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
WORK="$ROOT/build-rpi-$ARCH"
if [ -e "$WORK" ]; then
    echo "$WORK zaten var; önceki derleme otomatik silinmez. raspberrypi/README.md dosyasına bakın." >&2
    exit 1
fi
if ! "$CONFIGURE_ONLY"; then
    [ "$(id -u)" -eq 0 ] || { echo 'Gerçek Pi derlemesi için sudo gerekli.' >&2; exit 1; }
    for command in python3 curl tar sha256sum debootstrap arch-test losetup sfdisk mount udevadm xz xvfb-run xauth; do
        command -v "$command" >/dev/null || { echo "Derleme aracı eksik: $command" >&2; exit 1; }
    done
    if [ "$ARCH" = armhf ] && [ "$(getconf PAGESIZE)" != 4096 ]; then
        echo 'ARMv6/armhf derlemesi 4 KiB sayfalı host kernel gerektirir (Pi 5 16 KiB host uygun değil).' >&2
        exit 1
    fi
    arch-test "$ARCH" || { echo 'ARM çalıştırma desteği yok; QEMU/binfmt kaydını kontrol edin.' >&2; exit 1; }
    FREE_KIB=$(df -Pk "$ROOT" | awk 'END { print $4 }')
    [ "$FREE_KIB" -ge 20971520 ] || { echo 'En az 20 GiB boş çalışma alanı gerekli; 30 GiB önerilir.' >&2; exit 1; }
fi
python3 "$ROOT/scripts/configure-pi.py" --arch "$ARCH" --output "$WORK/configuration"
if "$CONFIGURE_ONLY"; then usage; exit 0; fi
(
    readarray -t SOURCE < <(python3 - "$ROOT/raspberrypi/pi-gen.lock.json" "$ARCH" <<'PY'
import json, sys
with open(sys.argv[1]) as stream:
    source = json.load(stream)[sys.argv[2]]
print(source['commit'])
print(source['archive_sha256'])
PY
    )
    ARCHIVE="$WORK/pi-gen-source.tar.gz"
    curl --fail --location --retry 3 --proto '=https' --tlsv1.2 \
        "https://codeload.github.com/RPi-Distro/pi-gen/tar.gz/${SOURCE[0]}" -o "$ARCHIVE"
    printf '%s  %s\n' "${SOURCE[1]}" "$ARCHIVE" | sha256sum --check --strict
    mkdir "$WORK/pi-gen"
    tar -xzf "$ARCHIVE" --strip-components=1 --no-same-owner -C "$WORK/pi-gen"
    # Güncel sürüme portta boot / kernel / kaynak mimarisi sessizce değişmesin.
    python3 "$ROOT/scripts/audit-pi-upstream.py" --arch "$ARCH" --source "$WORK/pi-gen" \
        --output "$WORK/pi-upstream-audit.json"
    # Denetlenen upstream farkı ayrı before/after SHA-256 raporuna kaydedilir.
    python3 "$ROOT/scripts/prepare-pi-apt.py" --arch "$ARCH" --source "$WORK/pi-gen" \
        --output "$WORK/pi-apt-adaptation.json"
    cp -a "$WORK/configuration/stage-oguzdows" "$WORK/pi-gen/"
    cp "$WORK/configuration/config" "$WORK/pi-gen/config"
    # Yalnızca OğuzDows masaüstü son aşaması dışa aktarılır; boş Lite imajı yok.
    touch "$WORK/pi-gen/stage2/SKIP_IMAGES"
    # Ortak NOPASSWD wizard yerine kilitli, Türkçe yerel hesap kurulumu.
    touch "$WORK/pi-gen/export-image/01-user-rename/SKIP"
    install -m 0755 "$WORK/configuration/export-check.sh" \
        "$WORK/pi-gen/export-image/04-set-partuuid/50-run.sh"
    cd "$WORK/pi-gen"
    ./build.sh
    RAW="$WORK/pi-gen/work/OguzDows-rpi-$ARCH/export-image/OguzDows-rpi-$ARCH.img"
    bash "$ROOT/scripts/verify-pi-image.sh" "$RAW" "$ARCH"
    DEPLOY="$WORK/pi-gen/deploy"
    cd "$DEPLOY"
    sha256sum "OguzDows-rpi-$ARCH.img.xz" > "OguzDows-rpi-$ARCH.img.xz.sha256"
    cp "$ROOT/raspberrypi/pi-gen.lock.json" "$DEPLOY/pi-gen.lock.json"
    # Büyük dosyalar yalnızca ignore edilen çalışma/çıktı konumlarında kalır.
    cp "OguzDows-rpi-$ARCH.img.xz" "OguzDows-rpi-$ARCH.img.xz.sha256" "$ROOT/"
    cp "OguzDows-rpi-$ARCH.info" "$ROOT/OguzDows-rpi-$ARCH.packages.txt"
    echo "OğuzDows Pi $ARCH imajı oluşturuldu; fiziksel kart testi henüz yapılmadı."
) 2>&1 | tee "$WORK/build.log"
