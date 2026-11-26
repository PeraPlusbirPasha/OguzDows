/* SPDX-License-Identifier: GPL-3.0-or-later
 * Gerçek GAppInfo başlatıcısı; modern Başlat, yerel ayarlar ve canlı durum.
 * Bildirim hizmetini sahiplenmez: GNOME/Plasma/Xfce'nin merkezi korunur.
 */
#define _POSIX_C_SOURCE 200809L
#include "ui.h"
#include <gio/gdesktopappinfo.h>
#include <json-glib/json-glib.h>
#include <glib/gstdio.h>
#include <sys/stat.h>
#include <string.h>
#include <unistd.h>

typedef struct { GAppInfo *info; gchar *search, *id; gboolean pinned; } App;
static GPtrArray *apps;
static GtkWidget *window, *flow, *search_entry, *status_label, *clock_label, *network_label, *battery_label, *sound_label, *more;
static GtkWidget *section_title, *all_button, *recent_section;
static gboolean all_apps;
static guint focus_source;
static gchar *query = NULL;
static GKeyFile *pins;
static guint clock_source, limit = 18;
static GDBusProxy *network_proxy, *battery_proxy;
static GCancellable *cancellable;
static GSubprocess *volume_process;
static guint volume_deadline;
#ifdef OGUZDOWS_HUB_TEST
static const gchar *smoke_directory;
#endif

static void app_free(gpointer pointer) {
    App *app = pointer; g_object_unref(app->info); g_free(app->search); g_free(app->id); g_free(app);
}

static gchar *normalized(const gchar *value) {
    gchar *folded = g_utf8_casefold(value ? value : "", -1);
    gchar *decomposed = g_utf8_normalize(folded, -1, G_NORMALIZE_NFKD); g_free(folded);
    GString *result = g_string_new(NULL);
    for (const gchar *p = decomposed; p && *p; p = g_utf8_next_char(p)) {
        gunichar ch = g_utf8_get_char(p);
        if (g_unichar_type(ch) != G_UNICODE_NON_SPACING_MARK) g_string_append_unichar(result, ch == 0x131 ? 'i' : ch);
    }
    g_free(decomposed); return g_string_free(result, FALSE);
}

static gint compare_apps(gconstpointer a, gconstpointer b) {
    const App *left = *(App * const *)a, *right = *(App * const *)b;
    if (left->pinned != right->pinned) return left->pinned ? -1 : 1;
    return g_utf8_collate(g_app_info_get_display_name(left->info), g_app_info_get_display_name(right->info));
}

static gboolean default_pin(const char *id) {
    const char *defaults[] = {"oguzdows-store.desktop", "oguzdows-news.desktop", "oguzdows-monitor.desktop", "oguzdows-desktop.desktop", "oguzdows-browser.desktop", "oguzdows-files.desktop", "oguzdows-terminal.desktop", "oguzdows-welcome.desktop", NULL};
    for (unsigned i = 0; defaults[i]; i++) if (!g_strcmp0(defaults[i], id)) return TRUE;
    return FALSE;
}

static void load_apps(void) {
    if (apps) g_ptr_array_unref(apps);
    if (pins) g_key_file_unref(pins);
    apps = g_ptr_array_new_with_free_func(app_free);
    pins = g_key_file_new();
    gchar *path = g_build_filename(g_get_user_config_dir(), "oguzdows", "pins.ini", NULL);
    gchar *contents = NULL;
    if (og_ui_read_file(path, 65536, &contents)) g_key_file_load_from_data(pins, contents, -1, G_KEY_FILE_NONE, NULL);
    g_free(contents); g_free(path);
    GList *all = g_app_info_get_all();
    for (GList *item = all; item; item = item->next) {
        GAppInfo *info = item->data;
        const char *id = g_app_info_get_id(info);
        if (!id || !g_app_info_should_show(info) || strlen(id) > 256 || apps->len >= 4096) continue;
        App *app = g_new0(App, 1); app->info = g_object_ref(info); app->id = g_strdup(id);
        const gchar *description = g_app_info_get_description(info);
        gchar *words = g_strdup_printf("%s %s %s", g_app_info_get_display_name(info), description ? description : "", id);
        app->search = normalized(words); g_free(words);
        app->pinned = g_key_file_has_key(pins, "Pins", id, NULL) ? g_key_file_get_boolean(pins, "Pins", id, NULL) : default_pin(id);
        g_ptr_array_add(apps, app);
    }
    g_list_free_full(all, g_object_unref); g_ptr_array_sort(apps, compare_apps);
}

static void launch(GtkButton *button, gpointer pointer) {
    (void)button; App *app = pointer;
    GError *error = NULL;
    GdkAppLaunchContext *context = gdk_display_get_app_launch_context(gtk_widget_get_display(window));
    gdk_app_launch_context_set_timestamp(context, gtk_get_current_event_time());
    if (!g_app_info_launch(app->info, NULL, G_APP_LAUNCH_CONTEXT(context), &error)) {
        gtk_label_set_text(GTK_LABEL(status_label), error->message); g_clear_error(&error);
    } else { og_ui_feedback(); gtk_widget_destroy(window); }
    g_object_unref(context);
}

