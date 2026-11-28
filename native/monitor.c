/* SPDX-License-Identifier: GPL-3.0-or-later
 * Native C / GTK / Cairo. 90 örnek sabit halka; gizli pencerede sayaç okunmaz.
 */
#define _POSIX_C_SOURCE 200809L
#include "metrics.h"
#include "ui.h"
#include <dirent.h>
#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/utsname.h>
#include <unistd.h>

#define HISTORY 90
static GtkWidget *window, *pages, *status_label, *process_view;
static GtkWidget *values[3], *details[3], *graphs[3];
static OgSnapshot previous;
static gboolean have_previous, minimized, obscured, paused;
static OgUsage history[HISTORY];
static unsigned head, count, timer, samples;
static unsigned interval = 1;
#ifdef OGUZDOWS_MONITOR_TEST
static const char *smoke_directory;
#endif

static GtkWidget *text(const char *value, const char *style) {
    GtkWidget *label = gtk_label_new(value);
    gtk_label_set_xalign(GTK_LABEL(label), 0);
    gtk_label_set_line_wrap(GTK_LABEL(label), TRUE);
    if (style) gtk_style_context_add_class(gtk_widget_get_style_context(label), style);
    return label;
}

static char *rate(double value) {
    const char *unit = "B/s";
    if (value >= 1048576) { value /= 1048576; unit = "MiB/s"; }
    else if (value >= 1024) { value /= 1024; unit = "KiB/s"; }
    return g_strdup_printf("%.1f %s", value, unit);
}

static void update_labels(const OgUsage *usage) {
    gchar *cpu = usage->cpu_valid ? g_strdup_printf("%.1f %%", usage->cpu_percent) : g_strdup("—");
    gchar *memory = usage->memory_valid ? g_strdup_printf("%.1f %%", usage->memory_percent) : g_strdup("—");
    gchar *received = usage->network_valid ? rate(usage->receive_rate) : g_strdup("—");
    gchar *sent = usage->network_valid ? rate(usage->send_rate) : g_strdup("—");
    gchar *network = g_strdup_printf("↓ %s", received);
    gchar *network_note = g_strdup_printf("↑ %s · loopback hariç", sent);
    gchar *memory_note = usage->memory_valid ? g_strdup_printf("%.0f / %.0f MiB · kullanılabilir hariç",
        usage->memory_used / 1048576.0, usage->memory_total / 1048576.0) : g_strdup("/proc/meminfo okunamadı");
    const char *labels[] = {cpu, memory, network};
    for (unsigned i = 0; i < 3; i++) {
        gtk_label_set_text(GTK_LABEL(values[i]), labels[i]);
        gtk_widget_queue_draw(graphs[i]);
    }
    gtk_label_set_text(GTK_LABEL(details[1]), memory_note);
    gtk_label_set_text(GTK_LABEL(details[2]), network_note);
    g_free(cpu); g_free(memory); g_free(received); g_free(sent); g_free(network); g_free(network_note); g_free(memory_note);
}

static gboolean allowed(void) {
    return gtk_widget_get_mapped(window) && !minimized && !obscured && !paused &&
        !g_strcmp0(gtk_stack_get_visible_child_name(GTK_STACK(pages)), "overview");
}

static gboolean sample(gpointer unused) {
    (void)unused;
    if (!allowed()) { timer = 0; have_previous = FALSE; return G_SOURCE_REMOVE; }
    OgSnapshot current;
    OgUsage usage;
    og_metrics_read(&current, "/proc");
    og_metrics_usage(have_previous ? &previous : NULL, &current, &usage);
    history[head] = usage; head = (head + 1) % HISTORY;
    if (count < HISTORY) count++;
    previous = current; have_previous = TRUE; samples++;
    update_labels(&usage);
    return G_SOURCE_CONTINUE;
}

static void scheduling(void) {
    if (!allowed()) {
        if (timer) { g_source_remove(timer); timer = 0; }
        have_previous = FALSE;
        gtk_label_set_text(GTK_LABEL(status_label), "Duraklatıldı · arka planda örnekleme yok");
    } else if (!timer) {
        gtk_label_set_text(GTK_LABEL(status_label), "Canlı · yalnız görünür performans sayfasında");
        sample(NULL);
        timer = g_timeout_add_seconds(interval, sample, NULL);
    }
}

