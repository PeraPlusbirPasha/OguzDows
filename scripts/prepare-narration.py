#!/usr/bin/env python3
"""Seçilmiş sesle hazırlanmış 1.1 WAV'larını doğrula ve çevrimdışı paketle.

Bu geliştirme aracı ses üretmez / indirmez. --source yalnızca açıkça üretilen
sabit panel dosyalarını içerir. Çalışan sistemin /usr dizinine karşı kullanılmaz.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'system/usr/lib/oguzdows'))
from rifki_narration_texts import TEXTS
from rifki_speech import text_key

FILES = {topic: 'panel-' + topic + '.wav' for topic in TEXTS}
FILES['wallpapers'] = 'panel-wallpapers-v11.wav'
OBSOLETE = {'panel-welcome.wav', 'panel-wallpapers.wav', 'topic-wallpapers.wav', 'panel-styles.wav'}


def prepare(source, root, metadata):
    if root.resolve() == Path('/') or root.is_symlink():
        raise ValueError('Çalışan sistem yerine ayrı bir kaynak / çıktı kökü kullanın.')
    destination = root / 'usr/share/oguzdows/rifki'
    if source.resolve() == destination.resolve():
        raise ValueError('Ham kayıt kaynağı ve paket hedefi ayrı olmalı.')
    clips = []
    # Bütün kaynaklar doğrulanmadan hedefte hiçbir değişiklik yapma.
    for topic, filename in FILES.items():
        path = source / filename
        if path.is_symlink() or not path.is_file():
            raise ValueError('Doğal kayıt eksik / sembolik bağ: ' + filename)
        with wave.open(str(path), 'rb') as stream:
            if (stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getcomptype()) != (1, 2, 24000, 'NONE'):
                raise ValueError('24 kHz / mono / 16 bit PCM gerekli: ' + filename)
            frames = stream.getnframes()
            if not 24000 <= frames < 90 * 24000:
                raise ValueError('Kayıt 1–90 saniye aralığında olmalı: ' + filename)
            if len(stream.readframes(frames)) != frames * 2:
                raise ValueError('Kesilmiş WAV: ' + filename)
        clips.append({'topic': topic, 'text': TEXTS[topic], 'text_key': text_key(TEXTS[topic]),
                      'file': filename, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'bytes': path.stat().st_size, 'sample_rate': 24000, 'channels': 1,
                      'sample_width': 2, 'frames': frames, 'duration_seconds': frames / 24000})
    destination.mkdir(parents=True, exist_ok=True)
    manifest_path = destination / 'speech.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if not isinstance(manifest, dict):
        raise ValueError('Mevcut konuşma eşleme dosyası nesne olmalı.')
    # Yenilenen aynı WAV dosyasına eski bir metnin hash'i bağlı kalmamalı.
    # Yeni metinler aşağıda tek kez eklenir; temel / sonuç kayıtları korunur.
    replaced = OBSOLETE | set(FILES.values())
    manifest = {key: value for key, value in manifest.items() if value not in replaced}
    for clip in clips:
        shutil.copyfile(source / clip['file'], destination / clip['file'])
        manifest[clip['text_key']] = clip['file']
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    # Yalnızca yeni metinlerle değiştirilen eski sabit açıklamalar emekli edilir.
    # Temel yardım / aşama / sonuç kayıtları ve önceki yayımlanmış sürüm korunur.
    for filename in OBSOLETE:
        (destination / filename).unlink(missing_ok=True)
    provenance = {'version': 1, 'language': 'tr', 'kind': 'AI-generated natural spoken narration',
                  'voice_selection': 'Explicitly selected by the user in a two-voice audition for version 1.1',
                  'not_a_human_studio_recording': True, 'runtime_synthesis': False, 'clips': clips}
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + '\n')
    print(str(len(clips)) + ' doğal yerel kayıt · ' + str(sum(clip['bytes'] for clip in clips)) + ' bayt')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.source, args.root, args.metadata)


if __name__ == '__main__':
    main()
