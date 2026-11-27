#!/usr/bin/env python3
"""Run a bounded one-shot build command; emit useful GHA annotations on failure (no secrets)."""
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


def annotate(message, title='Mobile build or emulator command failed', location=''):
    # GitHub truncates each annotation at 4096 characters; put the actual failure first.
    detail = message[:3000].replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
    print(f'::error title={title}{location}::{detail}')


def lint_annotations():
    root = Path(__file__).resolve().parents[2]
    report = root / 'mobile/android/app/build/reports/lint-results-debug.xml'
    if not report.is_file():
        return
    for issue in ET.parse(report).getroot().findall('issue'):
        if issue.get('severity') not in ('Error', 'Fatal'):
            continue
        location = issue.find('location')
        position = ''
        if location is not None:
            path = Path(location.get('file', ''))
            try:
                path = path.relative_to(root)
            except ValueError:
                pass
            position = f',file={path},line={location.get("line", "1")}'
        annotate(issue.get('message', 'Lint error'), title='Android lint ' + issue.get('id', ''), location=position)


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
        meaningful = [line for line in output.splitlines()
                      if 'DEVICE_UI_PREVIEW ' not in line and 'NATIVE_LAUNCHER_PREVIEW ' not in line
                      and (not line.startswith(('\tat ', '\t... ', '    at ', '> Task ', 'Daemon will ', 'To honour ', '::error ', '::notice '))
                          or 'at org.oguzdows.mobile.' in line)]
        detail = '\n'.join(meaningful)[-9000:]
        # Reverse chunks so the most recent error stays visible even when the step annotation limit is reached.
        chunks = [detail[i:i + 3000] for i in range(0, len(detail), 3000)]
        for index in reversed(range(len(chunks))):
            annotate(chunks[index], title=f'Mobile command failed (detail {index + 1}/{len(chunks)})')
        if 'lintDebug' in ' '.join(command):
            lint_annotations()
    return code


if __name__ == '__main__':
    raise SystemExit(main())