static void populate(void);
static void pin(GtkButton *button, gpointer pointer) {
    (void)button; App *app = pointer; gboolean old = app->pinned;
    app->pinned = !app->pinned; g_key_file_set_boolean(pins, "Pins", app->id, app->pinned);
    gchar *directory = g_build_filename(g_get_user_config_dir(), "oguzdows", NULL);
    gchar *path = g_build_filename(directory, "pins.ini", NULL);
    GError *error = NULL;
    if (g_mkdir_with_parents(directory, 0700) || !g_key_file_save_to_file(pins, path, &error)) {
        app->pinned = old; g_key_file_set_boolean(pins, "Pins", app->id, old);
        gtk_label_set_text(GTK_LABEL(status_label), error ? error->message : "Sabitleme kaydedilemedi."); g_clear_error(&error);
    } else { g_ptr_array_sort(apps, compare_apps); populate(); }
    g_free(directory); g_free(path);
}

static gboolean context_menu(GtkWidget *button, GdkEventButton *event, gpointer pointer) {
    if (event->button != GDK_BUTTON_SECONDARY) return FALSE;
    App *app = pointer;
    GtkWidget *popover = gtk_popover_new(button), *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 4);
    gtk_container_set_border_width(GTK_CONTAINER(box), 8);
    GtkWidget *open = gtk_button_new_with_label("Uygulamayı aç");
    GtkWidget *toggle = gtk_button_new_with_label(app->pinned ? "Sabitlenenlerden çıkar" : "Başlat'a sabitle");
    g_signal_connect(open, "clicked", G_CALLBACK(launch), app);
    g_signal_connect(toggle, "clicked", G_CALLBACK(pin), app);
    g_signal_connect(popover, "closed", G_CALLBACK(gtk_widget_destroy), NULL);
    gtk_box_pack_start(GTK_BOX(box), open, FALSE, FALSE, 0); gtk_box_pack_start(GTK_BOX(box), toggle, FALSE, FALSE, 0);
    gtk_container_add(GTK_CONTAINER(popover), box); gtk_widget_show_all(popover); gtk_popover_popup(GTK_POPOVER(popover));
    return TRUE;
}

static gboolean keyboard_menu(GtkWidget *button, gpointer pointer) {
    GdkEventButton event; memset(&event, 0, sizeof event); event.button = GDK_BUTTON_SECONDARY;
    return context_menu(button, &event, pointer);
}

static GtkWidget *app_button(App *app) {
    GtkWidget *button = gtk_button_new(), *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 7);
    gtk_style_context_add_class(gtk_widget_get_style_context(button), "hub-app");
    GIcon *icon = g_app_info_get_icon(app->info);
    GtkWidget *image = icon ? gtk_image_new_from_gicon(icon, GTK_ICON_SIZE_DIALOG)
        : gtk_image_new_from_icon_name("application-x-executable", GTK_ICON_SIZE_DIALOG);
    gtk_image_set_pixel_size(GTK_IMAGE(image), 32);
    GtkWidget *title = gtk_label_new(g_app_info_get_display_name(app->info));
    gtk_label_set_line_wrap(GTK_LABEL(title), TRUE); gtk_label_set_lines(GTK_LABEL(title), 2);
    gtk_label_set_max_width_chars(GTK_LABEL(title), 12); gtk_label_set_justify(GTK_LABEL(title), GTK_JUSTIFY_CENTER);
    gtk_label_set_ellipsize(GTK_LABEL(title), PANGO_ELLIPSIZE_END);
    gtk_box_pack_start(GTK_BOX(box), image, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(box), title, FALSE, FALSE, 0);
    gtk_container_add(GTK_CONTAINER(button), box);
    gtk_widget_set_size_request(button, 78, 88);
    gtk_widget_set_tooltip_text(button, g_app_info_get_display_name(app->info));
    atk_object_set_name(gtk_widget_get_accessible(button), g_app_info_get_display_name(app->info));
    g_signal_connect(button, "clicked", G_CALLBACK(launch), app);
    g_signal_connect(button, "button-press-event", G_CALLBACK(context_menu), app);
    g_signal_connect(button, "popup-menu", G_CALLBACK(keyboard_menu), app);
    return button;
}

