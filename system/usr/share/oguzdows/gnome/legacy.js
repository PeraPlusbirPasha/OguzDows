/* GNOME Shell 43/44: ES module sözdizimi içermez. */
const {Clutter, Gio, GLib, Meta, Shell, St} = imports.gi;
const Main = imports.ui.main;
const PanelMenu = imports.ui.panelMenu;
const PopupMenu = imports.ui.popupMenu;
const ExtensionUtils = imports.misc.extensionUtils;
// @OGUZDOWS_CORE@
let instance = null;
function init() {}
function enable() {
    instance = new OguzDowsGlass(ExtensionUtils.getSettings('org.oguzdows.desktop'));
    try { instance.enable(); } catch (error) { instance.disable(); instance = null; throw error; }
}
function disable() {
    if (instance) instance.disable();
    instance = null;
}
