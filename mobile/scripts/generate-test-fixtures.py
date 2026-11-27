#!/usr/bin/env python3
"""Generate ephemeral signed/tampered repo fixtures; no production signing key or remote data.

Requires a JDK (keytool, jarsigner) and the inert :fixture:assembleDebug output.
All outputs are ignored build assets and are packaged ONLY in the instrumentation APK.
"""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'android/app/build/generated/test-assets/generated'


def run(*args):
    subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def main():
    fixture = ROOT / 'android/fixture/build/outputs/apk/debug/fixture-debug.apk'
    if not fixture.is_file():
        raise SystemExit('Build the inert fixture first: ./gradlew :fixture:assembleDebug')
    OUT.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time() * 1000)
    package = {
        'versionName': '1.0', 'versionCode': 1, 'apkName': 'org.oguzdows.fixture_1.apk',
        'hash': hashlib.sha256(fixture.read_bytes()).hexdigest(), 'hashType': 'sha256',
        'size': fixture.stat().st_size, 'minSdkVersion': 29, 'targetSdkVersion': 35,
        'nativecode': [],
    }
    incompatible = [dict(package, versionCode=101, minSdkVersion=999),
                    dict(package, versionCode=102, maxSdkVersion=10),
                    dict(package, versionCode=103, antiFeatures=['KnownVuln']),
                    dict(package, versionCode=104, nativecode=['not-a-real-abi'])]
    index = {'repo': {'timestamp': timestamp},
             'apps': [{'packageName': 'org.oguzdows.fixture', 'name': 'Fixture',
                       'summary': 'Never a live store entry', 'license': 'MIT',
                       'localized': {'tr-TR': {'name': 'Rıfkı test paketi', 'summary': 'Yalnız imza ve geri alma testi'}}}],
             'packages': {'org.oguzdows.fixture': incompatible + [package]}}
    payload = json.dumps(index, ensure_ascii=False).encode()
    (OUT / 'index.json').write_bytes(payload)
    older = dict(index, repo={'timestamp': timestamp - 10000})
    (OUT / 'rollback.json').write_text(json.dumps(older, ensure_ascii=False))
    with tempfile.TemporaryDirectory(prefix='oguzdows-test-key-') as temporary:
        directory = Path(temporary)
        key = directory / 'fixture.p12'
        password = 'public-test-fixture-only'
        run('keytool', '-genkeypair', '-alias', 'fixture', '-keyalg', 'RSA', '-keysize', '2048',
            '-validity', '30', '-dname', 'CN=OguzDows TEST ONLY, O=NOT A PRODUCTION KEY',
            '-storetype', 'PKCS12', '-keystore', str(key), '-storepass', password, '-noprompt')
        cert = directory / 'certificate.der'
        run('keytool', '-exportcert', '-alias', 'fixture', '-keystore', str(key),
            '-storepass', password, '-file', str(cert))
        fingerprint = hashlib.sha256(cert.read_bytes()).hexdigest()
        jar = OUT / 'signed-index.jar'
        with zipfile.ZipFile(jar, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('index-v1.json', payload)
        run('jarsigner', '-keystore', str(key), '-storepass', password,
            '-sigalg', 'SHA256withRSA', '-digestalg', 'SHA-256', str(jar), 'fixture')
        with zipfile.ZipFile(jar) as original, zipfile.ZipFile(OUT / 'tampered-index.jar', 'w', compression=zipfile.ZIP_DEFLATED) as changed:
            for item in original.infolist():
                content = original.read(item.filename)
                if item.filename == 'index-v1.json':
                    content = content.replace(b'Fixture', b'Altered')
                changed.writestr(item.filename, content)
        with zipfile.ZipFile(OUT / 'unsigned-index.jar', 'w') as unsigned:
            unsigned.writestr('index-v1.json', payload)
        (OUT / 'metadata.json').write_text(json.dumps({'certificateSha256': fingerprint,
            'apkSha256': package['hash'], 'timestamp': timestamp, 'productionAnchor': False}, indent=2))
    shutil.copyfile(fixture, OUT / 'fixture.apk')
    print('Generated signed/wrong-pin/tampered/unsigned/rollback fixtures and inert APK; ephemeral key destroyed.')


if __name__ == '__main__':
    main()
