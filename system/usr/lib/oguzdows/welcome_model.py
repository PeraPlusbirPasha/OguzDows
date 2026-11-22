"""1.1 karşılayıcısı: GTK'den bağımsız oturum ve gezinme modeli.

Canlı, kurulu PC ve Pi ilk açılış işaretleri ayrıdır. Bir USB oturumunun
'gösterme' tercihi kurulu sistemin ilk karşılamasını susturamaz.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rifki_dialogue import PANELS
from rifki_narration_texts import TEXTS

PAGES = (
    ('welcome', 'Hoş geldin', 'go-home-symbolic'),
    ('styles', 'Tasarım', 'preferences-desktop-theme-symbolic'),
    ('appearance', 'Açık / koyu', 'display-brightness-symbolic'),
    ('wallpapers', 'Duvar kâğıdı', 'preferences-desktop-wallpaper-symbolic'),
    ('hardware', 'Donanım', 'computer-symbolic'),
    ('applications', 'Uygulamalar', 'system-software-install-symbolic'),
    ('support', 'Destek', 'help-browser-symbolic'),
)
PAGE_IDS = tuple(page[0] for page in PAGES)


@dataclass(frozen=True)
class Context:
    kind: str
    title: str
    subtitle: str
    intro: str

    @property
    def state_name(self):
        return 'welcome-' + self.kind + '-1.1-seen'

    @property
    def light_state_name(self):
        return 'light-start-' + self.kind + '-seen'

    @property
    def offers_installer(self):
        return self.kind == 'live'


def save_autostart_preference(directory, session, show_again):
    """Tam rehberdeki yeniden göster seçimi hafif başlangıçta da geçerlidir."""
    directory = Path(directory)
    state = directory / session.state_name
    if show_again:
        state.unlink(missing_ok=True)
        (directory / session.light_state_name).unlink(missing_ok=True)
    else:
        directory.mkdir(parents=True, exist_ok=True)
        state.write_text('OğuzDows\n', encoding='utf-8')


def context(live=False, pi=False):
    # Pi zaten SD/USB'ye kuruludur; /proc/cmdline üstünden PC kurucusu önerme.
    if pi:
        return Context('pi', 'OğuzDows · Pi karşılayıcısı', 'SD / USB üzerinde senin masaüstün',
                       'Sistemin SD veya USB üzerinde hazır. İlk adımlarını, görünümünü ve donanımını birlikte düzenleyelim.')
    if live:
        return Context('live', 'OğuzDows · Canlı karşılayıcı', 'Önce dene, hazır olunca kur',
                       'Diskine dokunmadan keşfet. Hazır olduğunda kurucuyu aç; disk ve kullanıcı seçimlerini son özette sen onaylarsın.')
    return Context('installed', 'OğuzDows · İlk adımlar', 'Kurulum bitti, şimdi kişiselleştirme zamanı',
                   'Masaüstün hazır. Tarzını ve temanı seç; uygulamalarını, güncellemelerini ve donanımını buradan yönet.')


def adjacent(page, direction):
    if direction not in (-1, 1):
        raise ValueError('Geçersiz gezinme yönü.')
    if page not in PAGE_IDS:
        return None  # Kurulum sonucundan kendiliğinden başka sayfaya geçme.
    index = PAGE_IDS.index(page) + direction
    return PAGE_IDS[index] if 0 <= index < len(PAGE_IDS) else None


def page_text(page, session):
    if page not in PAGE_IDS:
        return ''
    if page == 'welcome':
        # Canlı kurulum yönergesi kurulu PC / Pi ilk açılışında çalınmaz.
        return TEXTS['live' if session.kind == 'live' else 'installed']
    if page == 'hardware' and session.kind == 'pi':
        return TEXTS['hardware-pi']
    return PANELS[page]
