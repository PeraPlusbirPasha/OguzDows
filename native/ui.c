/* SPDX-License-Identifier: GPL-3.0-or-later */
#define _POSIX_C_SOURCE 200809L
#include "ui.h"
#include <json-glib/json-glib.h>
#include <math.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <string.h>
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

typedef struct { GtkWidget *image; double position, velocity; gint64 last, start; guint tick; gboolean hover; } Micro;

static gboolean spring(GtkWidget *widget, GdkFrameClock *clock, gpointer pointer) {
    (void)widget;
    Micro *micro = pointer;
    gint64 now = gdk_frame_clock_get_frame_time(clock);
    double dt = micro->last ? CLAMP((now - micro->last) / 1e6, 0.001, 0.032) : 0.016;
    if (!micro->start) micro->start = now;
    micro->last = now;
    double target = micro->hover ? 1 : 0;
    /* Sabit kütle / kritik sönüm; yalnız hover sırasında en çok 450 ms. */
    micro->velocity += (200 * (target - micro->position) - 28.284 * micro->velocity) * dt;
    micro->position += micro->velocity * dt;
    gtk_image_set_pixel_size(GTK_IMAGE(micro->image), 32 + (int)round(3 * CLAMP(micro->position, 0, 1)));
    if ((fabs(target - micro->position) < 0.008 && fabs(micro->velocity) < 0.02) || now - micro->start > 450000) {
        gtk_image_set_pixel_size(GTK_IMAGE(micro->image), micro->hover ? 35 : 32);
        micro->tick = 0; micro->last = 0; micro->start = 0;
        return G_SOURCE_REMOVE;
    }
    return G_SOURCE_CONTINUE;
}

static gboolean hover(GtkWidget *widget, GdkEventCrossing *event, gpointer pointer) {
    Micro *micro = pointer;
    micro->hover = event->type == GDK_ENTER_NOTIFY;
    if (motion && !micro->tick) micro->tick = gtk_widget_add_tick_callback(widget, spring, micro, NULL);
    return FALSE;
}

static void unmapped(GtkWidget *widget, gpointer pointer) {
    Micro *micro = pointer;
    if (micro->tick) gtk_widget_remove_tick_callback(widget, micro->tick);
    micro->tick = 0; micro->last = 0; micro->start = 0;
    micro->position = 0; micro->velocity = 0; micro->hover = FALSE;
    gtk_image_set_pixel_size(GTK_IMAGE(micro->image), 32);
}

void og_ui_setup(GtkWidget *window) {
    GtkCssProvider *provider = gtk_css_provider_new();
    GError *error = NULL;
    if (!gtk_css_provider_load_from_path(provider, OGUZDOWS_UI_CSS, &error)) {
        g_printerr("OğuzDows UI: %s\n", error->message); g_clear_error(&error);
    }
    gtk_style_context_add_provider_for_screen(gtk_widget_get_screen(window), GTK_STYLE_PROVIDER(provider), GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    g_object_unref(provider);
    gtk_style_context_add_class(gtk_widget_get_style_context(window), "oguzdows-modern");
    gboolean animations = FALSE, dark = FALSE;
    g_object_get(gtk_settings_get_default(), "gtk-enable-animations", &animations, "gtk-application-prefer-dark-theme", &dark, NULL);
    motion = animations;
    gchar *path = g_build_filename(g_get_user_config_dir(), "oguzdows", "desktop.json", NULL);
    JsonParser *parser = json_parser_new();
    gchar *preferences = NULL;
    if (og_ui_read_file(path, 65536, &preferences) && json_parser_load_from_data(parser, preferences, -1, NULL) && JSON_NODE_HOLDS_OBJECT(json_parser_get_root(parser))) {
        JsonObject *prefs = json_node_get_object(json_parser_get_root(parser));
        JsonNode *node = json_object_get_member(prefs, "motion");
        if (node && json_node_get_value_type(node) == G_TYPE_STRING) motion = motion && g_strcmp0(json_node_get_string(node), "reduced");
        node = json_object_get_member(prefs, "feedback");
        feedback = node && json_node_get_value_type(node) == G_TYPE_BOOLEAN && json_node_get_boolean(node);
        node = json_object_get_member(prefs, "appearance");
        if (node && json_node_get_value_type(node) == G_TYPE_STRING) dark = !g_strcmp0(json_node_get_string(node), "dark");
        node = json_object_get_member(prefs, "accent");
        const gchar *accent = node && json_node_get_value_type(node) == G_TYPE_STRING ? json_node_get_string(node) : NULL;
        if (accent && g_regex_match_simple("^#[a-fA-F0-9]{6}$", accent, 0, 0)) {
            GtkCssProvider *tint = gtk_css_provider_new();
            gchar *css = g_strdup_printf(".oguzdows-modern button:hover, .oguzdows-modern entry:focus {border-color: %s;} .oguzdows-modern .accent {color: %s;}", accent, accent);
            gtk_css_provider_load_from_data(tint, css, -1, NULL);
            gtk_style_context_add_provider_for_screen(gtk_widget_get_screen(window), GTK_STYLE_PROVIDER(tint), GTK_STYLE_PROVIDER_PRIORITY_APPLICATION + 1);
            g_free(css); g_object_unref(tint);
        }
    }
    g_object_unref(parser); g_free(path); g_free(preferences);
    if (dark) gtk_style_context_add_class(gtk_widget_get_style_context(window), "oguzdows-dark");
    /* Düşük RAM'de, başka bir DE GtkAnimations'ı açık bıraksa bile ikon tick'i yok. */
    gchar *contents = NULL;
    if (g_file_get_contents("/proc/meminfo", &contents, NULL, NULL)) {
        gchar *start = strstr(contents, "MemTotal:");
        if (!start || g_ascii_strtoull(start + 9, NULL, 10) <= 2097152) motion = FALSE;
        g_free(contents);
    } else motion = FALSE;
    if (!motion) gtk_style_context_add_class(gtk_widget_get_style_context(window), "reduced-motion");
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
    Micro *micro = g_new0(Micro, 1); micro->image = image;
    g_object_set_data_full(G_OBJECT(button), "oguz-micro", micro, g_free);
    g_signal_connect(button, "enter-notify-event", G_CALLBACK(hover), micro);
    g_signal_connect(button, "leave-notify-event", G_CALLBACK(hover), micro);
    g_signal_connect(button, "unmap", G_CALLBACK(unmapped), micro);
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
