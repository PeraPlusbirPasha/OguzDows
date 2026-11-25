/* Native Xfce panel component, not a shell / Plank / Python animation loop.
 * Windows: one expanding, screen-centred task group + native right-hand tray.
 * Mac: content-sized independent dock, traffic lights belong to GTK / Xfwm.
 * Magnification paints a cached pixbuf inside a fixed slot; no panel reflow.
 */
#define _POSIX_C_SOURCE 200809L
#define WNCK_I_KNOW_THIS_IS_UNSTABLE
#include <gtk/gtk.h>
#include <gdk/gdkx.h>
#include <gio/gdesktopappinfo.h>
#include <libwnck/libwnck.h>
#include <libxfce4panel/libxfce4panel.h>
#include <xfconf/xfconf.h>
#include <X11/Xatom.h>
#include <sys/stat.h>
#include <unistd.h>
#include <math.h>
#include <string.h>

#ifndef OGUZDOWS_HUB
#define OGUZDOWS_HUB "/usr/local/bin/oguzdows-hub"
#endif

typedef struct Tasks Tasks;
typedef struct {
    Tasks *owner;
    gchar *id;
    GAppInfo *app;
    GPtrArray *windows;
    GtkWidget *button, *area, *menu;
    GdkPixbuf *icon;
    gboolean start, active, hover;
    double scale, from, target;
    gint64 began;
} Item;
struct Tasks {
    XfcePanelPlugin *plugin;
    GtkWidget *fixed, *top;
    XfconfChannel *channel;
    WnckHandle *handle;
    WnckScreen *screen;
    GPtrArray *items, *watched;
    GFileMonitor *pins_monitor;
    gchar *style_key;
    guint refresh, animation;
    gint size;
    gboolean mac, disposing;
};

/* GtkFixed normally includes absolute child offsets in its minimum width.
 * That would retain yesterday's centring offset after a monitor shrinks. */
typedef struct { GtkFixed parent; } TaskStrip;
typedef struct { GtkFixedClass parent; } TaskStripClass;
G_DEFINE_TYPE(TaskStrip, task_strip, GTK_TYPE_FIXED)
static void preferred_width(GtkWidget *widget, gint *minimum, gint *natural) {
    Tasks *tasks = g_object_get_data(G_OBJECT(widget), "tasks");
    gint width = tasks && tasks->mac ? (gint)tasks->items->len * 58 + 16 : 80;
    *minimum = width; *natural = width;
}
static void task_strip_class_init(TaskStripClass *klass) { GTK_WIDGET_CLASS(klass)->get_preferred_width = preferred_width; }
static void task_strip_init(TaskStrip *strip) { (void)strip; }

static void queue_refresh(Tasks *tasks);
static void place(Tasks *tasks);

static gboolean animations(void) {
    gboolean enabled = FALSE;
    g_object_get(gtk_settings_get_default(), "gtk-enable-animations", &enabled, NULL);
    return enabled;
}

static void item_free(gpointer pointer) {
    Item *item = pointer;
    if (item->menu) gtk_widget_destroy(item->menu);
    g_clear_object(&item->app);
    g_clear_object(&item->icon);
    g_ptr_array_unref(item->windows);
    g_free(item->id); g_free(item);
}

