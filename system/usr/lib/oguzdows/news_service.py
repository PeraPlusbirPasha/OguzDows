#!/usr/bin/env python3
"""Yerel C Haber arayüzünün tek istek / tek JSON / kısa ömürlü işçisi."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from news_core import NewsError, Reader


def main():
    args = sys.argv[1:]
    try:
        if os.geteuid() == 0:
            raise NewsError('Haber okuyucusu yönetici olarak çalıştırılmaz.')
        reader = Reader()
        if args == ['list']:
            result = reader.stream()
        elif len(args) == 2 and args[0] == 'cached':
            result = reader.stream(args[1])
        elif len(args) == 2 and args[0] == 'refresh':
            result = reader.stream(args[1], network=True)
        elif len(args) == 3 and args[0] == 'add':
            added = reader.add(args[1], args[2])
            result = reader.stream(added['selected'])
        elif len(args) == 2 and args[0] == 'remove':
            remaining = reader.remove(args[1])
            result = reader.stream(remaining['selected'])
        else:
            raise NewsError('Sabit haber işlemi gerekli; serbest komut / dosya kabul edilmez.')
        print(json.dumps(result, ensure_ascii=False, separators=(',', ':')))
        return 0
    except (OSError, ValueError, TypeError) as error:
        print(json.dumps({'error': str(error)[:700]}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
