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
static gchar *query = NULL;
static GKeyFile *pins;
static guint clock_source, limit = 48;
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
    const char *defaults[] = {"oguzdows-store.desktop", "oguzdows-news.desktop", "oguzdows-monitor.desktop", "oguzdows-desktop.desktop", "oguzdows-browser.desktop", NULL};
    for (unsigned i = 0; defaults[i]; i++) if (!g_strcmp0(defaults[i], id)) return TRUE;
    return FALSE;
}

static void load_apps(void) {
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

static void populate(void) {
    GList *children = gtk_container_get_children(GTK_CONTAINER(flow));
    for (GList *item = children; item; item = item->next) gtk_widget_destroy(item->data);
    g_list_free(children);
    unsigned shown = 0, matches = 0;
    for (unsigned i = 0; i < apps->len; i++) {
        App *app = g_ptr_array_index(apps, i);
        if (query && *query && !strstr(app->search, query)) continue;
        matches++;
        if (shown >= limit) continue;
        gchar *title = g_strdup_printf("%s%s", app->pinned ? "★ " : "", g_app_info_get_display_name(app->info));
        GtkWidget *button = og_ui_action("application-x-executable", title); g_free(title);
        // og_ui_action'ın ilk kutusundaki ikonu GAppInfo'nun gerçek ölçeklenebilir
        // GIcon'uyla değiştir. Exec metni elle parse edilmez / shell'e verilmez.
        GList *parts = gtk_container_get_children(GTK_CONTAINER(gtk_bin_get_child(GTK_BIN(button))));
        GtkWidget *slot = parts ? parts->data : NULL;
        GList *icons = slot ? gtk_container_get_children(GTK_CONTAINER(slot)) : NULL;
        if (icons && g_app_info_get_icon(app->info)) gtk_image_set_from_gicon(GTK_IMAGE(icons->data), g_app_info_get_icon(app->info), GTK_ICON_SIZE_DIALOG);
        if (icons) gtk_image_set_pixel_size(GTK_IMAGE(icons->data), 32);
        g_list_free(icons); g_list_free(parts);
        gtk_widget_set_size_request(button, 100, 102);
        g_signal_connect(button, "clicked", G_CALLBACK(launch), app);
        g_signal_connect(button, "button-press-event", G_CALLBACK(context_menu), app);
        g_signal_connect(button, "popup-menu", G_CALLBACK(keyboard_menu), app);
        gtk_container_add(GTK_CONTAINER(flow), button); shown++;
    }
    gtk_widget_show_all(flow); gtk_widget_set_visible(more, matches > shown);
    gchar *message = g_strdup_printf("%u uygulama · %u gösteriliyor · sağ tık / Menü tuşuyla sabitle", matches, shown);
    gtk_label_set_text(GTK_LABEL(status_label), message); g_free(message);
}

static void search_changed(GtkSearchEntry *entry, gpointer data) {
    (void)data; g_free(query); query = normalized(gtk_entry_get_text(GTK_ENTRY(entry))); limit = 48; populate();
}
static void show_more(GtkButton *button, gpointer data) { (void)button; (void)data; limit += 48; populate(); }
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
    (void)widget; (void)data;
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
    gchar *json = g_strdup_printf("{\"schema\":1,\"native\":true,\"app_count\":%u,\"unicode_search\":true,\"no_apps_launched\":true,\"physical_device_verified\":false}\n", apps->len);
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
    window = gtk_application_window_new(application);
    gtk_window_set_title(GTK_WINDOW(window), "OğuzDows · Başlat"); gtk_window_set_icon_name(GTK_WINDOW(window), "oguzdows-hub");
    GdkMonitor *monitor = gdk_display_get_primary_monitor(gtk_widget_get_display(window)); GdkRectangle work = {0, 0, 1024, 768};
    if (monitor) gdk_monitor_get_workarea(monitor, &work);
    gtk_window_set_default_size(GTK_WINDOW(window), MIN(760, work.width - 20), MIN(680, work.height - 24));
    gtk_window_set_position(GTK_WINDOW(window), GTK_WIN_POS_CENTER); og_ui_setup(window);
    GtkWidget *header = gtk_header_bar_new(); gtk_header_bar_set_show_close_button(GTK_HEADER_BAR(header), TRUE);
    gtk_header_bar_set_title(GTK_HEADER_BAR(header), "Başlat");
    if (work.width >= 600) gtk_header_bar_set_subtitle(GTK_HEADER_BAR(header), "OĞUZDOWS · ELİNİN ALTINDA");
    gtk_header_bar_pack_end(GTK_HEADER_BAR(header), control_button("preferences-system-symbolic", "Ayarlar", "settings"));
    gtk_window_set_titlebar(GTK_WINDOW(window), header);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 12); gtk_container_set_border_width(GTK_CONTAINER(box), 16);
    gtk_container_add(GTK_CONTAINER(window), box);
    search_entry = gtk_search_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(search_entry), "Uygulama ara…");
    gtk_box_pack_start(GTK_BOX(box), search_entry, FALSE, FALSE, 0); g_signal_connect(search_entry, "search-changed", G_CALLBACK(search_changed), NULL);
    GtkWidget *strip = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8); gtk_style_context_add_class(gtk_widget_get_style_context(strip), "status-strip");
    clock_label = gtk_label_new("Saat"); gtk_label_set_ellipsize(GTK_LABEL(clock_label), PANGO_ELLIPSIZE_END); gtk_label_set_max_width_chars(GTK_LABEL(clock_label), 22); gtk_box_pack_start(GTK_BOX(strip), clock_label, TRUE, TRUE, 0);
    gtk_box_pack_end(GTK_BOX(strip), control_button("oguzdows-notifications-symbolic", "Bildirimler", "notifications"), FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(box), strip, FALSE, FALSE, 0);
    flow = gtk_flow_box_new(); gtk_flow_box_set_selection_mode(GTK_FLOW_BOX(flow), GTK_SELECTION_NONE); gtk_flow_box_set_min_children_per_line(GTK_FLOW_BOX(flow), 2); gtk_flow_box_set_max_children_per_line(GTK_FLOW_BOX(flow), 6);
    gtk_flow_box_set_homogeneous(GTK_FLOW_BOX(flow), TRUE); gtk_flow_box_set_column_spacing(GTK_FLOW_BOX(flow), 4); gtk_flow_box_set_row_spacing(GTK_FLOW_BOX(flow), 4);
    GtkWidget *scroll = gtk_scrolled_window_new(NULL, NULL); gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll), GTK_POLICY_NEVER, GTK_POLICY_AUTOMATIC);
    gtk_container_add(GTK_CONTAINER(scroll), flow); gtk_box_pack_start(GTK_BOX(box), scroll, TRUE, TRUE, 0);
    more = gtk_button_new_with_label("Daha fazla uygulama göster"); g_signal_connect(more, "clicked", G_CALLBACK(show_more), NULL); gtk_box_pack_start(GTK_BOX(box), more, FALSE, FALSE, 0);
    GtkWidget *controls = gtk_flow_box_new(); gtk_flow_box_set_selection_mode(GTK_FLOW_BOX(controls), GTK_SELECTION_NONE); gtk_flow_box_set_max_children_per_line(GTK_FLOW_BOX(controls), 4);
    const char *icons[] = {"oguzdows-audio-symbolic", "oguzdows-network-symbolic", "oguzdows-battery-symbolic", "oguzdows-cpu-symbolic"};
    const char *titles[] = {"Ses", "Ağ", "Pil", "Performans"}; const char *actions[] = {"audio", "network", "power", "monitor"};
    for (unsigned i = 0; i < 4; i++) {
        GtkWidget *button = control_button(icons[i], titles[i], actions[i]); gtk_container_add(GTK_CONTAINER(controls), button);
        GList *children = gtk_container_get_children(GTK_CONTAINER(gtk_bin_get_child(GTK_BIN(button))));
        GtkWidget *label = g_list_last(children)->data;
        if (i == 0) sound_label = label; else if (i == 1) network_label = label; else if (i == 2) battery_label = label;
        g_list_free(children);
    }
    gtk_box_pack_start(GTK_BOX(box), controls, FALSE, FALSE, 0);
    status_label = gtk_label_new("Kurulu uygulamalar okunuyor…"); gtk_label_set_line_wrap(GTK_LABEL(status_label), TRUE);
    gtk_style_context_add_class(gtk_widget_get_style_context(status_label), "subtitle"); gtk_box_pack_start(GTK_BOX(box), status_label, FALSE, FALSE, 0);
    load_apps(); populate();
    g_signal_connect(window, "map", G_CALLBACK(map), NULL); g_signal_connect(window, "unmap", G_CALLBACK(unmap), NULL);
    g_signal_connect(window, "destroy", G_CALLBACK(destroy), NULL); g_signal_connect(window, "destroy", G_CALLBACK(gtk_widget_destroyed), &window);
    gtk_widget_show_all(window); gtk_widget_grab_focus(search_entry); populate();