static void populate(void) {
    GList *children = gtk_container_get_children(GTK_CONTAINER(flow));
    for (GList *item = children; item; item = item->next) gtk_widget_destroy(item->data);
    g_list_free(children);
    gboolean searching = query && *query;
    unsigned shown = 0, matches = 0, pinned_count = 0;
    for (unsigned i = 0; i < apps->len; i++) pinned_count += ((App *)g_ptr_array_index(apps, i))->pinned;
    /* Empty personal pins remain empty; do not silently re-pin unrelated apps. */
    for (unsigned i = 0; i < apps->len; i++) {
        App *app = g_ptr_array_index(apps, i);
        if (searching ? !strstr(app->search, query) : !all_apps && !app->pinned) continue;
        matches++;
        if (shown >= limit) continue;
        gtk_container_add(GTK_CONTAINER(flow), app_button(app)); shown++;
    }
    gtk_label_set_text(GTK_LABEL(section_title), searching ? "Arama sonuçları" : all_apps ? "Tüm uygulamalar" : "Sabitlenenler");
    gtk_button_set_label(GTK_BUTTON(all_button), all_apps ? "← Sabitlenenler" : "Tüm uygulamalar  ›");
    gtk_widget_set_visible(recent_section, !searching && !all_apps);
    gtk_widget_show_all(flow); gtk_widget_set_visible(more, matches > shown);
    gchar *message = g_strdup_printf("%u uygulama · %u sabitlenen%s", apps->len, pinned_count,
        searching && !matches ? " · Sonuç yok, başka bir ad dene." : " · Sağ tıkla sabitle / kaldır");
    gtk_label_set_text(GTK_LABEL(status_label), message); g_free(message);
}

static void search_changed(GtkSearchEntry *entry, gpointer data) {
    (void)data; g_free(query); query = normalized(gtk_entry_get_text(GTK_ENTRY(entry)));
    limit = query && *query ? 48 : all_apps ? 48 : 18; populate();
}
static void show_more(GtkButton *button, gpointer data) { (void)button; (void)data; limit += 48; populate(); }
static void toggle_apps(GtkButton *button, gpointer data) {
    (void)button; (void)data; all_apps = !all_apps;
    gtk_entry_set_text(GTK_ENTRY(search_entry), ""); search_changed(GTK_SEARCH_ENTRY(search_entry), NULL);
}

