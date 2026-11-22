#!/bin/bash
# Host Xvfb + hedef ARM kullanıcı alanı. Fiziksel Pi boot/GPU/RAM testi değil.
set -euo pipefail
export CAPSH_ARG="${CAPSH_ARG:-}"
if [ "${ARCH}" = armhf ]; then
    emulator=/usr/bin/qemu-arm-static
    cpu=arm1176
elif [ "${ARCH}" = arm64 ]; then
    emulator=/usr/bin/qemu-aarch64-static
    cpu=cortex-a53
else
    echo 'Tanınmayan Pi mimarisi.' >&2
    exit 2
fi
for tool in "$emulator" xvfb-run xauth; do
    command -v "$tool" >/dev/null || { echo "Pi hedef GTK kontrolü için $tool gerekli." >&2; exit 1; }
done
socket="${ROOTFS_DIR}/tmp/.X11-unix"
if mountpoint -q "$socket"; then
    echo 'Pi test ekranı yolu önceden bağlı; üzerine bağlanmadı.' >&2
    exit 1
fi
runtime=''
cleanup() {
    local status=$?
    trap - EXIT
    if mountpoint -q "$socket"; then
        umount "$socket" || { [ "$status" -ne 0 ] || status=1; }
    fi
    if [ -n "$runtime" ]; then
        if [ -f "$runtime/report.json" ]; then
            install -m 0644 "$runtime/report.json" "${BASE_DIR}/../pi-runtime-report.json" || { [ "$status" -ne 0 ] || status=1; }
        fi
        # Yalnızca bu teste ait mktemp dizini; rootfs /run dizini silinmez.
        rm -rf -- "$runtime" || { [ "$status" -ne 0 ] || status=1; }
    fi
    rm -f "${ROOTFS_DIR}/tmp/oguzdows-qemu-static" || { [ "$status" -ne 0 ] || status=1; }
    exit "$status"
}
trap cleanup EXIT
# Resmî on_chroot /run ve /tmp'yi tmpfs bağlar. Dosyaları bundan SONRA koy.
# İşlev mount | grep -q kullandığından kendi upstream pipefail davranışı korunur.
(
set +o pipefail
on_chroot <<'EOF'
true
EOF
)
runtime=$(mktemp -d "${ROOTFS_DIR}/run/oguzdows-ci.XXXXXXXX")
install -d -m 0700 "$runtime/home" "$runtime/config" "$runtime/cache" "$runtime/data" "$runtime/state"
install -m 0755 "$emulator" "${ROOTFS_DIR}/tmp/oguzdows-qemu-static"
install -m 0644 files/pi-runtime-smoke.py "$runtime/smoke.py"
install -m 0644 files/pi_contract.py "$runtime/pi_contract.py"
install -m 0644 files/pi_session_smoke.py "$runtime/pi_session_smoke.py"
export OGUZDOWS_PI_CI_DIR="${runtime#"${ROOTFS_DIR}"}"
export OGUZDOWS_PI_CI_CPU="$cpu"
# X sunucusu hostta; hedef imaja Xvfb / xauth paketi veya daemon eklenmez.
xvfb-run --auto-servernum --auth-file="$runtime/Xauthority" \
    --server-args='-screen 0 1024x768x24 -nolisten tcp' bash files/pi-gui-chroot.sh
install -m 0644 "$runtime/report.json" "${ROOTFS_DIR}/usr/share/oguzdows/pi-build-report.json"
