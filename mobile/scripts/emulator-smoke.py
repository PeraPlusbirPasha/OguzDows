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
    adb('shell', 'am', 'start', '-n', PACKAGE + '/.HomeActivity')

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
                deadline = time.monotonic() + 40
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
            passed = process.returncode == 0 and bool(re.search(r'OK \(\d+ tests?\)', output)) and 'FAILURES!!!' not in output and 'INSTRUMENTATION_FAILED' not in output
            record = {'name': f'{klass}.{name or "suite"}', 'passed': passed, 'seconds': round(time.monotonic() - started, 2)}
            evidence['tests'].append(record)
            print(('PASS ' if passed else 'FAIL ') + record['name'], flush=True)
            if not passed:
                print(output[-16000:], flush=True)
            if klass == 'LiveRepositoryTest':
                for line in output.splitlines():
                    if 'LIVE_REPO_EVIDENCE ' in line:
                        try: evidence['live_repository'] = json.loads(line.split('LIVE_REPO_EVIDENCE ', 1)[1])
                        except json.JSONDecodeError: pass
                    if line.startswith('APK_REVIEW '): evidence['live_apk_review'] = line
        except Exception as error:
            process.kill(); output, _ = process.communicate(timeout=15)
            (OUT / f'{klass}-{name or "suite"}.txt').write_text(output + '\n' + str(error))
            evidence['tests'].append({'name': f'{klass}.{name or "suite"}', 'passed': False, 'error': str(error)})
            print(f'FAIL {klass}.{name}: {error}\n{output[-10000:]}', flush=True)
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
    run_test('', klass='RepositorySecurityTest')
    run_test('', klass='LiveRepositoryTest', timeout=480)
    adb('pull', f'/sdcard/Android/data/{PACKAGE}/files/evidence', str(OUT / 'screenshots'), check=False)
    # Dedicated emulator contains only fixture data, but keep the diagnostic narrowly scoped to app crashes.
    crash = adb('logcat', '-b', 'crash', '-d', '-t', '300', check=False)
    (OUT / 'crash-buffer.txt').write_text(crash)
    evidence['passed'] = all(item['passed'] for item in evidence['tests']) and len(evidence['tests']) == 10
    (OUT / 'evidence.json').write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence, indent=2))
    return 0 if evidence['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
