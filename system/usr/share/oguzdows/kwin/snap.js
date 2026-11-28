/* SPDX-License-Identifier: GPL-3.0-or-later
 * KWin 5.27 / 6: sabit beş işlem, boş varsayılan kısayol, eval / polling yok.
 * Yalnız açık kullanıcı Snap isteğinde yüklenir. KWin geometri / kuralları
 * uygular; panel, plasmoid, genel kısayol ve pencere yöneticisi değişmez.
 */
'use strict';
const oguzDowsRestore = new WeakMap();

function oguzDowsRectangle(rectangle) {
    return {x: rectangle.x, y: rectangle.y, width: rectangle.width, height: rectangle.height};
}

function oguzDowsSetRectangle(window, rectangle) {
    // Qt'nin QRectF değer tipini koru; keyfî JavaScript QObject ataması yok.
    const geometry = window.frameGeometry;
    geometry.x = rectangle.x; geometry.y = rectangle.y;
    geometry.width = rectangle.width; geometry.height = rectangle.height;
    window.frameGeometry = geometry;
}

function oguzDowsSnap(direction) {
    const window = workspace.activeWindow || workspace.activeClient;
    if (!window || !window.normalWindow || window.fullScreen || window.lockScreen) return;
    if (direction === 'minimize') {
        if (window.minimizable) window.minimized = true;
        return;
    }
    if (direction === 'restore') {
        window.setMaximize(false, false);  // Toggle DEĞİL: normal pencerede de güvenli.
        const saved = oguzDowsRestore.get(window);
        if (saved) {
            window.tile = null;
            oguzDowsSetRectangle(window, saved);
            oguzDowsRestore.delete(window);
        }
        return;
    }
    if (direction === 'maximize') {
        if (window.maximizable) window.setMaximize(true, true);
        return;
    }
    if (!window.moveable || !window.resizeable) return;
    const area = workspace.clientArea(KWin.MaximizeArea, window);
    if (!area || area.width < 160 || area.height < 100) return;
    if (!oguzDowsRestore.has(window))
        oguzDowsRestore.set(window, oguzDowsRectangle(window.frameGeometry));
    window.setMaximize(false, false);
    window.tile = null;
    const half = Math.floor(area.width / 2);
    oguzDowsSetRectangle(window, {x: direction === 'left' ? area.x : area.x + half,
        y: area.y, width: direction === 'left' ? half : area.width - half, height: area.height});
}

for (const direction of ['left', 'right', 'maximize', 'restore', 'minimize']) {
    // Global bir tuş kombinasyonu sahiplenilmez / kullanıcı tercihi ezilmez.
    registerShortcut('OguzDows Snap ' + direction, 'OğuzDows · ' + direction, '', () => oguzDowsSnap(direction));
}
