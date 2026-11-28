#!/usr/bin/env python3
"""Relay exact public CI JSON bytes as small ASCII annotations, GET/download only.

No artifact Python/shell is executed. This is a fallback when an API consumer
cannot access Actions' ZIP host or its text transport mangles Unicode escapes.
No token, signed download URL, arbitrary artifact or arbitrary file is emitted.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

KINDS = {
    'native-arm64-appearance': ('.github/workflows/portable.yml', {
        'arm64-appearance-bookworm': 'result.json', 'arm64-appearance-trixie': 'result.json'}),
    'pi-runtime': ('.github/workflows/raspberrypi.yml', {
        'OguzDows-Pi-gunluk-armhf': 'pi-runtime-report.json',
        'OguzDows-Pi-gunluk-arm64': 'pi-runtime-report.json'}),
}


def api(repository, path):
    return json.loads(subprocess.check_output(['gh', 'api', 'repos/' + repository + '/' + path], text=True))


def validate_run(run, *, repository, branch, source, workflow):
    if (run.get('status') != 'completed' or run.get('conclusion') != 'success'
            or run.get('repository', {}).get('full_name') != repository
            or run.get('head_repository', {}).get('full_name') != repository
            or run.get('head_branch') != branch or run.get('head_sha') != source
            or run.get('path') != workflow):
        raise ValueError('Only a successful same-repository/branch/exact-source CI run may be relayed.')


def report_chunks(content, identity):
    if not 0 < len(content) <= 2 * 1024**2:
        raise ValueError('CI JSON report size is out of bounds.')
    report = json.loads(content)
    if not isinstance(report, dict) or report.get('source_revision') != identity['source_revision'] or report.get('errors') != []:
        raise ValueError('CI JSON source/error fields do not match the successful run.')
    encoded = base64.b64encode(content).decode('ascii')
    chunks = [encoded[start:start + 1800] for start in range(0, len(encoded), 1800)]
    # Keep a complete collection retrievable through one <=100 annotation page.
    if len(chunks) > 40:
        raise ValueError('CI JSON report exceeds the small annotation relay budget.')
    return [{**identity, 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
             'part': index, 'parts': len(chunks), 'base64': chunk} for index, chunk in enumerate(chunks)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=int, required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--kind', choices=KINDS, required=True)
    args = parser.parse_args()
    repository, branch = os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_REF_NAME']
    if (args.run <= 0 or not re.fullmatch('[0-9a-f]{40}', args.source)
            or not re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository)):
        parser.error('A numeric run, exact source revision and valid repository are required.')
    workflow, wanted = KINDS[args.kind]
    run = api(repository, 'actions/runs/' + str(args.run))
    validate_run(run, repository=repository, branch=branch, source=args.source, workflow=workflow)
    artifacts = api(repository, f'actions/runs/{args.run}/artifacts?per_page=100')['artifacts']
    for name, filename in wanted.items():
        selected = [item for item in artifacts if item['name'] == name]
        if len(selected) != 1:
            raise ValueError('Exactly one allowlisted evidence artifact is required: ' + name)
        artifact = selected[0]
        if (artifact.get('expired') is not False or artifact.get('workflow_run', {}).get('id') != args.run
                or artifact['workflow_run'].get('head_sha') != args.source
                or not re.fullmatch('sha256:[0-9a-f]{64}', artifact.get('digest', ''))):
            raise ValueError('Evidence artifact source/expiry/digest does not match.')
        directory = Path('.cache/ci-json-relay') / name
        if directory.exists():
            raise ValueError('Do not merge or overwrite a previous artifact extraction.')
        subprocess.run(['gh', 'run', 'download', str(args.run), '--repo', repository,
                        '--name', name, '--dir', str(directory)], check=True)
        paths = list(directory.rglob(filename))
        if (len(paths) != 1 or paths[0].is_symlink() or not paths[0].is_file()
                or not paths[0].resolve().is_relative_to(directory.resolve())
                or not 0 < paths[0].stat().st_size <= 2 * 1024**2):
            raise ValueError('One bounded regular JSON report inside its artifact is required.')
        identity = {'source_run': args.run, 'source_revision': args.source, 'kind': args.kind,
                    'artifact_id': artifact['id'], 'artifact': name, 'artifact_digest': artifact['digest'], 'filename': filename}
        for chunk in report_chunks(paths[0].read_bytes(), identity):
            print('::notice title=CI JSON exact byte relay::' + json.dumps(chunk, ensure_ascii=True, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    main()