static gboolean draw_icon(GtkWidget *widget, cairo_t *cr, gpointer pointer) {
    Item *item = pointer;
    gint width = gtk_widget_get_allocated_width(widget), height = gtk_widget_get_allocated_height(widget);
    double base = MIN(item->owner->mac ? 40.0 : 30.0, width - 8.0);
    double pixels = MIN(height - 12.0, base * item->scale);
    if (item->icon && pixels > 0) {
        cairo_save(cr);
        cairo_translate(cr, (width - pixels) / 2, (height - pixels) / 2 - (item->owner->mac ? 3 : 1));
        cairo_scale(cr, pixels / gdk_pixbuf_get_width(item->icon), pixels / gdk_pixbuf_get_height(item->icon));
        gdk_cairo_set_source_pixbuf(cr, item->icon, 0, 0); cairo_paint(cr); cairo_restore(cr);
    }
    if (item->windows->len) {
        GdkRGBA color;
        GtkStyleContext *context = gtk_widget_get_style_context(item->button);
        if (!gtk_style_context_lookup_color(context, "theme_selected_bg_color", &color))
            gdk_rgba_parse(&color, "#287ab2");
        gdk_cairo_set_source_rgba(cr, &color);
        if (item->owner->mac) { cairo_arc(cr, width / 2.0, height - 5, item->active ? 2.5 : 1.8, 0, 2 * G_PI); cairo_fill(cr); }
        else { cairo_set_line_width(cr, 3); cairo_set_line_cap(cr, CAIRO_LINE_CAP_ROUND);
            cairo_move_to(cr, width / 2.0 - (item->active ? 8 : 3), height - 4);
            cairo_line_to(cr, width / 2.0 + (item->active ? 8 : 3), height - 4); cairo_stroke(cr); }
    }
    return FALSE;
}

static gboolean animate(gpointer pointer) {
    Tasks *tasks = pointer;
    gboolean moving = FALSE;
    gint64 now = g_get_monotonic_time();
    for (guint i = 0; i < tasks->items->len; i++) {
        Item *item = g_ptr_array_index(tasks->items, i);
        double t = CLAMP((now - item->began) / 150000.0, 0.0, 1.0);
        double ease = 1 - pow(1 - t, 3);
        item->scale = item->from + (item->target - item->from) * ease;
        gtk_widget_queue_draw(item->area);
        moving |= t < 1 && fabs(item->scale - item->target) > .001;
    }
    if (!moving) tasks->animation = 0;
    return moving ? G_SOURCE_CONTINUE : G_SOURCE_REMOVE;
}

static gboolean hover(GtkWidget *widget, GdkEventCrossing *event, gpointer pointer) {
    (void)widget;
    Item *item = pointer;
    item->hover = event->type == GDK_ENTER_NOTIFY;
    Tasks *tasks = item->owner;
    if (!tasks->mac || !animations()) return FALSE;
    for (guint i = 0; i < tasks->items->len; i++) {
        Item *other = g_ptr_array_index(tasks->items, i);
        other->from = other->scale;
        other->target = other->hover ? 1.24 : 1.0;
        other->began = g_get_monotonic_time();
    }
    if (!tasks->animation) tasks->animation = g_timeout_add(16, animate, tasks);
    return FALSE;
}

static void launch(Item *item) {
    GError *error = NULL;
    if (item->start) {
        const gchar *args[] = {OGUZDOWS_HUB, NULL};
        g_spawn_async(NULL, (gchar **)args, NULL, G_SPAWN_DEFAULT, NULL, NULL, NULL, &error);
    } else if (item->app) {
        GdkAppLaunchContext *context = gdk_display_get_app_launch_context(gdk_display_get_default());
        gdk_app_launch_context_set_timestamp(context, gtk_get_current_event_time());
        g_app_info_launch(item->app, NULL, G_APP_LAUNCH_CONTEXT(context), &error);
        g_object_unref(context);
    }
    if (error) { g_warning("OğuzDows görev başlatma: %s", error->message); g_error_free(error); }
}

static void activate_window(GtkMenuItem *menu, gpointer pointer) {
    (void)menu;
    WnckWindow *window = pointer;
    if (wnck_window_is_minimized(window)) wnck_window_unminimize(window, gtk_get_current_event_time());
    wnck_window_activate(window, gtk_get_current_event_time());
}

static void launch_menu(GtkMenuItem *menu, gpointer pointer) { (void)menu; launch(pointer); }

