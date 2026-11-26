"""Sabit, imzalı Flathub kullanıcı kaynağı; içe aktarırken ağ işlemi yok."""
import re
import subprocess

FLATHUB_DESCRIPTOR = 'https://dl.flathub.org/repo/flathub.flatpakrepo'
FLATHUB_URL = 'https://dl.flathub.org/repo/'


def run(command):
    result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                            text=True, errors='replace', timeout=180, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr[-2500:] or 'Mağaza işlemi tamamlanamadı.')
    return result.stdout.rstrip('\r\n')


def remote_state(listing):
    """Distinguish absent, disabled and usable; never bless a disabled remote.

    A conflicting name/URL or disabled signature check is NOT auto-repaired.
    Only an explicitly approved, official signed-but-disabled remote is enabled.
    """
    found = []
    for line in listing.splitlines():
        columns = line.split('\t')
        if columns[0] != 'flathub':
            continue
        # Flatpak may emit an empty final options column. Older callers used
        # strip(), which removed its trailing tab; that is still a valid row.
        if len(columns) not in (2, 3) or columns[1].rstrip('/') != FLATHUB_URL.rstrip('/'):
            raise ValueError('Flathub adı farklı bir kaynağa ait. Otomatik değiştirilmedi; Yazılım Depoları bölümünü kontrol edin.')
        options = set(re.split(r'[,;\s]+', columns[2] if len(columns) == 3 else ''))
        if 'no-gpg-verify' in options:
            raise ValueError('Flathub imza denetimi kapalı. İmzasız kaynak otomatik değiştirilmedi.')
        found.append('disabled' if 'disabled' in options else 'ready')
    if len(found) > 1:
        raise ValueError('Birden çok Flathub kaydı var; belirsiz kaynak otomatik değiştirilmedi.')
    return found[0] if found else 'missing'


def official_remote(listing):
    return remote_state(listing) == 'ready'


def setup_flathub(execute=run):
    try:
        architecture = execute(['/usr/bin/flatpak', '--default-arch'])
    except FileNotFoundError as error:
        raise ValueError('Flatpak kurulu değil. Mağaza → Kaynaklar → Flatpak bileşenlerini kur / tamamla ile önce sistem planını onaylayın.') from error
    if architecture not in ('x86_64', 'aarch64'):
        raise ValueError('Bu mimaride Flathub kapsamı doğrulanmadı. Sistem (APT) uygulamaları mağazada kullanılabilir; i386 / armhf için 64 bit uygulama kurulmaz.')
    command = ['/usr/bin/flatpak', '--user', 'remotes', '--columns=name,url,options']
    state = remote_state(execute(command))
    if state == 'ready':
        return
    if state == 'missing':
        execute(['/usr/bin/flatpak', '--user', 'remote-add', '--if-not-exists', '--from', 'flathub', FLATHUB_DESCRIPTOR])
    else:
        execute(['/usr/bin/flatpak', '--user', 'remote-modify', '--enable', 'flathub'])
    if remote_state(execute(command)) != 'ready':
        raise ValueError('Flathub etkin / imzalı olarak doğrulanamadı; başarı varsayılmadı ve imza denetimi kapatılmadı.')