static void recent_opened(GObject *source, GAsyncResult *result, gpointer data) {
    (void)source;
    GError *error = NULL;
    if (!g_app_info_launch_default_for_uri_finish(result, &error)) {
        if (window) gtk_label_set_text(GTK_LABEL(status_label), error ? error->message : "Dosya açılamadı.");
        g_clear_error(&error);
    } else if (window) gtk_widget_destroy(window);
    g_application_release(G_APPLICATION(data));
}
static void open_recent(GtkButton *button, gpointer data) {
    (void)button;
    const gchar *uri = data;
    if (!g_str_has_prefix(uri, "file:///")) return;
    GdkAppLaunchContext *context = gdk_display_get_app_launch_context(gtk_widget_get_display(window));
    gdk_app_launch_context_set_timestamp(context, gtk_get_current_event_time());
    GApplication *application = G_APPLICATION(gtk_window_get_application(GTK_WINDOW(window)));
    g_application_hold(application);
    g_app_info_launch_default_for_uri_async(uri, G_APP_LAUNCH_CONTEXT(context), NULL, recent_opened, application);
    g_object_unref(context);
}
static gint recent_compare(gconstpointer a, gconstpointer b) {
    time_t left = gtk_recent_info_get_modified((GtkRecentInfo *)a), right = gtk_recent_info_get_modified((GtkRecentInfo *)b);
    return left == right ? 0 : left > right ? -1 : 1;
}
static gboolean public_recent(GtkRecentInfo *info) {
    if (!gtk_recent_info_is_local(info) || gtk_recent_info_get_private_hint(info)) return FALSE;
    const gchar *uri = gtk_recent_info_get_uri(info);
    if (!uri || strlen(uri) > 8192 || !g_str_has_prefix(uri, "file:///")) return FALSE;
    gchar *filename = g_filename_from_uri(uri, NULL, NULL);
    if (!filename) return FALSE;
    gchar **parts = g_strsplit(filename, "/", -1); gboolean visible = TRUE;
    for (guint i = 0; parts[i]; i++) if (parts[i][0] == '.') visible = FALSE;
    g_strfreev(parts); g_free(filename); return visible;
}
static void load_recent(GtkWidget *box, gint columns) {
    GtkWidget *title = gtk_label_new("Son kullanılanlar");
    gtk_label_set_xalign(GTK_LABEL(title), 0); gtk_style_context_add_class(gtk_widget_get_style_context(title), "hub-section-title");
    gtk_box_pack_start(GTK_BOX(box), title, FALSE, FALSE, 0);
    GtkWidget *list = gtk_flow_box_new(); gtk_flow_box_set_selection_mode(GTK_FLOW_BOX(list), GTK_SELECTION_NONE);
    gtk_flow_box_set_min_children_per_line(GTK_FLOW_BOX(list), columns); gtk_flow_box_set_max_children_per_line(GTK_FLOW_BOX(list), columns);
    gtk_flow_box_set_homogeneous(GTK_FLOW_BOX(list), TRUE);
    gtk_box_pack_start(GTK_BOX(box), list, FALSE, FALSE, 0);
    gboolean enabled = FALSE; g_object_get(gtk_settings_get_default(), "gtk-recent-files-enabled", &enabled, NULL);
    GList *items = enabled ? gtk_recent_manager_get_items(gtk_recent_manager_get_default()) : NULL;
    items = g_list_sort(items, recent_compare);
    guint shown = 0;
    for (GList *it = items; it && shown < 4; it = it->next) {
        GtkRecentInfo *info = it->data;
        if (!public_recent(info)) continue;
        GtkWidget *button = gtk_button_new(), *line = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 10);
        gtk_style_context_add_class(gtk_widget_get_style_context(button), "hub-recent");
        GIcon *icon = g_content_type_get_icon(gtk_recent_info_get_mime_type(info));
        GtkWidget *image = gtk_image_new_from_gicon(icon, GTK_ICON_SIZE_LARGE_TOOLBAR); g_object_unref(icon);
        gtk_image_set_pixel_size(GTK_IMAGE(image), 26);
        GtkWidget *name = gtk_label_new(gtk_recent_info_get_display_name(info));
        gtk_label_set_xalign(GTK_LABEL(name), 0); gtk_label_set_max_width_chars(GTK_LABEL(name), 20);
        gtk_label_set_ellipsize(GTK_LABEL(name), PANGO_ELLIPSIZE_MIDDLE);
        gtk_box_pack_start(GTK_BOX(line), image, FALSE, FALSE, 0); gtk_box_pack_start(GTK_BOX(line), name, TRUE, TRUE, 0);
        gtk_container_add(GTK_CONTAINER(button), line); gtk_container_add(GTK_CONTAINER(list), button);
        gchar *uri = g_strdup(gtk_recent_info_get_uri(info)); g_object_set_data_full(G_OBJECT(button), "uri", uri, g_free);
        g_signal_connect(button, "clicked", G_CALLBACK(open_recent), uri); shown++;
    }
    g_list_free_full(items, (GDestroyNotify)gtk_recent_info_unref);
    if (!shown) {
        GtkWidget *note = gtk_label_new(enabled ? "Açtığın yerel dosyalar burada görünür. Gizli dosyalar ve ağ adresleri listelenmez." : "Son dosyaları kaydetme tercihin kapalı.");
        gtk_label_set_line_wrap(GTK_LABEL(note), TRUE); gtk_label_set_max_width_chars(GTK_LABEL(note), 52);
        gtk_label_set_xalign(GTK_LABEL(note), 0); gtk_style_context_add_class(gtk_widget_get_style_context(note), "dim-label");
        gtk_box_pack_start(GTK_BOX(box), note, FALSE, FALSE, 0);
    }
}
static void search_activate(GtkEntry *entry, gpointer data) {
    (void)entry; (void)data;
    if (!query || !*query) return;
    for (guint i = 0; i < apps->len; i++) {
        App *app = g_ptr_array_index(apps, i);
        if (strstr(app->search, query)) { launch(NULL, app); break; }
    }
}
static gboolean key_pressed(GtkWidget *widget, GdkEventKey *event, gpointer data) {
    (void)widget; (void)data;
    if (event->keyval == GDK_KEY_Escape) { gtk_widget_destroy(window); return TRUE; }
    return FALSE;
}
static gboolean check_focus(gpointer data) {
    (void)data; focus_source = 0;
    if (window && !gtk_window_is_active(GTK_WINDOW(window)) && !gtk_grab_get_current()) gtk_widget_destroy(window);
    return G_SOURCE_REMOVE;
}
static gboolean focus_out(GtkWidget *widget, GdkEventFocus *event, gpointer data) {
    (void)widget; (void)event; (void)data;
    if (!focus_source) focus_source = g_timeout_add(140, check_focus, NULL);
    return FALSE;
}
static void position_hub(void) {
    if (!window) return;
    GdkDisplay *display = gtk_widget_get_display(window);
    GdkMonitor *monitor = gdk_display_get_monitor_at_window(display, gtk_widget_get_window(window));
    if (!monitor) return;
    GdkRectangle work; gdk_monitor_get_workarea(monitor, &work);
    gint width, height; gtk_window_get_size(GTK_WINDOW(window), &width, &height);
    gtk_window_move(GTK_WINDOW(window), work.x + MAX(0, (work.width - width) / 2), work.y + MAX(0, work.height - height - 12));
}

static void control(GtkButton *button, gpointer pointer) {
    (void)button; GError *error = NULL;
    if (!og_ui_launch_control(pointer, &error)) { gtk_label_set_text(GTK_LABEL(status_label), error->message); g_clear_error(&error); }
    else og_ui_feedback();
}
static GtkWidget *control_button(const char *icon, const char *title, const char *action) {
    GtkWidget *button = gtk_button_new(); GtkWidget *box = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 6);
    gtk_box_pack_start(GTK_BOX(box), gtk_image_new_from_icon_name(icon, GTK_ICON_SIZE_BUTTON), FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(box), gtk_label_new(title), TRUE, TRUE, 0);
    gtk_container_add(GTK_CONTAINER(button), box); g_signal_connect(button, "clicked", G_CALLBACK(control), (gpointer)action);
    return button;
}