static void popup(Item *item, const GdkEvent *event) {
    if (item->menu) gtk_widget_destroy(item->menu);
    item->menu = gtk_menu_new();
    for (guint i = 0; i < item->windows->len; i++) {
        WnckWindow *window = g_ptr_array_index(item->windows, i);
        GtkWidget *row = gtk_menu_item_new_with_label(wnck_window_get_name(window));
        gtk_menu_shell_append(GTK_MENU_SHELL(item->menu), row);
        g_signal_connect(row, "activate", G_CALLBACK(activate_window), window);
    }
    if (item->app || item->start) {
        GtkWidget *row = gtk_menu_item_new_with_label(item->start ? "Başlat menüsü" : "Uygulamayı başlat");
        gtk_menu_shell_append(GTK_MENU_SHELL(item->menu), row);
        g_signal_connect(row, "activate", G_CALLBACK(launch_menu), item);
    }
    gtk_widget_show_all(item->menu);
    gtk_menu_popup_at_widget(GTK_MENU(item->menu), item->button, GDK_GRAVITY_NORTH, GDK_GRAVITY_SOUTH, event);
}

static gboolean press(GtkWidget *widget, GdkEventButton *event, gpointer pointer) {
    (void)widget;
    if (event->button != 3) return FALSE;
    popup(pointer, (GdkEvent *)event); return TRUE;
}

static void clicked(GtkButton *button, gpointer pointer) {
    (void)button;
    Item *item = pointer;
    if (item->windows->len > 1) { popup(item, NULL); return; }
    if (!item->windows->len) { launch(item); return; }
    WnckWindow *window = g_ptr_array_index(item->windows, 0);
    if (wnck_window_is_active(window) && !wnck_window_is_minimized(window)) wnck_window_minimize(window);
    else activate_window(NULL, window);
}

static gboolean keyboard_popup(GtkWidget *widget, gpointer pointer) {
    (void)widget; popup(pointer, NULL); return TRUE;
}

static Item *add_item(Tasks *tasks, const gchar *id, GAppInfo *app, WnckWindow *window, gboolean start) {
    Item *item = g_new0(Item, 1);
    item->owner = tasks; item->id = g_strdup(id); item->app = app ? g_object_ref(app) : NULL;
    item->start = start; item->scale = item->from = item->target = 1;
    item->windows = g_ptr_array_new_with_free_func(g_object_unref);
    item->button = gtk_button_new(); item->area = gtk_drawing_area_new();
    gtk_widget_set_can_focus(item->button, TRUE);
    gtk_widget_set_name(item->button, id);
    gtk_style_context_add_class(gtk_widget_get_style_context(item->button), "oguzdows-task");
    gtk_container_add(GTK_CONTAINER(item->button), item->area);
    gtk_fixed_put(GTK_FIXED(tasks->fixed), item->button, 0, 0);
    const gchar *title = start ? "Başlat" : app ? g_app_info_get_display_name(app) : window ? wnck_window_get_name(window) : id;
    gtk_widget_set_tooltip_text(item->button, title);
    atk_object_set_name(gtk_widget_get_accessible(item->button), title);
    GtkIconTheme *theme = gtk_icon_theme_get_default();
    GIcon *icon = app ? g_app_info_get_icon(app) : NULL;
    GtkIconInfo *info = icon ? gtk_icon_theme_lookup_by_gicon(theme, icon, 64, GTK_ICON_LOOKUP_FORCE_SIZE) : NULL;
    if (info) { item->icon = gtk_icon_info_load_icon(info, NULL); g_object_unref(info); }
    if (!item->icon && window && wnck_window_get_icon(window)) item->icon = g_object_ref(wnck_window_get_icon(window));
    if (!item->icon) item->icon = gtk_icon_theme_load_icon(theme, start ? "oguzdows" : "application-x-executable", 64, 0, NULL);
    g_signal_connect(item->area, "draw", G_CALLBACK(draw_icon), item);
    g_signal_connect(item->button, "clicked", G_CALLBACK(clicked), item);
    g_signal_connect(item->button, "button-press-event", G_CALLBACK(press), item);
    g_signal_connect(item->button, "enter-notify-event", G_CALLBACK(hover), item);
    g_signal_connect(item->button, "leave-notify-event", G_CALLBACK(hover), item);
    g_signal_connect(item->button, "popup-menu", G_CALLBACK(keyboard_popup), item);
    g_ptr_array_add(tasks->items, item); gtk_widget_show_all(item->button);
    return item;
}

