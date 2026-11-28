#!/usr/bin/env python3
"""İncelenen resmî pi-gen mimari sözleşmesini derlemeden önce doğrula.

Ağ / root gerektirmez. Yeni kaynak kilidi, yeni mimari inceleme olmadan sessizce
kabul edilmez. Bu karşılaştırma kaynak dosyaları içindir; binary Pi OS boot değil.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def audit(arch, source, lock=None, contract=None):
    lock = json.loads((ROOT / 'raspberrypi/pi-gen.lock.json').read_text()) if lock is None else lock
    contract = json.loads((ROOT / 'raspberrypi/upstream-contract.json').read_text()) if contract is None else contract
    expected = contract['architectures'][arch]
    report = {'schema': 1, 'arch': arch, 'scope': contract['evidence_type'], 'suite': lock['suite'],
              'pi_gen_commit': lock[arch]['commit'], 'archive_sha256': lock[arch]['archive_sha256'],
              'physical_boot': False, 'files': {}, 'adaptations': contract['adaptations'], 'errors': []}
    if contract['suite'] != lock['suite'] or any(expected[key] != lock[arch][key] for key in ('branch', 'commit', 'archive_sha256')):
        report['errors'].append('Kaynak kilidi değişmiş; upstream sözleşmesi yeniden incelenmeli.')
    for relative, wanted in expected['files'].items():
        path = Path(relative)
        try:
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Geçersiz kaynak yolu.')
            target = source / path
            if (target.is_symlink() or not target.resolve().is_relative_to(source.resolve())
                    or not target.is_file() or target.stat().st_size > 1024 * 1024):
                raise ValueError('Kaynak yolu kök içinde normal / sınırlı dosya olmalı.')
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            report['files'][relative] = digest
            if digest != wanted:
                report['errors'].append('İncelenen upstream dosyası değişmiş: ' + relative)
        except (OSError, ValueError) as error:
            report['errors'].append(relative + ': ' + str(error))
    config = source / 'stage1/00-boot-files/files/config.txt'
    if config.is_file() and config.resolve().is_relative_to(source.resolve()) and config.stat().st_size <= 1024 * 1024:
        values = {line.strip() for line in config.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')}
        for setting in contract['preserved_boot_settings']:
            if setting not in values:
                report['errors'].append('Resmî boot / çevre birimi varsayılanı eksik: ' + setting)
        if ('arm_64bit=1' in values) != (arch == 'arm64'):
            report['errors'].append('Resmî firmware bit modu hedef mimariyle eşleşmiyor.')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=('armhf', 'arm64'), required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.arch, args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    summary = {key: report[key] for key in ('arch', 'suite', 'pi_gen_commit', 'physical_boot', 'errors')}
    summary['upstream_files_checked'] = len(report['files'])
    print('::notice title=Pi resmî kaynak sözleşmesi::' + json.dumps(summary, ensure_ascii=False))
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