static void mapped(GtkWidget *widget, gpointer data) { (void)widget; (void)data; scheduling(); }
static void page_changed(GObject *object, GParamSpec *parameter, gpointer data) { (void)object; (void)parameter; (void)data; scheduling(); }
static void select_page(GtkComboBox *selector, gpointer data) {
    (void)data;
    const char *name = gtk_combo_box_get_active_id(selector);
    if (name) gtk_stack_set_visible_child_name(GTK_STACK(pages), name);
}
static gboolean window_state(GtkWidget *widget, GdkEventWindowState *event, gpointer data) {
    (void)widget; (void)data;
    minimized = (event->new_window_state & GDK_WINDOW_STATE_ICONIFIED) != 0;
    scheduling(); return FALSE;
}
static gboolean visibility(GtkWidget *widget, GdkEventVisibility *event, gpointer data) {
    (void)widget; (void)data;
    obscured = event->state == GDK_VISIBILITY_FULLY_OBSCURED;
    scheduling(); return FALSE;
}
static void pause_clicked(GtkToggleButton *button, gpointer data) { (void)data; paused = gtk_toggle_button_get_active(button); scheduling(); }
static void destroy(GtkWidget *widget, gpointer data) { (void)widget; (void)data; if (timer) g_source_remove(timer); timer = 0; }

static double number(const OgUsage *usage, unsigned graph, unsigned line, gboolean *valid) {
    if (graph == 0) { *valid = usage->cpu_valid; return usage->cpu_percent; }
    if (graph == 1) { *valid = usage->memory_valid; return usage->memory_percent; }
    *valid = usage->network_valid;
    return line ? usage->send_rate : usage->receive_rate;
}

static gboolean draw(GtkWidget *widget, cairo_t *cr, gpointer pointer) {
    unsigned graph = GPOINTER_TO_UINT(pointer);
    double width = gtk_widget_get_allocated_width(widget), height = gtk_widget_get_allocated_height(widget);
    double scale = 100;
    if (graph == 2) {
        scale = 1024;
        for (unsigned i = 0; i < count; i++) {
            const OgUsage *usage = &history[(head + HISTORY - count + i) % HISTORY];
            scale = MAX(scale, MAX(usage->receive_rate, usage->send_rate) * 1.12);
        }
    }
    cairo_set_line_width(cr, 1);
    cairo_set_source_rgba(cr, .43, .57, .72, .16);
    for (int y = 1; y < 4; y++) { cairo_move_to(cr, 0, height * y / 4); cairo_line_to(cr, width, height * y / 4); }
    for (int x = 1; x < 6; x++) { cairo_move_to(cr, width * x / 6, 0); cairo_line_to(cr, width * x / 6, height); }
    cairo_stroke(cr);
    const double colors[3][3] = {{.16, .55, .88}, {.13, .66, .63}, {.55, .43, .86}};
    for (unsigned line = 0; line < (graph == 2 ? 2u : 1u); line++) {
        gboolean connected = FALSE;
        cairo_new_path(cr);
        for (unsigned i = 0; i < count; i++) {
            gboolean valid;
            double value = number(&history[(head + HISTORY - count + i) % HISTORY], graph, line, &valid);
            if (!valid || !isfinite(value)) { connected = FALSE; continue; }
            double x = width * (HISTORY - count + i) / (HISTORY - 1);
            double y = height - 4 - CLAMP(value / scale, 0, 1) * (height - 12);
            if (connected) cairo_line_to(cr, x, y); else cairo_move_to(cr, x, y);
            connected = TRUE;
        }
        cairo_set_source_rgba(cr, line ? .94 : colors[graph][0], line ? .59 : colors[graph][1], line ? .30 : colors[graph][2], .96);
        cairo_set_line_width(cr, line ? 1.8 : 2.4);
        if (line) { double dashes[] = {5, 3}; cairo_set_dash(cr, dashes, 2, 0); }
        cairo_stroke(cr); cairo_set_dash(cr, NULL, 0, 0);
    }
    return FALSE;
}

