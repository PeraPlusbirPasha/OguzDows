#!/usr/bin/env python3
"""Gerçek initrd'nin boyutunu, açılan dosyaları ve GPU payload bütünlüğünü kaydet.

Arşivi yalnızca özel geçici dizine açar. Boyutlar dosya verisidir; inode,
çekirdek, page rounding ve sıkışık arşivin aynı anda RAM'de tutulması dahil
olmadığından 512 MiB açılış testinin yerine geçmez.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import os
import stat
import subprocess
import tempfile
from pathlib import Path

BLOCK = 1024 * 1024
MANIFEST = 'etc/oguzdows/initramfs-firmware.json'


def file_digest(stream):
    result = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: stream.read(BLOCK), b''):
        result.update(chunk)
        size += len(chunk)
    return result.hexdigest(), size


def member(stage, relative):
    path = stage / relative
    if Path(relative).is_absolute() or '..' in Path(relative).parts or not path.resolve().is_relative_to(stage.resolve()):
        raise ValueError('initrd kanıt yolu özel arşiv kökünün dışında.')
    return path


def inspect_tree(unpacked):
    """unmkinitramfs early/early2/main ağaçları; symlink dizinleri izlenmez."""
    totals = {'firmware': 0, 'modules': 0, 'other': 0}
    files, manifests = [], []
    seen = set()
    for stage in sorted(Path(unpacked).iterdir()):
        if stage.is_symlink() or not stage.is_dir():
            raise ValueError('Beklenmeyen unmkinitramfs kanıt kökü.')
        for directory, _dirs, names in os.walk(stage, followlinks=False):
            for name in names:
                path = Path(directory) / name
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode):
                    continue
                relative = str(path.relative_to(stage))
                inode = (info.st_dev, info.st_ino)
                if inode not in seen:
                    seen.add(inode)
                    key = ('firmware' if relative.startswith(('lib/firmware/', 'usr/lib/firmware/'))
                           else 'modules' if relative.startswith(('lib/modules/', 'usr/lib/modules/')) else 'other')
                    totals[key] += info.st_size
                    files.append({'path': stage.name + '/' + relative, 'bytes': info.st_size})
        manifest = member(stage, MANIFEST)
        if not manifest.is_file():
            continue
        data = json.loads(manifest.read_text())
        if data.get('schema') != 1 or data.get('scope') != 'initramfs-only-gpu-firmware':
            raise ValueError('initrd firmware kanıt şeması geçersiz.')
        verified = 0
        # Sıkışık dosyalar 0.148'de early, normal dosyalar main içinde olabilir.
        for item in data['converted']:
            matches = [member(part, item['path'] + '.xz') for part in Path(unpacked).iterdir()]
            matches = [path for path in matches if path.is_file()]
            if len(matches) != 1:
                raise ValueError('Paketlenmiş sıkışık firmware tekil değil / eksik: ' + item['path'])
            encoded = matches[0]
            if encoded.stat().st_size != item['compressed_bytes']:
                raise ValueError('Paketlenmiş firmware boyutu değişmiş: ' + item['path'])
            with lzma.open(encoded, 'rb') as stream:
                if file_digest(stream) != (item['sha256'], item['raw_bytes']):
                    raise ValueError('Paketlenmiş firmware ham SHA-256 / boyutu eşleşmiyor: ' + item['path'])
            for logical in (item['path'], *item['aliases']):
                for part in Path(unpacked).iterdir():
                    if os.path.lexists(member(part, logical)):
                        raise ValueError('Sıkıştırma sonrası ham firmware geri eklenmiş: ' + logical)
                links = [member(part, logical + '.xz') for part in Path(unpacked).iterdir()]
                if not any(link.is_file() and link.resolve() == encoded.resolve() for link in links):
                    raise ValueError('Firmware mantıksal adı korunmamış: ' + logical)
            verified += 1
        summary = {key: value for key, value in data.items() if key != 'converted'}
        summary['converted_files'] = len(data['converted'])
        summary['payloads_verified'] = verified
        summary['manifest_sha256'] = hashlib.sha256(manifest.read_bytes()).hexdigest()
        manifests.append((summary, data))
    return {'regular_file_bytes': sum(totals.values()), 'regular_file_count': len(files),
            'category_bytes': totals, 'largest_files': sorted(files, key=lambda item: (-item['bytes'], item['path']))[:8],
            'firmware': [summary for summary, _data in manifests]}, [data for _summary, data in manifests]


def record(image, output, work=None):
    image, output = Path(image), Path(output)
    if not image.is_file() or not stat.S_ISREG(image.stat().st_mode):
        raise ValueError('Normal initrd dosyası gerekli; blok aygıtı kabul edilmez.')
    with tempfile.TemporaryDirectory(prefix='oguzdows-initrd-report-', dir=work) as directory:
        destination = Path(directory) / 'unpacked'
        subprocess.run(['unmkinitramfs', str(image.resolve()), str(destination)], check=True, timeout=600,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        report, manifests = inspect_tree(destination)
    with image.open('rb') as stream:
        report['archive_sha256'], report['archive_bytes'] = file_digest(stream)
    report['archive'] = image.name
    report['size_limit_note'] = 'Dosya verisi; erken açılış RAM toplamı değildir. Gerçek VM / donanım açılışı ayrıca gerekli.'
    output.mkdir(parents=True, exist_ok=True)
    (output / (image.name + '-inventory.json')).write_text(json.dumps(report, ensure_ascii=True, indent=2) + '\n')
    (output / (image.name + '-firmware.json')).write_text(json.dumps(manifests, ensure_ascii=True, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(record(args.image, args.output), ensure_ascii=True))


if __name__ == '__main__':
    main()