static gboolean clock_tick(gpointer data) {
    (void)data;
    if (!window || !gtk_widget_get_mapped(window)) { clock_source = 0; return G_SOURCE_REMOVE; }
    GDateTime *now = g_date_time_new_now_local(); gchar *value = g_date_time_format(now, "%d %B · %H:%M");
    gtk_label_set_text(GTK_LABEL(clock_label), value); g_free(value); g_date_time_unref(now); return G_SOURCE_CONTINUE;
}
static void map(GtkWidget *widget, gpointer data) {
    (void)widget; (void)data; position_hub();
    if (!clock_source) { clock_tick(NULL); clock_source = g_timeout_add_seconds(30, clock_tick, NULL); }
}
static void unmap(GtkWidget *widget, gpointer data) { (void)widget; (void)data; if (clock_source) g_source_remove(clock_source); clock_source = 0; }

static void status_update(GDBusProxy *proxy, GVariant *changed, const gchar * const *invalidated, gpointer data) {
    (void)changed; (void)invalidated; (void)data;
    if (!window) return;
    if (proxy == network_proxy) {
        GVariant *value = g_dbus_proxy_get_cached_property(proxy, "State");
        if (value && g_variant_is_of_type(value, G_VARIANT_TYPE_UINT32)) {
            guint32 state = g_variant_get_uint32(value);
            gtk_label_set_text(GTK_LABEL(network_label), state >= 70 ? "Ağ bağlı" : state >= 50 ? "Yerel ağ" : state >= 40 ? "Bağlanıyor" : "Çevrimdışı");
        }
        if (value) g_variant_unref(value);
    } else {
        GVariant *present = g_dbus_proxy_get_cached_property(proxy, "IsPresent");
        GVariant *percentage = g_dbus_proxy_get_cached_property(proxy, "Percentage");
        if (present && percentage && g_variant_is_of_type(present, G_VARIANT_TYPE_BOOLEAN) &&
                g_variant_get_boolean(present) && g_variant_is_of_type(percentage, G_VARIANT_TYPE_DOUBLE)) {
            gchar *value = g_strdup_printf("Pil %.0f %%", CLAMP(g_variant_get_double(percentage), 0, 100));
            gtk_label_set_text(GTK_LABEL(battery_label), value); g_free(value);
        } else gtk_label_set_text(GTK_LABEL(battery_label), "Pil yok");
        if (present) g_variant_unref(present);
        if (percentage) g_variant_unref(percentage);
    }
}

static void proxy_ready(GObject *source, GAsyncResult *result, gpointer pointer) {
    (void)source;
    gboolean network = GPOINTER_TO_INT(pointer);
    GDBusProxy *proxy = g_dbus_proxy_new_for_bus_finish(result, NULL);
    if (!proxy) return;
    if (!window) { g_object_unref(proxy); return; }
    if (network) network_proxy = proxy; else battery_proxy = proxy;
    g_signal_connect(proxy, "g-properties-changed", G_CALLBACK(status_update), NULL);
    status_update(proxy, NULL, NULL, NULL);
}

static gboolean volume_timeout(gpointer data) {
    (void)data; volume_deadline = 0;
    if (volume_process) g_subprocess_force_exit(volume_process);
    return G_SOURCE_REMOVE;
}
static void volume_ready(GObject *source, GAsyncResult *result, gpointer data) {
    (void)data;
    gchar *output = NULL;
    gboolean success = g_subprocess_communicate_utf8_finish(G_SUBPROCESS(source), result, &output, NULL, NULL);
    if (volume_deadline) { g_source_remove(volume_deadline); volume_deadline = 0; }
    if (success && window && g_subprocess_get_successful(G_SUBPROCESS(source)) && output && strlen(output) < 4096) {
        gchar **parts = g_strsplit_set(output, " \t\n", -1);
        for (unsigned i = 0; parts[i]; i++) {
            if (g_str_has_suffix(parts[i], "%") && g_ascii_isdigit(parts[i][0])) {
                gchar *label = g_strdup_printf("Ses %s", parts[i]); gtk_label_set_text(GTK_LABEL(sound_label), label); g_free(label); break;
            }
        }
        g_strfreev(parts);
    }
    g_free(output); g_clear_object(&volume_process);
}

static void services(void) {
    cancellable = g_cancellable_new();
    // Sistem D-Bus servisleri otomatik başlatılmaz; ana GTK döngüsü bloklanmaz.
    GDBusProxyFlags flags = G_DBUS_PROXY_FLAGS_DO_NOT_AUTO_START;
    g_dbus_proxy_new_for_bus(G_BUS_TYPE_SYSTEM, flags, NULL, "org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager", "org.freedesktop.NetworkManager", cancellable, proxy_ready, GINT_TO_POINTER(TRUE));
    g_dbus_proxy_new_for_bus(G_BUS_TYPE_SYSTEM, flags, NULL, "org.freedesktop.UPower", "/org/freedesktop/UPower/devices/DisplayDevice", "org.freedesktop.UPower.Device", cancellable, proxy_ready, GINT_TO_POINTER(FALSE));
    if (g_file_test("/usr/bin/pactl", G_FILE_TEST_IS_EXECUTABLE)) {
        volume_process = g_subprocess_new(G_SUBPROCESS_FLAGS_STDOUT_PIPE | G_SUBPROCESS_FLAGS_STDERR_SILENCE, NULL,
            "/usr/bin/pactl", "get-sink-volume", "@DEFAULT_SINK@", NULL);
        if (volume_process) {
            g_subprocess_communicate_utf8_async(volume_process, NULL, cancellable, volume_ready, NULL);
            volume_deadline = g_timeout_add(1500, volume_timeout, NULL);
        }
    }
}