static GtkWidget *card(unsigned graph, const char *title, const char *icon) {
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
    gtk_widget_set_size_request(box, 244, -1);
    gtk_style_context_add_class(gtk_widget_get_style_context(box), "metric");
    GtkWidget *row = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    gtk_box_pack_start(GTK_BOX(row), gtk_image_new_from_icon_name(icon, GTK_ICON_SIZE_BUTTON), FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(row), text(title, "accent"), TRUE, TRUE, 0);
    gtk_box_pack_start(GTK_BOX(box), row, FALSE, FALSE, 0);
    values[graph] = text("—", "metric-value");
    gtk_box_pack_start(GTK_BOX(box), values[graph], FALSE, FALSE, 0);
    details[graph] = text(graph == 0 ? "Toplam çekirdek kullanımı · gerçek sayaç farkı" : "İlk ölçüm bekleniyor", "subtitle");
    gtk_label_set_max_width_chars(GTK_LABEL(details[graph]), 30);
    gtk_box_pack_start(GTK_BOX(box), details[graph], FALSE, FALSE, 0);
    graphs[graph] = gtk_drawing_area_new();
    gtk_widget_set_size_request(graphs[graph], 180, 116);
    g_signal_connect(graphs[graph], "draw", G_CALLBACK(draw), GUINT_TO_POINTER(graph));
    gtk_box_pack_start(GTK_BOX(box), graphs[graph], TRUE, TRUE, 0);
    gchar *axis = g_strdup_printf("Son %u saniye · %s", HISTORY * interval, graph == 2 ? "anlık B/s · otomatik ölçek" : "0 — 100 %");
    gtk_box_pack_start(GTK_BOX(box), text(axis, "subtitle"), FALSE, FALSE, 0); g_free(axis);
    return box;
}

typedef struct { unsigned long pid, pages; gchar *name; } Process;
static gint compare_process(gconstpointer a, gconstpointer b) {
    const Process *left = *(Process * const *)a, *right = *(Process * const *)b;
    return left->pages < right->pages ? 1 : left->pages > right->pages ? -1 : 0;
}
static void process_free(gpointer pointer) { Process *process = pointer; g_free(process->name); g_free(process); }

static void refresh_processes(GtkButton *button, gpointer data) {
    (void)button; (void)data;
    GPtrArray *items = g_ptr_array_new_with_free_func(process_free);
    DIR *directory = opendir("/proc");
    if (!directory) return;
    struct dirent *entry;
    while ((entry = readdir(directory)) && items->len < 8192) {
        gchar *end;
        unsigned long pid = strtoul(entry->d_name, &end, 10);
        if (*end || !pid) continue;
        char path[128]; unsigned long size, rss;
        g_snprintf(path, sizeof path, "/proc/%lu/statm", pid);
        FILE *stream = fopen(path, "r");
        if (!stream) continue;
        int valid = fscanf(stream, "%lu %lu", &size, &rss); fclose(stream);
        if (valid != 2) continue;
        g_snprintf(path, sizeof path, "/proc/%lu/comm", pid);
        stream = fopen(path, "r"); char name[256] = "?";
        if (stream) { if (!fgets(name, sizeof name, stream)) name[0] = '?'; fclose(stream); }
        g_strchomp(name);
        Process *process = g_new0(Process, 1);
        process->pid = pid; process->pages = rss; process->name = g_utf8_make_valid(name, -1);
        g_ptr_array_add(items, process);
    }
    closedir(directory); g_ptr_array_sort(items, compare_process);
    GtkListStore *model = GTK_LIST_STORE(gtk_tree_view_get_model(GTK_TREE_VIEW(process_view)));
    gtk_list_store_clear(model);
    long page_size = sysconf(_SC_PAGESIZE);
    if (page_size < 1) page_size = 4096;
    for (unsigned i = 0; i < MIN(items->len, 128); i++) {
        Process *process = g_ptr_array_index(items, i); GtkTreeIter iter;
        gchar *memory = g_strdup_printf("%.1f MiB", process->pages * (double)page_size / 1048576);
        gtk_list_store_append(model, &iter);
        gtk_list_store_set(model, &iter, 0, (guint)process->pid, 1, process->name, 2, memory, -1);
        g_free(memory);
    }
    g_ptr_array_unref(items);
}

