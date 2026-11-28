/* Event-driven xfconf observer. Idle: native GLib waits for D-Bus/file events.
 * A single bounded Python colour worker runs only after a wallpaper change.
 * No compositor control, shell parsing, network, image polling or root daemon.
 */
#define _POSIX_C_SOURCE 200809L
#include <gio/gio.h>
#include <json-glib/json-glib.h>
#include <xfconf/xfconf.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <string.h>

#ifndef OGUZDOWS_ACCENT_WORKER
#define OGUZDOWS_ACCENT_WORKER "/usr/lib/oguzdows/accent.py"
#endif

typedef struct {
    GApplication *application;
    XfconfChannel *desktop;
    GFileMonitor *monitor;
    GSubprocess *child;
    gchar *pending;
    guint debounce, retries;
    gboolean changed, running;
} Observer;

static gboolean automatic(void) {
    gchar *path = g_build_filename(g_get_user_config_dir(), "oguzdows", "desktop.json", NULL);
    int fd = open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK); g_free(path);
    if (fd < 0) return FALSE;
    struct stat info; char contents[65537]; ssize_t length = -1;
    if (!fstat(fd, &info) && S_ISREG(info.st_mode) && info.st_uid == getuid() && info.st_size <= 65536)
        length = read(fd, contents, sizeof(contents) - 1);
    close(fd);
    if (length <= 0 || length > 65536) return FALSE;
    contents[length] = 0;
    JsonParser *parser = json_parser_new(); gboolean result = FALSE;
    if (json_parser_load_from_data(parser, contents, length, NULL)) {
        JsonNode *root = json_parser_get_root(parser);
        if (root && JSON_NODE_HOLDS_OBJECT(root)) {
            JsonNode *value = json_object_get_member(json_node_get_object(root), "accent_source");
            if (value && JSON_NODE_HOLDS_VALUE(value) && json_node_get_value_type(value) == G_TYPE_STRING)
                result = !g_strcmp0(json_node_get_string(value), "wallpaper");
        }
    }
    g_object_unref(parser); return result;
}

static gboolean dispatch(gpointer pointer);
static void schedule(Observer *observer, guint milliseconds) {
    if (observer->debounce) g_source_remove(observer->debounce);
    observer->debounce = g_timeout_add(milliseconds, dispatch, observer);
}

static void finished(GObject *object, GAsyncResult *result, gpointer pointer) {
    Observer *observer = pointer; GError *error = NULL;
    gboolean waited = g_subprocess_wait_finish(G_SUBPROCESS(object), result, &error);
    gboolean busy = waited && g_subprocess_get_if_exited(G_SUBPROCESS(object)) && g_subprocess_get_exit_status(G_SUBPROCESS(object)) == 75;
    if (error) { g_warning("OğuzDows renk işçisi: %s", error->message); g_error_free(error); }
    g_clear_object(&observer->child);
    if (!automatic()) { g_application_quit(observer->application); return; }
    if (observer->changed) { observer->retries = 0; schedule(observer, 350); }
    else if (busy && observer->retries++ < 8) {
        observer->changed = TRUE;
        schedule(observer, MIN(30000u, 750u << MIN(observer->retries, 5u)));
    }
}

static gboolean dispatch(gpointer pointer) {
    Observer *observer = pointer; observer->debounce = 0;
    if (!automatic()) { g_application_quit(observer->application); return G_SOURCE_REMOVE; }
    if (observer->child) return G_SOURCE_REMOVE; /* exit callback dispatches latest event */
    observer->changed = FALSE;
    const gchar *args[] = {"/usr/bin/python3", "-I", OGUZDOWS_ACCENT_WORKER, "--sync",
                           observer->pending ? "--changed-property" : NULL, observer->pending, NULL};
    GError *error = NULL;
    observer->child = g_subprocess_newv(args, G_SUBPROCESS_FLAGS_STDOUT_SILENCE | G_SUBPROCESS_FLAGS_STDERR_SILENCE, &error);
    if (observer->child) g_subprocess_wait_async(observer->child, NULL, finished, observer);
    else { g_warning("OğuzDows renk işçisi başlayamadı: %s", error->message); g_error_free(error); }
    return G_SOURCE_REMOVE;
}

static void wallpaper_changed(XfconfChannel *channel, const gchar *property, const GValue *value, gpointer pointer) {
    (void)channel;
    if (!g_str_has_prefix(property, "/backdrop/") || !g_str_has_suffix(property, "/last-image")
            || strlen(property) > 1024 || !G_VALUE_HOLDS_STRING(value)) return;
    Observer *observer = pointer;
    g_free(observer->pending); observer->pending = g_strdup(property);
    observer->changed = TRUE; observer->retries = 0; schedule(observer, 350);
}

static void config_changed(GFileMonitor *monitor, GFile *file, GFile *other, GFileMonitorEvent event, gpointer pointer) {
    (void)monitor; (void)event;
    Observer *observer = pointer;
    gchar *name = g_file_get_basename(file), *destination = other ? g_file_get_basename(other) : NULL;
    if ((!g_strcmp0(name, "desktop.json") || !g_strcmp0(destination, "desktop.json")) && !automatic())
        g_application_quit(observer->application);
    g_free(name); g_free(destination);
}

static void activate(GApplication *application, gpointer pointer) {
    Observer *observer = pointer;
    if (observer->running || !automatic()) return;
    if (getuid() == 0 || !g_getenv("DISPLAY") || g_strcmp0(g_getenv("XDG_SESSION_TYPE"), "x11")) return;
    GError *error = NULL;
    if (!xfconf_init(&error)) { g_warning("xfconf renk izleme: %s", error->message); g_error_free(error); return; }
    observer->running = TRUE; observer->desktop = g_object_ref(xfconf_channel_get("xfce4-desktop"));
    g_signal_connect(observer->desktop, "property-changed", G_CALLBACK(wallpaper_changed), observer);
    gchar *directory = g_build_filename(g_get_user_config_dir(), "oguzdows", NULL);
    GFile *file = g_file_new_for_path(directory); g_free(directory);
    observer->monitor = g_file_monitor_directory(file, G_FILE_MONITOR_WATCH_MOVES, NULL, NULL); g_object_unref(file);
    if (observer->monitor) g_signal_connect(observer->monitor, "changed", G_CALLBACK(config_changed), observer);
    g_application_hold(application); observer->changed = TRUE; schedule(observer, 350);
}

int main(int argc, char **argv) {
    Observer observer = {0};
    gchar *hash = g_compute_checksum_for_string(G_CHECKSUM_SHA256, g_getenv("DISPLAY") ? g_getenv("DISPLAY") : "", -1);
    gchar *id = g_strdup_printf("org.oguzdows.AccentWatch.d%.12s", hash); g_free(hash);
    observer.application = g_application_new(id, G_APPLICATION_DEFAULT_FLAGS); g_free(id);
    g_signal_connect(observer.application, "activate", G_CALLBACK(activate), &observer);
    int status = g_application_run(observer.application, argc, argv);
    if (observer.debounce) g_source_remove(observer.debounce);
    /* A short-lived child checks the preference under its own transaction
     * lock; disabling automatic mode cannot re-enable or change manual colour. */
    g_clear_object(&observer.child); g_clear_object(&observer.monitor); g_clear_object(&observer.desktop);
    if (observer.running) xfconf_shutdown();
    g_free(observer.pending); g_object_unref(observer.application);
    return status;
}
