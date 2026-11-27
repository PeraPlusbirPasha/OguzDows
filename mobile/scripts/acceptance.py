#!/usr/bin/env python3
"""Fail-closed 0.4 acceptance rules; assembling an APK is not a device/capture pass.

Rules are also unit-tested with explicitly synthetic reports. Only the CI harness supplies
actual instrumentation / peer / MediaProjection evidence and a matching JPEG file.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
UNIT_CLASSES = {
    'org.oguzdows.mobile.PlatformRulesTest': 6,
    'org.oguzdows.mobile.LauncherRulesTest': 7,
    'org.oguzdows.mobile.ConnectedRulesTest': 7,
}
SELECTIONS = {
    **{'NativeDeviceTest.' + name: 1 for name in (
        'bundledBridgeRolesValidationAndIsolation', 'paidActionsRequireFinalNativeConsent',
        'systemVolumeBrightnessAndNativeThemeAreReal', 'incomingSmsUsesTheRealProviderAndRichInbox',
        'outgoingSmsWaitsForActualSentCallback', 'outgoingCallUsesTelecomAndOurInCallService',
        'incomingCallCanBeAnsweredMutedAndEndedInOurUi', 'localApkReviewCancelAndSystemInstall',
    )},
    'LauncherDeviceTest.suite': 5, 'ConnectedDeviceTest.suite': 4,
    'BridgeDeviceTest.nativeTls': 1, 'BridgeDeviceTest.pcArmInterop': 1,
    'BridgeDeviceTest.systemProjection': 1,
    'RepositorySecurityTest.suite': 3, 'LiveRepositoryTest.suite': 1,
}
# Inert fixture bytes, never selected user files. Both implementations independently
# hash the four actual transfers; the runner checks that their receipts agree.
INTEROP_PAYLOADS = {
    'native-to-desktop.txt': b'native-host to desktop-client fixture\n',
    'desktop-upload.txt': b'desktop-client to native-host fixture\n',
    'desktop-to-native.txt': b'desktop-host to native-client fixture\n',
    'native-upload.txt': b'native-client to desktop-host fixture\n',
}
APK_PATHS = (
    'app/build/outputs/apk/debug/app-debug.apk',
    'app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk',
    'fixture/build/outputs/apk/debug/fixture-debug.apk',
)


def require(condition, reason):
    if not condition:
        raise ValueError('Acceptance refused: ' + reason)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def valid_hash(value):
    return isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value) is not None


def validate_build(report, source_sha):
    require(report.get('source_sha') == source_sha, 'build source is not this checkout')
    require(report.get('java_test_classes') == UNIT_CLASSES, 'all three JVM suites / 20 cases are mandatory')
    tests = report.get('java_unit_tests', {})
    require(type(tests.get('tests')) is int and tests['tests'] == sum(UNIT_CLASSES.values()), 'JVM case count')
    require(all(tests.get(key) == 0 for key in ('failures', 'errors', 'skipped')), 'JVM failure / skip')
    require(not any(report.get('lint', {}).get(key, 0) for key in ('Error', 'Fatal')), 'lint errors are not waived')
    files = report.get('assembled', [])
    require(len(files) == len(APK_PATHS) and {item.get('file') for item in files} == set(APK_PATHS), 'three actual APKs')
    for item in files:
        require(type(item.get('bytes')) is int and item['bytes'] > 0 and valid_hash(item.get('sha256')), 'APK hash / size')


def validate_emulator(report, source_sha, frame):
    require(report.get('source_sha') == source_sha, 'device source is not this checkout')
    require(report.get('sdk') == '35' and report.get('abi') == 'x86_64' and report.get('emulator_only') is True,
            'disposable API35 x86_64 emulator scope')
    for key in ('physical_sim_tested', 'emergency_calls_tested', 'gms_certification_tested', 'mms_rcs_supported',
                'product_anr_detected', 'product_crash_detected'):
        require(report.get(key) is False, 'missing / unexpected scope or app health: ' + key)
    tests = report.get('tests', [])
    require(len(tests) == len(SELECTIONS) and {item.get('name') for item in tests} == set(SELECTIONS),
            'all 15 unique native selections are mandatory')
    for item in tests:
        require(item.get('passed') is True and type(item.get('test_cases')) is int
                and item['test_cases'] == SELECTIONS[item['name']] and not item.get('failure') and not item.get('error'),
                'failed / empty / skipped / wrong native case count: ' + item['name'])
    expected_hashes = {name: sha256(data) for name, data in INTEROP_PAYLOADS.items()}
    for key in ('device_bridge', 'native_device_bridge'):
        peer = report.get(key, {})
        require(type(peer.get('protocol')) is int and peer['protocol'] == 1, 'missing protocol receipt: ' + key)
        for flag in ('native_host_python_client', 'python_host_native_client', 'pinned_tls', 'sha256_verified'):
            require(peer.get(flag) is True, 'missing bidirectional peer proof: ' + key + '.' + flag)
        require(peer.get('physical_devices') is False and type(peer.get('files_verified')) is int
                and peer['files_verified'] == 4 and peer.get('file_sha256') == expected_hashes,
                'four independent inert-file hashes / virtual transport scope: ' + key)
    capture = report.get('screen_capture', {})
    for key in ('media_projection_consent', 'cancel_tested', 'foreground_service', 'fixture_only', 'stop_tested'):
        require(capture.get(key) is True, 'missing real capture proof: ' + key)
    require(capture.get('remote_input') is False, 'capture cannot claim input authority')
    require(isinstance(frame, bytes) and 0 < len(frame) <= 512 * 1024 and frame.startswith(b'\xff\xd8\xff'),
            'actual bounded JPEG capture file is required')
    require(type(capture.get('frame_bytes')) is int and capture['frame_bytes'] == len(frame)
            and capture.get('sha256') == sha256(frame), 'captured TLS frame file / receipt mismatch')
    repository = report.get('live_repository', {})
    require(type(repository.get('apps')) is int and repository['apps'] > 0
            and type(repository.get('compatible')) is int and repository['compatible'] > 0
            and repository.get('source') == 'https://f-droid.org/repo', 'live signed repository receipt')
    review = report.get('live_apk_review', '')
    require(isinstance(review, str) and 'installed=false' in review
            and re.search(r'sha256=[a-f0-9]{64}(?:\s|$)', review) is not None, 'real APK review, not silent installation')


def main():
    folder = ROOT / 'test-results/mobile'
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    build = json.loads((folder / 'build.json').read_text())
    device = json.loads((folder / 'emulator/evidence.json').read_text())
    frame = (folder / 'emulator/connected-real-mediaprojection.jpg').read_bytes()
    validate_build(build, head)
    validate_emulator(device, head, frame)
    require(device.get('passed') is True, 'harness did not pass')
    for item in build['assembled']:
        path = ROOT / 'mobile/android' / item['file']
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        require(path.stat().st_size == item['bytes'] and digest == item['sha256'], 'APK changed after SDK tests')
    receipt = {'source_sha': head, 'passed': True, 'native_cases': sum(SELECTIONS.values()),
               'jvm_cases': sum(UNIT_CLASSES.values()), 'interop_files': 4, 'real_capture_sha256': sha256(frame),
               'physical_devices_tested': False, 'rom_or_gms_certification': False}
    (folder / 'acceptance.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print('::notice title=Mobile complete acceptance::' + json.dumps(receipt, separators=(',', ':')))


if __name__ == '__main__':
    main()