static GtkWidget *processes(void) {
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 10);
    gtk_box_pack_start(GTK_BOX(box), text("Belleğe göre ilk 128 süreç. Yalnız Yenile ile okunur; süreç öldürme / root işlemi yok. RSS paylaşılan sayfaları da içerir, süreç toplamı fiziksel RAM toplamı değildir.", "subtitle"), FALSE, FALSE, 0);
    GtkWidget *refresh = gtk_button_new_with_label("Süreç anlık görüntüsünü yenile");
    gtk_label_set_line_wrap(GTK_LABEL(gtk_bin_get_child(GTK_BIN(refresh))), TRUE);
    gtk_label_set_max_width_chars(GTK_LABEL(gtk_bin_get_child(GTK_BIN(refresh))), 28);
    g_signal_connect(refresh, "clicked", G_CALLBACK(refresh_processes), NULL);
    gtk_box_pack_start(GTK_BOX(box), refresh, FALSE, FALSE, 0);
    GtkListStore *model = gtk_list_store_new(3, G_TYPE_UINT, G_TYPE_STRING, G_TYPE_STRING);
    process_view = gtk_tree_view_new_with_model(GTK_TREE_MODEL(model)); g_object_unref(model);
    const char *names[] = {"PID", "Uygulama / süreç", "RSS"};
    for (int i = 0; i < 3; i++) {
        GtkCellRenderer *renderer = gtk_cell_renderer_text_new();
        g_object_set(renderer, "ellipsize", PANGO_ELLIPSIZE_END, NULL);
        GtkTreeViewColumn *column = gtk_tree_view_column_new_with_attributes(names[i], renderer, "text", i, NULL);
        gtk_tree_view_column_set_sizing(column, GTK_TREE_VIEW_COLUMN_FIXED);
        gtk_tree_view_column_set_fixed_width(column, i == 0 ? 60 : i == 1 ? 126 : 84);
        if (i == 1) gtk_tree_view_column_set_expand(column, TRUE);
        gtk_tree_view_append_column(GTK_TREE_VIEW(process_view), column);
    }
    GtkWidget *scroll = gtk_scrolled_window_new(NULL, NULL);
    gtk_scrolled_window_set_min_content_height(GTK_SCROLLED_WINDOW(scroll), 280);
    gtk_container_add(GTK_CONTAINER(scroll), process_view);
    gtk_box_pack_start(GTK_BOX(box), scroll, TRUE, TRUE, 0);
    return box;
}

#ifdef OGUZDOWS_MONITOR_TEST
static gboolean smoke_finish(gpointer data) {
    (void)data;
    g_assert_cmpuint(samples, >=, 2);
    g_assert_cmpuint(count, <=, HISTORY);
    g_assert_true(history[(head + HISTORY - 1) % HISTORY].memory_valid);
    gtk_stack_set_visible_child_name(GTK_STACK(pages), "processes");
    g_assert_cmpuint(timer, ==, 0); g_assert_false(have_previous);
    refresh_processes(NULL, NULL);
    gtk_stack_set_visible_child_name(GTK_STACK(pages), "overview");
    g_assert_cmpuint(timer, >, 0);
    paused = TRUE; scheduling(); g_assert_cmpuint(timer, ==, 0);
    paused = FALSE; minimized = TRUE; scheduling(); g_assert_cmpuint(timer, ==, 0);
    minimized = FALSE; obscured = TRUE; scheduling(); g_assert_cmpuint(timer, ==, 0);
    obscured = FALSE; scheduling();
    gint width, height; gtk_window_get_size(GTK_WINDOW(window), &width, &height);
    gchar *result = g_strdup_printf("{\"schema\":1,\"native\":true,\"samples\":%u,\"history_limit\":90,\"hidden_sampling_stops\":true,\"source\":\"/proc\",\"window_width\":%d,\"window_height\":%d,\"physical_device_verified\":false}\n", samples, width, height);
    gchar *path = g_build_filename(smoke_directory, "monitor.json", NULL);
    g_file_set_contents(path, result, -1, NULL); g_free(path); g_free(result);
    GdkWindow *surface = gtk_widget_get_window(window);
    GdkPixbuf *capture = gdk_pixbuf_get_from_window(surface, 0, 0, gdk_window_get_width(surface), gdk_window_get_height(surface));
    if (capture) { path = g_build_filename(smoke_directory, "monitor.png", NULL); gdk_pixbuf_save(capture, path, "png", NULL, NULL); g_free(path); g_object_unref(capture); }
    gtk_widget_destroy(window); return G_SOURCE_REMOVE;
}
#endif

