"""Byte-relay integrity/permissions with synthetic JSON, NOT ARM acceptance."""
import base64
import hashlib
import json
import unittest
import zlib

import yaml

from support import ROOT, load

relay = load('read_ci_reports_test', '.github/scripts/read-ci-reports.py')
SOURCE = 'a' * 40


class CiReportReadTests(unittest.TestCase):
    def test_ascii_chunks_preserve_exact_utf8_bytes_not_lossy_annotation_escape_repair(self):
        content = (json.dumps({'source_revision': SOURCE, 'errors': [], 'header': 'Değer, 2 ögeden oluşan dizidir:',
                               'fixture': [{'label': 'İstanbul — Kaçkar / ışık', 'sha256': hashlib.sha256(str(i).encode()).hexdigest()}
                                           for i in range(60)]}, ensure_ascii=False, indent=2) + '\n').encode()
        identity = {'source_revision': SOURCE, 'source_run': 123, 'artifact_id': 456, 'filename': 'result.json'}
        chunks = relay.report_chunks(content, identity)
        self.assertGreater(len(chunks), 1)
        self.assertLessEqual(len(chunks), relay.MAX_REPORT_CHUNKS)
        for index, chunk in enumerate(chunks):
            self.assertEqual(chunk['part'], index)
            self.assertEqual(chunk['parts'], len(chunks))
            self.assertEqual(chunk['bytes'], len(content))
            self.assertEqual(chunk['sha256'], hashlib.sha256(content).hexdigest())
            self.assertEqual(chunk['encoding'], 'zlib-base64')
            self.assertLessEqual(len(json.dumps(chunk)), relay.MAX_NOTICE_BYTES)
            json.dumps(chunk).encode('ascii')
        reconstructed = zlib.decompress(base64.b64decode(''.join(item['base64'] for item in chunks), validate=True))
        self.assertEqual(reconstructed, content)

    def test_both_runtime_sized_reports_fit_actions_ten_notices_per_step_without_truncation(self):
        # Synthetic runtime-sized JSON, not accepted image/runtime evidence.
        content = json.dumps({'source_revision': SOURCE, 'errors': [], 'fixture': {
            f'file-{i}.py': hashlib.sha256(str(i).encode()).hexdigest() for i in range(75)}, 'padding': 'x' * 10000}).encode()
        self.assertGreater(len(content), 15000)
        both = [relay.report_chunks(content, {'source_revision': SOURCE, 'artifact': arch})
                for arch in ('armhf', 'arm64')]
        self.assertLessEqual(sum(map(len, both)), 10)
        self.assertGreater(sum(map(len, both)), 2)
        for chunks in both:
            self.assertEqual(zlib.decompress(base64.b64decode(''.join(item['base64'] for item in chunks), validate=True)), content)
            self.assertTrue(all(len(json.dumps(item)) <= 3000 for item in chunks))
        self.assertLessEqual(max(len(files) for _, files in relay.KINDS.values()) * relay.MAX_REPORT_CHUNKS, 10)

    def test_report_rejects_wrong_source_error_missing_json_or_oversized_annotation_budget(self):
        good = {'source_revision': SOURCE, 'errors': []}
        for value in ({**good, 'source_revision': 'b' * 40}, {**good, 'errors': ['TEST ONLY failure']},
                      {**good, 'errors': None}, [],
                      {**good, 'fixture': ''.join(hashlib.sha256(str(i).encode()).hexdigest() for i in range(300))}):
            with self.subTest(kind=type(value).__name__), self.assertRaises(ValueError):
                relay.report_chunks(json.dumps(value).encode(), {'source_revision': SOURCE})
        for content in (b'', b'not-json', b'x' * (2 * 1024**2 + 1)):
            with self.assertRaises(ValueError):
                relay.report_chunks(content, {'source_revision': SOURCE})
        with self.assertRaises(ValueError):
            relay.report_chunks(json.dumps(good).encode(), {'source_revision': SOURCE, 'artifact': 'x' * 4000})

    def test_run_is_exact_successful_same_repo_branch_and_workflow_not_pr_or_arbitrary_artifact(self):
        good = {'status': 'completed', 'conclusion': 'success', 'head_sha': SOURCE,
                'head_branch': 'test-branch', 'repository': {'full_name': 'test/repo'},
                'head_repository': {'full_name': 'test/repo'}, 'path': '.github/workflows/portable.yml'}
        options = dict(repository='test/repo', branch='test-branch', source=SOURCE, workflow='.github/workflows/portable.yml')
        relay.validate_run(good, **options)
        for change in ({'status': 'in_progress'}, {'conclusion': 'failure'}, {'head_sha': 'b' * 40},
                       {'head_branch': 'main'}, {'head_repository': {'full_name': 'foreign/repo'}},
                       {'path': '.github/workflows/other.yml'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                relay.validate_run({**good, **change}, **options)
        self.assertEqual(set(relay.KINDS), {'native-arm64-appearance', 'pi-runtime'})
        for _, files in relay.KINDS.values():
            self.assertEqual(len(files), 2)
            self.assertLessEqual(set(files.values()), {'result.json', 'pi-runtime-report.json'})

    def test_workflow_has_no_write_permissions_builds_artifact_execution_or_exposed_tokens(self):
        path = ROOT / '.github/workflows/report-read.yml'
        workflow = yaml.safe_load(path.read_text())
        self.assertEqual(workflow['permissions'], {'contents': 'read', 'actions': 'read'})
        job = workflow['jobs']['read']
        self.assertNotIn('permissions', job)
        self.assertEqual(len(job['steps']), 2)
        self.assertFalse(job['steps'][0]['with']['persist-credentials'])
        script = (ROOT / '.github/scripts/read-ci-reports.py').read_text()
        self.assertIn("'--name', name", script)
        self.assertIn('base64.b64encode(zlib.compress(content', script)
        for forbidden in ('gh release', 'git push', 'chroot', 'build-pi.sh', 'shell=True', 'os.system(', 'exec(', 'eval('):
            self.assertNotIn(forbidden, script)
        self.assertNotIn('${{ inputs.', job['steps'][1]['run'])


if __name__ == '__main__':
    unittest.main()
