#!/usr/bin/env python3
"""Destructive ONLY to a disposable emulator: install, select roles, inject virtual radio, test.

Never runs against a physical serial or ro.kernel.qemu != 1. No real carrier/SIM/emergency call.
Run inside android-emulator-runner after building both APKs and generating test assets.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'test-results/mobile/emulator'
PACKAGE = 'org.oguzdows.mobile'
COMPONENT = f'{PACKAGE}.test/androidx.test.runner.AndroidJUnitRunner'


def annotation(level, title, text):
    detail = text.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')[:3500]
    print(f'::{level} title={title}::{detail}', flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    serials = [line.split()[0] for line in subprocess.check_output(['adb', 'devices'], text=True).splitlines()[1:]
               if line.endswith('\tdevice')]
    candidates = [serial for serial in serials if serial.startswith('emulator-')]
    if len(candidates) != 1:
        raise SystemExit('Exactly one disposable emulator is required; physical targets are never used.')
    serial = candidates[0]

    def adb(*args, check=True, timeout=90):
        result = subprocess.run(['adb', '-s', serial, *args], text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout, check=False)
        if check and result.returncode:
            raise RuntimeError(f'adb {args[0]} failed: {result.stdout[-5000:]}')
        return result.stdout

    if adb('shell', 'getprop', 'ro.kernel.qemu').strip() != '1':
        raise SystemExit('REFUSED: this target is not a QEMU Android emulator.')
    evidence = {'source_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'sdk': adb('shell', 'getprop', 'ro.build.version.sdk').strip(),
                'abi': adb('shell', 'getprop', 'ro.product.cpu.abi').strip(),
                'image_fingerprint': adb('shell', 'getprop', 'ro.build.fingerprint').strip(),
                'emulator_only': True, 'physical_sim_tested': False, 'emergency_calls_tested': False,
                'gms_certification_tested': False, 'mms_rcs_supported': False, 'tests': []}
    adb('shell', 'input', 'keyevent', '82')
    adb('shell', 'settings', 'put', 'global', 'window_animation_scale', '0')
    adb('shell', 'settings', 'put', 'global', 'transition_animation_scale', '0')
    adb('shell', 'settings', 'put', 'global', 'animator_duration_scale', '0')
    adb('uninstall', 'org.oguzdows.fixture', check=False)
    adb('install', '-r', '-t', str(ROOT / 'mobile/android/app/build/outputs/apk/debug/app-debug.apk'))
    adb('install', '-r', '-t', str(ROOT / 'mobile/android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk'))
    for role in ('DIALER', 'SMS'):
        adb('shell', 'cmd', 'role', 'add-role-holder', '--user', '0', f'android.app.role.{role}', PACKAGE)
        holders = adb('shell', 'cmd', 'role', 'get-role-holders', '--user', '0', f'android.app.role.{role}')
        if PACKAGE not in holders:
            raise RuntimeError(f'{role}: app did not qualify for the real platform role')
    permissions = ['CALL_PHONE', 'READ_PHONE_STATE', 'SEND_SMS', 'RECEIVE_SMS', 'READ_SMS', 'RECEIVE_MMS', 'RECEIVE_WAP_PUSH']
    if int(evidence['sdk']) >= 33:
        permissions.append('POST_NOTIFICATIONS')
    for permission in permissions:
        adb('shell', 'pm', 'grant', PACKAGE, 'android.permission.' + permission)
    # This is equivalent to approving this source in a throwaway emulator, not a production bypass.
    adb('shell', 'appops', 'set', PACKAGE, 'REQUEST_INSTALL_PACKAGES', 'allow')
    # ActivityScenario owns the first visible launch. Do not cold-launch a WebView only
    # to have am instrument immediately tear that process down during focus delivery.

    def run_test(name, klass='NativeDeviceTest', fixture=None, timeout=180):
        started = time.monotonic()
        selection = f'{PACKAGE}.{klass}' + (f'#{name}' if name else '')
        marker = {'incoming-call': 'incoming-ready', 'incoming-sms': 'incoming-sms-ready'}.get(fixture)
        marker_path = f'/sdcard/Android/data/{PACKAGE}/files/{marker}' if marker else None
        if marker_path:
            adb('shell', 'rm', '-f', marker_path)
        command = ['adb', '-s', serial, 'shell', 'am', 'instrument', '-w', '-r', '-e', 'class', selection, COMPONENT]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            if marker_path:
                deadline = time.monotonic() + 90
                while time.monotonic() < deadline and process.poll() is None:
                    if adb('shell', f'if test -f {marker_path}; then echo ready; fi', check=False).strip() == 'ready':
                        break
                    time.sleep(0.25)
                else:
                    raise RuntimeError('Instrumentation did not signal radio-fixture readiness')
                if fixture == 'incoming-call':
                    output = adb('emu', 'gsm', 'call', '15555215554')
                else:
                    output = adb('emu', 'sms', 'send', '15555215554', 'OguzDows_emulator_inbound')
                if 'OK' not in output:
                    raise RuntimeError('Virtual modem injection failed: ' + output)
            output, _ = process.communicate(timeout=timeout)
            (OUT / f'{klass}-{name or "suite"}.txt').write_text(output)
            match = re.search(r'OK \((\d+) tests?\)', output)
            cases = int(match.group(1)) if match else 0
            expected = 5 if klass == 'LauncherDeviceTest' else 3 if klass == 'RepositorySecurityTest' else 1
            passed = process.returncode == 0 and cases == expected and 'FAILURES!!!' not in output and 'INSTRUMENTATION_FAILED' not in output
            record = {'name': f'{klass}.{name or "suite"}', 'passed': passed, 'test_cases': cases,
                      'seconds': round(time.monotonic() - started, 2)}
            evidence['tests'].append(record)
            print(('PASS ' if passed else 'FAIL ') + record['name'], flush=True)
            if not passed:
                print(output[-16000:], flush=True)
                concise = [line for line in output.splitlines()
                           if not line.startswith(('\tat ', '    at ')) or 'at org.oguzdows.mobile.' in line]
                failures = [line for line in concise if 'AssertionError' in line or 'Exception:' in line]
                if failures: record['failure'] = failures[0][-400:]
                annotation('error', 'Emulator ' + record['name'], '\n'.join(concise)[-3000:])
                # A system ANR dialog can cover every later test without producing an ANR
                # instrumentation result. Capture the real trace, not a blind retry/time increase.
                events = adb('logcat', '-b', 'events', '-d', '-s', 'am_anr', check=False)
                if PACKAGE in events:
                    anr = adb('shell', 'dumpsys', 'activity', 'lastanr', check=False)
                    dropbox = adb('shell', 'dumpsys', 'dropbox', '--print', 'data_app_anr', check=False)
                    (OUT / f'{klass}-{name or "suite"}-anr.txt').write_text(events + '\n' + anr + '\n' + dropbox)
                    # Only a disposable emulator's app main-thread diagnostic is surfaced.
                    main_stack = re.search(r'"main"[^\n]*\n[\s\S]{0,2800}', dropbox)
                    annotation('error', 'Emulator main-thread ANR', main_stack.group() if main_stack else (events + '\n' + anr)[:2800])
                    evidence['passed'] = False
                    raise SystemExit('App ANR: abort incomplete acceptance; no package. Inspect the recorded main-thread trace.')
            if klass == 'LauncherDeviceTest' and passed:
                # Bounded visual diagnostic from a disposable emulator, not personal device data.
                # Chunk below the checks-message cap; full-resolution screenshots stay in the artifact.
                for line in output.splitlines():
                    if 'NATIVE_LAUNCHER_PREVIEW ' not in line:
                        continue
                    encoded = line.split('NATIVE_LAUNCHER_PREVIEW ', 1)[1].strip()
                    if not re.fullmatch(r'[A-Za-z0-9+/=]{1,28000}', encoded):
                        continue
                    pieces = [encoded[i:i + 3400] for i in range(0, len(encoded), 3400)]
                    for index, piece in enumerate(pieces):
                        annotation('notice', f'Native launcher preview {index + 1:02}/{len(pieces):02}', piece)
            if klass == 'LiveRepositoryTest':
                for line in output.splitlines():
                    if 'LIVE_REPO_EVIDENCE ' in line:
                        try: evidence['live_repository'] = json.loads(line.split('LIVE_REPO_EVIDENCE ', 1)[1])
                        except json.JSONDecodeError: pass
                    if line.startswith('APK_REVIEW '): evidence['live_apk_review'] = line
        except Exception as error:
            process.kill(); output, _ = process.communicate(timeout=15)
            (OUT / f'{klass}-{name or "suite"}.txt').write_text(output + '\n' + str(error))
            evidence['tests'].append({'name': f'{klass}.{name or "suite"}', 'passed': False, 'test_cases': 0, 'error': str(error)})
            print(f'FAIL {klass}.{name}: {error}\n{output[-10000:]}', flush=True)
            annotation('error', f'Emulator {klass}.{name or "suite"}', str(error) + '\n' + output[-2500:])
        finally:
            # Only known virtual fixture calls are cleared, and only after the emulator guard above.
            for number in ('5551234', '15555215554'):
                adb('emu', 'gsm', 'cancel', number, check=False)
            (OUT / 'evidence.json').write_text(json.dumps(evidence, indent=2))

    run_test('bundledBridgeRolesValidationAndIsolation')
    run_test('paidActionsRequireFinalNativeConsent')
    run_test('systemVolumeBrightnessAndNativeThemeAreReal')
    run_test('incomingSmsUsesTheRealProviderAndRichInbox', fixture='incoming-sms')
    run_test('outgoingSmsWaitsForActualSentCallback')
    run_test('outgoingCallUsesTelecomAndOurInCallService')
    run_test('incomingCallCanBeAnsweredMutedAndEndedInOurUi', fixture='incoming-call')
    run_test('localApkReviewCancelAndSystemInstall')
    # Keep the original communications/installer acceptance on its original task setup;
    # native HOME is a separate role and task, qualified immediately before its own tests.
    adb('shell', 'cmd', 'role', 'add-role-holder', '--user', '0', 'android.app.role.HOME', PACKAGE)
    if PACKAGE not in adb('shell', 'cmd', 'role', 'get-role-holders', '--user', '0', 'android.app.role.HOME'):
        raise RuntimeError('HOME: app did not qualify for the real platform role')
    run_test('', klass='LauncherDeviceTest', timeout=300)
    run_test('', klass='RepositorySecurityTest')
    run_test('', klass='LiveRepositoryTest', timeout=480)
    adb('pull', f'/sdcard/Android/data/{PACKAGE}/files/evidence', str(OUT / 'screenshots'), check=False)
    # Dedicated emulator contains only fixture data, but keep the diagnostic narrowly scoped to app crashes.
    crash = adb('logcat', '-b', 'crash', '-d', '-t', '300', check=False)
    (OUT / 'crash-buffer.txt').write_text(crash)
    evidence['passed'] = (all(item['passed'] for item in evidence['tests']) and len(evidence['tests']) == 11
                          and sum(item['test_cases'] for item in evidence['tests']) == 17)
    (OUT / 'evidence.json').write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))
    annotation('notice', 'Mobile emulator evidence', json.dumps(evidence, separators=(',', ':')))
    return 0 if evidence['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
