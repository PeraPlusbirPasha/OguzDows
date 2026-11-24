/* SPDX-License-Identifier: GPL-3.0-or-later
 * KWin 5.27 / 6 yerel scripted effect. Panel/plasmoid değiştirmez.
 * Çalışan pencerelerde yalnız geçici paint dönüşümü; geometriyi WM belirler.
 */
'use strict';
class OguzDowsAero {
    constructor() {
        this.active = new Map();
        this.readConfig();
        effect.configChanged.connect(() => this.readConfig());
        effects.windowAdded.connect(window => { this.watch(window); this.transition(window, true, false); });
        effects.windowClosed.connect(window => this.transition(window, false, false));
        effects.windowDeleted.connect(window => this.active.delete(window));
        effects.windowDataChanged.connect((window, role) => {
            const row = this.active.get(window);
            if (row && row.role === role && effect.isGrabbed(window, role)) this.stop(window);
        });
        effect.animationEnded.connect(window => {
            const row = this.active.get(window);
            if (row && row.role) effect.ungrab(window, row.role);
            this.active.delete(window);
        });
        if (effects.windowMinimized) {
            effects.windowMinimized.connect(window => this.transition(window, false, true));
            effects.windowUnminimized.connect(window => this.transition(window, true, true));
        }
        if (effects.windowFrameGeometryChanged)
            effects.windowFrameGeometryChanged.connect((window, old) => this.geometry(window, old));
        for (const window of effects.stackingOrder) this.watch(window);
    }

    readConfig() {
        this.duration = animationTime(240);
        this.snap = effect.readConfig('Snap', false);
    }

    eligible(window) {
        return this.duration > 0 && !effects.hasActiveFullScreenEffect && !effects.sessionLocked &&
            window && (window.normalWindow || window.dialog) && !window.lockScreen &&
            !window.desktopWindow && !window.dock && !window.popupWindow && !window.fullScreen &&
            !/ksmserver|ksplashqml|spectacle|oguzdows-install|Rıfkı/.test(window.windowClass || '');
    }

    watch(window) {
        // KWin 6 bildirimleri EffectWindow'a taşındı. 5.27 sinyallerini
        // ikinci kez bağlamayıp aynı küçülmeye iki animasyon uygulama.
        if (!effects.windowMinimized && window.minimizedChanged)
            window.minimizedChanged.connect(() => this.transition(window, !window.minimized, true));
        if (!effects.windowFrameGeometryChanged && window.windowFrameGeometryChanged)
            window.windowFrameGeometryChanged.connect((_window, old) => this.geometry(window, old));
    }

    stop(window) {
        const row = this.active.get(window);
        if (row) {
            // Önce sil: cancel'ın senkron animationEnded callback'i yeni bir
            // animasyonun rolünü yanlışlıkla bırakmasın.
            this.active.delete(window);
            cancel(row.ids);
            if (row.role) effect.ungrab(window, row.role);
        }
    }

    transition(window, opening, minimized) {
        if (!this.eligible(window) || window.skipsCloseAnimation && !opening) return;
        const role = minimized ? (opening ? Effect.WindowUnminimizedGrabRole : Effect.WindowMinimizedGrabRole) :
            (opening ? Effect.WindowAddedGrabRole : Effect.WindowClosedGrabRole);
        if (role && effect.isGrabbed(window, role)) return;
        this.stop(window);
        if (role && !effect.grab(window, role)) return;
        const start = opening ? (minimized ? 0.88 : 0.95) : 1;
        const finish = opening ? 1 : (minimized ? 0.88 : 0.96);
        const ids = animate({window, duration: this.duration, curve: QEasingCurve.OutElastic,
            animations: [
                {type: Effect.Scale, from: start, to: finish},
                // Opaklık monoton kalır; yay yalnız ölçeğe uygulanır.
                {type: Effect.Opacity, from: opening ? 0 : 1, to: opening ? 1 : 0,
                    curve: QEasingCurve.OutCubic},
            ]});
        this.active.set(window, {ids, role});
    }

    geometry(window, old) {
        if (!this.snap || !this.eligible(window) || window.move || window.resize || !old) return;
        const now = window.geometry;
        if (!now || now.width <= 0 || now.height <= 0 || old.width <= 0 || old.height <= 0 ||
            Math.abs(old.width - now.width) + Math.abs(old.height - now.height) < 12) return;
        this.stop(window);
        const ids = animate({window, duration: this.duration, curve: QEasingCurve.OutElastic,
            animations: [
                {type: Effect.Scale, from: {value1: old.width / now.width, value2: old.height / now.height}, to: 1},
                {type: Effect.Translation, from: {value1: old.x - now.x + (old.width - now.width) / 2,
                    value2: old.y - now.y + (old.height - now.height) / 2}, to: {value1: 0, value2: 0}},
            ]});
        this.active.set(window, {ids, role: null});
    }
}
new OguzDowsAero();