static gchar *window_id(WnckWindow *window) {
    const gchar *value = wnck_window_get_class_group_name(window);
    gchar *lower = g_utf8_strdown(value ? value : "application", -1);
    const gchar *known = NULL;
    if (strstr(lower, "thunar")) known = "oguzdows-files.desktop";
    else if (strstr(lower, "firefox") || strstr(lower, "chromium")) known = "oguzdows-browser.desktop";
    else if (strstr(lower, "xfce4-terminal")) known = "oguzdows-terminal.desktop";
    else if (strstr(lower, "oguzdows") && strstr(lower, "store")) known = "oguzdows-store.desktop";
    if (known) { g_free(lower); return g_strdup(known); }
    return lower;
}

static Item *find_item(Tasks *tasks, const gchar *id, WnckWindow *window) {
    const gchar *wm = wnck_window_get_class_group_name(window);
    for (guint i = 0; i < tasks->items->len; i++) {
        Item *item = g_ptr_array_index(tasks->items, i);
        if (!g_strcmp0(item->id, id)) return item;
        const gchar *startup = item->app && G_IS_DESKTOP_APP_INFO(item->app)
            ? g_desktop_app_info_get_startup_wm_class(G_DESKTOP_APP_INFO(item->app)) : NULL;
        if (startup && wm && !g_ascii_strcasecmp(startup, wm)) return item;
    }
    return NULL;
}

static void window_changed(WnckWindow *window, gpointer pointer) { (void)window; queue_refresh(pointer); }
static void state_changed(WnckWindow *window, WnckWindowState old, WnckWindowState changed, gpointer pointer) {
    (void)old; (void)changed; window_changed(window, pointer);
}

static void clear_watches(Tasks *tasks) {
    for (guint i = 0; i < tasks->watched->len; i++) g_signal_handlers_disconnect_by_data(g_ptr_array_index(tasks->watched, i), tasks);
    g_ptr_array_set_size(tasks->watched, 0);
}

