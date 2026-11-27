#!/usr/bin/env python3
"""Run a bounded one-shot build command; emit useful GHA annotations on failure (no secrets)."""
import os
from pathlib import Path
import subprocess
import sys


def main():
    command = sys.argv[1:]
    if command[:1] == ['--']:
        command = command[1:]
    if not command:
        raise SystemExit('command required')
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors='replace', timeout=1200, check=False)
        output, code = result.stdout, result.returncode
    except subprocess.TimeoutExpired as error:
        output = error.stdout or b''
        if isinstance(output, bytes):
            output = output.decode('utf-8', 'replace')
        output += '\nCommand exceeded 1200 seconds; no success assumed.\n'
        code = 124
    print(output, end='')
    if code:
        detail = '\n'.join(output.splitlines()[-170:])[-24000:]
        detail = detail.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        print(f'::error title=Mobile build or emulator command failed::{detail}')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
