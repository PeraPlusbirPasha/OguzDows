/* Source/API contract tests only. Real Shell/KWin tests are smoke-shells.py. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const source = name => fs.readFileSync(path.join(root, 'system/usr/share', name), 'utf8');
const signal = () => {
    const callbacks = [];
    return {connect: callback => callbacks.push(callback), emit: (...args) => callbacks.slice().forEach(callback => callback(...args))};
};

// Never release KWin's grab on the first per-attribute completion (id == 0).
for (const version of [5, 6]) {
    const effect = {configChanged: signal(), animationEnded: signal(),
        readConfig: (_key, _default) => true, isGrabbed: () => false,
        grab: () => true, ungrab: () => released++};
    let released = 0; let cancelled = 0; let id = 0;
    const effects = {windowAdded: signal(), windowClosed: signal(), windowDeleted: signal(), windowDataChanged: signal(),
        stackingOrder: [], hasActiveFullScreenEffect: false, sessionLocked: false};
    if (version === 5) Object.assign(effects, {windowMinimized: signal(), windowUnminimized: signal(), windowFrameGeometryChanged: signal()});
    const subject = vm.runInNewContext(source('kwin/effects/oguzdows-aero/contents/code/main.js'), {
        effect, effects, animationTime: time => time, console: {debug() {}},
        Effect: {WindowAddedGrabRole: 1, WindowClosedGrabRole: 2, WindowMinimizedGrabRole: 3, WindowUnminimizedGrabRole: 4, Scale: 5, Opacity: 6, Translation: 7},
        QEasingCurve: {OutElastic: 1, OutCubic: 2},
        animate: options => options.animations.map(() => ++id), cancel: () => cancelled++,
    });
    const window = {normalWindow: true, geometry: {x: 0, y: 0, width: 400, height: 300},
        minimizedChanged: signal(), windowFrameGeometryChanged: signal()};
    effects.windowAdded.emit(window);
    assert.equal(subject.active.size, 1);
    effect.animationEnded.emit(window, 0);
    assert.equal(released, 0);
    assert.equal(subject.active.size, 1);
    effect.animationEnded.emit(window, 0);
    assert.equal(released, 1);
    assert.equal(subject.active.size, 0);
    effects.windowAdded.emit(window);
    subject.stop(window);
    assert.equal(cancelled, 1);
    assert.equal(released, 2);
    effect.animationEnded.emit(window, 0);
    assert.equal(released, 2);
    subject.geometry(window, {x: 10, y: 10, width: 200, height: 200});
    assert.equal(subject.active.size, 1);
    effect.animationEnded.emit(window, 0);
    assert.equal(subject.active.size, 1);
    effect.animationEnded.emit(window, 0);
    assert.equal(subject.active.size, 0);
    window.normalWindow = false;
    effects.windowAdded.emit(window);
    assert.equal(subject.active.size, 0);
}

// Fixed KWin bridge must not mistake a Maximize toggle for Restore.
for (const activeProperty of ['activeWindow', 'activeClient']) {
    const actions = new Map();
    const window = {normalWindow: true, moveable: true, resizeable: true, maximizable: true, minimizable: true,
        _geometry: {x: 80, y: 90, width: 360, height: 240}, _restore: null,
        get frameGeometry() { return {...this._geometry}; }, set frameGeometry(value) { this._geometry = {...value}; },
        setMaximize(vertical, horizontal) {
            if (vertical && horizontal && !this._restore) { this._restore = this.frameGeometry; this.frameGeometry = {x: 0, y: 24, width: 1001, height: 700}; }
            if (!vertical && !horizontal && this._restore) { this.frameGeometry = this._restore; this._restore = null; }
        }};
    const original = window.frameGeometry;
    vm.runInNewContext(source('oguzdows/kwin/snap.js'), {
        workspace: {[activeProperty]: window, clientArea: () => ({x: 0, y: 24, width: 1001, height: 700})},
        KWin: {MaximizeArea: 0},
        registerShortcut: (name, _label, shortcut, callback) => { assert.equal(shortcut, ''); actions.set(name.split(' ').at(-1), callback); },
    });
    for (const direction of ['restore', 'left', 'right', 'maximize', 'restore']) {
        actions.get(direction)(); const first = window.frameGeometry;
        actions.get(direction)(); assert.deepEqual(window.frameGeometry, first, direction + ' must be idempotent');
    }
    assert.deepEqual(window.frameGeometry, original);
    actions.get('maximize')(); actions.get('restore')();
    assert.deepEqual(window.frameGeometry, original);
    window.fullScreen = true; actions.get('left')(); assert.deepEqual(window.frameGeometry, original);
}

// GNOME uses a custom native timeline when exposed; new GI ABIs can instead
// expose only native easing modes. Both paths preserve Shell callbacks.
for (const customFunction of [false, true]) {
    const scope = {Meta: {WindowType: {NORMAL: 0}}, Clutter: {AnimationMode: {EASE_OUT_CUBIC: 2, EASE_OUT_ELASTIC: 3}}};
    vm.createContext(scope); vm.runInContext(source('oguzdows/gnome/core.js'), scope);
    const subject = new scope.OguzDowsGlass({get_string: () => 'spring'});
    subject.animations = () => true;
    const attached = [];
    const transitions = new Map(['scale-x', 'scale-y', 'opacity'].map(name => [name, customFunction ?
        {set_progress_func: callback => attached.push([name, callback])} : {set_progress_mode: mode => attached.push([name, mode])}]));
    let params;
    const actor = {meta_window: {get_window_type: () => 0}, connect: () => 1,
        get_transition: name => transitions.get(name), ease: value => {params = value; return 'original-return';}};
    const complete = () => {}; subject.wrap(actor);
    assert.equal(actor.ease({scale_x: 1, scale_y: 1, opacity: 255, onStopped: complete}), 'original-return');
    assert.equal(params.onStopped, complete);
    assert.equal(subject.springTransitions, 3);
    assert.equal(attached.length, 3);
    assert.equal(subject.springCurveApi, customFunction ? 'native-custom-critical-damping' : 'native-clutter-elastic');
    if (!customFunction) assert.equal(attached.find(([name]) => name === 'opacity')[1], 2);
}
console.log('Desktop JavaScript source/API contracts passed; not real compositor evidence.');
