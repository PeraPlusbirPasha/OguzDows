/* SPDX-License-Identifier: GPL-3.0-or-later
 * Yerel GNOME Shell katmanı. 43/44 ve 45–48 yükleyicileri ayrı dosyalardır.
 * Shell'in map/destroy completion sinyalleri değiştirilmez / engellenmez.
 */
var OguzDowsGlass = class {
    constructor(settings) {
        this.settings = settings;
        this.connections = [];
        this.materials = [];
        this.wrappers = new Map();
        this.sources = new Set();
        this.restoreRects = new WeakMap();
    }

    connect(object, signal, callback) {
        const id = object.connect(signal, callback);
        this.connections.push([object, id]);
        return id;
    }

    static response(_timeline, elapsed, duration) {
        const t = Math.min(1, Math.max(0, elapsed / Math.max(1, duration)));
        // Kritik sönümlü birim kütle-yay. Son frame TAM 1; hedefe sıçrama yok.
        return (1 - (1 + 9 * t) * Math.exp(-9 * t)) / (1 - 10 * Math.exp(-9));
    }

    enable() {
        this.interfaceSettings = new Gio.Settings({schema_id: 'org.gnome.desktop.interface'});
        this.button = new PanelMenu.Button(0.0, 'OğuzDows');
        this.button.add_child(new St.Icon({icon_name: 'oguzdows-hub-symbolic', style_class: 'system-status-icon'}));
        const items = [
            ['Başlat · uygulamalar', () => this.launch('/usr/local/bin/oguzdows-hub')],
            ['Etkinlikler', () => Main.overview.toggle()],
            ['Uygulama ızgarası', () => Main.overview.showApps()],
            ['Canlı CPU / RAM / ağ', () => this.launch('/usr/local/bin/oguzdows-monitor')],
            ['Masaüstü ve Aero ayarları', () => this.launch('/usr/local/bin/oguzdows-desktop')],
        ];
        for (const [title, callback] of items) {
            const item = new PopupMenu.PopupMenuItem(title);
            item.connect('activate', callback);
            this.button.menu.addMenuItem(item);
        }
        Main.panel.addToStatusArea('oguzdows-glass', this.button);
        this.button.set_pivot_point(0.5, 0.5);
        this.connect(this.button, 'notify::hover', () => {
            if (!this.animations()) return;
            const scale = this.button.hover ? 1.06 : 1;
            this.button.ease({scale_x: scale, scale_y: scale, duration: 180,
                mode: Clutter.AnimationMode.EASE_OUT_CUBIC});
        });
        this.connect(this.settings, 'changed', () => this.refresh());
        this.connect(this.interfaceSettings, 'changed::enable-animations', () => this.refresh());
        this.connect(Main.sessionMode, 'updated', () => this.refresh());
        this.connect(global.window_manager, 'map', (_wm, actor) => this.wrap(actor));
        for (const actor of global.get_window_actors()) this.wrap(actor);
        const xml = '<node><interface name="org.oguzdows.Desktop">' +
            '<method name="GetState"><arg direction="out" type="s" name="state"/></method>' +
            '<method name="Snap"><arg direction="in" type="s" name="direction"/></method>' +
            '<method name="Open"><arg direction="in" type="s" name="target"/></method>' +
            '</interface></node>';
        this.exported = Gio.DBusExportedObject.wrapJSObject(xml, {
            GetState: () => JSON.stringify({accent: this.settings.get_string('accent'),
                blur_attached: this.materials.length > 0, spring_enabled: this.animations() && this.settings.get_string('motion') === 'spring',
                scope: 'GNOME Shell açılır menüleri; opak üst çubuk ve uygulama içerikleri korunur.'}),
            Snap: direction => this.snap(direction),
            Open: target => this.open(target),
        });
        this.exported.export(Gio.DBus.session, '/org/oguzdows/Desktop');
        this.refresh();
    }

    launch(path) {
        // Sabit dahili yollar; komut metni / kullanıcı girdisi çalıştırılmaz.
        Gio.Subprocess.new([path], Gio.SubprocessFlags.NONE);
    }

    open(target) {
        if (target === 'notifications') Main.panel.statusArea.dateMenu.menu.toggle();
        else if (target === 'quick-settings') Main.panel.statusArea.quickSettings.menu.toggle();
        else if (target === 'apps') Main.overview.showApps();
        else if (target === 'hide-overview') Main.overview.hide();
        else throw new Error('İzin verilmeyen masaüstü hedefi');
    }

    animations() {
        return !Main.sessionMode.isLocked && !Main.sessionMode.isGreeter &&
            this.settings.get_string('motion') !== 'reduced' &&
            this.interfaceSettings.get_boolean('enable-animations');
    }

    wrap(actor) {
        if (this.wrappers.has(actor) || !actor.meta_window ||
            actor.meta_window.get_window_type() !== Meta.WindowType.NORMAL) return;
        const original = actor.ease;
        const own = Object.prototype.hasOwnProperty.call(actor, 'ease');
        const self = this;
        const wrapper = function(parameters) {
            // Başka uzantının callback / complete akışı korunur. Yalnız Shell'in
            // zaten oluşturduğu sınırlı geçişin eğrisi değiştirilir.
            if (!self.animations() || self.settings.get_string('motion') !== 'spring' ||
                !parameters || (!('scale_x' in parameters) && !('scale_y' in parameters)))
                return original.call(this, parameters);
            const values = {...parameters, duration: 240};
            if (values.scale_x === 1 && this.scale_x < 0.5 && values.opacity === 255) {
                this.set_pivot_point(0.5, 0.5);
                this.set_scale(0.94, 0.94);
            }
            const result = original.call(this, values);
            for (const property of ['scale-x', 'scale-y', 'opacity', 'x', 'y', 'translation-x', 'translation-y']) {
                const transition = this.get_transition(property);
                if (transition && typeof transition.set_progress_func === 'function')
                    transition.set_progress_func(OguzDowsGlass.response);
            }
            return result;
        };
        const destroyId = actor.connect('destroy', () => this.wrappers.delete(actor));
        this.wrappers.set(actor, {original, wrapper, own, destroyId});
        actor.ease = wrapper;
    }

    clearMaterials() {
        for (const row of this.materials) {
            try {
                if (row.actor.get_style() === row.style) row.actor.set_style(row.previous);
                row.actor.remove_style_class_name('oguzdows-glass');
                row.actor.remove_effect(row.effect);
            } catch (_error) { /* Shell menüsü yeniden yaratılmış olabilir. */ }
        }
        this.materials = [];
    }

    refresh() {
        this.clearMaterials();
        this.button.set_scale(1, 1);
        // Kilit / parola / greeter yüzeylerine efekt uygulanmaz.
        if (!this.settings.get_boolean('glass-enabled') || Main.sessionMode.isLocked || Main.sessionMode.isGreeter)
            return;
        const accent = this.settings.get_string('accent');
        if (!/^#[0-9a-fA-F]{6}$/.test(accent)) return;
        const dark = this.settings.get_boolean('dark');
        const rgb = dark ? '22,35,51' : '235,244,253';
        const actors = [this.button.menu.box, Main.panel.statusArea.quickSettings?.menu?.box,
            Main.panel.statusArea.dateMenu?.menu?.box].filter(Boolean);
        for (const actor of actors) {
            const effect = new Shell.BlurEffect({mode: Shell.BlurMode.BACKGROUND, brightness: 1.0});
            // Mutter 47+: radius, eski API: sigma. Çalışmayan özellik yazılmaz.
            if (typeof effect.set_radius === 'function') effect.set_radius(18);
            else effect.set_sigma(14);
            const previous = actor.get_style() || '';
            const style = previous + `;background-color: rgba(${rgb},0.88);border-color: ${accent};color: ${dark ? '#f3f7fb' : '#172b40'};`;
            actor.add_effect_with_name('oguzdows-backdrop', effect);
            actor.add_style_class_name('oguzdows-glass');
            actor.set_style(style);
            this.materials.push({actor, effect, previous, style});
        }
    }

    snap(direction) {
        if (!['left', 'right', 'maximize', 'restore', 'minimize'].includes(direction))
            throw new Error('Bilinmeyen Snap yönü');
        const window = global.display.focus_window;
        if (!window || window.get_window_type() !== Meta.WindowType.NORMAL || Main.sessionMode.isLocked)
            throw new Error('Yerleştirilebilir etkin pencere yok');
        if (direction === 'minimize') { window.minimize(); return; }
        const old = window.get_frame_rect();
        if (direction === 'restore') {
            window.unmaximize(Meta.MaximizeFlags.BOTH);
            const saved = this.restoreRects.get(window);
            if (saved) {
                window.move_resize_frame(true, saved.x, saved.y, saved.width, saved.height);
                this.restoreRects.delete(window);
            }
            return;
        }
        if (!this.restoreRects.has(window)) this.restoreRects.set(window, old);
        if (direction === 'maximize') { window.maximize(Meta.MaximizeFlags.BOTH); return; }
        const area = window.get_work_area_current_monitor();
        const half = Math.floor(area.width / 2);
        window.unmaximize(Meta.MaximizeFlags.BOTH);
        window.move_resize_frame(true, direction === 'left' ? area.x : area.x + half,
            area.y, direction === 'left' ? half : area.width - half, area.height);
        if (!this.animations() || !this.settings.get_boolean('snap-animation')) return;
        // Tek boşta callback: yeni buffer geometrisini bekle; periyodik iş yok.
        const source = GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
            this.sources.delete(source);
            const actor = window.get_compositor_private();
            const now = window.get_frame_rect();
            if (!actor || now.width <= 0 || now.height <= 0 || actor.get_transition('scale-x'))
                return GLib.SOURCE_REMOVE;
            actor.set_pivot_point(0, 0);
            actor.scale_x = old.width / now.width;
            actor.scale_y = old.height / now.height;
            actor.translation_x = old.x - now.x;
            actor.translation_y = old.y - now.y;
            actor.ease({scale_x: 1, scale_y: 1, translation_x: 0, translation_y: 0,
                duration: 220, mode: Clutter.AnimationMode.EASE_OUT_CUBIC});
            return GLib.SOURCE_REMOVE;
        });
        this.sources.add(source);
    }

    disable() {
        this.exported?.unexport();
        this.exported = null;
        for (const source of this.sources) GLib.Source.remove(source);
        this.sources.clear();
        for (const [object, id] of this.connections) object.disconnect(id);
        this.connections = [];
        this.clearMaterials();
        for (const [actor, row] of this.wrappers) {
            if (actor.ease === row.wrapper) {
                if (row.own) actor.ease = row.original;
                else delete actor.ease;
            }
            actor.disconnect(row.destroyId);
        }
        this.wrappers.clear();
        // Devam eden native geçişi durdurma: Shell completion callback'i doğal
        // olarak çalışır. Callback salt matematik fonksiyonuna bağlıdır.
        this.button?.destroy();
        this.button = null;
        this.interfaceSettings = null;
        this.restoreRects = new WeakMap();
    }
};
