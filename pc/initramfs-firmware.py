#!/usr/bin/env python3
"""Plymouth'un genel GPU firmware'ini silmeden erken açılış RAM'ini azaltır.

Yalnızca mkinitramfs'in geçici DESTDIR kopyasında, çekirdek XZ firmware desteği
kanıtlanırsa çalışır. MODULES=most, microcode, disk/ağ firmware'i ve kurulu
/usr/lib/firmware aynen kalır. Dış arşivi daha iyi sıkıştırmak tek başına açılmış
rootfs RAM'ini azaltmaz; burada her GPU dosyası istenene kadar sıkışık tutulur.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import os
import re
import stat
import tempfile
from collections import deque
from pathlib import Path, PurePosixPath

GRAPHICS = frozenset(('amdgpu', 'radeon', 'i915', 'xe', 'nvidia'))
BLOCK = 1024 * 1024
MANIFEST = 'etc/oguzdows/initramfs-firmware.json'


def local_path(root, relative):
    """Arşiv içi mutlak symlink /lib/... de hosta değil, DESTDIR'e aittir."""
    pending = deque(PurePosixPath(relative).parts)
    parts = []
    links = 0
    while pending:
        part = pending.popleft()
        if part == '/':
            parts.clear()
        elif part == '..':
            if not parts:
                raise ValueError('initramfs dışına çıkan firmware bağlantısı reddedildi.')
            parts.pop()
        elif part not in ('', '.'):
            path = root.joinpath(*parts, part)
            if path.is_symlink():
                links += 1
                if links > 40:
                    raise ValueError('Firmware bağlantı döngüsü reddedildi.')
                pending.extendleft(reversed(PurePosixPath(os.readlink(path)).parts))
            else:
                parts.append(part)
    return root.joinpath(*parts)


def digest(stream):
    result = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: stream.read(BLOCK), b''):
        result.update(chunk)
        size += len(chunk)
    return result.hexdigest(), size


