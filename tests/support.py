"""Testler hiçbir zaman gerçek disklere, paket yöneticisine veya root ayarlarına yazmaz."""
import importlib.machinery
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "system/usr/lib/oguzdows"))


def native_gtk_imports(Gtk, Gdk):
    """Measure GTK's own optional binding imports before loading the product.

    With python3-gi-cairo installed, plain GTK rendering / GDK capture can load
    pycairo via GI's foreign marshaller. Do not mistake that toolkit dependency
    for an eager application import. Pillow / the old pet rig remain forbidden.
    The callers run only on their disposable CI Xvfb displays.
    """
    window = Gtk.Window()
    try:
        window.set_default_size(64, 48)
        window.add(Gtk.Label(label='GTK'))
        window.show_all()
        for _ in range(60):
            if not Gtk.events_pending():
                break
            Gtk.main_iteration_do(False)
        native = window.get_window()
        native.process_updates(True)
        width, height = window.get_size()
        assert Gdk.pixbuf_get_from_window(native, 0, 0, width, height) is not None
    finally:
        window.destroy()
    return frozenset({'cairo'}.intersection(sys.modules))


def load(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(ROOT / path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module
