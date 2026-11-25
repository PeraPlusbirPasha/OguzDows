/* SPDX-License-Identifier: GPL-3.0-or-later */
#define _POSIX_C_SOURCE 200809L
#include "ui.h"
#include <json-glib/json-glib.h>
#include <gdk/gdkx.h>
#include <X11/Xlib.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <string.h>
#include <math.h>
#ifndef OGUZDOWS_UI_CSS
#define OGUZDOWS_UI_CSS "/usr/share/oguzdows/ui/modern.css"
#endif
static gboolean feedback, motion = FALSE;

gboolean og_ui_read_file(const char *path, gsize maximum, gchar **contents) {
    *contents = NULL;
    int fd = open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0) return FALSE;
    struct stat info;
    if (fstat(fd, &info) || !S_ISREG(info.st_mode) || info.st_uid != getuid() || info.st_size < 0 || (guint64)info.st_size > maximum) {
        close(fd); return FALSE;
    }
    gchar *data = g_malloc(maximum + 1); gsize used = 0;
    while (used < maximum) {
        ssize_t length = read(fd, data + used, maximum - used);
        if (length < 0) { g_free(data); close(fd); return FALSE; }
        if (!length) break;
        used += (gsize)length;
    }
    char extra;
    gboolean complete = read(fd, &extra, 1) == 0;
    close(fd);
    if (!complete || memchr(data, '\0', used)) { g_free(data); return FALSE; }
    data[used] = '\0'; *contents = data; return TRUE;
}

/* Event-driven material + motion. No idle animation loop, no renderer daemon. */
static JsonObject *read_object(const gchar *path, JsonParser **parser) {
    gchar *data = NULL;
    *parser = json_parser_new();
    if (!og_ui_read_file(path, 65536, &data)) return NULL;
    gboolean valid = json_parser_load_from_data(*parser, data, -1, NULL);
    g_free(data);
    JsonNode *root = valid ? json_parser_get_root(*parser) : NULL;
    return root && JSON_NODE_HOLDS_OBJECT(root) ? json_node_get_object(root) : NULL;
}

static const gchar *string(JsonObject *object, const gchar *key) {
    JsonNode *node = object ? json_object_get_member(object, key) : NULL;
    return node && JSON_NODE_HOLDS_VALUE(node) && json_node_get_value_type(node) == G_TYPE_STRING ? json_node_get_string(node) : "";
}

static gboolean boolean(JsonObject *object, const gchar *key) {
    JsonNode *node = object ? json_object_get_member(object, key) : NULL;
    return node && JSON_NODE_HOLDS_VALUE(node) && json_node_get_value_type(node) == G_TYPE_BOOLEAN && json_node_get_boolean(node);
}

static gboolean resource_budget(void) {
    gchar *data = NULL;
    if (!g_file_get_contents("/proc/meminfo", &data, NULL, NULL)) return FALSE;
    gchar *start = strstr(data, "MemTotal:");
    gboolean enough = start && g_ascii_strtoull(start + 9, NULL, 10) > 2097152;
    g_free(data);
    if (!enough || !g_file_get_contents("/proc/cmdline", &data, NULL, NULL)) return FALSE;
    enough = !strstr(data, "nomodeset") && !strstr(data, "oguzdows.profile=mini") && !strstr(data, "oguzdows.profile=light");
    g_free(data);
    const gchar *configs[] = {"/etc/oguzdows/resources.conf", "/etc/oguzdows/pi.conf"};
    for (guint i = 0; i < G_N_ELEMENTS(configs); i++) {
        if (g_file_get_contents(configs[i], &data, NULL, NULL)) {
            if (g_regex_match_simple("(?m)^\\s*profile\\s*=\\s*(mini|light)\\s*(#.*)?$", data, 0, 0)) enough = FALSE;
            g_free(data);
        }
    }
    if (!enough) return FALSE;
    /* RAM alone is NOT acceleration evidence; same DRM allowlist as policy. */
    GDir *directory = g_dir_open("/sys/class/drm", 0, NULL);
    if (!directory) return FALSE;
    const gchar *name; gboolean graphics = FALSE;
    while ((name = g_dir_read_name(directory))) {
        if (!g_regex_match_simple("^card[0-9]+$", name, 0, 0)) continue;
        gchar *path = g_build_filename("/sys/class/drm", name, "device/driver", NULL);
        gchar *link = g_file_read_link(path, NULL), *driver = link ? g_path_get_basename(link) : NULL;
        const gchar *allowed[] = {"vc4", "v3d", "i915", "xe", "amdgpu", "radeon", "nouveau", "nvidia", "virtio_gpu", "panfrost", "lima", "msm", "etnaviv"};
        for (guint i = 0; driver && i < G_N_ELEMENTS(allowed); i++) if (!strcmp(driver, allowed[i])) graphics = TRUE;
        g_free(driver); g_free(link); g_free(path);
    }
    g_dir_close(directory); return graphics;
}