static gboolean rebuild(gpointer pointer) {
    Tasks *tasks = pointer; tasks->refresh = 0;
    if (tasks->animation) { g_source_remove(tasks->animation); tasks->animation = 0; }
    clear_watches(tasks);
    for (guint i = 0; i < tasks->items->len; i++) gtk_widget_destroy(((Item *)g_ptr_array_index(tasks->items, i))->button);
    g_ptr_array_set_size(tasks->items, 0);
    if (!tasks->mac) add_item(tasks, "oguzdows-start", NULL, NULL, TRUE);
    GKeyFile *pins = g_key_file_new();
    gchar *path = g_build_filename(g_get_user_config_dir(), "oguzdows", "pins.ini", NULL);
    struct stat details;
    if (!lstat(path, &details) && S_ISREG(details.st_mode) && details.st_uid == getuid() && details.st_size < 65536)
        g_key_file_load_from_file(pins, path, G_KEY_FILE_NONE, NULL);
    g_free(path);
    const gchar *defaults[] = {"oguzdows-browser.desktop", "oguzdows-files.desktop", "oguzdows-store.desktop", "oguzdows-terminal.desktop", NULL};
    GPtrArray *ids = g_ptr_array_new_with_free_func(g_free);
    for (guint i = 0; defaults[i]; i++)
        if (!g_key_file_has_key(pins, "Pins", defaults[i], NULL) || g_key_file_get_boolean(pins, "Pins", defaults[i], NULL))
            g_ptr_array_add(ids, g_strdup(defaults[i]));
    gsize count = 0; gchar **keys = g_key_file_get_keys(pins, "Pins", &count, NULL);
    for (gsize i = 0; keys && i < count && ids->len < 16; i++) {
        gboolean duplicate = FALSE;
        for (guint n = 0; n < ids->len; n++) duplicate |= !g_strcmp0(keys[i], g_ptr_array_index(ids, n));
        if (!duplicate && g_str_has_suffix(keys[i], ".desktop") && !strchr(keys[i], '/') && strlen(keys[i]) < 256
                && g_key_file_get_boolean(pins, "Pins", keys[i], NULL)) g_ptr_array_add(ids, g_strdup(keys[i]));
    }
    g_strfreev(keys); g_key_file_unref(pins);
    for (guint i = 0; i < ids->len; i++) {
        const gchar *id = g_ptr_array_index(ids, i);
        GDesktopAppInfo *app = g_desktop_app_info_new(id);
        if (app) { add_item(tasks, id, G_APP_INFO(app), NULL, FALSE); g_object_unref(app); }
    }
    g_ptr_array_unref(ids);
    for (GList *row = wnck_screen_get_windows(tasks->screen); row; row = row->next) {
        WnckWindow *window = row->data;
        if (wnck_window_is_skip_tasklist(window) || wnck_window_get_window_type(window) != WNCK_WINDOW_NORMAL) continue;
        g_ptr_array_add(tasks->watched, g_object_ref(window));
        g_signal_connect(window, "state-changed", G_CALLBACK(state_changed), tasks);
        g_signal_connect(window, "icon-changed", G_CALLBACK(window_changed), tasks);
        g_signal_connect(window, "name-changed", G_CALLBACK(window_changed), tasks);
        gchar *id = window_id(window);
        Item *item = find_item(tasks, id, window);
        if (!item) {
            gchar *desktop_id = g_strconcat(id, ".desktop", NULL);
            GDesktopAppInfo *app = g_desktop_app_info_new(desktop_id); g_free(desktop_id);
            item = add_item(tasks, id, app ? G_APP_INFO(app) : NULL, window, FALSE);
            g_clear_object(&app);
        }
        g_free(id); g_ptr_array_add(item->windows, g_object_ref(window));
        item->active |= wnck_window_is_active(window);
    }
    for (guint i = 0; i < tasks->items->len; i++) {
        Item *item = g_ptr_array_index(tasks->items, i);
        gtk_widget_set_state_flags(item->button, item->active ? GTK_STATE_FLAG_CHECKED : GTK_STATE_FLAG_NORMAL, TRUE);
    }
    gint width = tasks->mac ? (gint)tasks->items->len * 58 + 16 : 80;
    gtk_widget_set_size_request(tasks->fixed, width, tasks->size);
    place(tasks); gtk_widget_queue_resize(tasks->fixed);
    return G_SOURCE_REMOVE;
}

static void queue_refresh(Tasks *tasks) {
    if (!tasks->disposing && !tasks->refresh) tasks->refresh = g_idle_add(rebuild, tasks);
}

static void screen_changed(WnckScreen *screen, WnckWindow *window, gpointer pointer) {
    (void)screen; (void)window; queue_refresh(pointer);
}

