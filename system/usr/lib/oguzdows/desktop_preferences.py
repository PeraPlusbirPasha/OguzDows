"""Xfce / GNOME / Plasma ortak tercihleri; kabuk ve panel düzenleri ayrı kalır."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import desktop_runtime as runtime
import desktop_state as state
from resource_policy import current_policy


def wallpaper_entry(identifier):
    import wallpapers
    item = next((item for item in wallpapers.catalog() if item['id'] == identifier), None)
    if not item or not Path(item['path']).is_file():
        raise ValueError('Ortak duvar kâğıdı katalogda / diskte bulunamadı.')
    return item


def wallpaper_accent(path):
    from accent import extract
    return extract(path)


def gtk_theme(preferences):
    import profiles
    if runtime.current() != 'xfce':
        return 'OguzDows' if preferences['appearance'] == 'dark' else 'OguzDowsLight'
    identifier, _ = profiles.selection()
    return next(value for channel, key, _kind, value in profiles.settings(
        identifier, preferences['appearance'], preferences['effects'])
        if channel == 'xsettings' and key == '/Net/ThemeName')


def apply_current(preferences, directory, resources, *, wallpaper=False, undo=None):
    desktop = runtime.current()
    budget = bool(resources['compositing'])
    notes = []
    result = {'desktop': desktop, 'physical_gpu_verified': False}
    if desktop == 'xfce':
        import effects
        import profiles
        import aero
        checkpoint = effects.prepare_undo(resources) if undo is not None else None
        capability = (aero.probe() if budget and preferences['effects'] == 'aero' and
                      (preferences['blur'] or preferences['motion'] == 'spring') else None)
        planned = aero.plan(preferences, resources, capability)
        surface = dict(preferences, blur=planned['blur_configured'])
        from desktop_material import install
        identifier = profiles.selection()[0]
        material = install(preferences['accent'], preferences['appearance'] == 'dark',
                           identifier=identifier, glass=surface['blur'], base_theme=gtk_theme(preferences))
        profiles.set_shared(surface, resources=resources, material_theme=material, undo=undo)
        if wallpaper and preferences['wallpaper']:
            import wallpapers
            wallpapers.apply_xfce(preferences['wallpaper'], undo=undo)
        if checkpoint is not None:
            undo.append(checkpoint)
        result.update(effects.reconcile(preferences['effects'], resources, preferences=preferences, capability=capability, checkpoint=checkpoint))
        if surface['blur'] and not result['blur_configured']:
            fallback = install(preferences['accent'], preferences['appearance'] == 'dark',
                               identifier=identifier, glass=False, base_theme=gtk_theme(preferences))
            profiles.set_shared(dict(preferences, blur=False), resources=resources, material_theme=fallback, surface_only=True, undo=undo)
            material = fallback
        # XSettings is live GTK3; INI covers subsequent GTK3 clients and
        # color-scheme is what libadwaita / the Settings portal actually read.
        import desktop_appearance
        notes.extend(desktop_appearance.apply(preferences, material, directory, undo=undo))
    elif desktop == 'gnome':
        import desktop_gnome as gnome
        backend = gnome.GnomeSettings()
        changes = gnome.changes(preferences, resources, backend)
        if wallpaper and preferences['wallpaper']:
            changes.update(gnome.wallpaper_changes(wallpaper_entry(preferences['wallpaper'])['path'], backend))
        state.Journal(backend, directory).apply(changes, undo=undo)
        result.update(gnome.status())
        result['message'] = ('GNOME tercihleri uygulandı; Etkinlikler ve üst çubuk korunuyor. '
            'Yeni uzantı ilk kez kurulmuşsa sonraki giriş gerekir. GNOME 43/44 ile 45–48 için ayrı yükleyiciler kullanılır.')
        if result.get('extension_active'):
            try:
                details = runtime.dbus('org.gnome.Shell', '/org/oguzdows/Desktop',
                    'org.oguzdows.Desktop', 'GetState')[0]
                result.update(gnome.shell_state(details))
            except (RuntimeError, ValueError, IndexError, TypeError):
                notes.append('Uzantı etkin görünse de gerçek blur durumu yanıtı alınamadı.')
    elif desktop == 'kde':
        import desktop_plasma as plasma
        backend = plasma.PlasmaSettings()
        journal = state.Journal(backend, directory)
        import desktop_decoration
        decoration = desktop_decoration.available(backend.major)
        changes = {**plasma.palette(preferences), **plasma.changes(preferences, resources, backend.major, decoration)}
        for token in ('scale', 'fading', 'scale5', 'fading5', 'magiclamp', 'squash', 'squash5',
                      'maximize', 'maximize5', 'theme', 'decoration-library', 'decoration-theme'):
            if token not in changes and token in journal.rows:
                row = journal.rows[token]
                # Yalnız bizim son değerimiz hâlâ duruyorsa geçici override'ı bırak.
                if backend.read(token) == row['applied']:
                    changes[token] = row['before']
        if budget and preferences['effects'] == 'aero' and preferences['blur']:
            plasma.install_tint(preferences)
            if decoration:
                desktop_decoration.install(plasma.theme_name(preferences), preferences['accent'], preferences['appearance'] == 'dark')
            else:
                notes.append('Aurorae eklentisi yok: mevcut pencere dekorasyonu korundu; yalnız Plasma yüzeyleri cam olabilir.')
        if wallpaper and preferences['wallpaper']:
            current = plasma.wallpaper_state()
            uri = Path(wallpaper_entry(preferences['wallpaper'])['path']).resolve().as_uri()
            changes['wallpaper'] = [dict(row, plugin='org.kde.image', image=uri) for row in current]
        if undo is not None:
            def refresh_rollback():
                plasma.notify_settings()
                runtime.dbus('org.kde.KWin', '/KWin', 'org.kde.KWin', 'reconfigure')
            undo.append(refresh_rollback)
        journal.apply(changes, undo=undo)
        try:
            result.update(plasma.refresh(preferences, resources))
        except (RuntimeError, ImportError) as error:
            notes.append('Tercih kaydedildi; çalışan KWin efektleri doğrulanamadı: ' + str(error))
        result['message'] = 'Plasma tercihleri uygulandı. Yerel panelin, plasmoidlerin ve KWin pencere yönetimin korundu.'
    else:
        raise ValueError('Bu masaüstü için ayar arka ucu yok.')
    if not budget:
        notes.append('Düşük kaynak / GPU koruması: blur ve yay kapalı; yerel Wayland kompozitörü zorla durdurulmaz.')
    if desktop in ('gnome', 'kde'):
        notes.append('Diğer uygulamaların özel dekorasyonları / GTK4 libadwaita kuralları ayrı kalabilir.')
    result['notes'] = notes
    return result


def update_and_apply(changes, resources=None, *, observed_wallpaper=None, profile=None):
    runtime.normal_session()
    if runtime.installation_busy():
        raise RuntimeError('Kurucu / sürücü işlemi sürüyor; görünüm değişikliği ertelendi.')
    resources = current_policy() if resources is None else resources
    with state.locked() as directory:
        original = state.load()
        from accent import restored
        if observed_wallpaper is not None and (original['accent_source'] != 'wallpaper' or restored(original)):
            return {'changed': False, 'message': 'Otomatik renk kapatıldı; son kullanıcı rengi korundu.'}
        preferences = state.merged(original, changes)
        accent_note = ''
        if preferences['accent_source'] == 'wallpaper':
            sample = observed_wallpaper
            if sample is None and 'wallpaper' in changes and preferences['wallpaper']:
                sample = wallpaper_entry(preferences['wallpaper'])['path']
            elif sample is None and runtime.current() == 'xfce':
                from accent import current_wallpaper
                try:
                    sample = current_wallpaper()
                except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
                    accent_note = 'Okunabilir JPEG / PNG / WebP duvar kâğıdı yok; önceki vurgu korundu.'
            elif sample is None and preferences['wallpaper']:
                sample = wallpaper_entry(preferences['wallpaper'])['path']
            if sample is not None:
                preferences['accent'] = wallpaper_accent(sample)
        path = state.config_path()
        receipt = directory / (runtime.current() + '-applied.json')
        old_files = {path: state.read_json(path), receipt: state.read_json(receipt)}
        new_files = {receipt: {'revision': preferences['revision'], 'compositing': bool(resources['compositing'])},
                     path: preferences}
        undo = []
        try:
            if profile is not None:
                if runtime.current() != 'xfce' or os.environ.get('XDG_SESSION_TYPE') != 'x11':
                    raise ValueError('Bu panel düzenleri yalnız Xfce içindir; diğer kabuklar korunur.')
                import profiles
                profiles.apply(profile, appearance=preferences['appearance'], manage_compositor=False, undo=undo)
            result = apply_current(preferences, directory, resources, wallpaper='wallpaper' in changes, undo=undo)
            # Ortak tercih en son görünür olur. Önceki native DE değerleri
            # ortak varsayılanlarla tahmin edilmez: tam işlem kaydı geri alınır.
            for target, value in new_files.items():
                state.atomic_json(target, value)
        except Exception as failure:
            errors = []
            for rollback in reversed(undo):
                try:
                    rollback()
                except Exception as error:
                    errors.append(str(error))
            for target, value in new_files.items():
                try:
                    if state.read_json(target) == value:
                        if old_files[target] is None:
                            target.unlink(missing_ok=True)
                        else:
                            state.atomic_json(target, old_files[target])
                except (OSError, ValueError) as error:
                    errors.append(str(error))
            if errors:
                raise RuntimeError('İşlem tamamlanamadı; geri alma da eksik kaldı. Kalıcı günlükten geri almayı deneyin: '
                                   + '; '.join(errors)) from failure
            raise
        result['revision'] = preferences['revision']
        if accent_note:
            result.setdefault('notes', []).append(accent_note)
        # GApplication enforces one tiny native observer per display. Starting
        # it is optional infrastructure, never a reason to undo valid settings.
        try:
            from accent import ensure_observer
            ensure_observer(preferences)
        except (OSError, RuntimeError, ImportError) as error:
            result.setdefault('notes', []).append('Renk kaydedildi; otomatik izleyici başlayamadı: ' + str(error))
        return result


def session(resources=None):
    # Ortak tercih yoksa bir başka DE'nin ilk girişini kişisel varsayılanlarla
    # bırak. Her girişte görünümü tekrar zorlayıp harici değişikliği ezme.
    if not state.config_path().exists():
        return {'message': 'Ortak tercih yok; yerel masaüstü ayarları korunuyor.'}
    runtime.normal_session()
    resources = current_policy() if resources is None else resources
    with state.locked() as directory:
        preferences = state.load()
        path = directory / (runtime.current() + '-applied.json')
        last = state.read_json(path, {})
        if not isinstance(last, dict):
            raise ValueError('Oturum tercih kaydı geçersiz.')
        if last.get('revision') == preferences['revision'] and last.get('restored') is True:
            return {'message': 'Bu masaüstünde geri alma seçimin korunuyor; aynı tercihler tekrar zorlanmadı.'}
        # Bütçe her girişte denetlenir; güçlü PC'de açılmış blur daha küçük ARM
        # cihaza taşınsa da efektler atlanmaz / bütçe koruması devreye girer.
        if (last.get('revision') == preferences['revision'] and runtime.current() != 'xfce'
                and last.get('compositing') == bool(resources['compositing'])):
            return {'message': 'Bu oturumda ortak tercihler güncel; kişisel yerel değişiklikler korunuyor.'}
        result = apply_current(preferences, directory, resources, wallpaper=last.get('revision') != preferences['revision'] and runtime.current() != 'xfce')
        from accent import ensure_observer
        ensure_observer(preferences)
        state.atomic_json(path, {'revision': preferences['revision'], 'compositing': bool(resources['compositing'])})
        return result


def restore():
    runtime.normal_session()
    if runtime.installation_busy():
        raise RuntimeError('Kurucu / sürücü işlemi sürüyor; geri alma ertelendi.')
    desktop = runtime.current()
    with state.locked() as directory:
        if desktop == 'xfce':
            import effects
            import profiles
            effects.reconcile('off')
            profiles.restore()
            import desktop_appearance
            skipped = desktop_appearance.restore(directory)
        else:
            if desktop == 'gnome':
                from desktop_gnome import GnomeSettings
                backend = GnomeSettings()
            else:
                from desktop_plasma import PlasmaSettings
                backend = PlasmaSettings()
            skipped = state.Journal(backend, directory).restore()
            if desktop == 'kde':
                from desktop_plasma import notify_settings
                notify_settings()
                runtime.dbus('org.kde.KWin', '/KWin', 'org.kde.KWin', 'reconfigure')
        # Geri alma açık kullanıcı tercihidir: oturum bu sürümü tekrar zorlamaz.
        state.atomic_json(directory / (desktop + '-applied.json'), {'revision': state.load()['revision'], 'restored': True})
        return {'message': 'Bu masaüstünün yedekli ayarları geri alındı; diğer oturumların düzenlerine dokunulmadı.',
                'preserved_external_changes': skipped}


def status():
    preferences = state.load()
    return {'desktop': runtime.current(), 'protocol': os.environ.get('XDG_SESSION_TYPE', 'unknown'),
            'preferences': preferences, 'resources': current_policy(),
            'session_note': 'Oturum seçmek açık uygulamaları taşımaz / kapatmaz. Kaydedip normal çıkış yapın. Uygulama kendi oturum geri yüklemesini destekliyorsa ayrıca kullanabilirsiniz.'}


if __name__ == '__main__':
    print(json.dumps(status(), ensure_ascii=False, indent=2))
