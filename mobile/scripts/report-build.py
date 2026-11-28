#!/usr/bin/env python3
"""Persist actual SDK build/Java test/lint evidence, never infer an emulator pass from assembly.

The short GitHub notice is readable via the checks API as well as the full downloadable reports.
No APKs, generated keys or SDK files are committed to the source tree.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from acceptance import validate_build

ROOT = Path(__file__).resolve().parents[2]


def main():
    tests = Counter()
    classes = {}
    reports = list((ROOT / 'mobile/android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'))
    if not reports:
        raise RuntimeError('No actual Java unit test XML report; assembly alone is insufficient.')
    for report in reports:
        node = ET.parse(report).getroot()
        name = node.get('name')
        if name in classes:
            raise RuntimeError('Duplicate JVM suite report')
        classes[name] = int(node.get('tests', '0'))
        if len(node.findall('testcase')) != classes[name] or node.findall('.//failure') or node.findall('.//error') or node.findall('.//skipped'):
            raise RuntimeError('JVM test XML contains empty/failed/skipped cases')
        tests.update({key: int(node.get(key, '0')) for key in ('tests', 'failures', 'errors', 'skipped')})
    if tests['tests'] < 1 or any(tests[key] for key in ('failures', 'errors', 'skipped')):
        raise RuntimeError('Java test reports have failures, skips or no tests.')
    lint = ET.parse(ROOT / 'mobile/android/app/build/reports/lint-results-debug.xml').getroot()
    issues = Counter(issue.get('severity') for issue in lint.findall('issue'))
    if issues['Error'] or issues['Fatal']:
        raise RuntimeError('Android lint errors are not waived or baselined.')
    artifacts = []
    for path in ('app/build/outputs/apk/debug/app-debug.apk',
                 'app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk',
                 'fixture/build/outputs/apk/debug/fixture-debug.apk'):
        file = ROOT / 'mobile/android' / path
        digest = hashlib.sha256()
        with file.open('rb') as content:
            for block in iter(lambda: content.read(65536), b''):
                digest.update(block)
        artifacts.append({'file': path, 'bytes': file.stat().st_size, 'sha256': digest.hexdigest()})
    evidence = {
        'source_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'assembled': artifacts, 'java_unit_tests': dict(tests), 'java_test_classes': classes, 'lint': dict(issues),
        'lint_warning_ids': dict(Counter(issue.get('id') for issue in lint.findall('issue') if issue.get('severity') == 'Warning')),
        'emulator_passed': None, 'physical_sim_tested': False, 'gms_certification_tested': False,
    }
    validate_build(evidence, evidence['source_sha'])
    output = ROOT / 'test-results/mobile/build.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    detail = json.dumps(evidence, ensure_ascii=False, separators=(',', ':')).replace('%', '%25')
    if len(detail) > 3500:
        raise RuntimeError('Build evidence notice exceeds its reviewed bounded length.')
    print('::notice title=Mobile build evidence::' + detail)


if __name__ == '__main__':
    main()