static void place(Tasks *tasks) {
    if (!tasks->items->len || !gtk_widget_get_realized(tasks->fixed)) return;
    gint width = gtk_widget_get_allocated_width(tasks->fixed), height = gtk_widget_get_allocated_height(tasks->fixed);
    gint origin_x = 0, origin_y = 0, offset_x = 0, offset_y = 0;
    GtkWidget *top = gtk_widget_get_toplevel(tasks->fixed);
    GdkWindow *window = gtk_widget_get_window(top);
    if (!window) return;
    gdk_window_get_origin(window, &origin_x, &origin_y);
    if (gtk_widget_translate_coordinates(tasks->fixed, top, 0, 0, &offset_x, &offset_y)) { origin_x += offset_x; origin_y += offset_y; }
    gint cell = MIN(tasks->mac ? 58 : 44, MAX(16, (width - 12) / (gint)tasks->items->len));
    gint content = cell * (gint)tasks->items->len;
    gint left = (width - content) / 2;
    if (!tasks->mac) {
        GdkMonitor *monitor = gdk_display_get_monitor_at_point(gdk_display_get_default(), origin_x + width / 2, origin_y);
        if (monitor) { GdkRectangle rect; gdk_monitor_get_geometry(monitor, &rect);
            left = CLAMP(rect.x + rect.width / 2 - origin_x - content / 2, 0, MAX(0, width - content)); }
    }
    for (guint i = 0; i < tasks->items->len; i++) {
        Item *item = g_ptr_array_index(tasks->items, i);
        gtk_widget_set_size_request(item->button, cell, MAX(20, height - 2));
        gtk_fixed_move(GTK_FIXED(tasks->fixed), item->button, left + (gint)i * cell, 0);
    }
    /* Read-only geometry for accessibility / integration diagnostics. The
     * property is on our own panel window, never an arbitrary client/root. */
    if (GDK_IS_X11_WINDOW(window)) {
        Display *display = gdk_x11_display_get_xdisplay(gdk_window_get_display(window));
        unsigned long bounds[] = {(unsigned long)MAX(0, origin_x + left), (unsigned long)MAX(0, origin_y),
                                  (unsigned long)content, (unsigned long)height, tasks->items->len};
        XChangeProperty(display, GDK_WINDOW_XID(window), XInternAtom(display, "_OGUZDOWS_TASK_BOUNDS", False),
                        XA_CARDINAL, 32, PropModeReplace, (unsigned char *)bounds, 5);
    }
}

static void allocated(GtkWidget *widget, GtkAllocation *allocation, gpointer pointer) { (void)widget; (void)allocation; place(pointer); }
static gboolean configured(GtkWidget *widget, GdkEventConfigure *event, gpointer pointer) {
    (void)widget; (void)event; place(pointer); return FALSE;
}

static gboolean size_changed(XfcePanelPlugin *plugin, gint size, gpointer pointer) {
    (void)plugin; Tasks *tasks = pointer; tasks->size = size; queue_refresh(tasks); return TRUE;
}

static void set_style(Tasks *tasks) {
    gchar *mode = xfconf_channel_get_string(tasks->channel, tasks->style_key, "mac");
    tasks->mac = !g_strcmp0(mode, "mac"); g_free(mode);
    xfce_panel_plugin_set_expand(tasks->plugin, !tasks->mac);
    tasks->top = gtk_widget_get_toplevel(GTK_WIDGET(tasks->plugin));
    GtkStyleContext *context = gtk_widget_get_style_context(tasks->top);
    gtk_style_context_remove_class(context, tasks->mac ? "oguzdows-taskbar" : "oguzdows-dock");
    gtk_style_context_add_class(context, tasks->mac ? "oguzdows-dock" : "oguzdows-taskbar");
    queue_refresh(tasks);
}

static void property_changed(XfconfChannel *channel, const gchar *property, const GValue *value, gpointer pointer) {
    (void)channel; (void)value; Tasks *tasks = pointer;
    if (!g_strcmp0(property, tasks->style_key)) set_style(tasks);
}
static void pins_changed(GFileMonitor *monitor, GFile *file, GFile *other, GFileMonitorEvent event, gpointer pointer) {
    (void)monitor; (void)other; (void)event;
    gchar *name = g_file_get_basename(file);
    if (!g_strcmp0(name, "pins.ini")) queue_refresh(pointer);
    g_free(name);
}

