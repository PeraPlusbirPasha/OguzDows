#!/usr/bin/env python3
"""PrintScreen's short-lived, unprivileged native Xfce capture entry point."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

TOOL = Path('/usr/bin/xfce4-screenshooter')
MODES = {'fullscreen': '-f', 'region': '-r', 'window': '-w'}


def command(mode, tool=TOOL):
    if mode not in MODES:
        raise ValueError('Geçersiz ekran yakalama kipi.')
    if not tool.is_file() or not os.access(tool, os.X_OK):
        raise ValueError('Ekran yakalama aracı kurulu değil. Paket yöneticisinden xfce4-screenshooter kurun.\n\n'
                         'Terminal komutu: sudo apt install xfce4-screenshooter')
    # No shell, silent upload, automatic overwrite or clipboard interception.
    # Screenshooter shows its native save/copy dialog; Escape cancels selection.
    return [str(tool), MODES[mode]]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    for mode in MODES:
        modes.add_argument('--' + mode, dest='mode', action='store_const', const=mode)
    parser.set_defaults(mode='fullscreen')
    args = parser.parse_args(argv)
    try:
        if os.getuid() == 0 or not os.environ.get('DISPLAY'):
            raise ValueError('Ekran görüntüsü açık Xfce/X11 oturumunda normal kullanıcıyla alınır.')
        argv = command(args.mode)
        os.execv(argv[0], argv)
    except (OSError, ValueError) as error:
        import sys
        print('OğuzDows ekran görüntüsü: ' + str(error), file=sys.stderr)
        try:
            import gi
            gi.require_version('Gtk', '3.0')
            from gi.repository import Gtk
            if Gtk.init_check([])[0]:
                dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.CLOSE,
                                           text='Ekran görüntüsü alınamadı')
                dialog.format_secondary_text(str(error))
                import ui_theme
                ui_theme.setup(dialog)
                dialog.run(); dialog.destroy()
        except ImportError:
            pass
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
