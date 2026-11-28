#!/usr/bin/env python3
"""GET-only bridge for GitHub's draft-release permission limitation.

A separate job needs contents:write just to GET a private draft. It exports NO
GitHub token: only short-lived, asset-scoped, read-only signed download URLs in
a one-day Actions artifact. The independent image auditor has contents:read.
URLs are never included in notices, source control, or durable release receipts.
The publication collector must recheck live Release metadata after the audit;
a snapshot is explicitly NOT a second live API read by the read-only auditor.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

RELEASE_FIELDS = ('id', 'tag_name', 'target_commitish', 'body', 'draft', 'prerelease')
ASSET_FIELDS = ('id', 'name', 'size', 'digest', 'state', 'browser_download_url', 'url')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def snapshot(release):
    return {**{key: release[key] for key in RELEASE_FIELDS},
            'assets': sorted([{key: item[key] for key in ASSET_FIELDS} for item in release['assets']],
                             key=lambda item: item['name'])}


def snapshot_hash(release):
    value = snapshot(release)
    # GitHub uses /untagged-<20hex>/ in private draft browser routes and replaces
    # it with the real tag on publication. Bind stable API asset IDs/URLs and all
    # hashes/sizes instead; validate_snapshot checks the browser route separately.
    for item in value['assets']:
        item.pop('browser_download_url')
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     separators=(',', ':')).encode()).hexdigest()


def signed_url_expiry(url, now):
    """Reject other origins, write SAS permissions, and excessive lifetimes."""
    try:
        parsed = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qs(parsed.query, strict_parsing=True)
        expires = datetime.fromisoformat(query['se'][0].replace('Z', '+00:00')).timestamp()
        valid = (parsed.scheme == 'https' and parsed.netloc == 'release-assets.githubusercontent.com'
                 and not parsed.username and not parsed.password and not parsed.fragment
                 and parsed.path.startswith('/github-production-release-asset/')
                 and query.get('sp') == ['r'] and len(query['se']) == 1
                 and query.get('sig') and 0 < expires - now <= 3700)
    except (KeyError, TypeError, ValueError, OverflowError):
        valid = False
    if not valid:
        # Never include the capability in a URL validation exception.
        raise ValueError('Geçerli, kısa ömürlü, yalnız dosya okuma URL’si gerekli.')
    return expires


def asset_read_url(asset):
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token:
        raise ValueError('Taslak üstverisini GET eden yardımcı için GitHub token gerekli.')
    request = urllib.request.Request(asset['url'], headers={
        'Accept': 'application/octet-stream', 'Authorization': 'Bearer ' + token,
        'User-Agent': 'OguzDows-GET-only-draft-bridge'})
    try:
        try:
            response = urllib.request.build_opener(NoRedirect).open(request, timeout=60)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            if response.status not in (302, 307) or not response.headers.get('Location'):
                raise ValueError('Dosyaya özgü GET yönlendirmesi alınamadı.')
            url = response.headers['Location']
            signed_url_expiry(url, time.time())
            return url
    except (OSError, ValueError):
        raise ValueError('Taslak dosyası için yalnız okuma erişimi alınamadı: ' + asset['name']) from None


def validate_snapshot(release, *, repository, names):
    assets = release.get('assets', [])
    if (len(assets) != len(names) or {item.get('name') for item in assets} != set(names)
            or len({item.get('id') for item in assets}) != len(names)):
        raise ValueError('Tam ve benzersiz ARM taslak dosya listesi gerekli.')
    prefix = 'https://api.github.com/repos/' + repository + '/releases/assets/'
    browser_prefix = 'https://github.com/' + repository + '/releases/download/'
    route_tag = re.escape(release['tag_name'])
    if release.get('draft') is True:
        route_tag = '(?:' + route_tag + '|untagged-[0-9a-f]{20})'
    route_tags = set()
    for item in assets:
        browser = item.get('browser_download_url', '')
        pattern = re.escape(browser_prefix) + '(' + route_tag + ')/' + re.escape(item['name'])
        match = re.fullmatch(pattern, browser)
        if (type(item.get('id')) is not int or item['id'] <= 0
                or type(item.get('size')) is not int or item['size'] <= 0
                or item.get('state') != 'uploaded'
                or not re.fullmatch('sha256:[0-9a-f]{64}', item.get('digest', ''))
                or item.get('url') != prefix + str(item['id']) or not match):
            raise ValueError('Taslak dosya kimliği / hash / API adresi geçersiz.')
        route_tags.add(match.group(1))
    if len(route_tags) != 1:
        raise ValueError('Taslak dosyalarının tarayıcı rotası tek olmalı.')


def create_grant(release, path, *, repository, names):
    validate_snapshot(release, repository=repository, names=names)
    issued = int(time.time())
    urls = {item['name']: asset_read_url(item) for item in release['assets']}
    grant = {'schema': 1, 'kind': 'asset-scoped-read-only-draft-GET', 'repository': repository,
             'issued_at': issued, 'expires_at': min(signed_url_expiry(url, issued) for url in urls.values()),
             'release': snapshot(release), 'snapshot_sha256': snapshot_hash(release), 'urls': urls}
    path.parent.mkdir(parents=True, exist_ok=True)
    # No bearer credential is persisted. This file is an expiring read capability,
    # not publication evidence; only upload it as a short-retention Actions artifact.
    with path.open('x', encoding='utf-8') as output:
        os.chmod(path, 0o600)
        json.dump(grant, output, ensure_ascii=True)
        output.write('\n')
    return grant


def load_grant(path, *, repository, names):
    if path.stat().st_size > 256 * 1024:
        raise ValueError('Taslak okuma erişim belgesi çok büyük.')
    grant = json.loads(path.read_text())
    now = time.time()
    if (grant.get('schema') != 1 or grant.get('kind') != 'asset-scoped-read-only-draft-GET'
            or grant.get('repository') != repository or not isinstance(grant.get('issued_at'), (int, float))
            or not isinstance(grant.get('expires_at'), (int, float))
            or not 0 <= now - grant['issued_at'] <= 3600 or not now < grant['expires_at'] <= now + 3700
            or set(grant.get('urls', {})) != set(names)):
        raise ValueError('Taslak okuma erişimi yanlış kapsamlı veya süresi geçmiş.')
    validate_snapshot(grant['release'], repository=repository, names=names)
    if grant.get('snapshot_sha256') != snapshot_hash(grant['release']):
        raise ValueError('Taslak üstveri snapshot hash’i eşleşmedi.')
    for url in grant['urls'].values():
        if signed_url_expiry(url, now) < grant['expires_at']:
            raise ValueError('Okuma URL’si belge ömründen önce sona eriyor.')
    return grant


def download(grant, destination):
    """GET all exact assets, with no Authorization header and no API writes."""
    destination.mkdir(parents=True, exist_ok=False)
    for item in grant['release']['assets']:
        url = grant['urls'][item['name']]
        signed_url_expiry(url, time.time())
        # Defence in depth for Actions debug/error output, never a durable notice.
        print('::add-mask::' + url, flush=True)
        request = urllib.request.Request(url, headers={'User-Agent': 'OguzDows-read-only-image-audit'})
        path = destination / item['name']
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=180) as response, path.open('xb') as output:
                if response.status != 200:
                    raise ValueError('Dosya GET yanıtı başarılı değil.')
                digest, count = hashlib.sha256(), 0
                while chunk := response.read(1024 * 1024):
                    count += len(chunk)
                    if count > item['size']:
                        raise ValueError('Dosya beklenen üstveri boyutunu aşıyor.')
                    digest.update(chunk)
                    output.write(chunk)
            if count != item['size'] or 'sha256:' + digest.hexdigest() != item['digest']:
                raise ValueError('GET dosyası beklenen hash / boyutla eşleşmiyor.')
        except (OSError, ValueError):
            path.unlink(missing_ok=True)
            raise ValueError('Bağımsız taslak dosyası GET / hash doğrulaması başarısız: ' + item['name']) from None
        print('Salt okunur GET / hash tamam: ' + item['name'], flush=True)
