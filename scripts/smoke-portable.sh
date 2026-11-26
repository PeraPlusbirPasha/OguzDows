#!/bin/bash
# Geçici GitHub runner'ında imzası doğrulanan Debian kökü. ISO / IMG üretmez.
# Kullanıcının kurulu sisteminde paket, chroot veya root işlemi yapmayı reddeder.
set -Eeuo pipefail
if [[ ${CI:-} != true || ${GITHUB_ACTIONS:-} != true || $EUID != 0 || $# != 2 ]]; then
    echo 'Yalnız tek kullanımlık GitHub CI: smoke-portable.sh i386|armhf|arm64 bookworm|trixie' >&2
    exit 2
fi
arch=$1
suite=$2
case "$arch:$suite" in
    i386:bookworm) emulator=i386; cpu=pentium3 ;;
    armhf:bookworm) emulator=arm; cpu=cortex-a7 ;;
    arm64:bookworm|arm64:trixie) emulator=aarch64; cpu=cortex-a53 ;;
    *) echo 'Doğrulanmayan mimari / taban çifti.' >&2; exit 2 ;;
esac
project=$(pwd -P)
test -d "$project/.git"
revision=$(git -c safe.directory="$project" rev-parse HEAD)
# RUNNER_TEMP is outside the repository and contains ONLY this job's rootfs.
: "${RUNNER_TEMP:?GitHub runner geçici dizini gerekli}"
root=$(mktemp -d "$RUNNER_TEMP/oguzdows-portable-$arch-XXXXXX")
cleanup() {
    result=$?
    if [[ $result != 0 && -f "$root/debootstrap/debootstrap.log" ]]; then
        tail -n 8 "$root/debootstrap/debootstrap.log" >&2
    fi
    case "$root" in
        "$RUNNER_TEMP"/oguzdows-portable-*)
            for part in proc sys dev/pts; do
                if mountpoint -q "$root/$part"; then umount "$root/$part"; fi
            done
            rm -rf --one-file-system -- "$root"
            ;;
    esac
}
trap cleanup EXIT
stage=bootstrap
failed() { printf '::error title=Portable stage::%s failed (%d): %s\n' "$stage" "$1" "$2" >&2; }
trap 'failed "$?" "$BASH_COMMAND"' ERR
# Never --no-check-gpg, trusted=yes, foreign package / CPU flags or march=native.
decret=/usr/share/keyrings/debian-archive-keyring.gpg
test -s "$decret"
decl_cmd=(debootstrap --foreign --variant=minbase --include=ca-certificates --arch="$arch" --keyring="$decret")
"${decl_cmd[@]}" "$suite" "$root" https://deb.debian.org/debian
stage=interpreter
install -m755 "/usr/bin/qemu-$emulator-static" "$root/usr/bin/"
# Ubuntu's amd64 kernel runs IA32 directly; qemu-i386 is deliberately NOT a
# globally registered binfmt on all runners. Explicitly emulate the actual
# Python / native ABI probes instead of requiring a nonexistent registration.
probe=()
if [[ $arch == i386 ]]; then probe=(/usr/bin/qemu-i386-static)
else update-binfmts --enable "qemu-$emulator"
fi
export QEMU_CPU="$cpu"
stage=second-stage
chroot "$root" /bin/sh /debootstrap/debootstrap --second-stage
# Do not let package postinst start daemons in this private user-QEMU root.
printf '#!/bin/sh\nexit 101\n' > "$root/usr/sbin/policy-rc.d"
chmod 755 "$root/usr/sbin/policy-rc.d"
stage=target-packages
chroot "$root" /usr/bin/env DEBIAN_FRONTEND=noninteractive /bin/sh -ec '
    apt-get update
    apt-get install -y --no-install-recommends python3 python3-pil python3-gi \
        tzdata build-essential pkg-config libgtk-3-dev libjson-glib-dev
'
mkdir -p "$root/src"
git -c safe.directory="$project" -C "$project" archive HEAD | tar -x -C "$root/src"
# The inner shell expands only the fixed interpreter path passed via env.
stage=core-tests-and-native-build
# shellcheck disable=SC2016
chroot "$root" /usr/bin/env LANG=C.UTF-8 LC_ALL=C.UTF-8 OGUZDOWS_TEST_PROBE="${probe[*]}" /bin/sh -ec '
    cd /src
    $OGUZDOWS_TEST_PROBE /usr/bin/python3 -W error::ResourceWarning -m unittest discover -s tests -p test_workbench.py -v
    $OGUZDOWS_TEST_PROBE /usr/bin/python3 -W error::ResourceWarning -m unittest discover -s tests -p test_store_bootstrap.py -v
    mkdir -p /src/test-results/portable-bin
    sh scripts/build-native.sh /src/test-results/portable-bin/store
    sh scripts/build-news.sh /src/test-results/portable-bin/news
    sh scripts/build-desktop.sh hub /src/test-results/portable-bin/hub
    sh scripts/build-desktop.sh monitor /src/test-results/portable-bin/monitor
'
chroot "$root" /usr/bin/env LANG=C.UTF-8 LC_ALL=C.UTF-8 OGUZDOWS_TARGET_ARCH="$arch" \
    OGUZDOWS_TARGET_SUITE="$suite" OGUZDOWS_SOURCE_REVISION="$revision" "${probe[@]}" /usr/bin/python3 - <<'PY'
import hashlib
import json
import os
import struct
import subprocess
from pathlib import Path
base = Path('/src')
arch = subprocess.check_output(['/usr/bin/dpkg', '--print-architecture'], text=True).strip()
assert arch == os.environ['OGUZDOWS_TARGET_ARCH'], arch
assert struct.calcsize('P') == (8 if arch == 'arm64' else 4)
versions = {}
for component in ('store', 'news', 'hub', 'monitor'):
    prefix = ['/usr/bin/qemu-i386-static'] if arch == 'i386' else []
    text = subprocess.check_output([*prefix, str(base / 'test-results/portable-bin' / component), '--version'], text=True).strip()
    assert 'OğuzDows' in text, text
    versions[component] = text
hashes = {name: hashlib.sha256((base / name).read_bytes()).hexdigest() for name in (
    'system/usr/lib/oguzdows/workbench.py', 'system/usr/lib/oguzdows/workbench_core.py',
    'system/usr/lib/oguzdows/store_core.py', 'system/usr/lib/oguzdows/store_service.py',
    'native/store.c', 'native/news.c', 'native/hub.c', 'native/ui.c')}
report = {'schema': 1, 'scope': 'target-user-QEMU-core-and-C-ABI-not-GUI-or-physical',
          'arch': arch, 'suite': os.environ['OGUZDOWS_TARGET_SUITE'], 'qemu_cpu_for_core_and_abi_probes': os.environ['QEMU_CPU'],
          'source_revision': os.environ['OGUZDOWS_SOURCE_REVISION'], 'pointer_bits': struct.calcsize('P') * 8,
          'core_and_bootstrap_tests_passed': True, 'native_versions': versions, 'source_hashes': hashes,
          'physical_device': False, 'gpu_or_performance_benchmark': False, 'armv6_tested': False}
(base / 'test-results/portable.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print('::notice title=Portable target ABI and tools::' + json.dumps(report, ensure_ascii=False), flush=True)
PY
mkdir -p "$project/test-results/portable-$arch-$suite"
cp "$root/src/test-results/portable.json" "$project/test-results/portable-$arch-$suite/portable.json"