static gboolean confirmed_blur(GtkWidget *window) {
    GdkDisplay *display = gtk_widget_get_display(window);
    if (!GDK_IS_X11_DISPLAY(display) || !gdk_screen_is_composited(gtk_widget_get_screen(window))) return FALSE;
    gchar *key = g_compute_checksum_for_string(G_CHECKSUM_SHA256, g_getenv("DISPLAY") ? g_getenv("DISPLAY") : "", -1);
    key[16] = '\0';
    gchar *base = g_build_filename(g_get_user_state_dir(), "oguzdows/effects", key, NULL);
    gchar *path = g_build_filename(base, "status.json", NULL);
    JsonParser *status_parser, *owner_parser;
    JsonObject *state = read_object(path, &status_parser);
    g_free(path); path = g_build_filename(base, "picom.json", NULL);
    JsonObject *owner = read_object(path, &owner_parser);
    gboolean valid = state && owner && boolean(state, "blur_configured") && !strcmp(string(state, "engine"), "picom");
    if (valid) {
        JsonNode *pid_node = json_object_get_member(owner, "pid"), *xid_node = json_object_get_member(owner, "owner");
        valid = pid_node && xid_node && JSON_NODE_HOLDS_VALUE(pid_node) && JSON_NODE_HOLDS_VALUE(xid_node) && json_node_get_value_type(pid_node) == G_TYPE_INT64 && json_node_get_value_type(xid_node) == G_TYPE_INT64;
        if (valid) {
            gint64 pid = json_node_get_int(pid_node), xid = json_node_get_int(xid_node);
            gchar *atom = g_strdup_printf("_NET_WM_CM_S%d", gdk_x11_screen_get_screen_number(gtk_widget_get_screen(window)));
            Display *xdisplay = gdk_x11_display_get_xdisplay(display);
            valid = pid > 1 && xid > 0 && (guint64)XGetSelectionOwner(xdisplay, XInternAtom(xdisplay, atom, False)) == (guint64)xid;
            g_free(atom);
            gchar *proc = g_strdup_printf("/proc/%" G_GINT64_FORMAT, pid);
            struct stat info;
            valid = valid && !stat(proc, &info) && info.st_uid == getuid();
            gchar *stat_path = g_build_filename(proc, "stat", NULL), *data = NULL;
            if (valid && g_file_get_contents(stat_path, &data, NULL, NULL)) {
                gchar *tail = g_strrstr(data, ") ");
                gchar **fields = tail ? g_strsplit(tail + 2, " ", 0) : NULL;
                valid = fields && g_strv_length(fields) > 19 && strcmp(fields[0], "Z") && !strcmp(fields[19], string(owner, "started"));
                g_strfreev(fields); g_free(data);
            } else valid = FALSE;
            gchar *cmd_path = g_build_filename(proc, "cmdline", NULL); gsize length = 0;
            const gchar *config = string(owner, "config");
            gchar *recipe = g_path_get_basename(config);
            const gchar *blur_recipes[] = {"blur.conf", "blur-still.conf", "blur9.conf", "blur9-still.conf", "full.conf", "full-snap.conf"};
            gboolean blur_recipe = FALSE;
            for (guint i = 0; i < G_N_ELEMENTS(blur_recipes); i++) if (!strcmp(recipe, blur_recipes[i])) blur_recipe = TRUE;
            valid = valid && blur_recipe && !strcmp(config, string(state, "config"));
            g_free(recipe);
            if (valid && g_file_get_contents(cmd_path, &data, &length, NULL)) {
                const gchar *prefix = "/usr/bin/picom\0--config\0";
                gsize prefix_length = sizeof("/usr/bin/picom\0--config\0") - 1;
                valid = g_str_has_prefix(config, "/usr/share/oguzdows/compositor/") &&
                    length == prefix_length + strlen(config) + 1 && !memcmp(data, prefix, prefix_length) && !memcmp(data + prefix_length, config, strlen(config) + 1);
                g_free(data);
            } else valid = FALSE;
            g_free(proc); g_free(stat_path); g_free(cmd_path);
        }
    }
    g_object_unref(status_parser); g_object_unref(owner_parser);
    g_free(path); g_free(base); g_free(key); return valid;
}

void og_ui_stack_setup(GtkWidget *stack) {
    gtk_stack_set_transition_type(GTK_STACK(stack), motion ? GTK_STACK_TRANSITION_TYPE_CROSSFADE : GTK_STACK_TRANSITION_TYPE_NONE);
    gtk_stack_set_transition_duration(GTK_STACK(stack), motion ? 200 : 0);
}