static void free_tasks(XfcePanelPlugin *plugin, gpointer pointer) {
    (void)plugin; Tasks *tasks = pointer; tasks->disposing = TRUE;
    if (tasks->refresh) g_source_remove(tasks->refresh);
    if (tasks->animation) g_source_remove(tasks->animation);
    clear_watches(tasks);
    g_signal_handlers_disconnect_by_data(tasks->screen, tasks);
    g_signal_handlers_disconnect_by_data(tasks->channel, tasks);
    if (tasks->top) {
        g_signal_handlers_disconnect_by_data(tasks->top, tasks);
        GtkStyleContext *context = gtk_widget_get_style_context(tasks->top);
        gtk_style_context_remove_class(context, "oguzdows-dock"); gtk_style_context_remove_class(context, "oguzdows-taskbar");
    }
    g_signal_handlers_disconnect_by_data(tasks->fixed, tasks);
    gtk_widget_destroy(tasks->fixed);
    g_clear_object(&tasks->pins_monitor);
    g_ptr_array_unref(tasks->items); g_ptr_array_unref(tasks->watched);
    g_object_unref(tasks->handle); g_object_unref(tasks->channel);
    g_free(tasks->style_key); g_free(tasks);
}

static void construct(XfcePanelPlugin *plugin) {
    if (!GDK_IS_X11_DISPLAY(gdk_display_get_default())) {
        GtkWidget *label = gtk_label_new("Görev grubu X11 gerektirir");
        gtk_container_add(GTK_CONTAINER(plugin), label); gtk_widget_show(label); return;
    }
    Tasks *tasks = g_new0(Tasks, 1); tasks->plugin = plugin;
    tasks->size = xfce_panel_plugin_get_size(plugin);
    tasks->items = g_ptr_array_new_with_free_func(item_free);
    tasks->watched = g_ptr_array_new_with_free_func(g_object_unref);
    tasks->channel = g_object_ref(xfconf_channel_get("xfce4-panel"));
    tasks->style_key = g_strdup_printf("%s/style", xfce_panel_plugin_get_property_base(plugin));
    tasks->handle = wnck_handle_new(WNCK_CLIENT_TYPE_PAGER);
    tasks->screen = wnck_handle_get_default_screen(tasks->handle);
    wnck_screen_force_update(tasks->screen);
    tasks->fixed = g_object_new(task_strip_get_type(), NULL);
    g_object_set_data(G_OBJECT(tasks->fixed), "tasks", tasks);
    gtk_container_add(GTK_CONTAINER(plugin), tasks->fixed);
    gtk_widget_show(tasks->fixed);
    g_signal_connect(tasks->fixed, "size-allocate", G_CALLBACK(allocated), tasks);
    g_signal_connect(plugin, "size-changed", G_CALLBACK(size_changed), tasks);
    g_signal_connect(plugin, "free-data", G_CALLBACK(free_tasks), tasks);
    g_signal_connect(tasks->channel, "property-changed", G_CALLBACK(property_changed), tasks);
    g_signal_connect(tasks->screen, "window-opened", G_CALLBACK(screen_changed), tasks);
    g_signal_connect(tasks->screen, "window-closed", G_CALLBACK(screen_changed), tasks);
    g_signal_connect(tasks->screen, "active-window-changed", G_CALLBACK(screen_changed), tasks);
    set_style(tasks);
    g_signal_connect(tasks->top, "configure-event", G_CALLBACK(configured), tasks);
    gchar *directory = g_build_filename(g_get_user_config_dir(), "oguzdows", NULL);
    g_mkdir_with_parents(directory, 0700);
    GFile *file = g_file_new_for_path(directory); g_free(directory);
    tasks->pins_monitor = g_file_monitor_directory(file, G_FILE_MONITOR_WATCH_MOVES, NULL, NULL); g_object_unref(file);
    if (tasks->pins_monitor) g_signal_connect(tasks->pins_monitor, "changed", G_CALLBACK(pins_changed), tasks);
}

XFCE_PANEL_PLUGIN_REGISTER(construct)
