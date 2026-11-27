"""Synthetic rule tests only, never Android/runtime or physical interoperability evidence."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'mobile/scripts'
sys.path.insert(0, str(SCRIPTS))
import acceptance


def synthetic_build():
    return {'source_sha': 'a' * 40, 'java_test_classes': dict(acceptance.UNIT_CLASSES),
            'java_unit_tests': dict(tests=20, failures=0, errors=0, skipped=0), 'lint': {'Warning': 47},
            'assembled': [{'file': path, 'bytes': 1, 'sha256': 'b' * 64} for path in acceptance.APK_PATHS]}


def synthetic_device():
    # Real, preexisting JPEG bytes are just the hash/format fixture for this pure rule test.
    frame = (ROOT / 'mobile/screenshots/launcher-native-emulator.jpg').read_bytes()
    peer = dict(protocol=1, native_host_python_client=True, python_host_native_client=True,
                pinned_tls=True, sha256_verified=True, physical_devices=False, files_verified=4,
                file_sha256={name: acceptance.sha256(data) for name, data in acceptance.INTEROP_PAYLOADS.items()})
    return {'source_sha': 'a' * 40, 'sdk': '35', 'abi': 'x86_64', 'emulator_only': True,
            'physical_sim_tested': False, 'emergency_calls_tested': False, 'gms_certification_tested': False,
            'mms_rcs_supported': False, 'product_anr_detected': False, 'product_crash_detected': False,
            'tests': [dict(name=name, passed=True, test_cases=cases, seconds=1.25) for name, cases in acceptance.SELECTIONS.items()],
            'device_bridge': copy.deepcopy(peer), 'native_device_bridge': copy.deepcopy(peer),
            'screen_capture': dict(media_projection_consent=True, cancel_tested=True, foreground_service=True,
                                   fixture_only=True, remote_input=False, stop_tested=True,
                                   frame_bytes=len(frame), sha256=acceptance.sha256(frame)),
            'live_repository': dict(apps=1, compatible=1, source='https://f-droid.org/repo'),
            'live_apk_review': 'APK_REVIEW inert.fixture sha256=' + 'c' * 64 + ' installed=false'}, frame


class AcceptanceRulesTests(unittest.TestCase):
    def test_complete_synthetic_reports_exercise_the_rules_not_a_device(self):
        report, frame = synthetic_device()
        acceptance.validate_build(synthetic_build(), 'a' * 40)
        acceptance.validate_emulator(report, 'a' * 40, frame)
        self.assertEqual((len(acceptance.SELECTIONS), sum(acceptance.SELECTIONS.values())), (15, 24))
        self.assertEqual(sum(acceptance.UNIT_CLASSES.values()), 20)

    def test_assembly_and_previous_17_case_baseline_cannot_pass_connected_gate(self):
        report, frame = synthetic_device()
        report['tests'] = [test for test in report['tests'] if not test['name'].startswith(('ConnectedDeviceTest.', 'BridgeDeviceTest.'))]
        with self.assertRaisesRegex(ValueError, '15 unique'):
            acceptance.validate_emulator(report, 'a' * 40, frame)
        build = synthetic_build(); build['java_test_classes'].pop('org.oguzdows.mobile.ConnectedRulesTest')
        with self.assertRaises(ValueError): acceptance.validate_build(build, 'a' * 40)

    def test_duplicate_missing_failed_skipped_or_zero_case_native_selections_fail_closed(self):
        for mutate in (lambda tests: tests.append(tests[0]), lambda tests: tests.pop(),
                       lambda tests: tests.__setitem__(0, dict(tests[1])),
                       lambda tests: tests[0].update(passed=False), lambda tests: tests[0].update(test_cases=0),
                       lambda tests: tests[0].update(test_cases=True), lambda tests: tests[0].update(error='fixture failed')):
            report, frame = synthetic_device(); mutate(report['tests'])
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                acceptance.validate_emulator(report, 'a' * 40, frame)

    def test_missing_capture_consent_cancel_stop_or_actual_file_cannot_pass(self):
        for field in ('screen_capture', 'media_projection_consent', 'cancel_tested', 'stop_tested', 'foreground_service', 'fixture_only'):
            report, frame = synthetic_device()
            if field == 'screen_capture': report.pop(field)
            else: report['screen_capture'].pop(field)
            with self.subTest(field=field), self.assertRaises(ValueError):
                acceptance.validate_emulator(report, 'a' * 40, frame)
        report, frame = synthetic_device()
        for actual in (None, b'', b'not an image', frame[:-1], b'\xff\xd8\xff' + b'x' * (512 * 1024)):
            with self.subTest(size=len(actual) if actual is not None else None), self.assertRaises(ValueError):
                acceptance.validate_emulator(report, 'a' * 40, actual)

    def test_both_peer_implementations_must_report_four_real_matching_fixture_hashes(self):
        for key in ('device_bridge', 'native_device_bridge'):
            for field in ('pinned_tls', 'sha256_verified', 'native_host_python_client', 'python_host_native_client', 'files_verified', 'file_sha256'):
                report, frame = synthetic_device(); report[key].pop(field)
                with self.subTest(peer=key, field=field), self.assertRaises(ValueError):
                    acceptance.validate_emulator(report, 'a' * 40, frame)
            report, frame = synthetic_device()
            report[key]['file_sha256']['native-upload.txt'] = '0' * 64
            with self.assertRaises(ValueError): acceptance.validate_emulator(report, 'a' * 40, frame)

    def test_app_crash_anr_physical_claims_and_wrong_commit_are_not_waived(self):
        for field in ('product_anr_detected', 'product_crash_detected', 'physical_sim_tested', 'gms_certification_tested', 'emergency_calls_tested'):
            report, frame = synthetic_device(); report[field] = True
            with self.subTest(field=field), self.assertRaises(ValueError):
                acceptance.validate_emulator(report, 'a' * 40, frame)
        report, frame = synthetic_device()
        with self.assertRaises(ValueError): acceptance.validate_emulator(report, 'd' * 40, frame)
        with self.assertRaises(ValueError): acceptance.validate_build(synthetic_build(), 'd' * 40)

    def test_jvm_failures_skips_missing_apks_and_lint_errors_prevent_packaging(self):
        for mutate in (lambda r: r['java_unit_tests'].update(skipped=1), lambda r: r['java_unit_tests'].update(tests=19),
                       lambda r: r['lint'].update(Error=1), lambda r: r['assembled'].pop(),
                       lambda r: r['assembled'][0].update(sha256='not a hash')):
            report = synthetic_build(); mutate(report)
            with self.assertRaises(ValueError): acceptance.validate_build(report, 'a' * 40)
        workflow = (ROOT / '.github/workflows/mobile-emulator.yml').read_text()
        self.assertLess(workflow.index('python3 mobile/scripts/acceptance.py'), workflow.index('mkdir -p test-results/mobile/package'))

    def test_completed_interop_marker_is_checked_before_a_fast_process_exit(self):
        import bridge_fixture
        class Finished:
            def poll(self): return 0
        self.assertEqual(bridge_fixture.wait_for(Finished(), 'synthetic final marker', lambda: 'verified'), 'verified')
        with self.assertRaisesRegex(RuntimeError, 'exited before'):
            bridge_fixture.wait_for(Finished(), 'missing final marker', lambda: False)

    def test_full_success_and_failure_notices_keep_valid_bounded_json(self):
        spec = importlib.util.spec_from_file_location('emulator_smoke_notice_test', SCRIPTS / 'emulator-smoke.py')
        harness = importlib.util.module_from_spec(spec); spec.loader.exec_module(harness)
        report, _ = synthetic_device()
        report['image_fingerprint'] = 'google/sdk_gphone64_x86_64/emu64xa:15/AE3A.240806.043/12960925:userdebug/dev-keys'
        for failed in (False, True):
            if failed:
                for item in report['tests']: item.update(passed=False, error='An intentionally long synthetic error ' * 15, visible_ui='fixture' * 100)
            output = io.StringIO()
            with contextlib.redirect_stdout(output): harness.evidence_notice(report)
            detail = output.getvalue().strip().split('::', 2)[2]
            decoded = json.loads(detail.replace('%0A', '\n').replace('%0D', '\r').replace('%25', '%'))
            self.assertEqual(len(decoded['tests']), 15)
            self.assertLessEqual(len(detail.encode()), 3500)
        self.assertEqual(len(report['device_bridge']['file_sha256']), 4, 'Summary cannot mutate the complete receipt')


if __name__ == '__main__':
    unittest.main()