#ifdef OGUZDOWS_HUB_TEST
    if (smoke_directory) g_timeout_add(900, smoke_finish, NULL); else services();
#else
    services();
#endif
}

int main(int argc, char **argv) {
    if (argc == 2 && !strcmp(argv[1], "--version")) { puts("OğuzDows Başlat · native 1"); return 0; }
    gboolean test = FALSE;
#ifdef OGUZDOWS_HUB_TEST
    if (argc == 3 && !strcmp(argv[1], "--smoke-test")) { smoke_directory = argv[2]; g_mkdir_with_parents(smoke_directory, 0700); argc = 1; test = TRUE; }
#endif
    if (argc != 1) { fputs("Kullanım: oguzdows-hub [--version]\n", stderr); return 2; }
    if (!test && getuid() == 0) { fputs("Başlat normal kullanıcı hesabında çalışır.\n", stderr); return 1; }
    GtkApplication *application = gtk_application_new("org.oguzdows.Hub", G_APPLICATION_DEFAULT_FLAGS);
    g_signal_connect(application, "activate", G_CALLBACK(activate), NULL);
    int result = g_application_run(G_APPLICATION(application), argc, argv);
    if (cancellable) g_cancellable_cancel(cancellable);
    g_clear_object(&cancellable); g_clear_object(&volume_process);
    if (apps) g_ptr_array_unref(apps);
    if (pins) g_key_file_unref(pins);
    g_free(query); g_object_unref(application); return result;
}
