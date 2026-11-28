#!/bin/bash
# Yalnızca izole Pi derleme hostu. Hedef imaj / çalışan Pi içinde çalıştırılmaz.
set -euo pipefail
usage() {
    echo 'Kullanım: sudo scripts/prepare-pi-binfmt.sh armhf|arm64'
    echo 'Kurulu QEMU paketinin ARM kaydını etkinleştirir; özel boş chroot içinde sınar.'
}
if [ "$#" -eq 1 ] && [[ "$1" == --help || "$1" == -h ]]; then usage; exit 0; fi
if [ "$#" -ne 1 ] || [[ ! "$1" =~ ^(armhf|arm64)$ ]]; then usage >&2; exit 2; fi
[ "$(id -u)" -eq 0 ] || { echo 'Binfmt hazırlığı izole derleme hostunda root gerektirir.' >&2; exit 1; }
arch=$1
if [ "$arch" = armhf ]; then cpu=arm; else cpu=aarch64; fi
emulator="/usr/bin/qemu-$cpu-static"
[ -x "$emulator" ] || { echo "Statik QEMU eksik: $emulator" >&2; exit 1; }

# Yeni paketler systemd binfmt.d kullanır; bunlar update-binfmts'in ayrı veri
# tabanında görünmez. Yeni ELF magic / maske uydurma veya uzaktan betik alma:
# yalnızca dağıtımın kurulu QEMU paketine ait standart tanımı kullan.
config=''
for candidate in "/usr/lib/binfmt.d/qemu-$cpu-static.conf" "/usr/lib/binfmt.d/qemu-$cpu.conf" "/usr/share/qemu/binfmt.d/qemu-$cpu.conf"; do
    if [ -f "$candidate" ]; then config=$candidate; break; fi
done
if [ -n "$config" ]; then
    [ -x /usr/lib/systemd/systemd-binfmt ] || { echo 'systemd-binfmt bulunamadı.' >&2; exit 1; }
    echo "Paket tanımı: $config"
    cat "$config"
    /usr/lib/systemd/systemd-binfmt "$config"
else
    # Eski bookworm paketinin binfmt-support kaydı. Kayıt yoksa hatayı saklama;
    # apt / debootstrap aşamasına yanlış bir hazır bilgisiyle geçme.
    update-binfmts --enable "qemu-$cpu"
fi
arch-test "$arch"

# Yalnızca hostta çalışmak yetmez: F/persistent kaydı olmayan yorumlayıcı,
# debootstrap'ın chroot'una geçildiğinde kaybolabilir. Hiçbir hedef rootfs'e
# dokunmadan, yeni boş dizinde statik arch-test yardımcısını gerçekten çalıştır.
probe=$(mktemp -d -t oguzdows-pi-binfmt.XXXXXXXX)
cleanup() {
    local status=$?
    rmdir "$probe" || return 1
    return "$status"
}
trap cleanup EXIT
arch-test -c "$probe" "$arch"
echo "QEMU $arch: host ve özel boş chroot doğrulandı; Pi boot testi değildir."