gboolean og_ui_motion_enabled(void) { return motion; }

static void refresh_stacks(GtkWidget *widget, gpointer data) {
    (void)data;
    if (GTK_IS_STACK(widget)) og_ui_stack_setup(widget);
    if (GTK_IS_CONTAINER(widget)) gtk_container_foreach(GTK_CONTAINER(widget), refresh_stacks, NULL);
}

static void refresh_style(GtkWidget *window) {
    gboolean animations = FALSE, dark = FALSE;
    gchar *theme = NULL;
    g_object_get(gtk_settings_get_default(), "gtk-enable-animations", &animations, "gtk-application-prefer-dark-theme", &dark, "gtk-theme-name", &theme, NULL);
    gboolean high_contrast = theme && strstr(theme, "HighContrast");
    GtkStyleContext *context = gtk_widget_get_style_context(window);
    if (high_contrast) gtk_style_context_remove_class(context, "oguzdows-modern");
    else gtk_style_context_add_class(context, "oguzdows-modern");
    if (theme && g_str_has_prefix(theme, "OguzDowsMac")) gtk_style_context_add_class(context, "oguzdows-mac");
    else gtk_style_context_remove_class(context, "oguzdows-mac");
    if (theme && g_str_has_prefix(theme, "OguzDowsEleven")) gtk_style_context_add_class(context, "oguzdows-eleven");
    else gtk_style_context_remove_class(context, "oguzdows-eleven");
    g_free(theme);
    gboolean budget = resource_budget();
    motion = animations && budget; feedback = FALSE;
    gchar *path = g_build_filename(g_get_user_config_dir(), "oguzdows", "desktop.json", NULL);
    JsonParser *parser;
    JsonObject *prefs = read_object(path, &parser);
    if (prefs) {
        motion = motion && strcmp(string(prefs, "motion"), "reduced");
        feedback = boolean(prefs, "feedback");
        if (*string(prefs, "appearance")) dark = !strcmp(string(prefs, "appearance"), "dark");
    }
    if (dark) gtk_style_context_add_class(context, "oguzdows-dark"); else gtk_style_context_remove_class(context, "oguzdows-dark");
    if (!motion) gtk_style_context_add_class(context, "reduced-motion"); else gtk_style_context_remove_class(context, "reduced-motion");
    /* Only the independently confirmed owned Picom path gets alpha. GNOME /
       unknown compositor / Wayland retain the fully readable opaque material. */
    gboolean glass = prefs && !strcmp(string(prefs, "effects"), "aero") && boolean(prefs, "blur") && budget && confirmed_blur(window);
    if (glass) gtk_style_context_add_class(context, "oguzdows-glass"); else gtk_style_context_remove_class(context, "oguzdows-glass");
    static GtkCssProvider *tint;
    if (!tint) {
        tint = gtk_css_provider_new();
        gtk_style_context_add_provider_for_screen(gtk_widget_get_screen(window), GTK_STYLE_PROVIDER(tint), GTK_STYLE_PROVIDER_PRIORITY_APPLICATION + 1);
    }
    const gchar *accent = prefs ? string(prefs, "accent") : "";
    if (!g_regex_match_simple("^#[a-fA-F0-9]{6}$", accent, 0, 0)) accent = "#187e91";
    GdkRGBA rgba; gdk_rgba_parse(&rgba, accent);
    double components[] = {rgba.red, rgba.green, rgba.blue}, luminance = 0;
    const double weights[] = {.2126, .7152, .0722};
    for (guint i = 0; i < 3; i++) luminance += weights[i] * (components[i] <= .04045
        ? components[i] / 12.92 : pow((components[i] + .055) / 1.055, 2.4));
    gchar *css = g_strdup_printf("@define-color og_accent %s; @define-color og_accent_fg %s;", accent, luminance > .179 ? "#11202f" : "#ffffff");
    gtk_css_provider_load_from_data(tint, css, -1, NULL); g_free(css);
    g_object_unref(parser); g_free(path);
    refresh_stacks(window, NULL);
}

static void changed(GFileMonitor *monitor, GFile *file, GFile *other, GFileMonitorEvent event, gpointer data) {
    (void)monitor;
    if (event != G_FILE_MONITOR_EVENT_CHANGES_DONE_HINT && event != G_FILE_MONITOR_EVENT_CREATED && event != G_FILE_MONITOR_EVENT_DELETED && event != G_FILE_MONITOR_EVENT_MOVED_IN && event != G_FILE_MONITOR_EVENT_RENAMED && event != G_FILE_MONITOR_EVENT_MOVED_OUT) return;
    gchar *name = g_file_get_basename(file), *destination = other ? g_file_get_basename(other) : NULL;
    if (!g_strcmp0(name, "desktop.json") || !g_strcmp0(destination, "desktop.json")) refresh_style(GTK_WIDGET(data));
    g_free(name); g_free(destination);
}

