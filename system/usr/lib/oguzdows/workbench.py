#!/usr/bin/env python3
"""OğuzDows Atölye: tembel kurulan GTK sayfaları, tek istek üzerine işçi."""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workbench_core as core


def application():
    # --list-tools and importing the backend never load GTK / Pillow.
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk, Gio, GLib, Gtk
    import ui_theme

    def style(widget, *names):
        for name in names:
            widget.get_style_context().add_class(name)
        return widget

    def label(text='', css=None):
        widget = Gtk.Label(label=text, xalign=0, wrap=True, max_width_chars=60)
        widget.set_line_wrap_mode(2)  # Pango.WrapMode.WORD_CHAR; no eager Cairo.
        widget.set_selectable(True)
        return style(widget, css) if css else widget

    class Workbench(Gtk.Application):
        def __init__(self):
            super().__init__(application_id='org.oguzdows.Workbench', flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
            self.window = None
            self.lib = core.Library()
            self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='Atolye')
            self.cancel = None
            self.busy = self.mutating = self.closed = self.dirty = False
            self.clock_id = None
            self.clock_tick = None
            self.current_tool = 'home'
            self.requested_tool = 'home'
            self.search_text = ''
            self.nav_rows = []
            self.save_action = None
            self.plan = None

        def do_command_line(self, command_line):
            arguments = command_line.get_arguments()[1:]
            if arguments:
                if len(arguments) != 2 or arguments[0] != '--tool' or arguments[1] not in {item[0] for item in core.TOOLS}:
                    return 2
                self.requested_tool = arguments[1]
            self.activate()
            return 0

        def do_activate(self):
            if self.window:
                self.window.present()
                if self.requested_tool != 'home':
                    self.navigate(self.requested_tool)
                return
            self.window = Gtk.ApplicationWindow(application=self, title='OğuzDows · Atölye')
            self.window.set_icon_name('oguzdows-workbench')
            display = self.window.get_display()
            monitor = display.get_primary_monitor() or display.get_monitor(0)
            area = monitor.get_workarea() if monitor else Gdk.Rectangle(x=0, y=0, width=1024, height=768)
            self.window.set_default_size(min(1040, area.width - 24), min(730, area.height - 48))
            self.window.set_size_request(300, 340)
            ui_theme.setup(self.window)
            style(self.window, 'workbench-window')
            header = Gtk.HeaderBar(title='Atölye', subtitle='Daha az kaynak. Daha çok iş.', show_close_button=True)
            home = Gtk.Button.new_from_icon_name('go-home-symbolic', Gtk.IconSize.BUTTON)
            home.set_tooltip_text('Atölye ana sayfası')
            home.connect('clicked', lambda *_: self.navigate('home'))
            header.pack_start(home)
            search = Gtk.Button.new_from_icon_name('system-search-symbolic', Gtk.IconSize.BUTTON)
            search.set_tooltip_text('Araç bul · Ctrl+K')
            search.connect('clicked', lambda *_: self.search.grab_focus())
            header.pack_end(search)
            self.window.set_titlebar(header)
            root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.search = Gtk.SearchEntry(placeholder_text='Araç ara…  Ctrl+K')
            self.search.set_width_chars(10)
            self.search.set_margin_start(12); self.search.set_margin_end(12); self.search.set_margin_top(10)
            self.search.connect('search-changed', self.filter_tools)
            self.search.connect('activate', self.search_activate)
            self.search.set_tooltip_text('Hesap, not, dosya, renk, başlangıç… Araç adı yazıp Enter’a bas.')
            root.pack_start(self.search, False, False, 0)
            self.selector = Gtk.ComboBoxText()
            self.selector.append('home', 'Atölye · Genel bakış')
            for identifier, title, _, _ in core.TOOLS:
                self.selector.append(identifier, title)
            self.selector.set_active_id('home')
            self.selector.connect('changed', lambda combo: self.navigate(combo.get_active_id()) if combo.get_active_id() != self.current_tool else None)
            self.selector.set_margin_start(12); self.selector.set_margin_end(12); self.selector.set_margin_top(8)
            root.pack_start(self.selector, False, False, 0)
            body = Gtk.Box(spacing=0)
            self.sidebar = style(Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE), 'workbench-sidebar')
            for identifier, title, summary, icon in core.TOOLS:
                row = Gtk.ListBoxRow()
                row.identifier = identifier
                line = Gtk.Box(spacing=9, margin=10)
                line.pack_start(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.BUTTON), False, False, 0)
                line.pack_start(Gtk.Label(label=title, xalign=0), True, True, 0)
                row.add(line); row.set_tooltip_text(summary)
                self.sidebar.add(row); self.nav_rows.append(row)
            self.sidebar.connect('row-activated', lambda _box, row: self.navigate(row.identifier))
            self.side_scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
            self.side_scroll.set_size_request(188, -1)
            self.side_scroll.add(self.sidebar)
            body.pack_start(self.side_scroll, False, False, 0)
            self.stack = Gtk.Stack()
            ui_theme.configure_stack(self.window, self.stack)
            body.pack_start(self.stack, True, True, 0)
            root.pack_start(body, True, True, 0)
            bottom = style(Gtk.Box(spacing=8, margin=10), 'workbench-status')
            self.spinner = Gtk.Spinner()
            self.status = label('Yerel araçlar · ağ isteği ve arka plan indekslemesi yok.', 'dim-label')
            self.status.set_max_width_chars(60)
            self.status.set_lines(3); self.status.set_ellipsize(3)
            self.stop = Gtk.Button.new_from_icon_name('process-stop-symbolic', Gtk.IconSize.BUTTON)
            self.stop.set_tooltip_text('Okuma / hesaplama isteğini durdur')
            self.stop.connect('clicked', self.stop_job)
            bottom.pack_start(self.spinner, False, False, 0); bottom.pack_start(self.status, True, True, 0); bottom.pack_end(self.stop, False, False, 0)
            root.pack_start(bottom, False, False, 0)
            self.window.add(root)
            self.window.connect('delete-event', self.close_requested)
            self.window.connect('destroy', self.destroyed)
            self.window.connect('configure-event', self.configured)
            self.window.connect('unmap', self.clock_unmap)
            self.window.connect('map', self.clock_map)
            self.window.connect('key-press-event', self.key_pressed)
            self.window.show_all()
            self.resize(area.width - 24)
            self.stop.set_sensitive(False)
            self.navigate(self.requested_tool)

        def say(self, text):
            if not self.closed:
                self.status.set_text(str(text)[:1500])

        def guard(self, function, *arguments):
            try:
                return function(*arguments)
            except (OSError, ValueError, TypeError, KeyError, SyntaxError, ArithmeticError) as error:
                self.say(str(error))
                return None

        def button(self, box, title, callback, css=None):
            button = Gtk.Button(label=title)
            if css: style(button, css)
            text = button.get_child()
            text.set_line_wrap(True); text.set_line_wrap_mode(2); text.set_max_width_chars(22)
            button.connect('clicked', lambda *_: self.guard(callback))
            box.add(button)
            return button

        def actions(self, box):
            line = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=False, max_children_per_line=4, row_spacing=5, column_spacing=5)
            line.set_min_children_per_line(1)
            box.pack_start(line, False, False, 0)
            return line

        def entry(self, box, title, value='', placeholder=''):
            box.pack_start(label(title, 'field-label'), False, False, 0)
            widget = Gtk.Entry(text=value, placeholder_text=placeholder)
            widget.set_width_chars(10); widget.set_max_length(1024)
            box.pack_start(widget, False, False, 0)
            widget.get_accessible().set_name(title)
            return widget

        def text(self, box, title, editable=True, height=150):
            box.pack_start(label(title, 'field-label'), False, False, 0)
            view = Gtk.TextView(editable=editable, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
            view.set_left_margin(10); view.set_right_margin(10); view.set_top_margin(10); view.set_bottom_margin(10)
            view.get_accessible().set_name(title)
            scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
            scroll.set_min_content_height(height)
            scroll.add(view); box.pack_start(scroll, False, True, 0)
            return view.get_buffer()

        @staticmethod
        def value(buffer):
            return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)

        def combo(self, box, title, values):
            box.pack_start(label(title, 'field-label'), False, False, 0)
            combo = Gtk.ComboBoxText()
            for value in values:
                combo.append_text(value)
            combo.set_active(0)
            combo.get_accessible().set_name(title)
            box.pack_start(combo, False, False, 0)
            return combo

        def chooser(self, box, title, folder=False):
            entry = self.entry(box, title, placeholder='Seç düğmesini kullanın…')
            entry.set_editable(False)
            line = self.actions(box)
            def choose():
                path = self.choose(title, folder=folder)
                if path: entry.set_text(path)
            self.button(line, 'Klasör seç…' if folder else 'Dosya seç…', choose)
            return entry

        def choose(self, title, *, folder=False, save=False, name=''):
            action = Gtk.FileChooserAction.SAVE if save else Gtk.FileChooserAction.SELECT_FOLDER if folder else Gtk.FileChooserAction.OPEN
            dialog = Gtk.FileChooserNative.new(title, self.window, action, 'Seç' if not save else 'Dışa aktar', 'Vazgeç')
            if save: dialog.set_current_name(name)
            result = dialog.run()
            path = dialog.get_filename() if result == Gtk.ResponseType.ACCEPT else None
            dialog.destroy()
            return path

        def confirm(self, title, text):
            dialog = Gtk.MessageDialog(transient_for=self.window, modal=True, message_type=Gtk.MessageType.QUESTION,
                                       buttons=Gtk.ButtonsType.OK_CANCEL, text=title)
            dialog.format_secondary_text(text)
            dialog.set_default_response(Gtk.ResponseType.CANCEL)
            ui_theme.setup(dialog)
            result = dialog.run() == Gtk.ResponseType.OK
            dialog.destroy()
            return result

        def export(self, text, name='Atolye.txt'):
            path = self.choose('Yeni dosya olarak dışa aktar · mevcut dosyanın üzerine yazılmaz', save=True, name=name)
            if path:
                self.job(lambda _cancel: core.export_text(Path(path).parent, Path(path).name, text), lambda value: self.say('Kaydedildi: ' + value), mutating=True)

        def copy(self, text):
            Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(text, -1)
            self.say('Seçtiğiniz metin panoya kopyalandı. Pano geçmişi toplanmaz.')

        def job(self, function, done, *, mutating=False):
            if self.closed: return
            if self.busy:
                self.say('Önce açık isteğin bitmesini bekleyin. Aynı anda yalnız bir iş çalışır.')
                return
            self.busy = True; self.mutating = mutating
            if mutating: self.stack.set_sensitive(False)
            self.cancel = threading.Event()
            self.stop.set_sensitive(not mutating)
            self.spinner.start()
            self.say('İşleniyor… Kaynak dosyalar yalnızca açıkça onaylanan adlandırmada değişir.')
            def work():
                try:
                    if not mutating: core.check_cancel(self.cancel)
                    value, error = function(self.cancel), None
                    if not mutating: core.check_cancel(self.cancel)
                except Exception as problem:
                    value, error = None, problem
                GLib.idle_add(finished, value, error)
            def finished(value, error):
                self.busy = self.mutating = False
                if self.closed: return GLib.SOURCE_REMOVE
                self.stack.set_sensitive(True)
                self.spinner.stop(); self.stop.set_sensitive(False)
                if self.cancel.is_set() and not mutating: error = ValueError('İşlem iptal edildi; kaynaklar değiştirilmedi.')
                if error: self.say(str(error))
                else: self.guard(done, value)
                return GLib.SOURCE_REMOVE
            try:
                self.pool.submit(work)
            except (RuntimeError, OSError) as error:
                self.busy = self.mutating = False
                self.stack.set_sensitive(True)
                self.spinner.stop(); self.stop.set_sensitive(False); self.say(str(error))

        def stop_job(self, *_):
            if self.cancel and self.busy and not self.mutating:
                self.cancel.set(); self.say('Durdurma istendi; açık dosya bloğu tamamlanınca sonuç gösterilecek.')

        def filter_tools(self, *_):
            self.search_text = core.normalized(self.search.get_text())
            for row, tool in zip(self.nav_rows, core.TOOLS):
                row.set_visible(self.search_text in core.normalized(' '.join(tool[:3])))
            if self.current_tool == 'home':
                for child in self.home_cards.get_children():
                    child.set_visible(self.search_text in child.search)

        def search_activate(self, *_):
            for identifier, title, description, _ in core.TOOLS:
                if self.search_text in core.normalized(title + ' ' + description + ' ' + identifier):
                    self.navigate(identifier)
                    return
            self.say('Araç bulunamadı. Not, hesap, renk veya dosya yazmayı deneyin.')

        def resize(self, width):
            compact = width < 760
            self.side_scroll.set_visible(not compact)
            self.selector.set_visible(compact)
            for child in self.stack.get_children():
                child.set_margin_start(12 if compact else 26); child.set_margin_end(12 if compact else 26)

        def configured(self, _window, event):
            self.resize(event.width)
            return False

        def key_pressed(self, _window, event):
            if event.state & Gdk.ModifierType.CONTROL_MASK:
                if event.keyval in (Gdk.KEY_k, Gdk.KEY_K): self.search.grab_focus(); return True
                if event.keyval in (Gdk.KEY_s, Gdk.KEY_S) and self.save_action:
                    self.guard(self.save_action); return True
            if event.keyval == Gdk.KEY_Escape and self.busy:
                self.stop_job(); return True
            return False

        def close_requested(self, *_):
            if self.mutating:
                self.say('Onayladığınız yazma işlemi bitmeden pencere kapatılmaz.')
                return True
            if self.dirty and not self.confirm('Kaydedilmemiş metin var', 'Kaydetmeden kapatılsın mı? Son kaydedilen kayıt korunur.'):
                return True
            return False

        def destroyed(self, *_):
            self.closed = True
            if self.cancel: self.cancel.set()
            if self.clock_id: GLib.source_remove(self.clock_id); self.clock_id = None
            self.pool.shutdown(wait=False, cancel_futures=True)

        def navigate(self, identifier):
            if identifier not in {'home', *(tool[0] for tool in core.TOOLS)}: return
            if self.busy:
                self.say('İstek sürerken sayfa değiştirilmez; okuma işlemini durdurabilirsiniz.')
                self.selector.set_active_id(self.current_tool)
                return
            if self.dirty and not self.confirm('Kaydedilmemiş metin var', 'Sayfadan kaydetmeden ayrılsın mı?'):
                self.selector.set_active_id(self.current_tool)
                return
            if self.clock_id: GLib.source_remove(self.clock_id); self.clock_id = None
            self.dirty = False; self.save_action = None; self.current_tool = identifier
            self.selector.set_active_id(identifier)
            for child in self.stack.get_children(): self.stack.remove(child); child.destroy()
            page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=22, margin_bottom=24)
            scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
            scroll.add(page)
            self.stack.add_named(scroll, identifier)
            self.stack.set_visible_child(scroll)
            if identifier == 'home': self.home_page(page)
            else:
                tool = next(item for item in core.TOOLS if item[0] == identifier)
                page.pack_start(label('OĞUZDOWS / ATÖLYE', 'eyebrow'), False, False, 0)
                page.pack_start(label(tool[1], 'page-title'), False, False, 0)
                page.pack_start(label(tool[2], 'dim-label'), False, False, 0)
                if identifier in ('tasks', 'notes', 'snippets', 'folders'):
                    self.collection_page(page, identifier)
                else: getattr(self, identifier + '_page')(page)
            scroll.show_all()
            self.resize(self.window.get_allocated_width())
            self.say('Çevrimdışı · bu araç kapandığında arka plan hizmeti kalmaz.')

        def home_page(self, page):
            page.pack_start(label('SANA AİT BİR ÇALIŞMA ALANI', 'eyebrow'), False, False, 0)
            hero = style(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_bottom=14), 'workbench-hero')
            hero.pack_start(label('Küçük araçlar.\nBüyük kolaylıklar.', 'hero-title'), False, False, 0)
            hero.pack_start(label('Notlarını toparla, dosyalarını hazırla, bir fikre renk ver. ARM dahil aynı araçlar; ağsız, hesapsız ve yalnız sen açınca.', 'hero-description'), False, False, 0)
            hero.pack_start(label('16 ARAÇ  /  YENİ SERVİS YOK  /  YEREL VERİ', 'hero-caption'), False, False, 0)
            page.pack_start(hero, False, False, 0)
            page.pack_start(label('Bugün ne yapmak istersin?', 'section-title'), False, False, 0)
            self.home_cards = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True, max_children_per_line=3,
                                          min_children_per_line=1, row_spacing=10, column_spacing=10)
            for identifier, title, description, icon in core.TOOLS:
                button = style(Gtk.Button(), 'tool-card')
                contents = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=8)
                image = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.DND); image.set_halign(Gtk.Align.START)
                contents.pack_start(image, False, False, 0)
                contents.pack_start(label(title, 'section-title'), False, False, 0)
                text = label(description, 'dim-label'); text.set_max_width_chars(23)
                contents.pack_start(text, False, False, 0)
                button.add(contents)
                button.connect('clicked', lambda _button, value=identifier: self.navigate(value))
                self.home_cards.add(button)
                button.get_parent().search = core.normalized(title + ' ' + description + ' ' + identifier)
            page.pack_start(self.home_cards, False, False, 0)
            page.pack_start(label('Notlar ve metin rafı şifreli kasa değildir. Araçlar dosyalarını kendiliğinden taramaz, silmez veya göndermez.', 'dim-label'), False, False, 0)

        def collection_page(self, page, kind):
            self.record_id = ''
            query = Gtk.SearchEntry(placeholder_text='Bu koleksiyonda ara…')
            query.set_width_chars(8); page.pack_start(query, False, False, 0)
            mode = self.combo(page, 'Görev filtresi', ('Açık görevler', 'Tümü', 'Tamamlanan', 'Yüksek öncelik', 'Bugün / geciken')) if kind == 'tasks' else None
            records = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
            records.set_activate_on_single_click(True)
            style(records, 'record-list')
            scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vscrollbar_policy=Gtk.PolicyType.AUTOMATIC)
            scroll.set_min_content_height(140); scroll.set_max_content_height(220); scroll.set_propagate_natural_height(True)
            scroll.add(records); page.pack_start(scroll, False, False, 0)
            title = self.entry(page, 'Başlık')
            title.set_max_length(160)
            body = self.text(page, 'Klasör yolu' if kind == 'folders' else 'Metin / ayrıntı', height=100)
            priority = self.combo(page, 'Öncelik', ('Normal', 'Yüksek', 'Düşük')) if kind == 'tasks' else None
            due = self.entry(page, 'Son tarih · isteğe bağlı', placeholder='YYYY-AA-GG') if kind == 'tasks' else None
            done = Gtk.CheckButton(label='Tamamlandı') if kind == 'tasks' else None
            if done: page.pack_start(done, False, False, 0)
            for widget, signal in ((title, 'changed'), (body, 'changed'), (due, 'changed'), (priority, 'changed'), (done, 'toggled')):
                if widget: widget.connect(signal, lambda *_: setattr(self, 'dirty', True))
            state = {'rows': []}
            def indexed(row):
                # Unicode folding of up to 4 MiB belongs on the worker, not on
                # every GTK keystroke. The derived key is never persisted.
                return {**row, '_search': core.normalized(row['title'] + ' ' + row.get('body', ''))}
            def display():
                for row in records.get_children(): row.destroy()
                needle = core.normalized(query.get_text())
                rows = sorted(state['rows'], key=lambda row: (row.get('done', False), {'high': 0, 'normal': 1, 'low': 2}.get(row.get('priority'), 1), row.get('due') or '9999', row['updated']), reverse=False)
                for row in rows:
                    if needle not in row['_search']: continue
                    if mode:
                        chosen = mode.get_active()
                        if chosen == 0 and row['done'] or chosen == 2 and not row['done'] or chosen == 3 and row['priority'] != 'high': continue
                        if chosen == 4 and (not row.get('due') or row['due'] > date.today().isoformat() or row['done']): continue
                    item = Gtk.ListBoxRow(); item.record = row
                    caption = ('✓ ' if row.get('done') else '• ' if kind == 'tasks' else '') + row['title']
                    if row.get('due'): caption += '  ·  ' + row['due']
                    widget = label(caption); widget.set_margin_top(8); widget.set_margin_bottom(8); widget.set_margin_start(10)
                    item.add(widget); records.add(item)
                if not records.get_children():
                    records.add(label('Henüz kayıt yok veya filtreyle eşleşmiyor.', 'dim-label'))
                records.show_all()
            def refresh(_value=None):
                def received(value): state['rows'] = value; display()
                self.job(lambda _cancel: [indexed(row) for row in self.lib.read()[kind]], received)
            def set_record(row=None):
                if self.dirty and not self.confirm('Kaydedilmemiş metin var', 'Başka kayda kaydetmeden geçilsin mi?'): return
                row = row or {}
                self.record_id = row.get('id', '')
                title.set_text(row.get('title', '')); body.set_text(row.get('body', ''))
                if priority: priority.set_active(('normal', 'high', 'low').index(row.get('priority', 'normal')))
                if due: due.set_text(row.get('due', ''))
                if done: done.set_active(row.get('done', False))
                self.dirty = False
            def save():
                fields = {'title': title.get_text(), 'body': self.value(body)}
                if kind == 'tasks': fields.update(priority=('normal', 'high', 'low')[priority.get_active()], due=due.get_text().strip(), done=done.get_active())
                identifier = self.record_id
                def saved(value):
                    self.record_id = value['id']; self.dirty = False
                    state['rows'] = [row for row in state['rows'] if row['id'] != value['id']] + [value]
                    display(); self.say('Kaydedildi · yalnızca bu hesabın özel kitaplığında.')
                self.job(lambda _cancel: indexed(self.lib.update(kind, identifier=identifier, **fields)), saved, mutating=True)
            def delete():
                identifier = self.record_id
                if not identifier or not self.confirm('Seçili kayıt silinsin mi?', 'Yalnızca bu kitaplık kaydı silinir; dosya / klasör silinmez.'): return
                def deleted(_value):
                    state['rows'] = [row for row in state['rows'] if row['id'] != identifier]
                    self.dirty = False; set_record(); display(); self.say('Kitaplık kaydı silindi.')
                self.job(lambda _cancel: self.lib.update(kind, identifier=identifier, delete=True), deleted, mutating=True)
            def selected(_box, row):
                if hasattr(row, 'record'): set_record(row.record)
            def folder():
                value = self.choose('Yerlerime klasör ekle', folder=True)
                if value: body.set_text(value); title.set_text(Path(value).name)
            def open_folder():
                path = Path(self.value(body))
                _, fd = core._directory(path); os.close(fd)
                Gio.AppInfo.launch_default_for_uri(path.as_uri(), None)
            records.connect('row-activated', selected)
            query.connect('search-changed', lambda *_: display())
            if mode: mode.connect('changed', lambda *_: display())
            actions = self.actions(page)
            self.button(actions, 'Yeni', lambda: set_record())
            self.button(actions, 'Kaydet · Ctrl+S', save, 'suggested-action')
            self.button(actions, 'Kaydı sil…', delete)
            if kind == 'folders':
                self.button(actions, 'Klasör seç…', folder)
                self.button(actions, 'Klasörü aç', open_folder)
            else:
                self.button(actions, 'Metni kopyala', lambda: self.copy(self.value(body)))
                self.button(actions, 'TXT dışa aktar…', lambda: self.export(title.get_text() + '\n\n' + self.value(body)))
            self.save_action = save
            self.dirty = False
            refresh()

        def find_page(self, page):
            root = self.chooser(page, 'Aranacak klasör', folder=True)
            query = self.entry(page, 'Dosya adında geçen', placeholder='Örn. fatura')
            results = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
            output = label('En fazla 20.000 girdi / 200 sonuç / 8 saniye. Gizli konumlar, bağlı diskler ve bağlantılar izlenmez.', 'dim-label')
            def received(value):
                for row in results.get_children(): row.destroy()
                for item in value['files']:
                    row = Gtk.ListBoxRow(); row.path = item['path']
                    row.add(label(item['relative'] + ' · ' + str(item['bytes']) + ' B'))
                    results.add(row)
                results.show_all()
                output.set_text(f"{len(value['files'])} sonuç · {value['visited']} girdi" + (' · Sınıra ulaşıldı; daha küçük klasör seçin.' if value['limited'] else ''))
            def start():
                directory, needle = root.get_text(), query.get_text()
                self.job(lambda cancel: core.find_files(directory, needle, cancel), received)
            def open_result(_box, row):
                if hasattr(row, 'path'):
                    stream, _ = core._regular(row.path); stream.close()
                    # Reveal parent, never execute a found program / desktop file.
                    Gio.AppInfo.launch_default_for_uri(Path(row.path).parent.as_uri(), None)
            self.button(self.actions(page), 'Bu klasörde ara', start, 'suggested-action')
            page.pack_start(output, False, False, 0)
            results.connect('row-activated', lambda *args: self.guard(open_result, *args))
            page.pack_start(results, False, False, 0)

        def checksum_page(self, page):
            source = self.chooser(page, 'Doğrulanacak dosya')
            algorithm = self.combo(page, 'Algoritma', ('sha256', 'sha512'))
            expected = self.entry(page, 'Beklenen özet · boşsa yalnız hesapla')
            output = self.text(page, 'Sonuç', editable=False)
            last = [0.0]
            def progress(done, total):
                if time.monotonic() - last[0] < .25: return
                last[0] = time.monotonic()
                GLib.idle_add(lambda: self.say(f'{done:,} / {total:,} bayt · sabit 256 KiB okuma bloğu'))
            def received(value):
                match = 'Özet hesaplandı; özgün kaynağı ayrıca doğrulayın.' if value['matches'] is None else 'EŞLEŞTİ' if value['matches'] else 'EŞLEŞMEDİ · dosyayı kullanmayın!'
                # Keep the result bound to its immutable input snapshot, even
                # if the user edits the chooser/algorithm while the worker runs.
                output.set_text('Dosya: ' + repr(value['path']) + '\n' + value['algorithm'].upper() + '\n' + value['digest']
                                + ('\nBeklenen: ' + value['expected'] if value['expected'] else '')
                                + '\n\n' + match + '\n' + str(value['bytes']) + ' bayt')
                self.say(match)
            def start():
                path, algo, check = source.get_text(), algorithm.get_active_text(), expected.get_text()
                self.job(lambda cancel: core.file_checksum(path, algo, check, cancel, progress), received)
            actions = self.actions(page)
            self.button(actions, 'Özeti hesapla / doğrula', start, 'suggested-action')
            self.button(actions, 'Sonucu kopyala', lambda: self.copy(self.value(output)))

        def rename_page(self, page):
            root = self.chooser(page, 'Yalnızca bu klasörün görünür dosyaları', folder=True)
            prefix = self.entry(page, 'Önek · {n} sıralı numaradır', placeholder='Örn. Gezi-{n}-')
            find = self.entry(page, 'Bul · boşsa ad korunur')
            replace = self.entry(page, 'Yerine yaz')
            output = self.text(page, 'Önizleme / geri alma planı', editable=False, height=220)
            self.plan = None
            def preview():
                directory, pre, old, new = root.get_text(), prefix.get_text(), find.get_text(), replace.get_text()
                def received(value):
                    self.plan = value
                    output.set_text('\n'.join(row['before'] + '  →  ' + row['after'] for row in value['changes']))
                    self.say('Önizleme hazır; henüz hiçbir dosya adı değişmedi.')
                self.job(lambda cancel: core.rename_preview(directory, pre, old, new, cancel=cancel), received)
            def apply():
                if not self.plan: raise ValueError('Önce önizlemeyi oluşturun.')
                if not self.confirm('Gösterilen adlandırma uygulansın mı?', self.plan['directory'] + '\nEn fazla 200 dosya. Hedeflerin üzerine yazılmaz; plan yeniden doğrulanır.'): return
                plan = self.plan
                self.job(lambda _cancel: core.rename_apply(plan, self.lib.root), lambda count: self.say(str(count) + ' dosya adlandırıldı. Son işlem geri alınabilir.'), mutating=True)
            def undo():
                def received(value):
                    output.set_text(value['directory'] + '\n\n' + '\n'.join(row['after'] + '  →  ' + row['before'] for row in value['changes']))
                    if self.confirm('Son adlandırma geri alınsın mı?', value['directory'] + '\nDeğişmiş dosya veya çakışma varsa işlem reddedilir.'):
                        self.job(lambda _cancel: core.rename_apply(value, self.lib.root, undo=True), lambda count: self.say(str(count) + ' ad geri alındı.'), mutating=True)
                self.job(lambda _cancel: core.rename_history(self.lib.root), received)
            def forget():
                if self.confirm('Geri alma kaydı bırakılsın mı?', 'Dosyalar silinmez. Son adlandırmayı bu araçtan artık geri alamazsınız.'):
                    self.job(lambda _cancel: core.rename_history(self.lib.root, forget=True), lambda _value: self.say('Yalnız geri alma kaydı bırakıldı.'), mutating=True)
            actions = self.actions(page)
            self.button(actions, '1 · Önizle', preview)
            self.button(actions, '2 · Onayla ve uygula…', apply, 'suggested-action')
            self.button(actions, 'Son işlemi geri al…', undo)
            self.button(actions, 'Geri alma kaydını bırak…', forget)
            page.pack_start(label('İçerik, uzantı ve klasörler kendiliğinden değiştirilmez. Aynı hedef / var olan ad / dış değişiklikte üzerine yazma yoktur.', 'dim-label'), False, False, 0)

        def image_page(self, page):
            source = self.chooser(page, 'Kaynak görsel · en fazla 8 megapiksel')
            destination = self.chooser(page, 'Yeni dosyanın klasörü', folder=True)
            name = self.entry(page, 'Yeni dosya adı', 'Hazir-gorsel.jpg')
            format_widget = self.combo(page, 'Çıktı biçimi', ('JPEG', 'PNG', 'WEBP'))
            width = self.entry(page, 'Azami genişlik · piksel', '1600')
            height = self.entry(page, 'Azami yükseklik · piksel', '1600')
            def changed(*_):
                name.set_text('Hazir-gorsel.' + {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp'}[format_widget.get_active_text()])
            format_widget.connect('changed', changed)
            def start():
                arguments = (source.get_text(), destination.get_text(), name.get_text(), int(width.get_text()), int(height.get_text()), format_widget.get_active_text())
                self.job(lambda cancel: core.prepare_image(*arguments, cancel=cancel), lambda value: self.say(f"Yeni görsel: {value['path']} · {value['width']}×{value['height']}"), mutating=True)
            self.button(self.actions(page), 'Yeni görsel oluştur', start, 'suggested-action')
            page.pack_start(label('Oran korunur, büyütme yapılmaz. GPS/EXIF/XMP bilgisi çıktıya taşınmaz; kaynak korunur. Animasyonlar reddedilir. Bu bir güvenli anonimleştirme garantisi değildir; görünür içerik de bilgi içerebilir.', 'dim-label'), False, False, 0)

        def diff_page(self, page):
            left = self.text(page, 'Önce')
            right = self.text(page, 'Sonra')
            result = self.text(page, 'Satır farkı · − silinen / + eklenen', editable=False)
            def start():
                a, b = self.value(left), self.value(right)
                self.job(lambda _cancel: core.text_diff(a, b), lambda value: result.set_text(value))
            actions = self.actions(page)
            self.button(actions, 'Karşılaştır', start, 'suggested-action')
            self.button(actions, 'Farkı dışa aktar…', lambda: self.export(self.value(result), 'Degisiklik.diff'))

        def json_page(self, page):
            source = self.text(page, 'JSON girdisi')
            result = self.text(page, 'Doğrulanmış sonuç', editable=False)
            def start(compact):
                value = self.value(source)
                self.job(lambda _cancel: core.format_json(value, compact), lambda text: result.set_text(text))
            actions = self.actions(page)
            self.button(actions, 'Doğrula ve düzenle', lambda: start(False), 'suggested-action')
            self.button(actions, 'Küçült', lambda: start(True))
            self.button(actions, 'Kopyala', lambda: self.copy(self.value(result)))
            self.button(actions, 'JSON dışa aktar…', lambda: self.export(self.value(result), 'Duzenli.json'))
            page.pack_start(label('Yinelenen anahtarlar, NaN/Infinity, 40 katmandan derin veya 128 KiB’den büyük içerik reddedilir. Kod çalıştırılmaz.', 'dim-label'), False, False, 0)

        def calculator_page(self, page):
            source = self.entry(page, 'Aritmetik ifade', placeholder='Örn. (1250 * 1.20) / 3 + sqrt(81)')
            source.set_max_length(256)
            output = label('0', 'calculator-result')
            page.pack_start(output, False, False, 0)
            history = self.text(page, 'Bu oturumdaki hesaplar · diske kaydedilmez', editable=False)
            def start():
                expression = source.get_text()
                value = core.calculate(expression)
                output.set_text(value)
                history.set_text((expression + ' = ' + value + '\n' + self.value(history))[:8000])
            source.connect('activate', lambda *_: self.guard(start))
            actions = self.actions(page)
            self.button(actions, 'Hesapla', start, 'suggested-action')
            self.button(actions, 'Sonucu kopyala', lambda: self.copy(output.get_text()))
            page.pack_start(label('+ − * / // % **, parantez, sqrt(x), abs(x), pi ve e. Ondalık ayırıcı noktadır. Üs −12…12. Python eval / shell kullanılmaz.', 'dim-label'), False, False, 0)

        def units_page(self, page):
            value = self.entry(page, 'Değer', '1')
            category = self.combo(page, 'Kategori', tuple(core.UNITS))
            source = self.combo(page, 'Kaynak birim', ())
            target = self.combo(page, 'Hedef birim', ())
            output = label('', 'calculator-result'); page.pack_start(output, False, False, 0)
            def changed(*_):
                source.remove_all(); target.remove_all()
                for unit in core.UNITS[category.get_active_text()]: source.append_text(unit); target.append_text(unit)
                source.set_active(0); target.set_active(1)
            category.connect('changed', changed); changed()
            actions = self.actions(page)
            self.button(actions, 'Dönüştür', lambda: output.set_text(core.convert_unit(value.get_text(), category.get_active_text(), source.get_active_text(), target.get_active_text())), 'suggested-action')
            self.button(actions, 'Sonucu kopyala', lambda: self.copy(output.get_text()))

        def colors_page(self, page):
            foreground = self.entry(page, 'Metin rengi', '#213247')
            background = self.entry(page, 'Zemin rengi', '#ffffff')
            preview = Gtk.Label(label='Aa · Okunaklı bir fikir')
            style(preview, 'color-preview'); page.pack_start(preview, False, False, 0)
            provider = Gtk.CssProvider(); preview.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 2)
            output = label(); page.pack_start(output, False, False, 0)
            saved = self.combo(page, 'Kayıtlı renkler', ())
            def inspect():
                first, second = foreground.get_text(), background.get_text()
                value = core.color_info(first, second)
                provider.load_from_data(f'label {{ color: {first}; background-color: {second}; }}'.encode())
                output.set_text(f"RGB {value['rgb']}\nKontrast {value['ratio']:.2f}:1 · AA {'✓' if value['aa'] else 'yetersiz'} · AAA {'✓' if value['aaa'] else 'yetersiz'}\nBüyük metin AA: {'uygun' if value['large_aa'] else 'yetersiz'}")
            def selected_palette(*_):
                color = saved.get_active_text()
                if color: foreground.set_text(color); inspect()
            saved.connect('changed', selected_palette)
            def load_palette():
                def received(value):
                    saved.remove_all()
                    for row in value['palettes']: saved.append(row['id'], row['body'])
                    if value['palettes']: saved.set_active(len(value['palettes']) - 1)
                self.job(lambda _cancel: self.lib.read(), received)
            def save():
                color = foreground.get_text(); core.color_info(color, '#ffffff')
                self.job(lambda _cancel: self.lib.update('palettes', title=color, body=color), lambda _value: load_palette(), mutating=True)
            def remove_palette():
                identifier = saved.get_active_id()
                if not identifier: raise ValueError('Önce kayıtlı bir renk seçin.')
                if self.confirm('Seçili renk paletten kaldırılsın mı?', saved.get_active_text()):
                    self.job(lambda _cancel: self.lib.update('palettes', identifier=identifier, delete=True), lambda _value: load_palette(), mutating=True)
            actions = self.actions(page)
            self.button(actions, 'Kontrastı ölç', inspect, 'suggested-action')
            self.button(actions, 'Metin rengini palete ekle', save)
            self.button(actions, 'Seçili rengi kaldır…', remove_palette)
            self.button(actions, 'Paleti CSS olarak dışa aktar…', lambda: self.job(lambda _cancel: self.lib.read(), lambda value: self.export(':root {\n' + ''.join(f"  --renk-{index + 1}: {row['body']};\n" for index, row in enumerate(value['palettes'])) + '}\n', 'Palet.css')))
            inspect(); load_palette()

        def clock_unmap(self, *_):
            if self.clock_id: GLib.source_remove(self.clock_id); self.clock_id = None

        def clock_map(self, *_):
            if self.current_tool == 'clocks' and self.clock_tick and not self.clock_id:
                self.clock_tick()
                self.clock_id = GLib.timeout_add_seconds(60, self.clock_tick)

        def clocks_page(self, page):
            output = label('', 'world-clocks'); page.pack_start(output, False, False, 0)
            def tick():
                if self.closed or self.current_tool != 'clocks': self.clock_id = None; return GLib.SOURCE_REMOVE
                if self.window.get_mapped():
                    output.set_text('\n\n'.join(f"{row['time']}   {row['zone'].replace('_', ' ')}\n{row['date']}  UTC{row['offset']}" for row in core.world_times()))
                return GLib.SOURCE_CONTINUE
            self.clock_tick = tick
            tick()
            self.clock_id = GLib.timeout_add_seconds(60, tick)
            page.pack_start(label('Yaz saati, kurulu saat dilimi verisinden hesaplanır. GPS, ağ ve konum izni gerekmez. Zamanlayıcı yalnız bu sayfa açıkken vardır.', 'dim-label'), False, False, 0)

        def text_page(self, page):
            source = self.text(page, 'Kaynak metin')
            operation = self.combo(page, 'İşlem', ('Türkçe BÜYÜK', 'Türkçe küçük', 'Satırları sırala', 'Tekrarlı satırları kaldır', 'Kenar boşluklarını temizle'))
            result = self.text(page, 'Sonuç', editable=False)
            stats = label('', 'dim-label'); page.pack_start(stats, False, False, 0)
            def received(value):
                result.set_text(value['text'])
                stats.set_text(f"{value['characters']} karakter · {value['words']} sözcük · {value['lines']} satır")
            def start():
                text, action = self.value(source), operation.get_active_text()
                self.job(lambda _cancel: core.transform_text(text, action), received)
            actions = self.actions(page)
            self.button(actions, 'Uygula', start, 'suggested-action')
            self.button(actions, 'Kopyala', lambda: self.copy(self.value(result)))
            self.button(actions, 'TXT dışa aktar…', lambda: self.export(self.value(result)))

        def startup_page(self, page):
            page.pack_start(label('Çalışan süreçlere dokunulmaz. Değişiklik sonraki oturum içindir; yalnızca kullanıcı başlangıç dosyası / gölgelemesi yazılır. Sistem dosyaları ve servisler değiştirilmez. Yeni komut eklenmez.', 'dim-label'), False, False, 0)
            rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
            page.pack_start(rows, False, False, 0)
            info = label('Bir kayıt seçin.', 'scope-note'); page.pack_start(info, False, False, 0)
            selected = {'entry': None}
            def refresh(_value=None):
                def received(entries):
                    selected['entry'] = None
                    for row in rows.get_children(): row.destroy()
                    for entry in entries:
                        row = Gtk.ListBoxRow(); row.entry = entry
                        row.add(label(('● ' if entry['enabled'] else '○ ') + entry['name'] + ' · ' + entry['scope']))
                        rows.add(row)
                    rows.show_all(); info.set_text('Bir kayıt seçin. Yalnız geçerli masaüstüne ait OnlyShowIn kayıtları oturumda açılır.')
                self.job(lambda cancel: core.startup_entries(cancel=cancel), received)
            def select(_box, row):
                if not hasattr(row, 'entry'): return
                selected['entry'] = row.entry
                info.set_text(row.entry['name'] + '\nKomut (çalıştırılmaz): ' + row.entry['command'] + '\nOnlyShowIn: ' + row.entry['only'])
            rows.connect('row-selected', select)
            def toggle():
                entry = selected['entry']
                if not entry: raise ValueError('Önce bir başlangıç kaydı seçin.')
                if not self.confirm('Sonraki oturum başlangıcı değişsin mi?', entry['name'] + ('\nDevre dışı bırakılacak.' if entry['enabled'] else '\nEtkinleştirilecek. Komutu kontrol edin:\n' + entry['command'])): return
                self.job(lambda _cancel: core.toggle_startup(entry['id'], not entry['enabled']), lambda _value: refresh(), mutating=True)
            def restore():
                entry = selected['entry']
                if not entry: raise ValueError('Önce bir kayıt seçin.')
                if self.confirm('Bu aracın değişikliği geri alınsın mı?', entry['name']):
                    self.job(lambda _cancel: core.restore_startup(entry['id']), lambda _value: refresh(), mutating=True)
            actions = self.actions(page)
            self.button(actions, 'Etkinleştir / devre dışı bırak…', toggle)
            self.button(actions, 'Özgün ayarı geri al…', restore)
            self.button(actions, 'Yenile', refresh)
            refresh()

    return Workbench()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list-tools', action='store_true', help='GTK yüklemeden araç sözleşmesini JSON olarak yaz')
    parser.add_argument('--tool', choices=[item[0] for item in core.TOOLS])
    args = parser.parse_args(argv)
    if args.list_tools:
        print(json.dumps([{'id': item[0], 'name': item[1], 'summary': item[2]} for item in core.TOOLS], ensure_ascii=False))
        return 0
    if os.geteuid() == 0:
        print('Atölye yönetici olarak açılmaz; kişisel masaüstü hesabını kullanın.', file=sys.stderr)
        return 1
    app = application()
    return app.run([sys.argv[0], *(['--tool', args.tool] if args.tool else [])])


if __name__ == '__main__':
    raise SystemExit(main())
