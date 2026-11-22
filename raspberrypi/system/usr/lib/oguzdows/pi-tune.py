#!/usr/bin/env python3
"""Mevcut Pi servisinin ortak, sınırlı PC / ARM bellek işçisine köprüsü."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from pi_support import current_policy, is_pi
from resource_tune import apply as tune_resources, write_changed


def apply(root=Path('/')):
    if not is_pi(root):
        raise ValueError('Bu giriş yalnızca Raspberry Pi imajı içindir.')
    settings = tune_resources(root)
    write_changed(root / 'run/oguzdows/pi-profile.json', json.dumps(settings, indent=2) + '\n')
    return settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.apply and os.geteuid() != 0:
        parser.error('Uygulamak için yönetici yetkisi gerekli.')
    print(json.dumps(apply() if args.apply else current_policy(), ensure_ascii=False))


if __name__ == '__main__':
    main()
