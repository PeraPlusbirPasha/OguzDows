#!/usr/bin/env python3
"""Two rebuilt Pi images -> a NEW draft, never replace historical v2.0 bytes.

No builds, publication, tags, deletes or clobber. A separate read-only audit
redownloads every asset and repeats image/contract/runtime inspection.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load('arm_refresh_shared_release', 'scripts/release-assets.py')
config = load('arm_refresh_pi_config', 'scripts/configure-pi.py')
draft_read = load('arm_refresh_draft_read', 'scripts/release-draft-read.py')
TAG = 'v2.0-arm2'
VERSION = '2.0'
NAMES = {f'OguzDows-rpi-{arch}.{suffix}' for arch in base.PI_ARCHES
         for suffix in ('img.xz', 'img.xz.sha256', 'packages.txt')}
NAMES |= {'pi-gen.lock.json', 'SHA256SUMS', 'INDIRME-REHBERI.md', 'test-evidence.tar.gz', 'release-manifest.json'}
EVIDENCE = {f'{name}-{arch}.json' for arch in base.PI_ARCHES for name in
            ('pi-runtime-report', 'pi-upstream-audit', 'pi-apt-adaptation', 'collection', 'image-identity', 'pi-contract')}
EVIDENCE.add('native-arm64-xfconf-locale.json')
NATIVE_EVIDENCE = ROOT / 'docs/evidence/arm-xfconf-locale.json'
NATIVE_RUNTIME = ('desktop_preferences.py', 'desktop_runtime.py', 'desktop_material.py', 'wallpapers.py', 'profiles.py')
LOCALE_TRUE = ('single_item_array', 'utf8_value_roundtrip', 'array_read_write_readback', 'typed_backup',
               'compare_rollback', 'persistence_failure_rollback', 'personal_panel_arrays_unchanged', 'persistence_failure_injected')


def validate_locale(receipt, *, reproduced):
    if (not isinstance(receipt, dict) or type(receipt.get('schema')) is not int or receipt['schema'] != 1
            or receipt.get('environment') != {'LANG': 'tr_TR.UTF-8', 'LANGUAGE': 'tr:en', 'LC_ALL': 'tr_TR.UTF-8'}
            or receipt.get('raw_turkish_header') != 'Değer, 2 ögeden oluşan dizidir:'
            or receipt.get('runners') != ['profiles', 'desktop_runtime', 'wallpapers']
            or receipt.get('typed_arrays') != ['int-array', 'double-array']
            or any(receipt.get(key) is not True for key in LOCALE_TRUE)
            or type(receipt.get('unfixed_reader_error_reproduced')) is not bool
            or reproduced and receipt['unfixed_reader_error_reproduced'] is not True
            or receipt.get('unfixed_reader_header') != ('Değer, 4 ögeden oluşan dizidir:'
                if receipt['unfixed_reader_error_reproduced'] else 'Value is an array with 4 items:')
            or receipt.get('settings_backend_mocked') is not False):
        raise ValueError('Türkçe gerçek Xfconf dizi / yedek / geri alma kanıtı geçersiz.')


def validate_native_evidence(data, revision):
    acceptance = data.get('acceptance', {}) if isinstance(data, dict) else {}
    if (not isinstance(data, dict) or type(data.get('schema')) is not int or data['schema'] != 1
            or data.get('scope') != 'native-ARM64-Turkish-Xfce-Welcome-and-real-pixels-not-physical-Pi'
            or not isinstance(acceptance, dict) or acceptance.get('source_revision') != revision
            or acceptance.get('conclusion') != 'success' or type(acceptance.get('run_id')) is not int
            or acceptance['run_id'] <= 0 or not isinstance(acceptance.get('results'), list)
            or len(acceptance['results']) != 2
            or any(not isinstance(item, dict) for item in acceptance['results'])
            or {item.get('suite') for item in acceptance['results']} != {'bookworm', 'trixie'}):
        raise ValueError('Aynı kaynaklı iki taban gerçek ARM64 Türkçe görünüm kabulü gerekli.')
    hashes = {name: base.sha256(ROOT / 'system/usr/lib/oguzdows' / name) for name in NATIVE_RUNTIME}
    for item in acceptance['results']:
        report = item.get('report', {})
        if (item.get('conclusion') != 'success' or type(item.get('job_id')) is not int or item['job_id'] <= 0
                or not isinstance(report, dict) or report.get('source_revision') != revision
                or report.get('scope') != 'private-nonroot-native-Xfce-Welcome-theme-wallpaper-and-root-pixels'
                or report.get('architecture') != 'arm64' or report.get('runtime_sha256') != hashes
                or report.get('locale_probe_sha256') != base.sha256(ROOT / 'scripts/pi_session_smoke.py')
                or report.get('errors') != [] or report.get('synthetic_image_fixture') is not True
                or any(report.get(key) is not False for key in ('physical_pi', 'physical_gpu', 'performance_measurement', 'settings_backend_mocked'))
                or any(report.get(key) is not True for key in ('welcome_theme_callbacks_and_GTK_reload',
                           'welcome_wallpaper_callbacks_and_real_pixels', 'stale_connector_does_not_swallow_change',
                           'randr_failure_injected', 'fallback_real_gdk_helper_and_pixels'))
                or not isinstance(report.get('profile_themes'), dict)
                or set(report['profile_themes']) != {'oguzdows', 'kde', 'gnome', 'xfce', 'windows11', 'mac'}
                or report.get('fixture-red_root_rgb') != [160, 30, 40] or report.get('fixture-blue_root_rgb') != [30, 60, 160]
                or not isinstance(report.get('dark_theme'), str) or not isinstance(report.get('light_theme'), str)
                or report['dark_theme'] == report['light_theme']):
            raise ValueError('ARM64 Türkçe görünüm kaynağı / gerçek callback / piksel kanıtı eşleşmedi.')
        validate_locale(report.get('xfconf_locale'), reproduced=item['suite'] == 'bookworm')


def native_evidence(revision):
    data = base.read_json(NATIVE_EVIDENCE)
    validate_native_evidence(data, revision)
    repository, branch = os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_REF_NAME']
    acceptance = data['acceptance']
    run = base.api(f'repos/{repository}/actions/runs/{acceptance["run_id"]}')
    if (run.get('status') != 'completed' or run.get('conclusion') != 'success'
            or run.get('head_sha') != revision or run.get('head_branch') != branch
            or run.get('path') != '.github/workflows/portable.yml'
            or run.get('repository', {}).get('full_name') != repository
            or run.get('head_repository', {}).get('full_name') != repository):
        raise ValueError('Canlı gerçek ARM64 Türkçe görünüm çalışması kaynakla eşleşmedi.')
    jobs = base.api(f'repos/{repository}/actions/runs/{acceptance["run_id"]}/jobs?per_page=100')['jobs']
    for item in acceptance['results']:
        selected = [job for job in jobs if job['id'] == item['job_id']]
        if (len(selected) != 1 or selected[0]['conclusion'] != 'success'
                or selected[0]['name'] != 'ARM64 · gerçek Xfce tema ve duvar kâğıdı · ' + item['suite'] + ' (kart değil)'):
            raise ValueError('Canlı ARM64 Türkçe görünüm işi kaynak kaydıyla eşleşmedi.')
    artifacts = base.api(f'repos/{repository}/actions/runs/{acceptance["run_id"]}/artifacts?per_page=100')['artifacts']
    selected = [{key: item[key] for key in ('id', 'name', 'size_in_bytes', 'digest')} for item in artifacts
                if item['name'] in ('arm64-appearance-bookworm', 'arm64-appearance-trixie')]
    if (sorted(selected, key=lambda item: item['name']) != sorted(acceptance.get('artifacts', []), key=lambda item: item['name'])
            or any(item['expired'] is not False or item['workflow_run']['head_sha'] != revision for item in artifacts)):
        raise ValueError('Canlı ARM64 Türkçe görünüm artefakt kimlikleri eşleşmedi.')
    return NATIVE_EVIDENCE


def validate_changes(paths):
    for path in paths:
        if path.startswith('website/') or path in ('scripts/release-arm-refresh.py', 'scripts/release-draft-read.py'):
            continue
        base.validate_changes([path])


def source_contract(arch, revision, directory):
    """Trusted unchanged recipe, never Python imported from a mounted image."""
    config.configure(arch, directory)
    path = directory / 'stage-oguzdows/00-desktop/files/overlay/usr/share/oguzdows/pi-contract.json'
    contract = base.read_json(path)
    contract['source_revision'] = revision  # publisher HEAD may differ ONLY in allowlisted docs/tools
    if (contract.get('appearance_runtime_schema') != 1 or contract.get('xfconf_locale_runtime_schema') != 1
            or len(contract['asset_hashes']) != 75):
        raise ValueError('ARM düzeltmesi 75 kaynak/varlık, gerçek görünüm ve Türkçe Xfconf kapısını gerektirir.')
    return contract


def validate_manifest(manifest, *, repository, run_id, release_id, revision):
    previous = base.read_json(ROOT / 'docs/releases/v2.0-release.json')
    previous_arm = base.read_json(ROOT / 'docs/releases/v2.0-arm1-release.json')
    if not isinstance(manifest, dict):
        raise ValueError('ARM düzeltme manifesti nesne olmalı.')
    if (type(manifest.get('schema')) is not int or manifest['schema'] != 1 or manifest.get('kind') != 'oguzdows-arm-refresh'
            or manifest.get('repository') != repository or manifest.get('tag') != TAG
            or manifest.get('product_version') != VERSION or manifest.get('release_id') != release_id
            or manifest.get('source_run_id') != run_id or manifest.get('source_revision') != revision
            or not isinstance(manifest.get('publisher_revision'), str)
            or not re.fullmatch('[0-9a-f]{40}', manifest['publisher_revision'])
            or manifest.get('images_built_in_source_run') is not True
            or any(manifest.get(key) is not False for key in ('images_repacked_by_publisher', 'pc_rebuilt', 'mobile_rebuilt', 'physical_boot'))
            or manifest.get('previous_release') != {'tag': 'v2.0', 'source_revision': previous['source_revision'], 'assets_modified': False}
            or manifest.get('supersedes_arm_release') != {'tag': 'v2.0-arm1', 'source_revision': previous_arm['source_revision'], 'assets_modified': False}
            or not isinstance(manifest.get('files'), dict) or set(manifest['files']) != NAMES - {'release-manifest.json'}
            or not isinstance(manifest.get('evidence_files'), dict) or set(manifest['evidence_files']) != EVIDENCE
            or not isinstance(manifest.get('image_identity'), dict) or set(manifest['image_identity']) != set(base.PI_ARCHES)):
        raise ValueError('ARM düzeltme manifestinin kaynak/kapsam/dosya sözleşmesi geçersiz.')


def inspect(inputs, work, revision, runtime, evidence, *, audit=False):
    identities = {}
    for arch in base.PI_ARCHES:
        expected = source_contract(arch, revision, work / ('config-' + arch))
        report = runtime[arch]
        if (report.get('feature_presence', {}).get('asset_hashes') != 75
                or report.get('full_session', {}).get('appearance', {}).get('settings_backend_mocked') is not False):
            raise ValueError('ARM hedef görünüm işlemi / 75 hash kanıtı eksik: ' + arch)
        validate_locale(report.get('full_session', {}).get('appearance', {}).get('xfconf_locale'), reproduced=True)
        image = (inputs if audit else inputs / ('rpi-' + arch)) / f'OguzDows-rpi-{arch}.img.xz'
        identities[arch] = base.inspect_pi(image, arch, revision, VERSION, work, report, expected_contract=expected)
        if identities[arch]['build'].get('source_dirty') is not False:
            raise ValueError('Yeni ARM imajının kaynak ağacı açıkça temiz olmalı: ' + arch)
        if audit:
            if base.read_json(evidence['pi-contract-' + arch + '.json']) != expected:
                raise ValueError('Yeniden indirilen kaynak sözleşmesi eşleşmedi: ' + arch)
        else:
            for name, value in (('image-identity', identities[arch]), ('pi-contract', expected)):
                path = work / f'{name}-{arch}.json'
                path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
                evidence[path.name] = path
        print('::notice title=ARM salt okunur imaj kimliği::' + json.dumps({'arch': arch, **identities[arch]}, ensure_ascii=True), flush=True)
    return identities


def prepare(inputs, output, *, repository, run_id, release_id, revision, publisher_revision, notes, artifacts):
    output.mkdir(parents=True, exist_ok=False)
    work = output.parent / 'inspection'
    work.mkdir(exist_ok=False)
    sums, evidence = [], {}
    runtime = base.prepare_pi(inputs, output, revision, sums, evidence)
    identities = inspect(inputs, work, revision, runtime, evidence)
    evidence['native-arm64-xfconf-locale.json'] = native_evidence(revision)
    if set(evidence) != EVIDENCE:
        raise ValueError('ARM düzeltme ham kanıt dosya listesi eksik.')
    base.deterministic_bundle(evidence, output / 'test-evidence.tar.gz')
    (output / 'INDIRME-REHBERI.md').write_text(notes)
    (output / 'SHA256SUMS').write_text(''.join(sums))
    previous = base.read_json(ROOT / 'docs/releases/v2.0-release.json')
    previous_arm = base.read_json(ROOT / 'docs/releases/v2.0-arm1-release.json')
    manifest = {'schema': 1, 'kind': 'oguzdows-arm-refresh', 'repository': repository,
                'tag': TAG, 'product_version': VERSION, 'release_id': release_id,
                'source_revision': revision, 'publisher_revision': publisher_revision,
                'source_run_id': run_id, 'source_run_url': f'https://github.com/{repository}/actions/runs/{run_id}',
                'images_built_in_source_run': True, 'images_repacked_by_publisher': False,
                'pc_rebuilt': False, 'mobile_rebuilt': False, 'physical_boot': False,
                'previous_release': {'tag': 'v2.0', 'source_revision': previous['source_revision'], 'assets_modified': False},
                'supersedes_arm_release': {'tag': 'v2.0-arm1', 'source_revision': previous_arm['source_revision'], 'assets_modified': False},
                'source_artifacts': artifacts, 'artifact_digest_scope': 'ZIP archive only; image SHA-256 is in files/SHA256SUMS',
                'image_identity': identities,
                'evidence_files': {name: {'size': path.stat().st_size, 'sha256': base.sha256(path)}
                                   for name, path in sorted(evidence.items())},
                'files': base.inventory(output)}
    validate_manifest(manifest, repository=repository, run_id=run_id, release_id=release_id, revision=revision)
    (output / 'release-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return base.inventory(output)


def unpack_evidence(archive_path, directory, expected):
    if set(expected) != EVIDENCE:
        raise ValueError('Beklenen sabit ARM kanıt listesi gerekli.')
    directory.mkdir(exist_ok=False)
    paths = {}
    with tarfile.open(archive_path, 'r:gz') as archive:
        members = archive.getmembers()
        if (len(members) != len(EVIDENCE) or {item.name for item in members} != EVIDENCE
                or any(not item.isfile() or not 0 < item.size <= 2 * 1024**2 for item in members)):
            raise ValueError('ARM kanıt arşivi sabit, düz, normal ve sınırlı dosyalardan oluşmalı.')
        for item in members:
            with archive.extractfile(item) as stream:
                content = stream.read(2 * 1024**2 + 1)
            path = directory / item.name
            path.write_bytes(content)
            if {'size': len(content), 'sha256': base.sha256(path)} != expected[item.name]:
                raise ValueError('ARM ham kanıt hash/boyutu eşleşmedi: ' + item.name)
            paths[item.name] = path
    return paths


def audit_release(release, work, *, repository, run_id, release_id, revision, notes, artifacts, read_grant=None):
    work.mkdir(parents=True, exist_ok=False)
    downloaded = work / 'download'
    if read_grant is None:
        base.command('gh', 'release', 'download', TAG, '--repo', repository, '--pattern', '*', '--dir', str(downloaded))
    else:
        draft_read.download(read_grant, downloaded)
    manifest = base.read_json(downloaded / 'release-manifest.json')
    validate_manifest(manifest, repository=repository, run_id=run_id, release_id=release_id, revision=revision)
    base.command('git', 'merge-base', '--is-ancestor', manifest['publisher_revision'], 'HEAD')
    if manifest.get('source_artifacts') != artifacts:
        raise ValueError('ARM ZIP kaynak artefakt kimlikleri eşleşmedi.')
    expected = dict(manifest['files'])
    expected['release-manifest.json'] = {'size': (downloaded / 'release-manifest.json').stat().st_size,
                                         'sha256': base.sha256(downloaded / 'release-manifest.json')}
    base.check_remote(release, expected, complete=True)
    if base.inventory(downloaded) != expected or (downloaded / 'INDIRME-REHBERI.md').read_text() != notes:
        raise ValueError('ARM yeniden indirme SHA-256/boyut/sürüm notları eşleşmedi.')
    evidence = unpack_evidence(downloaded / 'test-evidence.tar.gz', work / 'evidence', manifest['evidence_files'])
    native = evidence['native-arm64-xfconf-locale.json']
    validate_native_evidence(base.read_json(native), revision)
    if native.read_bytes() != native_evidence(revision).read_bytes():
        raise ValueError('Yeniden indirilen gerçek ARM64 Türkçe görünüm kanıtı kaynak kaydıyla eşleşmedi.')
    # Independently rerun the original lock/upstream/APT/collection/source
    # checks using only the newly downloaded bytes; hardlinks do not repack.
    inputs = work / 'input'
    for arch in base.PI_ARCHES:
        target = inputs / ('rpi-' + arch)
        target.mkdir(parents=True)
        for suffix in ('img.xz', 'img.xz.sha256', 'packages.txt'):
            name = f'OguzDows-rpi-{arch}.{suffix}'
            os.link(downloaded / name, target / name)
        os.link(downloaded / 'pi-gen.lock.json', target / 'pi-gen.lock.json')
        proof = inputs / 'evidence' / ('OguzDows-Pi-gunluk-' + arch)
        proof.mkdir(parents=True)
        for name in ('pi-runtime-report', 'pi-upstream-audit', 'pi-apt-adaptation', 'collection'):
            os.link(evidence[f'{name}-{arch}.json'], proof / (name + '.json'))
    checked = work / 'checked'
    checked.mkdir()
    sums, raw = [], {}
    runtime = base.prepare_pi(inputs, checked, revision, sums, raw)
    inspection = work / 'inspection'
    inspection.mkdir()
    identities = inspect(downloaded, inspection, revision, runtime, evidence, audit=True)
    for arch, identity in identities.items():
        if identity != manifest['image_identity'][arch] or identity != base.read_json(evidence['image-identity-' + arch + '.json']):
            raise ValueError('Bağımsız salt-okunur ARM imaj kimliği ilk denetimle eşleşmedi: ' + arch)
    sums = []
    for arch in base.PI_ARCHES:
        name = f'OguzDows-rpi-{arch}.img.xz'
        _, _, digest = base.checked_image(downloaded, name)
        sums.append(digest + '  ' + name + '\n')
    if (downloaded / 'SHA256SUMS').read_text() != ''.join(sums):
        raise ValueError('İki ARM birleşik SHA256SUMS listesi eşleşmedi.')
    # GitHub denies private-draft metadata to contents:read. A grant contains
    # the GET-only helper's snapshot, not a pretend second live API response.
    # The separate publication collector MUST compare live metadata afterward.
    current = base.api(f'repos/{repository}/releases/{release_id}') if read_grant is None else read_grant['release']
    base.validate_draft(current, release_id, TAG, revision, notes)
    base.check_remote(current, expected, complete=True)
    base.emit_files(expected)
    print('::notice title=ARM release bağımsız yeniden indirme kabulü::' + json.dumps({
        'release_id': release_id, 'tag': TAG, 'source_run_id': run_id, 'source_revision': revision,
        'publisher_revision': manifest['publisher_revision'], 'asset_count': len(expected), 'evidence_file_count': len(evidence),
        'all_release_assets_redownloaded_and_hashed': True, 'both_images_reinspected_read_only': True,
        'expected_75_source_asset_contracts_matched': True, 'turkish_xfconf_runtime_gate_matched': True,
        'native_ARM64_Turkish_Welcome_evidence_matched': True, 'release_modified': False, 'draft': True,
        'download_access': 'asset-scoped-signed-GET' if read_grant is not None else 'authenticated-release-API',
        'live_draft_metadata_rechecked_inside_audit': read_grant is None,
        'publication_collector_must_recheck_live_metadata': read_grant is not None,
        'draft_snapshot_sha256': draft_read.snapshot_hash(release),
        'physical_boot': False}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=int, required=True)
    parser.add_argument('--release-id', type=int, required=True)
    parser.add_argument('--tag', choices=[TAG], required=True)
    parser.add_argument('--audit', action='store_true')
    parser.add_argument('--create-read-grant', type=Path, help='GET-only helper; never transfer or audit images')
    parser.add_argument('--read-grant', type=Path, help='Expiring asset-only GET access; audit only, no bearer token')
    parser.add_argument('--work', type=Path, default=Path('.cache/arm-release'))
    args = parser.parse_args()
    if (args.create_read_grant and (args.audit or args.read_grant)) or (args.read_grant and not args.audit):
        parser.error('GET erişim yardımcısı aktarım/denetim yapmaz; okuma belgesi yalnız --audit ile kullanılabilir.')
    repository, branch = os.environ['GITHUB_REPOSITORY'], os.environ['GITHUB_REF_NAME']
    if args.run <= 0 or args.release_id <= 0 or not re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        parser.error('Geçerli kaynak çalışma / taslak kimliği / depo gerekli.')
    revision = base.validate_run(base.api(f'repos/{repository}/actions/runs/{args.run}'), args.run, repository, branch, pi=True)
    base.command('git', 'merge-base', '--is-ancestor', revision, 'HEAD')
    validate_changes(base.command('git', 'diff', '--name-only', revision, 'HEAD').splitlines())
    if base.command('git', 'status', '--porcelain', '--untracked-files=normal').strip():
        raise ValueError('ARM yayımlayıcı çalışma ağacı temiz olmalı.')
    notes = (ROOT / 'docs/releases' / (TAG + '.md')).read_text()
    if revision not in notes or f'actions/runs/{args.run}' not in notes:
        raise ValueError('Sürüm notları doğru başarılı ARM çalışması / commit içermeli.')
    endpoint = f'repos/{repository}/releases/{args.release_id}'
    read_grant = draft_read.load_grant(args.read_grant, repository=repository, names=NAMES) if args.read_grant else None
    release = base.api(endpoint) if read_grant is None else read_grant['release']
    base.validate_draft(release, args.release_id, TAG, revision, notes)
    names = ['OguzDows-rpi-' + arch for arch in base.PI_ARCHES] + ['OguzDows-Pi-gunluk-' + arch for arch in base.PI_ARCHES]
    artifacts = base.validate_artifacts(base.api(f'repos/{repository}/actions/runs/{args.run}/artifacts?per_page=100'), names, args.run, revision)
    if args.create_read_grant:
        grant = draft_read.create_grant(release, args.create_read_grant, repository=repository, names=NAMES)
        current = base.api(endpoint)
        base.validate_draft(current, args.release_id, TAG, revision, notes)
        if draft_read.snapshot_hash(current) != grant['snapshot_sha256']:
            raise ValueError('Taslak üstverisi GET erişimi oluşturulurken değişti.')
        print('::notice title=ARM draft GET-only access snapshot::' + json.dumps({
            'release_id': args.release_id, 'tag': TAG, 'source_revision': revision,
            'asset_count': len(current['assets']), 'snapshot_sha256': grant['snapshot_sha256'],
            'asset_read_only': True, 'bearer_token_exported': False, 'release_modified': False,
            'max_lifetime_seconds': 3700, 'draft': True}), flush=True)
        return
    if args.audit:
        audit_release(release, args.work, repository=repository, run_id=args.run, release_id=args.release_id,
                      revision=revision, notes=notes, artifacts=artifacts, read_grant=read_grant)
        return
    args.work.mkdir(parents=True, exist_ok=False)
    inputs, output = args.work / 'input', args.work / 'upload'
    for name in names:
        destination = inputs / ('evidence/' + name if name.startswith('OguzDows-Pi-gunluk-') else name.removeprefix('OguzDows-'))
        base.command('gh', 'run', 'download', str(args.run), '--repo', repository, '--name', name, '--dir', str(destination))
    expected = prepare(inputs, output, repository=repository, run_id=args.run, release_id=args.release_id,
                       revision=revision, publisher_revision=base.command('git', 'rev-parse', 'HEAD').strip(), notes=notes, artifacts=artifacts)
    release = base.api(endpoint)
    base.validate_draft(release, args.release_id, TAG, revision, notes)
    missing = base.check_remote(release, expected, complete=False)
    for name in sorted(missing):
        base.command('gh', 'release', 'upload', TAG, str(output / name), '--repo', repository)
    release = base.api(endpoint)
    base.validate_draft(release, args.release_id, TAG, revision, notes)
    base.check_remote(release, expected, complete=True)
    base.emit_files(expected)
    print('::notice title=ARM düzeltme taslağı doğrulandı::' + json.dumps({
        'release_id': args.release_id, 'tag': TAG, 'draft': True, 'source_revision': revision,
        'source_run_id': args.run, 'asset_count': len(expected), 'historical_v2_assets_modified': False}), flush=True)


if __name__ == '__main__':
    main()
