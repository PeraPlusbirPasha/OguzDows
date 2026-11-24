/* GNOME Shell 45–48: ayrı ES module yükleyicisi. */
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
// @OGUZDOWS_CORE@
export default class extends Extension {
    enable() {
        this.instance = new OguzDowsGlass(this.getSettings('org.oguzdows.desktop'));
        try { this.instance.enable(); } catch (error) { this.instance.disable(); this.instance = null; throw error; }
    }
    disable() {
        this.instance?.disable();
        this.instance = null;
    }
}
