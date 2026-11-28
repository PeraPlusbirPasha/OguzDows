"""Yerel mağazanın gözden geçirilmiş uygulamaları. Veri komut değildir.

Yetkili APT yardımcısı yalnızca buradaki paket demetlerini kabul eder. Kaynak
sürüm kontrolündedir; kullanıcıdan veya ağdan paket / shell komutu alınmaz.
"""
from __future__ import annotations

import re

CATEGORIES = ('Tümü', 'İnternet', 'Ofis', 'Görsel', 'Ses ve video', 'Geliştirme', 'Oyun', 'Araçlar')


def app(identifier, name, summary, category, packages, flatpak='', icon='application-x-executable'):
    return {'id': identifier, 'name': name, 'summary': summary, 'category': category,
            'packages': tuple(packages.split()), 'flatpak': flatpak, 'icon': icon,
            'fallback_icon': 'oguzdows-app-' + identifier}


APPS = (
    app('firefox', 'Firefox', 'Gizlilik denetimleri olan web tarayıcısı.', 'İnternet', 'firefox-esr', 'org.mozilla.firefox', 'firefox-esr'),
    app('thunderbird', 'Thunderbird', 'E-posta, adres defteri ve takvim bir arada.', 'İnternet', 'thunderbird', 'org.mozilla.Thunderbird', 'thunderbird'),
    app('transmission', 'Transmission', 'Sade ve hafif BitTorrent istemcisi.', 'İnternet', 'transmission-gtk', 'com.transmissionbt.Transmission', 'transmission'),
    app('filezilla', 'FileZilla', 'FTP ve SFTP ile dosya aktarımı.', 'İnternet', 'filezilla', 'org.filezillaproject.Filezilla', 'filezilla'),
    app('remmina', 'Remmina', 'Uzak masaüstü bağlantılarını tek yerde yönet.', 'İnternet', 'remmina', 'org.remmina.Remmina', 'org.remmina.Remmina'),
    app('libreoffice', 'LibreOffice', 'Metin, hesap tablosu ve sunum araçları.', 'Ofis', 'libreoffice-writer libreoffice-calc libreoffice-impress libreoffice-l10n-tr', 'org.libreoffice.LibreOffice', 'libreoffice-startcenter'),
    app('evince', 'Belge Görüntüleyici', 'PDF ve belge dosyalarını oku.', 'Ofis', 'evince', 'org.gnome.Evince', 'org.gnome.Evince'),
    app('xournalpp', 'Xournal++', 'El yazısı notlar ve PDF üzerine açıklamalar.', 'Ofis', 'xournalpp', 'com.github.xournalpp.xournalpp', 'com.github.xournalpp.xournalpp'),
    app('gimp', 'GIMP', 'Fotoğraf düzenleme ve katmanlı görsel üretimi.', 'Görsel', 'gimp', 'org.gimp.GIMP', 'gimp'),
    app('inkscape', 'Inkscape', 'Ölçeklenebilir vektör çizimler ve illüstrasyon.', 'Görsel', 'inkscape', 'org.inkscape.Inkscape', 'org.inkscape.Inkscape'),
    app('krita', 'Krita', 'Dijital çizim, fırçalar ve boyama.', 'Görsel', 'krita', 'org.kde.krita', 'krita'),
    app('blender', 'Blender', '3B modelleme ve animasyon; güçlü donanım ister.', 'Görsel', 'blender', 'org.blender.Blender', 'blender'),
    app('vlc', 'VLC', 'Çok sayıda ses ve video biçimini oynat.', 'Ses ve video', 'vlc', 'org.videolan.VLC', 'vlc'),
    app('audacity', 'Audacity', 'Ses kaydı, kesme ve çok kanallı düzenleme.', 'Ses ve video', 'audacity', 'org.audacityteam.Audacity', 'audacity'),
    app('kdenlive', 'Kdenlive', 'Çok kanallı video kurgu; ek RAM ve GPU ister.', 'Ses ve video', 'kdenlive', 'org.kde.kdenlive', 'kdenlive'),
    app('obs', 'OBS Studio', 'Ekran kaydı ve canlı yayın; eski cihazlar için ağırdır.', 'Ses ve video', 'obs-studio', 'com.obsproject.Studio', 'com.obsproject.Studio'),
    app('handbrake', 'HandBrake', 'Video dönüştürme ve sıkıştırma.', 'Ses ve video', 'handbrake', 'fr.handbrake.ghb', 'fr.handbrake.ghb'),
    app('geany', 'Geany', 'Hızlı açılan hafif kod ve metin düzenleyici.', 'Geliştirme', 'geany', '', 'geany'),
    app('builder', 'Builder', 'GNOME uygulamaları için geliştirme ortamı.', 'Geliştirme', 'gnome-builder', 'org.gnome.Builder', 'org.gnome.Builder'),
    app('gitg', 'gitg', 'Git geçmişini ve değişikliklerini görsel incele.', 'Geliştirme', 'gitg', 'org.gnome.gitg', 'org.gnome.gitg'),
    app('supertuxkart', 'SuperTuxKart', 'Renkli kart yarışı; 3B hızlandırma ister.', 'Oyun', 'supertuxkart', 'net.supertuxkart.SuperTuxKart', 'supertuxkart'),
    app('supertux', 'SuperTux', 'İki boyutlu, açık kaynak platform oyunu.', 'Oyun', 'supertux', 'org.supertuxproject.SuperTux', 'supertux'),
    app('aisleriot', 'İskambil Oyunları', 'Tek kişilik kart oyunu koleksiyonu.', 'Oyun', 'aisleriot', 'org.gnome.Aisleriot', 'gnome-aisleriot'),
    app('keepassxc', 'KeePassXC', 'Parolalarını yerel şifreli kasada sakla.', 'Araçlar', 'keepassxc', 'org.keepassxc.KeePassXC', 'keepassxc'),
    app('baobab', 'Disk Kullanımı', 'Klasörlerin kapladığı alanı incele.', 'Araçlar', 'baobab', 'org.gnome.baobab', 'org.gnome.baobab'),
    app('bleachbit', 'BleachBit', 'Temizlik aracıdır; sileceği dosyaları dikkatle incele.', 'Araçlar', 'bleachbit', 'org.bleachbit.BleachBit', 'bleachbit'),
    dict(app('flatpak-support', 'Flatpak bileşenleri', 'Flatpak, Python API ve yerel portal. Flathub yalnız uygun 64 bit mimaride ayrıca onayla eklenir.', 'Araçlar', 'flatpak gir1.2-flatpak-1.0 xdg-desktop-portal xdg-desktop-portal-gtk ca-certificates', '', 'package-x-generic'), managed_bundle=True),
    dict(app('software-center', 'GNOME Yazılımlar', 'GNOME Software, Flatpak eklentisi, PackageKit ve dil verisi. Ağır katalog isteğe bağlıdır; otomatik açılmaz.', 'Araçlar', 'gnome-software gnome-software-plugin-flatpak packagekit iso-codes flatpak gir1.2-flatpak-1.0 python3-xlib', '', 'org.gnome.Software'), managed_bundle=True),
    app('wine', 'Windows Uyumluluğu', 'Wine ile uygun EXE dosyaları; güvenlik alanı değildir.', 'Araçlar', 'wine', '', 'application-x-ms-dos-executable'),
)
FEATURED = ('gimp', 'vlc', 'geany', 'libreoffice', 'keepassxc')
BY_ID = {item['id']: item for item in APPS}
# Yalnızca sabit, sistem paketinin sağladığı masaüstü dosyaları. Bir uygulama
# motorunun (Wine) dosyasız çalıştırılacağı varsayılmaz; EXE inceleyici ayrıdır.
DESKTOP_IDS = {
    'software-center': ('oguzdows-software.desktop',),
    'firefox': ('firefox-esr.desktop', 'firefox.desktop'),
    'thunderbird': ('thunderbird.desktop',), 'transmission': ('transmission-gtk.desktop',),
    'filezilla': ('filezilla.desktop',), 'remmina': ('org.remmina.Remmina.desktop',),
    'libreoffice': ('libreoffice-startcenter.desktop', 'libreoffice-writer.desktop'),
    'evince': ('org.gnome.Evince.desktop',), 'xournalpp': ('com.github.xournalpp.xournalpp.desktop',),
    'gimp': ('gimp.desktop',), 'inkscape': ('org.inkscape.Inkscape.desktop', 'inkscape.desktop'),
    'krita': ('org.kde.krita.desktop',), 'blender': ('blender.desktop',), 'vlc': ('vlc.desktop',),
    'audacity': ('audacity.desktop',), 'kdenlive': ('org.kde.kdenlive.desktop',),
    'obs': ('com.obsproject.Studio.desktop',), 'handbrake': ('fr.handbrake.ghb.desktop',),
    'geany': ('geany.desktop',), 'builder': ('org.gnome.Builder.desktop',), 'gitg': ('org.gnome.gitg.desktop',),
    'supertuxkart': ('supertuxkart.desktop',), 'supertux': ('supertux2.desktop', 'supertux.desktop'),
    'aisleriot': ('sol.desktop', 'org.gnome.Aisleriot.desktop'), 'keepassxc': ('org.keepassxc.KeePassXC.desktop',),
    'baobab': ('org.gnome.baobab.desktop',), 'bleachbit': ('bleachbit.desktop',),
}



def get(identifier):
    try:
        return BY_ID[identifier]
    except (KeyError, TypeError):
        raise ValueError('Mağaza uygulaması tanınmadı; serbest paket adı kabul edilmez.')


def packages(identifier):
    return list(get(identifier)['packages'])


def flatpak_id(value):
    # Argüman / ref / komut değil, tek bir ters-DNS uygulama kimliği.
    if not isinstance(value, str) or len(value) > 200 or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_][A-Za-z0-9_-]*){2,}', value):
        raise ValueError('Geçersiz Flatpak uygulama kimliği.')
    return value
