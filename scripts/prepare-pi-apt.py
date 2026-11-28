#!/usr/bin/env python3
"""Hash'i denetlenmiş pi-gen'e dar, kaydı tutulan post-bootstrap APT uyarlaması.

Sürüm, mimari, anahtar veya paket listesi değişmez. Raspbian mirror director'ın
ulaşılamayan aynası yerine APT'nin kendi sınırlı failover taşıması kullanılır.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_LIST = 'stage0/00-configure-apt/files/sources.list'
ORIGINAL = 'http://raspbian.raspberrypi.com/raspbian/'
MIRROR = 'mirror+file:/etc/apt/mirrors/oguzdows-raspbian.list'


def prepare(source, arch, output):
    if arch not in ('armhf', 'arm64'):
        raise ValueError('Tanınmayan Pi mimarisi.')
    contract = json.loads((ROOT / 'raspberrypi/upstream-contract.json').read_text())['architectures'][arch]
    path = source / SOURCE_LIST
    data = path.read_bytes()
    before = hashlib.sha256(data).hexdigest()
    if before != contract['files'][SOURCE_LIST]:
        raise ValueError('Resmî APT şablonu değişmiş; uyarlama uygulanmadı.')
    stage = source / 'stage0/00-apt-resilience'
    if stage.exists() or output.exists():
        raise ValueError('Mevcut APT uyarlaması / raporu üzerine yazılmaz.')
    stage.mkdir()
    files = stage / 'files'
    files.mkdir()
    shutil.copy2(ROOT / 'raspberrypi/apt/80oguzdows-resilience', files / '80oguzdows-resilience')
    shutil.copy2(ROOT / 'raspberrypi/apt/raspbian.mirrors', files / 'raspbian.mirrors')
    script = stage / '00-run.sh'
    script.write_text('''#!/bin/bash
set -euo pipefail
install -d "${ROOTFS_DIR}/etc/apt/apt.conf.d" "${ROOTFS_DIR}/etc/apt/mirrors"
install -m 0644 files/80oguzdows-resilience "${ROOTFS_DIR}/etc/apt/apt.conf.d/80oguzdows-resilience"
if [ "${ARCH}" = armhf ]; then
    install -m 0644 files/raspbian.mirrors "${ROOTFS_DIR}/etc/apt/mirrors/oguzdows-raspbian.list"
fi
''')
    script.chmod(0o755)
    if arch == 'armhf':
        if data.count(ORIGINAL.encode()) != 2:
            raise ValueError('Raspbian şablonu beklenen iki URI içermiyor.')
        path.write_bytes(data.replace(ORIGINAL.encode(), MIRROR.encode()))
    report = {'schema': 1, 'arch': arch, 'pi_gen_commit': contract['commit'],
              'scope': 'post-debootstrap APT transport; no package, key, suite, ABI or boot changes',
              'source_template': SOURCE_LIST, 'before_sha256': before,
              'after_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'mirror_list_sha256': hashlib.sha256((files / 'raspbian.mirrors').read_bytes()).hexdigest(),
              'apt_config_sha256': hashlib.sha256((files / '80oguzdows-resilience').read_bytes()).hexdigest(),
              'signature_checks_disabled': False}
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--arch', choices=('armhf', 'arm64'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.arch, args.output)))