static void composited(GdkScreen *screen, gpointer data) { (void)screen; refresh_style(GTK_WIDGET(data)); }
static void settings_changed(GObject *settings, GParamSpec *spec, gpointer data) { (void)settings; (void)spec; refresh_style(GTK_WIDGET(data)); }

void og_ui_setup(GtkWidget *window) {
    static gboolean loaded;
    if (!loaded) {
        GtkCssProvider *provider = gtk_css_provider_new(); GError *error = NULL;
        if (!gtk_css_provider_load_from_path(provider, OGUZDOWS_UI_CSS, &error)) {
            g_printerr("OğuzDows UI: %s\n", error->message); g_clear_error(&error);
        }
        gtk_style_context_add_provider_for_screen(gtk_widget_get_screen(window), GTK_STYLE_PROVIDER(provider), GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
        g_object_unref(provider); loaded = TRUE;
    }
    GdkScreen *screen = gtk_widget_get_screen(window);
    GdkVisual *visual = gdk_screen_get_rgba_visual(screen);
    if (visual && !gtk_widget_get_realized(window)) gtk_widget_set_visual(window, visual);
    refresh_style(window);
    g_signal_connect_object(screen, "composited-changed", G_CALLBACK(composited), window, 0);
    const gchar *properties[] = {"notify::gtk-enable-animations", "notify::gtk-application-prefer-dark-theme", "notify::gtk-theme-name"};
    for (guint i = 0; i < G_N_ELEMENTS(properties); i++)
        g_signal_connect_object(gtk_settings_get_default(), properties[i], G_CALLBACK(settings_changed), window, 0);
    gchar *path = g_build_filename(g_get_user_config_dir(), "oguzdows", NULL);
    GFile *directory = g_file_new_for_path(path);
    GFileMonitor *monitor = g_file_monitor_directory(directory, G_FILE_MONITOR_WATCH_MOVES, NULL, NULL);
    if (monitor) {
        g_signal_connect(monitor, "changed", G_CALLBACK(changed), window);
        g_object_set_data_full(G_OBJECT(window), "oguz-theme-monitor", monitor, g_object_unref);
    }
    g_object_unref(directory); g_free(path);
}

GtkWidget *og_ui_action(const char *icon, const char *text) {
    GtkWidget *button = gtk_button_new(), *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
    gtk_style_context_add_class(gtk_widget_get_style_context(button), "oguz-action");
    GtkWidget *slot = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    gtk_widget_set_size_request(slot, 44, 42);
    GtkWidget *image = gtk_image_new_from_icon_name(icon, GTK_ICON_SIZE_DIALOG);
    gtk_image_set_pixel_size(GTK_IMAGE(image), 32);
    gtk_box_pack_start(GTK_BOX(slot), image, TRUE, FALSE, 0);
    GtkWidget *label = gtk_label_new(text);
    gtk_label_set_line_wrap(GTK_LABEL(label), TRUE);
    gtk_label_set_max_width_chars(GTK_LABEL(label), 17);
    gtk_label_set_lines(GTK_LABEL(label), 2);
    gtk_label_set_ellipsize(GTK_LABEL(label), PANGO_ELLIPSIZE_END);
    gtk_label_set_justify(GTK_LABEL(label), GTK_JUSTIFY_CENTER);
    gtk_box_pack_start(GTK_BOX(box), slot, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(box), label, FALSE, FALSE, 0);
    gtk_container_add(GTK_CONTAINER(button), box);
    gtk_widget_set_tooltip_text(button, text);
    gtk_widget_set_can_focus(button, TRUE);
    /* Hover uses only CSS color/opacity: never resize an icon per frame. */
    return button;
}

void og_ui_feedback(void) {
    if (!feedback || !g_file_test("/usr/bin/paplay", G_FILE_TEST_IS_EXECUTABLE)) return;
    gchar *argv[] = {"/usr/bin/paplay", "--property=media.role=event", "/usr/share/oguzdows/ui/confirm.wav", NULL};
    g_spawn_async(NULL, argv, NULL, G_SPAWN_STDOUT_TO_DEV_NULL | G_SPAWN_STDERR_TO_DEV_NULL, NULL, NULL, NULL, NULL);
}

gboolean og_ui_launch_control(const char *action, GError **error) {
    /* action dahili sabit kimliktir; Python tarafı ayrıca izin listesi uygular. */
    gchar *argv[] = {"/usr/local/bin/oguzdows-desktop", "--control", (gchar *)action, NULL};
    return g_spawn_async(NULL, argv, NULL, G_SPAWN_STDOUT_TO_DEV_NULL, NULL, NULL, NULL, error);
}