static void destroy(GtkWidget *widget, gpointer data) {
    (void)widget; (void)data; unmap(NULL, NULL);
    if (focus_source) { g_source_remove(focus_source); focus_source = 0; }
    if (cancellable) g_cancellable_cancel(cancellable);
    if (volume_process) g_subprocess_force_exit(volume_process);
    if (volume_deadline) g_source_remove(volume_deadline);
    volume_deadline = 0;
    g_clear_object(&network_proxy); g_clear_object(&battery_proxy);
}

#ifdef OGUZDOWS_HUB_TEST
static gboolean smoke_finish(gpointer data) {
    (void)data;
    gchar *turkish = normalized("İŞLEMCI Çay GÖRÜNÜM");
    g_assert_nonnull(strstr(turkish, "islemci cay gorunum")); g_free(turkish);
    g_assert_cmpuint(apps->len, >, 0);
    gtk_entry_set_text(GTK_ENTRY(search_entry), "oguzdows");
    search_changed(GTK_SEARCH_ENTRY(search_entry), NULL);
    g_assert_nonnull(query);
    gtk_entry_set_text(GTK_ENTRY(search_entry), ""); search_changed(GTK_SEARCH_ENTRY(search_entry), NULL);
    GtkFlowBoxChild *first = gtk_flow_box_get_child_at_index(GTK_FLOW_BOX(flow), 0);
    g_assert_nonnull(first);
    gchar *path = g_build_filename(smoke_directory, "hub.json", NULL);
    gint width, height; gtk_window_get_size(GTK_WINDOW(window), &width, &height);
    gchar *json = g_strdup_printf("{\"schema\":1,\"native\":true,\"app_count\":%u,\"unicode_search\":true,\"no_apps_launched\":true,\"window_width\":%d,\"window_height\":%d,\"physical_device_verified\":false}\n", apps->len, width, height);
    g_file_set_contents(path, json, -1, NULL); g_free(path); g_free(json);
    GdkWindow *surface = gtk_widget_get_window(window);
    GdkPixbuf *capture = gdk_pixbuf_get_from_window(surface, 0, 0, gdk_window_get_width(surface), gdk_window_get_height(surface));
    if (capture) { path = g_build_filename(smoke_directory, "hub.png", NULL); gdk_pixbuf_save(capture, path, "png", NULL, NULL); g_free(path); g_object_unref(capture); }
    gtk_widget_hide(window); g_assert_cmpuint(clock_source, ==, 0);
    gtk_widget_destroy(window); return G_SOURCE_REMOVE;
}
#endif