def compress_copy(path):
    """CRC32 + 1 MiB sözlük: kernel XZ decoder uyumu ve sınırlı çalışma RAM'i."""
    details = path.stat()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.oguzdows-fw-', dir=path.parent, delete=False) as out:
            temporary = Path(out.name)
            compressor = lzma.LZMACompressor(format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC32,
                filters=[{'id': lzma.FILTER_LZMA2, 'preset': 6, 'dict_size': BLOCK}])
            original = hashlib.sha256()
            size = 0
            with path.open('rb') as source:
                for chunk in iter(lambda: source.read(BLOCK), b''):
                    original.update(chunk)
                    size += len(chunk)
                    out.write(compressor.compress(chunk))
            out.write(compressor.flush())
        # Hata / disk dolması / yanlış payload, ham dosya kaldırılmadan yakalanır.
        with lzma.open(temporary, 'rb') as compressed:
            if digest(compressed) != (original.hexdigest(), size):
                raise ValueError('Sıkıştırılan firmware içeriği eşleşmedi: ' + path.name)
        compressed_size = temporary.stat().st_size
        if compressed_size + 4096 >= size:
            return None  # Küçük / zaten sıkışık payload için fazladan iş yok.
        temporary.chmod(stat.S_IMODE(details.st_mode))
        os.utime(temporary, ns=(details.st_atime_ns, details.st_mtime_ns))
        # Mevcut .xz/.zst dosyası preflight'ta korunur; asla üzerine yazılmaz.
        destination = path.with_name(path.name + '.xz')
        os.link(temporary, destination)
        return {'raw_bytes': size, 'compressed_bytes': compressed_size, 'sha256': original.hexdigest()}
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def optimize(root, version, kernel_config):
    root = Path(root)
    if not root.is_absolute() or not root.is_dir() or root.resolve() == Path('/'):
        raise ValueError('Yalnızca geçici, mutlak mkinitramfs kökü kabul edilir.')
    root = root.resolve()
    if not local_path(root, 'init').is_file() or not local_path(root, 'scripts').is_dir():
        raise ValueError('mkinitramfs init / scripts yapısı yok; firmware değiştirilmedi.')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+_~:-]*', version):
        raise ValueError('Çekirdek sürümü geçersiz.')
    report = {'schema': 1, 'kernel_version': version, 'scope': 'initramfs-only-gpu-firmware',
              'codec': 'xz-crc32-lzma2-dict-1MiB', 'graphics_directories': sorted(GRAPHICS),
              'kernel_support_verified': False, 'converted': [], 'renamed_aliases': 0,
              'saved_unpacked_bytes': 0}
    config = Path(kernel_config)
    text = config.read_text() if config.is_file() else ''
    if not all(flag + '=y' in text.splitlines() for flag in ('CONFIG_FW_LOADER_COMPRESS', 'CONFIG_FW_LOADER_COMPRESS_XZ')):
        report['skip_reason'] = 'Hedef çekirdeğin XZ firmware desteği doğrulanamadı; ham dosyalar korundu.'
        return report
    report['kernel_support_verified'] = True
    report['kernel_config_sha256'] = hashlib.sha256(config.read_bytes()).hexdigest()
    firmware = local_path(root, 'usr/lib/firmware')
    if not firmware.is_dir():
        firmware = local_path(root, 'lib/firmware')
    if not firmware.is_dir():
        report['skip_reason'] = 'Bu initramfs içinde firmware yok.'
        return report
    regular, symlinks = [], []
    for directory, dirs, files in os.walk(firmware, followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            if path.is_symlink():
                symlinks.append(path)
            elif path.is_file():
                regular.append(path)
    # Her bağlantıyı ÖNCE çöz: geçersiz / dışarı kaçan bir ağaç yarım değiştirilmez.
    aliases = {}
    for link in symlinks:
        resolved = local_path(root, str(link.relative_to(root)))
        aliases.setdefault(resolved, []).append(link)
    report['firmware_regular_bytes_before'] = sum(path.stat().st_size for path in regular)
    report['firmware_regular_files_before'] = len(regular)
    for path in sorted(regular):
        relative = path.relative_to(firmware)
        if (len(relative.parts) < 2 or relative.parts[0] not in GRAPHICS
                or path.suffix in ('.xz', '.zst') or path.stat().st_size < 8192
                or path.stat().st_nlink != 1):
            continue
        names = [path, *aliases.get(path, [])]
        if any(os.path.lexists(str(name) + suffix) for name in names for suffix in ('.xz', '.zst')):
            continue  # Var olan alternatif dosya / bağlantı / içerik asla ezilmez.
        item = compress_copy(path)
        if item is None:
            continue
        compressed = path.with_name(path.name + '.xz')
        item['path'] = str(path.relative_to(root))
        item['aliases'] = [str(link.relative_to(root)) for link in names[1:]]
        for link in names[1:]:
            # Zinciri kısalt; bütün mantıksal firmware adları .xz fallback ile kalır.
            destination = link.with_name(link.name + '.xz')
            destination.symlink_to(os.path.relpath(compressed, link.parent))
        for link in names[1:]:
            link.unlink()
        path.unlink()
        report['converted'].append(item)
        report['renamed_aliases'] += len(names) - 1
        report['saved_unpacked_bytes'] += item['raw_bytes'] - item['compressed_bytes']
    report['firmware_regular_bytes_after'] = report['firmware_regular_bytes_before'] - report['saved_unpacked_bytes']
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--kernel-version', required=True)
    args = parser.parse_args()
    version = args.kernel_version
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+_~:-]*', version):
        parser.error('Çekirdek sürümü geçersiz.')
    # Kopya değil gerçekten paketlenmekte olan çekirdeğin yapılandırması.
    configs = (Path('/boot/config-' + version), Path('/lib/modules') / version / ('config-' + version))
    config = next((path for path in configs if path.is_file()), configs[0])
    report = optimize(args.root, version, config)
    manifest = local_path(args.root.resolve(), MANIFEST)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(report, ensure_ascii=True, indent=2) + '\n')
    summary = {key: value for key, value in report.items() if key != 'converted'}
    summary['converted_files'] = len(report['converted'])
    print('OğuzDows initramfs firmware: ' + json.dumps(summary, ensure_ascii=True), flush=True)


if __name__ == '__main__':
    main()
