"""Xfce için EWMH Snap; WM geometrinin son sahibidir, ekran izleyicisi yoktur."""
from __future__ import annotations

import ctypes as C
import re

from desktop_runtime import run
from effects import X11


class Message(C.Structure):
    _fields_ = [('type', C.c_int), ('serial', C.c_ulong), ('send_event', C.c_int),
                ('display', C.c_void_p), ('window', C.c_ulong), ('message_type', C.c_ulong),
                ('format', C.c_int), ('data', C.c_long * 5)]


class Event(C.Union):
    _fields_ = [('client', Message), ('padding', C.c_long * 24)]


def snap(direction):
    if direction not in ('left', 'right', 'maximize', 'restore', 'minimize'):
        raise ValueError('Bilinmeyen Snap yönü.')
    x = X11()
    lib, display = x.lib, x.display
    lib.XDefaultRootWindow.argtypes = [C.c_void_p]; lib.XDefaultRootWindow.restype = C.c_ulong
    lib.XGetWindowProperty.argtypes = [C.c_void_p, C.c_ulong, C.c_ulong, C.c_long, C.c_long,
        C.c_int, C.c_ulong, C.POINTER(C.c_ulong), C.POINTER(C.c_int), C.POINTER(C.c_ulong),
        C.POINTER(C.c_ulong), C.POINTER(C.c_void_p)]
    lib.XGetWindowProperty.restype = C.c_int
    lib.XFree.argtypes = [C.c_void_p]
    lib.XSendEvent.argtypes = [C.c_void_p, C.c_ulong, C.c_int, C.c_long, C.POINTER(Event)]
    lib.XFlush.argtypes = [C.c_void_p]
    lib.XIconifyWindow.argtypes = [C.c_void_p, C.c_ulong, C.c_int]
    lib.XGetGeometry.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong),
        C.POINTER(C.c_int), C.POINTER(C.c_int), C.POINTER(C.c_uint), C.POINTER(C.c_uint),
        C.POINTER(C.c_uint), C.POINTER(C.c_uint)]
    lib.XTranslateCoordinates.argtypes = [C.c_void_p, C.c_ulong, C.c_ulong, C.c_int, C.c_int,
        C.POINTER(C.c_int), C.POINTER(C.c_int), C.POINTER(C.c_ulong)]
    lib.XChangeProperty.argtypes = [C.c_void_p, C.c_ulong, C.c_ulong, C.c_ulong,
        C.c_int, C.c_int, C.c_void_p, C.c_int]
    lib.XDeleteProperty.argtypes = [C.c_void_p, C.c_ulong, C.c_ulong]
    root = lib.XDefaultRootWindow(display)
    atom = lambda name: lib.XInternAtom(display, name.encode(), 0)

    def property_value(window, name):
        actual, form, count, remaining, data = C.c_ulong(), C.c_int(), C.c_ulong(), C.c_ulong(), C.c_void_p()
        result = lib.XGetWindowProperty(display, window, atom(name), 0, 64, 0, 0,
            C.byref(actual), C.byref(form), C.byref(count), C.byref(remaining), C.byref(data))
        try:
            if result or form.value != 32 or not data or count.value > 64 or remaining.value:
                return []
            return list(C.cast(data, C.POINTER(C.c_ulong))[:count.value])
        finally:
            if data: lib.XFree(data)

    def send(name, values):
        event = Event()
        event.client = Message(33, 0, 1, display, window, atom(name), 32, (C.c_long * 5)(*values))
        if not lib.XSendEvent(display, root, 0, (1 << 20) | (1 << 19), C.byref(event)):
            raise RuntimeError('Pencere yöneticisine Snap isteği gönderilemedi.')

    try:
        active = property_value(root, '_NET_ACTIVE_WINDOW')
        if not active or not active[0] or active[0] == root:
            raise ValueError('Yerleştirilecek etkin pencere bulunamadı.')
        window = active[0]
        states = [atom('_NET_WM_STATE_MAXIMIZED_HORZ'), atom('_NET_WM_STATE_MAXIMIZED_VERT')]
        if direction == 'minimize':
            lib.XIconifyWindow(display, window, lib.XDefaultScreen(display))
        elif direction == 'maximize':
            send('_NET_WM_STATE', [1, *states, 2, 0])
        else:
            send('_NET_WM_STATE', [0, *states, 2, 0])
            saved = property_value(window, '_OGUZDOWS_RESTORE_GEOMETRY')
            if direction == 'restore':
                if len(saved) == 4:
                    send('_NET_MOVERESIZE_WINDOW', [0x2F00, *saved])
                    lib.XDeleteProperty(display, window, atom('_OGUZDOWS_RESTORE_GEOMETRY'))
            else:
                parent, px, py = C.c_ulong(), C.c_int(), C.c_int()
                width, height, border, depth = C.c_uint(), C.c_uint(), C.c_uint(), C.c_uint()
                if not lib.XGetGeometry(display, window, C.byref(parent), C.byref(px), C.byref(py),
                        C.byref(width), C.byref(height), C.byref(border), C.byref(depth)):
                    raise ValueError('Pencere boyutu okunamadı.')
                lib.XTranslateCoordinates(display, window, root, 0, 0, C.byref(px), C.byref(py), C.byref(parent))
                geometry = (px.value, py.value, width.value, height.value)
                if len(saved) != 4:
                    values = (C.c_ulong * 4)(*geometry)
                    lib.XChangeProperty(display, window, atom('_OGUZDOWS_RESTORE_GEOMETRY'), atom('CARDINAL'), 32, 0, values, 4)
                desk = property_value(root, '_NET_CURRENT_DESKTOP') or [0]
                areas = property_value(root, '_NET_WORKAREA')
                area = areas[desk[0] * 4:desk[0] * 4 + 4]
                if len(area) != 4:
                    raise ValueError('Çalışma alanı okunamadı; boyut tahmin edilmedi.')
                # Çok monitörlü birleşik workarea'yı etkin pencerenin monitörüne
                # kes. RandR yoksa EWMH çalışma alanı kullanılır.
                listing = run(['/usr/bin/xrandr', '--listactivemonitors'])
                for match in re.finditer(r'(\d+)/(?:\d+)x(\d+)/(?:\d+)([+-]\d+)([+-]\d+)', listing.stdout):
                    mw, mh, mx, my = map(int, match.groups())
                    if mx <= px.value + width.value / 2 < mx + mw and my <= py.value + height.value / 2 < my + mh:
                        ax, ay = max(area[0], mx), max(area[1], my)
                        area = [ax, ay, min(area[0] + area[2], mx + mw) - ax, min(area[1] + area[3], my + mh) - ay]
                        break
                ax, ay, aw, ah = area
                if aw < 80 or ah < 80:
                    raise ValueError('Çalışma alanı Snap için çok küçük.')
                split = aw // 2
                send('_NET_MOVERESIZE_WINDOW', [0x2F00, ax if direction == 'left' else ax + split, ay,
                                               split if direction == 'left' else aw - split, ah])
        lib.XFlush(display)
    finally:
        x.close()