static void activate(GtkApplication *application, gpointer data) {
    (void)data;
    if (window) { gtk_widget_show(window); gtk_window_present(GTK_WINDOW(window)); return; }
    all_apps = FALSE; limit = 18; g_clear_pointer(&query, g_free);
    window = gtk_application_window_new(application);
    gtk_window_set_title(GTK_WINDOW(window), "OğuzDows · Başlat"); gtk_window_set_icon_name(GTK_WINDOW(window), "oguzdows-hub");
    gtk_window_set_decorated(GTK_WINDOW(window), FALSE); gtk_window_set_resizable(GTK_WINDOW(window), FALSE);
    gtk_window_set_skip_taskbar_hint(GTK_WINDOW(window), TRUE); gtk_window_set_skip_pager_hint(GTK_WINDOW(window), TRUE);
    gtk_window_set_keep_above(GTK_WINDOW(window), TRUE);
    GdkDisplay *display = gtk_widget_get_display(window);
    GdkSeat *seat = gdk_display_get_default_seat(display); gint px = 0, py = 0;
    if (seat && gdk_seat_get_pointer(seat)) gdk_device_get_position(gdk_seat_get_pointer(seat), NULL, &px, &py);
    GdkMonitor *monitor = gdk_display_get_monitor_at_point(display, px, py); GdkRectangle work = {0, 0, 1024, 768};
    if (monitor) gdk_monitor_get_workarea(monitor, &work);
    gint width = MIN(660, work.width - 24), columns = width >= 590 ? 6 : width >= 480 ? 5 : width >= 390 ? 4 : 3;
    gtk_window_set_default_size(GTK_WINDOW(window), width, MIN(640, work.height - 24));
    gtk_window_set_position(GTK_WINDOW(window), GTK_WIN_POS_CENTER); og_ui_setup(window);
    gtk_style_context_add_class(gtk_widget_get_style_context(window), "hub-window");
    GtkWidget *root = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0); gtk_container_add(GTK_CONTAINER(window), root);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 16); gtk_container_set_border_width(GTK_CONTAINER(box), width < 480 ? 18 : 28);
    gtk_box_pack_start(GTK_BOX(root), box, TRUE, TRUE, 0);
    search_entry = gtk_search_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(search_entry), "Uygulama ara…");
    gtk_style_context_add_class(gtk_widget_get_style_context(search_entry), "hub-search");
    gtk_box_pack_start(GTK_BOX(box), search_entry, FALSE, FALSE, 0);
    g_signal_connect(search_entry, "search-changed", G_CALLBACK(search_changed), NULL);
    g_signal_connect(search_entry, "activate", G_CALLBACK(search_activate), NULL);
    GtkWidget *heading = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    section_title = gtk_label_new("Sabitlenenler"); gtk_label_set_xalign(GTK_LABEL(section_title), 0);
    gtk_style_context_add_class(gtk_widget_get_style_context(section_title), "hub-section-title");
    gtk_box_pack_start(GTK_BOX(heading), section_title, TRUE, TRUE, 0);
    all_button = gtk_button_new_with_label("Tüm uygulamalar  ›");
    gtk_style_context_add_class(gtk_widget_get_style_context(all_button), "hub-link");
    g_signal_connect(all_button, "clicked", G_CALLBACK(toggle_apps), NULL);
    gtk_box_pack_end(GTK_BOX(heading), all_button, FALSE, FALSE, 0); gtk_box_pack_start(GTK_BOX(box), heading, FALSE, FALSE, 0);
    GtkWidget *scroll = gtk_scrolled_window_new(NULL, NULL); gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll), GTK_POLICY_NEVER, GTK_POLICY_AUTOMATIC);
    GtkWidget *body = gtk_box_new(GTK_ORIENTATION_VERTICAL, 14); gtk_container_add(GTK_CONTAINER(scroll), body);
    gtk_box_pack_start(GTK_BOX(box), scroll, TRUE, TRUE, 0);
    flow = gtk_flow_box_new(); gtk_flow_box_set_selection_mode(GTK_FLOW_BOX(flow), GTK_SELECTION_NONE);
    gtk_flow_box_set_min_children_per_line(GTK_FLOW_BOX(flow), columns); gtk_flow_box_set_max_children_per_line(GTK_FLOW_BOX(flow), columns);
    gtk_flow_box_set_homogeneous(GTK_FLOW_BOX(flow), TRUE); gtk_flow_box_set_column_spacing(GTK_FLOW_BOX(flow), 2); gtk_flow_box_set_row_spacing(GTK_FLOW_BOX(flow), 4);
    gtk_box_pack_start(GTK_BOX(body), flow, FALSE, FALSE, 0);
    more = gtk_button_new_with_label("Daha fazla göster"); g_signal_connect(more, "clicked", G_CALLBACK(show_more), NULL);
    gtk_box_pack_start(GTK_BOX(body), more, FALSE, FALSE, 0);
    recent_section = gtk_box_new(GTK_ORIENTATION_VERTICAL, 12);
    gtk_widget_set_margin_top(recent_section, 14); gtk_box_pack_start(GTK_BOX(body), recent_section, FALSE, FALSE, 0);
    load_recent(recent_section, width < 480 ? 1 : 2);
    GtkWidget *footer = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 10); gtk_container_set_border_width(GTK_CONTAINER(footer), 14);
    gtk_style_context_add_class(gtk_widget_get_style_context(footer), "hub-footer");
    gtk_box_pack_end(GTK_BOX(root), footer, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(footer), gtk_image_new_from_icon_name("avatar-default-symbolic", GTK_ICON_SIZE_LARGE_TOOLBAR), FALSE, FALSE, 6);
    GtkWidget *user = gtk_label_new(g_get_real_name()); gtk_label_set_max_width_chars(GTK_LABEL(user), width < 480 ? 10 : 18);
    gtk_label_set_ellipsize(GTK_LABEL(user), PANGO_ELLIPSIZE_END); gtk_box_pack_start(GTK_BOX(footer), user, FALSE, FALSE, 0);
    clock_label = gtk_label_new("Saat"); gtk_style_context_add_class(gtk_widget_get_style_context(clock_label), "dim-label");
    gtk_label_set_ellipsize(GTK_LABEL(clock_label), PANGO_ELLIPSIZE_END); gtk_label_set_max_width_chars(GTK_LABEL(clock_label), 22);
    gtk_box_pack_start(GTK_BOX(footer), clock_label, TRUE, TRUE, 0);
    GtkWidget *quick = gtk_menu_button_new(); gtk_button_set_image(GTK_BUTTON(quick), gtk_image_new_from_icon_name("preferences-system-symbolic", GTK_ICON_SIZE_BUTTON));
    gtk_widget_set_tooltip_text(quick, "Hızlı ayarlar"); atk_object_set_name(gtk_widget_get_accessible(quick), "Hızlı ayarlar");
    GtkWidget *popover = gtk_popover_new(quick), *quick_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
    gtk_container_set_border_width(GTK_CONTAINER(quick_box), 12); gtk_container_add(GTK_CONTAINER(popover), quick_box);
    GtkWidget *controls = gtk_flow_box_new(); gtk_flow_box_set_selection_mode(GTK_FLOW_BOX(controls), GTK_SELECTION_NONE); gtk_flow_box_set_max_children_per_line(GTK_FLOW_BOX(controls), 2);
    const char *icons[] = {"oguzdows-audio-symbolic", "oguzdows-network-symbolic", "oguzdows-battery-symbolic", "oguzdows-cpu-symbolic"};
    const char *titles[] = {"Ses", "Ağ", "Pil", "Performans"}; const char *actions[] = {"audio", "network", "power", "monitor"};
    for (unsigned i = 0; i < 4; i++) {
        GtkWidget *button = control_button(icons[i], titles[i], actions[i]); gtk_container_add(GTK_CONTAINER(controls), button);
        GList *children = gtk_container_get_children(GTK_CONTAINER(gtk_bin_get_child(GTK_BIN(button))));
        GtkWidget *label = g_list_last(children)->data;
        if (i == 0) sound_label = label; else if (i == 1) network_label = label; else if (i == 2) battery_label = label;
        g_list_free(children);
    }
    gtk_box_pack_start(GTK_BOX(quick_box), controls, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(quick_box), control_button("preferences-system-symbolic", "Sistem ayarları", "settings"), FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(quick_box), control_button("oguzdows-notifications-symbolic", "Bildirimler", "notifications"), FALSE, FALSE, 0);
    gtk_widget_show_all(quick_box); gtk_menu_button_set_popover(GTK_MENU_BUTTON(quick), popover);
    gtk_box_pack_end(GTK_BOX(footer), quick, FALSE, FALSE, 0);
    GtkWidget *power = control_button("system-shutdown-symbolic", "", "session");
    gtk_widget_set_tooltip_text(power, "Oturum / kapatma seçenekleri…"); atk_object_set_name(gtk_widget_get_accessible(power), "Oturum ve kapatma seçenekleri");
    gtk_box_pack_end(GTK_BOX(footer), power, FALSE, FALSE, 0);
    status_label = gtk_label_new("Kurulu uygulamalar okunuyor…"); gtk_label_set_line_wrap(GTK_LABEL(status_label), TRUE);
    gtk_label_set_max_width_chars(GTK_LABEL(status_label), 66); gtk_label_set_xalign(GTK_LABEL(status_label), 0);
    gtk_style_context_add_class(gtk_widget_get_style_context(status_label), "hub-hint"); gtk_box_pack_start(GTK_BOX(box), status_label, FALSE, FALSE, 0);
    load_apps(); populate();
    g_signal_connect(window, "map", G_CALLBACK(map), NULL); g_signal_connect(window, "unmap", G_CALLBACK(unmap), NULL);
    g_signal_connect(window, "key-press-event", G_CALLBACK(key_pressed), NULL);
    g_signal_connect(window, "focus-out-event", G_CALLBACK(focus_out), NULL);
    g_signal_connect(window, "destroy", G_CALLBACK(destroy), NULL); g_signal_connect(window, "destroy", G_CALLBACK(gtk_widget_destroyed), &window);
    gtk_widget_show_all(window); gtk_widget_grab_focus(search_entry); populate(); position_hub();