static void activate(GtkApplication *application, gpointer data) {
    (void)data;
    if (window) { gtk_window_present(GTK_WINDOW(window)); return; }
    OgSnapshot initial; og_metrics_read(&initial, "/proc");
    interval = initial.memory_valid && initial.memory_total <= UINT64_C(2147483648) ? 2 : 1;
#ifdef OGUZDOWS_MONITOR_TEST
    if (smoke_directory) interval = 1;
#endif
    window = gtk_application_window_new(application);
    gtk_window_set_title(GTK_WINDOW(window), "OğuzDows · Sistem İzleyici");
    GdkScreen *screen = gtk_widget_get_screen(window);
    GdkMonitor *monitor = gdk_display_get_primary_monitor(gdk_screen_get_display(screen));
    GdkRectangle work = {0, 0, 1024, 768};
    if (monitor) gdk_monitor_get_workarea(monitor, &work);
    gtk_window_set_default_size(GTK_WINDOW(window), MIN(940, work.width - 20), MIN(590, work.height - 24));
    gtk_window_set_icon_name(GTK_WINDOW(window), "oguzdows-monitor");
    og_ui_setup(window);
    GtkWidget *header = gtk_header_bar_new(); gtk_header_bar_set_show_close_button(GTK_HEADER_BAR(header), TRUE);
    gtk_header_bar_set_title(GTK_HEADER_BAR(header), work.width < 600 ? "İzleyici" : "Sistem İzleyici");
    if (work.width >= 600) gtk_header_bar_set_subtitle(GTK_HEADER_BAR(header), "OĞUZDOWS · CANLI PERFORMANS");
    GtkWidget *pause = work.width < 600 ? gtk_toggle_button_new() : gtk_toggle_button_new_with_label("Duraklat");
    if (work.width < 600) gtk_button_set_image(GTK_BUTTON(pause), gtk_image_new_from_icon_name("media-playback-pause-symbolic", GTK_ICON_SIZE_BUTTON));
    gtk_widget_set_tooltip_text(pause, "Canlı ölçümü duraklat / sürdür");
    gtk_header_bar_pack_end(GTK_HEADER_BAR(header), pause); g_signal_connect(pause, "toggled", G_CALLBACK(pause_clicked), NULL);
    gtk_window_set_titlebar(GTK_WINDOW(window), header);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 16); gtk_container_set_border_width(GTK_CONTAINER(box), 18);
    gtk_container_add(GTK_CONTAINER(window), box);
    pages = gtk_stack_new(); og_ui_stack_setup(pages);
    gtk_stack_set_hhomogeneous(GTK_STACK(pages), FALSE);
    GtkWidget *switcher;
    if (work.width < 600) {
        switcher = gtk_combo_box_text_new();
        gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(switcher), "overview", "Performans");
        gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(switcher), "processes", "Süreçler");
        gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(switcher), "system", "Sistem");
        gtk_combo_box_set_active_id(GTK_COMBO_BOX(switcher), "overview");
        g_signal_connect(switcher, "changed", G_CALLBACK(select_page), NULL);
    } else {
        switcher = gtk_stack_switcher_new(); gtk_stack_switcher_set_stack(GTK_STACK_SWITCHER(switcher), GTK_STACK(pages));
    }
    gtk_box_pack_start(GTK_BOX(box), switcher, FALSE, FALSE, 0);
    GtkWidget *overview = gtk_box_new(GTK_ORIENTATION_VERTICAL, 14);
    GtkWidget *flow = gtk_flow_box_new(); gtk_flow_box_set_selection_mode(GTK_FLOW_BOX(flow), GTK_SELECTION_NONE);
    gtk_flow_box_set_min_children_per_line(GTK_FLOW_BOX(flow), 1); gtk_flow_box_set_max_children_per_line(GTK_FLOW_BOX(flow), 3);
    gtk_flow_box_set_homogeneous(GTK_FLOW_BOX(flow), TRUE); gtk_flow_box_set_column_spacing(GTK_FLOW_BOX(flow), 12); gtk_flow_box_set_row_spacing(GTK_FLOW_BOX(flow), 12);
    const char *names[] = {"İşlemci", "Bellek", "Ağ"};
    const char *icons[] = {"oguzdows-cpu-symbolic", "oguzdows-memory-symbolic", "oguzdows-network-symbolic"};
    for (unsigned i = 0; i < 3; i++) gtk_container_add(GTK_CONTAINER(flow), card(i, names[i], icons[i]));
    gtk_box_pack_start(GTK_BOX(overview), flow, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(overview), text("CPU: çekirdeklerin toplam meşgul oranı. RAM: MemTotal − MemAvailable. Ağ: lo hariç arayüz farkları; köprü / VPN kullanılıyorsa aynı trafik birden fazla arayüzde sayılabilir. Kesik çizgi gönderimdir. Eksik ölçümler sıfır gibi çizilmez.", "subtitle"), FALSE, FALSE, 0);
    GtkWidget *scroll = gtk_scrolled_window_new(NULL, NULL); gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll), GTK_POLICY_NEVER, GTK_POLICY_AUTOMATIC);
    gtk_container_add(GTK_CONTAINER(scroll), overview); gtk_stack_add_titled(GTK_STACK(pages), scroll, "overview", "Performans");
    gtk_stack_add_titled(GTK_STACK(pages), processes(), "processes", "Süreçler");
    struct utsname system; gchar *info;
    if (!uname(&system)) info = g_strdup_printf("OğuzDows\n\nÇekirdek: %s %s\nMimari: %s\nMantıksal işlemci: %ld\n\nSalt okunur yerel ölçüm. Ağ isteği, telemetri, Python izleme servisi veya sürekli arka plan grafiği yok. Görünürlük bildirimi vermeyen Wayland kabuklarında tam örtülme algılanamayabilir; küçültme, sayfa değiştirme ve Duraklat desteklenir.", system.sysname, system.release, system.machine, sysconf(_SC_NPROCESSORS_ONLN));
    else info = g_strdup("Sistem kimliği okunamadı.");
    gtk_stack_add_titled(GTK_STACK(pages), text(info, NULL), "system", "Sistem"); g_free(info);
    gtk_box_pack_start(GTK_BOX(box), pages, TRUE, TRUE, 0);
    status_label = text("Canlı ölçüm hazırlanıyor", "subtitle"); gtk_box_pack_end(GTK_BOX(box), status_label, FALSE, FALSE, 0);
    gtk_widget_add_events(window, GDK_VISIBILITY_NOTIFY_MASK);
    g_signal_connect(window, "map", G_CALLBACK(mapped), NULL); g_signal_connect(window, "unmap", G_CALLBACK(mapped), NULL);
    g_signal_connect(window, "window-state-event", G_CALLBACK(window_state), NULL); g_signal_connect(window, "visibility-notify-event", G_CALLBACK(visibility), NULL);
    g_signal_connect(window, "destroy", G_CALLBACK(destroy), NULL); g_signal_connect(window, "destroy", G_CALLBACK(gtk_widget_destroyed), &window);
    g_signal_connect(pages, "notify::visible-child", G_CALLBACK(page_changed), NULL);
    gtk_widget_show_all(window);
#ifdef OGUZDOWS_MONITOR_TEST
    if (smoke_directory) g_timeout_add(3200, smoke_finish, NULL);
#endif
}

int main(int argc, char **argv) {
    if (argc == 2 && !strcmp(argv[1], "--version")) { puts("OğuzDows Sistem İzleyici · native 1"); return 0; }
#ifdef OGUZDOWS_MONITOR_TEST
    if (argc == 3 && !strcmp(argv[1], "--smoke-test")) {
        smoke_directory = argv[2]; g_mkdir_with_parents(smoke_directory, 0700); argc = 1;
    }
#endif
    if (argc != 1) { fputs("Kullanım: oguzdows-monitor [--version]\n", stderr); return 2; }
    GtkApplication *application = gtk_application_new("org.oguzdows.Monitor", G_APPLICATION_DEFAULT_FLAGS);
    g_signal_connect(application, "activate", G_CALLBACK(activate), NULL);
    int result = g_application_run(G_APPLICATION(application), argc, argv);
    g_object_unref(application); return result;
}
