#!/usr/bin/env python3
"""Explicit CI-only RSS health probe; never runs when opening the reader.

Each source gets its own bounded process. Network failures are reported, not
turned into fabricated news or a claim that every publisher is available.
Unexpected Python failures are fatal. Offline fallback is covered separately.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'system/usr/lib/oguzdows'))
from news_core import NewsError, Reader

SOURCES = ROOT / 'system/usr/share/oguzdows/news-sources.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.source:
        with tempfile.TemporaryDirectory(prefix='oguz-rss-probe-') as directory:
            reader = Reader(SOURCES, Path(directory) / 'config', Path(directory) / 'cache')
            try:
                data = reader.refresh(args.source)
                result = {'id': args.source, 'live': True, 'items': len(data['items'])}
            except (NewsError, OSError) as error:
                result = {'id': args.source, 'live': False, 'error': str(error)[:500]}
            print(json.dumps(result, ensure_ascii=False))
        return
    if args.output is None:
        parser.error('--output required')
    results = []
    for source in json.loads(SOURCES.read_text()):
        try:
            process = subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--source', source['id']],
                                     capture_output=True, text=True, timeout=24, check=True)
            result = json.loads(process.stdout)
        except subprocess.TimeoutExpired:
            result = {'id': source['id'], 'live': False, 'error': '24 second worker deadline'}
        except subprocess.CalledProcessError as error:
            raise AssertionError('RSS worker code failure, not disguised as offline: ' + error.stderr[-2500:]) from error
        results.append(result)
        print('::notice title=Explicit live RSS ' + source['id'] + '::' + json.dumps(result, ensure_ascii=False))
    report = {'explicit_ci_probe': True, 'python': sys.version.split()[0], 'sources': results,
              'available_sources': sum(source['live'] for source in results),
              'all_sources_available': all(source['live'] for source in results),
              'network_failure_falls_back_to_labelled_example': True}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('::notice title=RSS live source health::' + json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