#ifdef OGUZDOWS_HUB_TEST
    if (smoke_directory) g_timeout_add(900, smoke_finish, NULL); else services();
#else
    services();
#endif
}

static int command_line(GApplication *application, GApplicationCommandLine *line, gpointer data) {
    (void)data;
    gboolean toggle = g_variant_dict_contains(g_application_command_line_get_options_dict(line), "toggle");
    if (toggle && window && gtk_widget_get_mapped(window)) gtk_widget_destroy(window);
    else g_application_activate(application);
    return 0;
}

int main(int argc, char **argv) {
    if (argc == 2 && !strcmp(argv[1], "--version")) { puts("OğuzDows Başlat · native 1"); return 0; }
    gboolean test = FALSE;
#ifdef OGUZDOWS_HUB_TEST
    if (argc == 3 && !strcmp(argv[1], "--smoke-test")) { smoke_directory = argv[2]; g_mkdir_with_parents(smoke_directory, 0700); argc = 1; test = TRUE; }
#endif
    if (argc != 1 && !(argc == 2 && !strcmp(argv[1], "--toggle"))) { fputs("Kullanım: oguzdows-hub [--toggle|--version]\n", stderr); return 2; }
    if (!test && getuid() == 0) { fputs("Başlat normal kullanıcı hesabında çalışır.\n", stderr); return 1; }
    GtkApplication *application = gtk_application_new("org.oguzdows.Hub", G_APPLICATION_HANDLES_COMMAND_LINE);
    g_signal_connect(application, "activate", G_CALLBACK(activate), NULL);
    g_signal_connect(application, "command-line", G_CALLBACK(command_line), NULL);
    g_application_add_main_option(G_APPLICATION(application), "toggle", 0, G_OPTION_FLAG_NONE, G_OPTION_ARG_NONE, "Başlat menüsünü aç / kapat", NULL);
    int result = g_application_run(G_APPLICATION(application), argc, argv);
    if (cancellable) g_cancellable_cancel(cancellable);
    g_clear_object(&cancellable); g_clear_object(&volume_process);
    if (apps) g_ptr_array_unref(apps);
    if (pins) g_key_file_unref(pins);
    g_free(query); g_object_unref(application); return result;
}
