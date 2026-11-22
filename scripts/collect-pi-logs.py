#!/usr/bin/env python3
"""Pi CI: rootfs'i taramadan yalnızca bilinen günlükleri okunabilir alana al.

Kaynak dosyaların izinleri değişmez. Her dosyanın son 2 MiB'ı saklanır; eksik /
kesilmiş / reddedilmiş dosyalar raporda açıkça belirtilir. İmaj veya özel /etc
verisi kopyalanmaz. Bu araç imaj derleme adımının çıkış kodunu değiştirmez.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 2 * 1024 * 1024


def candidates(arch):
    if arch not in ('armhf', 'arm64'):
        raise ValueError('Pi mimarisi armhf veya arm64 olmalı.')
    work = f'pi-gen/work/OguzDows-rpi-{arch}'
    return (
        ('build.log', 'build.log'),
        ('pi-gen/build.log', 'pi-gen.log'),
        (work + '/build.log', 'pi-gen-work.log'),
        (work + '/stage0/rootfs/debootstrap/debootstrap.log', 'stage0-debootstrap.log'),
        (work + '/stage0/rootfs/var/log/bootstrap.log', 'stage0-bootstrap.log'),
        (work + '/stage-oguzdows/rootfs/var/log/apt/term.log', 'desktop-apt.log'),
        ('pi-upstream-audit.json', 'pi-upstream-audit.json'),
        ('pi-apt-adaptation.json', 'pi-apt-adaptation.json'),
        ('pi-runtime-report.json', 'pi-runtime-report.json'),
    )


def collect(arch, build, output):
    files = candidates(arch)
    build = Path(build).resolve()
    output = Path(output)
    if output.is_symlink():
        raise ValueError('Günlük çıktı dizini bağlantı olamaz.')
    if output.resolve().is_relative_to(build):
        raise ValueError('Günlük çıktısı derleme rootfs’inden ayrı olmalı.')
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('Günlük çıktı dizini boş olmalı; eski dosyalar ezilmedi.')
    records = []
    for relative, name in files:
        source = build / relative
        record = {'source': relative, 'file': name}
        try:
            # Mutlak / dışarı taşan bir rootfs symlink'i host verisi sızdırmasın.
            if not source.resolve().is_relative_to(build):
                raise ValueError('Günlük yolu çalışma alanının dışına çıkıyor.')
            descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
            with os.fdopen(descriptor, 'rb') as stream:
                details = os.fstat(stream.fileno())
                if not stat.S_ISREG(details.st_mode):
                    raise ValueError('Günlük normal dosya değil.')
                if name.endswith('.json') and details.st_size > MAX_BYTES:
                    raise ValueError('Yapı raporu kesilerek geçerli JSON gibi sunulamaz.')
                offset = max(0, details.st_size - MAX_BYTES)
                stream.seek(offset)
                data = stream.read(MAX_BYTES)
            destination = output / name
            with destination.open('xb') as stream:
                stream.write(data)
                os.fchmod(stream.fileno(), 0o644)  # Yalnızca yeni günlük kopyası.
            record.update(status='copied', source_bytes=details.st_size, copied_bytes=len(data), truncated=bool(offset))
        except FileNotFoundError:
            record['status'] = 'missing'
        except (OSError, ValueError, RuntimeError) as error:
            record.update(status='error', error=str(error))
        records.append(record)
    report = {'schema': 1, 'arch': arch, 'max_bytes_per_log': MAX_BYTES,
              'recursive_rootfs_scan': False, 'source_permissions_changed': False, 'logs': records}
    report_path = output / 'collection.json'
    with report_path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        os.fchmod(stream.fileno(), 0o644)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=('armhf', 'arm64'), required=True)
    args = parser.parse_args()
    try:
        report = collect(args.arch, ROOT / ('build-rpi-' + args.arch), ROOT / ('test-results/pi-build-' + args.arch))
    except (OSError, ValueError) as error:
        print('Pi günlükleri toplanamadı: ' + str(error), file=sys.stderr)
        return 1
    errors = [row for row in report['logs'] if row['status'] == 'error']
    print(json.dumps(report, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
