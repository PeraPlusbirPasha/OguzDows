#!/bin/bash
# xvfb-run çocuğu: yalnızca X soketi paylaşılır; host ev / runtime / D-Bus yok.
set -euo pipefail
# xvfb-run /bin/sh üzerinden geçer; export -f on_chroot korunmaz.
# Kopya bir chroot uygulaması değil, hash'i denetlenen resmî işlev yeniden alınır.
# shellcheck source=/dev/null
source "${BASE_DIR}/scripts/common"
[[ "$DISPLAY" =~ ^:[0-9]+(\.[0-9]+)?$ ]]
[[ "$OGUZDOWS_PI_CI_DIR" =~ ^/run/oguzdows-ci\.[a-zA-Z0-9]+$ ]]
install -d -m 1777 "${ROOTFS_DIR}/tmp/.X11-unix"
mount --bind /tmp/.X11-unix "${ROOTFS_DIR}/tmp/.X11-unix"
# Temizlik / unmount, 02-run.sh EXIT kapanışındadır; hata kodu gizlenmez.
# Resmî işlev mount | grep -q kullanır; pipefail onu SIGPIPE ile yanıltmasın.
(
set +o pipefail
on_chroot <<EOF
exec /usr/bin/env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin LANG=C.UTF-8 \\
    HOME="$OGUZDOWS_PI_CI_DIR/home" USER=root LOGNAME=root \\
    DISPLAY="$DISPLAY" XAUTHORITY="$OGUZDOWS_PI_CI_DIR/Xauthority" \\
    XDG_RUNTIME_DIR="$OGUZDOWS_PI_CI_DIR" XDG_CONFIG_HOME="$OGUZDOWS_PI_CI_DIR/config" \\
    XDG_CACHE_HOME="$OGUZDOWS_PI_CI_DIR/cache" XDG_DATA_HOME="$OGUZDOWS_PI_CI_DIR/data" \\
    XDG_STATE_HOME="$OGUZDOWS_PI_CI_DIR/state" GSETTINGS_BACKEND=memory NO_AT_BRIDGE=1 \\
    QEMU_CPU="$OGUZDOWS_PI_CI_CPU" \\
    /usr/bin/dbus-run-session -- /tmp/oguzdows-qemu-static -cpu "$OGUZDOWS_PI_CI_CPU" \\
    /usr/bin/python3 "$OGUZDOWS_PI_CI_DIR/smoke.py" --arch "$ARCH" --cpu "$OGUZDOWS_PI_CI_CPU" \\
    --output "$OGUZDOWS_PI_CI_DIR/report.json"
EOF
)
