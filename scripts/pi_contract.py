"""Pi yapı / salt-okunur export kapısının ortak veri okuyucuları.

Hedef kodu çalıştırmaz. Bağlı imajın yolları hosta taşamaz; göreli, kök içinde
kalan paket symlink'leri (ör. python3 -> python3.11) kullanılabilir. Kontroller
build zamanındadır, masaüstü açılışında tarama veya servis oluşturmaz.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import struct
from pathlib import Path

MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_ASSET_BYTES = 64 * 1024 * 1024
PACKAGE = re.compile(r'[a-z0-9][a-z0-9+.-]*\Z')


def checked_path(root, relative, allow_empty=False):
    if not isinstance(relative, str) or not relative or len(relative) > 1024 or '\x00' in relative:
        raise ValueError('Sözleşmede geçersiz göreli yol.')
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('Sözleşmede geçersiz göreli yol: ' + relative)
    root = Path(root).resolve(strict=True)
    try:
        target = (root / path).resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ValueError('Ürün dosyası eksik / çözülemeyen bağlantı: ' + relative) from error
    if not target.is_relative_to(root):
        raise ValueError('Ürün dosyası hedef kökün dışına çıkıyor: ' + relative)
    details = target.stat()
    if not stat.S_ISREG(details.st_mode) or (not allow_empty and details.st_size == 0):
        raise ValueError('Ürün dosyası normal dosya değil / boş: ' + relative)
    return target


def open_regular(path, maximum):
    # Bağlı imaj salt okunurdur. O_NONBLOCK özel dosya ikamesinde beklemeyi,
    # O_NOFOLLOW ise son bileşenin kontrol sonrası symlink olmasını önler.
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or details.st_size > maximum:
            raise ValueError('Ürün dosyası normal / boyut sınırında değil: ' + str(path))
        return os.fdopen(descriptor, 'rb')
    except BaseException:
        os.close(descriptor)
        raise


def read_bytes(root, relative, maximum=MAX_JSON_BYTES, allow_empty=False):
    path = checked_path(root, relative, allow_empty=allow_empty)
    with open_regular(path, maximum) as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError('Ürün dosyası okuma sınırını aştı: ' + relative)
    return data


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Yapı JSON içinde tekrarlı anahtar: ' + key)
        result[key] = value
    return result


def read_json(root, relative):
    return json.loads(read_bytes(root, relative), object_pairs_hook=unique_object)


def elf_info(path, expected):
    with open_regular(path, 128 * 1024 * 1024) as stream:
        header = stream.read(64)
    if len(header) < (64 if expected['elf_class'] == 2 else 52) or header[:4] != b'\x7fELF' or header[5] != 1:
        raise ValueError('Geçersiz / little-endian olmayan ELF: ' + str(path))
    machine = struct.unpack_from('<H', header, 18)[0]
    if header[4] != expected['elf_class'] or machine != expected['elf_machine']:
        raise ValueError('Hedef ARM ABI yerine yanlış ELF mimarisi: ' + str(path))
    flags = struct.unpack_from('<I', header, 36 if header[4] == 1 else 48)[0]
    if machine == 40 and not flags & 0x400:
        raise ValueError('ARMv6 hard-float ABI eksik: ' + str(path))
    return {'bits': header[4] * 32, 'machine': machine, 'hard_float': bool(flags & 0x400) if machine == 40 else None}


def feature_presence(root, contract):
    if not isinstance(contract, dict):
        raise ValueError('Pi özellik sözleşmesi nesne olmalı.')
    packages = contract['required_packages']
    if (not isinstance(packages, list) or not 0 < len(packages) <= 2048
            or not all(isinstance(name, str) and PACKAGE.fullmatch(name) for name in packages)
            or len(set(packages)) != len(packages)):
        raise ValueError('Sözleşmede geçersiz / tekrarlı paket listesi.')
    required = set(packages)
    features = contract['features']
    if not isinstance(features, dict) or not 0 < len(features) <= 64:
        raise ValueError('Ortak özellik grupları nesne olmalı.')
    groups = []
    for name, group in features.items():
        if (not isinstance(group, dict) or not isinstance(group.get('packages'), list)
                or not isinstance(group.get('files'), list) or len(group['files']) > 2048
                or not all(isinstance(value, str) for value in group['packages'])):
            raise ValueError('Ortak özellik grubu şeması bozuk: ' + name)
        if not set(group['packages']).issubset(required):
            raise ValueError('Ortak ürün özelliğinin paketi Pi tarifinden düşmüş: ' + name)
        for relative in group['files']:
            checked_path(root, relative)
        groups.append(name)
    hashes = contract['asset_hashes']
    if not isinstance(hashes, dict) or not 0 < len(hashes) <= 1024:
        raise ValueError('Görsel / doğal kayıt hash sözleşmesi bozuk.')
    for relative, expected in hashes.items():
        if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected):
            raise ValueError('Geçersiz SHA-256 sözleşmesi: ' + relative)
        with open_regular(checked_path(root, relative), MAX_ASSET_BYTES) as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != expected:
            raise ValueError('Kaynak / görsel / doğal kayıt hash eşleşmedi: ' + relative)
    for key in ('minimum_wallpapers', 'minimum_selected_narration'):
        if type(contract[key]) is not int or not 0 < contract[key] <= 512:
            raise ValueError('Geçersiz özellik alt sınırı: ' + key)
    gallery = read_json(root, 'usr/share/oguzdows/wallpapers.json')
    if (not isinstance(gallery, list) or len(gallery) > 512
            or not all(isinstance(entry, dict) and isinstance(entry.get('path'), str)
                       and isinstance(entry.get('preview'), str) and entry['preview'].startswith('/') for entry in gallery)):
        raise ValueError('Duvar kâğıdı katalog şeması bozuk.')
    expected_wallpapers = {'/' + key for key in hashes if key.startswith('usr/share/backgrounds/')}
    if len(gallery) < contract['minimum_wallpapers'] or len(gallery) != len(expected_wallpapers) or {entry['path'] for entry in gallery} != expected_wallpapers:
        raise ValueError('Kültür duvar kâğıdı sayısı / içeriği kaybolmuş.')
    for entry in gallery:
        checked_path(root, entry['preview'].removeprefix('/'))
    speech = read_json(root, 'usr/share/oguzdows/rifki/speech.json')
    if not isinstance(speech, dict) or len(speech) > 4096 or not all(isinstance(name, str) for name in speech.values()):
        raise ValueError('Doğal kayıt eşleme manifesti nesne / geçerli metin olmalı.')
    names = set(speech.values())
    selected = {Path(key).name for key in hashes if key.startswith('usr/share/oguzdows/rifki/')}
    if len(selected) < contract['minimum_selected_narration'] or not selected.issubset(names):
        raise ValueError('Seçilmiş doğal kayıt özelliği kaybolmuş.')
    for name in names:
        if not re.fullmatch(r'[a-z0-9-]+\.wav', name):
            raise ValueError('Doğal kayıt dosya adı geçersiz.')
        checked_path(root, 'usr/share/oguzdows/rifki/' + name)
    return {'groups': groups, 'asset_hashes': len(hashes), 'wallpapers': len(gallery),
            'selected_narration': len(selected), 'speech_contexts': len(speech)}
