/* OğuzDows Haber — native GTK3, plain RSS text; no webview or resident worker. */
#define _POSIX_C_SOURCE 200809L
#define G_LOG_DOMAIN "OguzDows-Haber"
#include <gtk/gtk.h>
#include <json-glib/json-glib.h>
#include <glib/gstdio.h>
#include <locale.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#ifndef NEWS_SERVICE
#define NEWS_SERVICE "/usr/lib/oguzdows/news_service.py"
#endif

typedef struct { gchar *title, *body, *link, *published; } Article;
static GtkApplication *application;
static GtkWidget *window, *pages, *headlines, *sources, *refresh_button, *add_button, *remove_button;
static GtkWidget *status_label, *cancel_button, *spinner, *article_title, *article_meta, *article_text;
static GtkWidget *open_button, *back_button, *font_label, *empty_note;
static GtkTextTag *reader_tag;
static GPtrArray *articles;
static GSubprocess *worker;
static guint deadline_id;
static gboolean filling, closing, busy;
static gchar *source_name, *selected_source;
static Article *current;
static gint points = 16;
#ifdef OGUZDOWS_NEWS_TEST
static const gchar *smoke_directory;
static guint smoke_step, smoke_wait;
#endif

static void run_service(const gchar *first, const gchar *second, const gchar *third);

static const gchar *text_member(JsonObject *object, const gchar *key) {
    JsonNode *node = json_object_get_member(object, key);
    return node && JSON_NODE_HOLDS_VALUE(node) && json_node_get_value_type(node) == G_TYPE_STRING ? json_node_get_string(node) : "";
}

static JsonArray *array_member(JsonObject *object, const gchar *key) {
    JsonNode *node = json_object_get_member(object, key);
    return node && JSON_NODE_HOLDS_ARRAY(node) ? json_node_get_array(node) : NULL;
}

static GtkWidget *label(const gchar *text, const gchar *css) {
    GtkWidget *widget = gtk_label_new(text);
    gtk_label_set_xalign(GTK_LABEL(widget), 0);
    gtk_label_set_line_wrap(GTK_LABEL(widget), TRUE);
    gtk_label_set_line_wrap_mode(GTK_LABEL(widget), PANGO_WRAP_WORD_CHAR);
    if (css) gtk_style_context_add_class(gtk_widget_get_style_context(widget), css);
    return widget;
}

static GtkWidget *icon_button(const gchar *icon, const gchar *tip, GCallback callback) {
    GtkWidget *button = gtk_button_new_from_icon_name(icon, GTK_ICON_SIZE_BUTTON);
    gtk_widget_set_tooltip_text(button, tip);
    atk_object_set_name(gtk_widget_get_accessible(button), tip);
    if (callback) g_signal_connect(button, "clicked", callback, NULL);
    return button;
}

static void status(const gchar *text) { gtk_label_set_text(GTK_LABEL(status_label), text); }

static gchar *preference_path(void) {
    return g_build_filename(g_get_user_config_dir(), "oguzdows", "news", "reader.ini", NULL);
}

static void font_size(gint change) {
    points = CLAMP(points + change, 12, 26);
    g_object_set(reader_tag, "size-points", (gdouble)points, NULL);
    gchar *value = g_strdup_printf("%d", points);
    gtk_label_set_text(GTK_LABEL(font_label), value);
    g_free(value);
    if (!change) return;
    gchar *path = preference_path(), *parent = g_path_get_dirname(path);
    if (!g_file_test(path, G_FILE_TEST_IS_SYMLINK) && !g_file_test(parent, G_FILE_TEST_IS_SYMLINK) && g_mkdir_with_parents(parent, 0700) == 0) {
        gchar *contents = g_strdup_printf("[Reader]\nsize=%d\n", points);
        GError *error = NULL;
        if (!g_file_set_contents_full(path, contents, -1, G_FILE_SET_CONTENTS_CONSISTENT, 0600, &error)) {
            status("Yazı boyutu bu oturumda değişti; tercih dosyaya kaydedilemedi.");
            g_clear_error(&error);
        }
        g_free(contents);
    }
    g_free(path); g_free(parent);
}

static void smaller(GtkButton *button, gpointer data) { (void)button; (void)data; font_size(-1); }
static void larger(GtkButton *button, gpointer data) { (void)button; (void)data; font_size(1); }

static void article_free(gpointer data) {
    Article *article = data;
    g_free(article->title); g_free(article->body); g_free(article->link); g_free(article->published); g_free(article);
}

static void show_list(GtkButton *button, gpointer data) {
    (void)button; (void)data;
    gtk_stack_set_visible_child_name(GTK_STACK(pages), "headlines");
    gtk_widget_set_sensitive(back_button, FALSE);
}

static void select_article(GtkListBox *box, GtkListBoxRow *row, gpointer data) {
    (void)box; (void)data;
    if (!row) return;
    current = g_object_get_data(G_OBJECT(row), "article");
    if (!current) return;
    gtk_label_set_text(GTK_LABEL(article_title), current->title);
    gchar *meta = g_strdup_printf("%s\n%s", source_name ? source_name : "", *current->published ? current->published : "Yayıncı tarih belirtmedi");
    gtk_label_set_text(GTK_LABEL(article_meta), meta); g_free(meta);
    GtkTextBuffer *buffer = gtk_text_view_get_buffer(GTK_TEXT_VIEW(article_text));
    gtk_text_buffer_set_text(buffer, current->body, -1);
    GtkTextIter start, end;
    gtk_text_buffer_get_bounds(buffer, &start, &end);
    gtk_text_buffer_apply_tag(buffer, reader_tag, &start, &end);
    gtk_widget_set_sensitive(open_button, *current->link != '\0');
    gtk_widget_set_sensitive(back_button, TRUE);
    gtk_stack_set_visible_child_name(GTK_STACK(pages), "reader");
}

static void open_source(GtkButton *button, gpointer data) {
    (void)button; (void)data;
    if (!current || !*current->link || strlen(current->link) > 2048) return;
    GError *error = NULL;
    GUri *uri = g_uri_parse(current->link, G_URI_FLAGS_NONE, &error);
    if (!uri || !g_uri_get_host(uri) || g_uri_get_userinfo(uri) ||
        (g_strcmp0(g_uri_get_scheme(uri), "https") && g_strcmp0(g_uri_get_scheme(uri), "http"))) {
        status("Geçersiz web bağlantısı açılmadı."); g_clear_error(&error); if (uri) g_uri_unref(uri); return;
    }
    g_uri_unref(uri);
    /* Gio resolves the user's browser; never execute a feed's shell/Exec text. */
    if (!g_app_info_launch_default_for_uri(current->link, NULL, &error)) {
        status(error ? error->message : "Tarayıcı açılamadı."); g_clear_error(&error);
    }
}

static void narrate(GtkButton *button, gpointer data) {
    (void)button; (void)data;
    const gchar *argv[] = {"/usr/local/bin/oguzdows-narrate", "news", NULL};
    GError *error = NULL;
    GSubprocess *process = g_subprocess_newv(argv, G_SUBPROCESS_FLAGS_NONE, &error);
    if (!process) { status(error ? error->message : "Rehber sesi açılamadı."); g_clear_error(&error); }
    else g_object_unref(process);
}

static void set_busy(gboolean value) {
    busy = value;
    gtk_widget_set_sensitive(sources, !value);
    gtk_widget_set_sensitive(refresh_button, !value);
    gtk_widget_set_sensitive(add_button, !value);
    gtk_widget_set_sensitive(remove_button, !value);
    gtk_widget_set_sensitive(cancel_button, value);
    if (value) gtk_spinner_start(GTK_SPINNER(spinner)); else gtk_spinner_stop(GTK_SPINNER(spinner));
}

static void cancel(GtkButton *button, gpointer data) {
    (void)button; (void)data;
    if (worker) g_subprocess_force_exit(worker);
    status("Haber isteği durduruldu; eski önbellek korunur.");
}

static gboolean timed_out(gpointer data) {
    (void)data;
    deadline_id = 0;
    if (worker) g_subprocess_force_exit(worker);
    return G_SOURCE_REMOVE;
}

static gboolean on_close(GtkWidget *widget, GdkEvent *event, gpointer data) {
    (void)widget; (void)event; (void)data;
    closing = TRUE;
    if (worker) g_subprocess_force_exit(worker);
    return FALSE;
}

static void source_changed(GtkComboBox *box, gpointer data) {
    (void)data;
    if (!filling && !busy) run_service("cached", gtk_combo_box_get_active_id(box), NULL);
}

static gboolean load_feed(JsonObject *root) {
    JsonArray *feed_sources = array_member(root, "sources"), *items = array_member(root, "items");
    if (!feed_sources || !items || json_array_get_length(feed_sources) > 16 || json_array_get_length(items) > 60) return FALSE;
    filling = TRUE;
    gtk_combo_box_text_remove_all(GTK_COMBO_BOX_TEXT(sources));
    for (guint i = 0; i < json_array_get_length(feed_sources); i++) {
        JsonNode *node = json_array_get_element(feed_sources, i);
        if (!JSON_NODE_HOLDS_OBJECT(node)) { filling = FALSE; return FALSE; }
        JsonObject *item = json_node_get_object(node);
        gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(sources), text_member(item, "id"), text_member(item, "name"));
    }
    g_free(selected_source); selected_source = g_strdup(text_member(root, "selected"));
    g_free(source_name); source_name = g_strdup(text_member(root, "source"));
    gtk_combo_box_set_active_id(GTK_COMBO_BOX(sources), selected_source);
    filling = FALSE;
    current = NULL;
    GList *children = gtk_container_get_children(GTK_CONTAINER(headlines));
    for (GList *it = children; it; it = it->next) gtk_widget_destroy(it->data);
    g_list_free(children); g_ptr_array_set_size(articles, 0);
    for (guint i = 0; i < json_array_get_length(items); i++) {
        JsonNode *node = json_array_get_element(items, i);
        if (!JSON_NODE_HOLDS_OBJECT(node)) return FALSE;
        JsonObject *item = json_node_get_object(node);
        Article *article = g_new0(Article, 1);
        article->title = g_strdup(text_member(item, "title")); article->body = g_strdup(text_member(item, "body"));
        article->link = g_strdup(text_member(item, "url")); article->published = g_strdup(text_member(item, "published"));
        if (g_utf8_strlen(article->body, -1) > 8192 || g_utf8_strlen(article->title, -1) > 240) { article_free(article); return FALSE; }
        g_ptr_array_add(articles, article);
        GtkWidget *row = gtk_list_box_row_new(), *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 6);
        gtk_style_context_add_class(gtk_widget_get_style_context(row), "news-item");
        GtkWidget *title = label(article->title, "news-headline");
        gtk_label_set_max_width_chars(GTK_LABEL(title), 66);
        gtk_box_pack_start(GTK_BOX(box), title, FALSE, FALSE, 0);
        GtkWidget *date = label(*article->published ? article->published : source_name, "dim-label");
        gtk_label_set_max_width_chars(GTK_LABEL(date), 50);
        gtk_box_pack_start(GTK_BOX(box), date, FALSE, FALSE, 0);
        gchar *excerpt = g_utf8_substring(article->body, 0, MIN((glong)110, g_utf8_strlen(article->body, -1)));
        GtkWidget *summary = label(excerpt, NULL); g_free(excerpt);
        gtk_label_set_max_width_chars(GTK_LABEL(summary), 66);
        gtk_label_set_lines(GTK_LABEL(summary), 2); gtk_label_set_ellipsize(GTK_LABEL(summary), PANGO_ELLIPSIZE_END);
        gtk_box_pack_start(GTK_BOX(box), summary, FALSE, FALSE, 0);
        gtk_container_add(GTK_CONTAINER(row), box); g_object_set_data(G_OBJECT(row), "article", article);
        gtk_container_add(GTK_CONTAINER(headlines), row);
    }
    gtk_widget_show_all(headlines);
    gtk_widget_set_visible(empty_note, articles->len == 0);
    gtk_widget_set_sensitive(open_button, FALSE);
    show_list(NULL, NULL);
    gchar *info = g_strdup_printf("%u haber · %s%s · Yalnızca RSS metni / özeti; tam makale garantisi yok.", articles->len,
        *text_member(root, "cached_at") ? "Önbellek: " : "Henüz indirilmedi", text_member(root, "cached_at"));
    status(info); g_free(info);
    /* Opt-in GLib diagnostics: counts only, never article text / URLs. */
    g_debug("cached-view-ready: %u items", articles->len);
    return TRUE;
}

static void service_done(GObject *object, GAsyncResult *result, gpointer data) {
    (void)data;
    gchar *output = NULL, *errors = NULL;
    GError *error = NULL;
    gboolean ok = g_subprocess_communicate_utf8_finish(G_SUBPROCESS(object), result, &output, &errors, &error);
    if (deadline_id) { g_source_remove(deadline_id); deadline_id = 0; }
    g_clear_object(&worker);
    if (!closing) {
        set_busy(FALSE);
        JsonParser *parser = json_parser_new();
        if (ok && output && strlen(output) <= 2 * 1024 * 1024 && json_parser_load_from_data(parser, output, -1, &error) && JSON_NODE_HOLDS_OBJECT(json_parser_get_root(parser))) {
            JsonObject *root = json_node_get_object(json_parser_get_root(parser));
            if (*text_member(root, "error")) status(text_member(root, "error"));
            else if (!load_feed(root)) status("Haber işçisinin yanıtı okunamadı; ağ isteği tekrarlanmadı.");
        } else status(error ? error->message : "İstek durdu / süre sınırı doldu. Eski önbellek korunur; yeniden denemek senin elinde.");
        g_object_unref(parser);
    }
    g_clear_error(&error); g_free(output); g_free(errors);
    g_application_release(G_APPLICATION(application));
}

static void run_service(const gchar *first, const gchar *second, const gchar *third) {
    if (busy || closing) return;
    const gchar *argv[] = {"/usr/bin/python3", "-I", NEWS_SERVICE, first, second, third, NULL};
    GError *error = NULL;
    worker = g_subprocess_newv(argv, G_SUBPROCESS_FLAGS_STDOUT_PIPE | G_SUBPROCESS_FLAGS_STDERR_PIPE, &error);
    if (!worker) { status(error ? error->message : "Haber işçisi açılamadı."); g_clear_error(&error); return; }
    set_busy(TRUE);
    status(!strcmp(first, "refresh") ? "Yalnızca seçili RSS kaynağı alınıyor… Eski metin bu sırada okunabilir." : "Yerel kaynak / önbellek okunuyor; ağ isteği yok…");
    deadline_id = g_timeout_add_seconds(24, timed_out, NULL);
    g_application_hold(G_APPLICATION(application));
    g_subprocess_communicate_utf8_async(worker, NULL, NULL, service_done, NULL);
}

static void refresh(GtkButton *button, gpointer data) { (void)button; (void)data; if (selected_source) run_service("refresh", selected_source, NULL); }

static void add_source(GtkButton *button, gpointer data) {
    (void)button; (void)data;
    GtkWidget *dialog = gtk_dialog_new_with_buttons("Kendi RSS / Atom kaynağın", GTK_WINDOW(window), GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        "Vazgeç", GTK_RESPONSE_CANCEL, "Ekle", GTK_RESPONSE_OK, NULL);
    gtk_dialog_set_default_response(GTK_DIALOG(dialog), GTK_RESPONSE_CANCEL);
    GtkWidget *box = gtk_dialog_get_content_area(GTK_DIALOG(dialog));
    gtk_container_set_border_width(GTK_CONTAINER(box), 16); gtk_box_set_spacing(GTK_BOX(box), 10);
    GtkWidget *name = gtk_entry_new(), *address = gtk_entry_new();
    gtk_entry_set_max_length(GTK_ENTRY(name), 80); gtk_entry_set_max_length(GTK_ENTRY(address), 2048);
    gtk_entry_set_placeholder_text(GTK_ENTRY(name), "Kaynağın adı"); gtk_entry_set_placeholder_text(GTK_ENTRY(address), "https://…/rss.xml");
    GtkWidget *note = label("Kaynak eklemek indirme başlatmaz. HTTPS RSS / Atom adresi gerekir. Yenile düğmesiyle yalnızca seçili kaynağa bağlanılır.", NULL);
    gtk_label_set_max_width_chars(GTK_LABEL(note), 28);
    atk_object_set_name(gtk_widget_get_accessible(name), "Kaynağın adı");
    atk_object_set_name(gtk_widget_get_accessible(address), "HTTPS RSS / Atom adresi");
    gtk_box_pack_start(GTK_BOX(box), note, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(box), name, FALSE, FALSE, 0); gtk_box_pack_start(GTK_BOX(box), address, FALSE, FALSE, 0);
    gtk_widget_show_all(dialog);
    if (gtk_dialog_run(GTK_DIALOG(dialog)) == GTK_RESPONSE_OK) run_service("add", gtk_entry_get_text(GTK_ENTRY(address)), gtk_entry_get_text(GTK_ENTRY(name)));
    gtk_widget_destroy(dialog);
}

static void remove_source(GtkButton *button, gpointer data) {
    (void)button; (void)data;
    if (!selected_source) return;
    GtkWidget *dialog = gtk_message_dialog_new(GTK_WINDOW(window), GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        GTK_MESSAGE_QUESTION, GTK_BUTTONS_OK_CANCEL, "Kişisel RSS kaynağı kaldırılsın mı?");
    gtk_message_dialog_format_secondary_text(GTK_MESSAGE_DIALOG(dialog), "Yalnızca seçili kişisel kaynak ve kendi haber önbelleği kaldırılır. Yerleşik kaynaklar korunur.");
    gtk_dialog_set_default_response(GTK_DIALOG(dialog), GTK_RESPONSE_CANCEL);
    if (gtk_dialog_run(GTK_DIALOG(dialog)) == GTK_RESPONSE_OK) run_service("remove", selected_source, NULL);
    gtk_widget_destroy(dialog);
}

static void activate(GtkApplication *app, gpointer data) {
    (void)data;
    if (window) { gtk_window_present(GTK_WINDOW(window)); return; }
    articles = g_ptr_array_new_with_free_func(article_free);
    gchar *path = preference_path(); GStatBuf st;
    if (!g_lstat(path, &st) && S_ISREG(st.st_mode) && st.st_size <= 4096 && st.st_uid == getuid()) {
        GKeyFile *prefs = g_key_file_new();
        if (g_key_file_load_from_file(prefs, path, G_KEY_FILE_NONE, NULL)) {
            gint saved = g_key_file_get_integer(prefs, "Reader", "size", NULL);
            if (saved >= 12 && saved <= 26) points = saved;
        }
        g_key_file_unref(prefs);
    }
    g_free(path);
    window = gtk_application_window_new(app);
    gtk_window_set_title(GTK_WINDOW(window), "OğuzDows Haber");
    gtk_window_set_icon_name(GTK_WINDOW(window), "oguzdows-news");
    GdkDisplay *display = gtk_widget_get_display(window);
    GdkMonitor *monitor = gdk_display_get_primary_monitor(display);
    if (!monitor) monitor = gdk_display_get_monitor(display, 0);
    GdkRectangle area = {0, 0, 1024, 768}; if (monitor) gdk_monitor_get_workarea(monitor, &area);
    gtk_window_set_default_size(GTK_WINDOW(window), MIN(880, area.width - 24), MIN(660, area.height - 48));
    gtk_widget_set_size_request(window, 296, 300);
    g_signal_connect(window, "delete-event", G_CALLBACK(on_close), NULL);
    GtkCssProvider *css = gtk_css_provider_new();
    gtk_css_provider_load_from_data(css,
        ".news-item { padding: 14px 16px; margin: 3px 8px; border-radius: 12px; }"
        ".news-headline { font-size: 16px; font-weight: 600; }"
        ".reader-title { font-size: 22px; font-weight: 700; }"
        ".news-status { font-size: 11px; }", -1, NULL);
    gtk_style_context_add_provider_for_screen(gtk_widget_get_screen(window), GTK_STYLE_PROVIDER(css), GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    g_object_unref(css);
    GtkWidget *header = gtk_header_bar_new(); gtk_header_bar_set_show_close_button(GTK_HEADER_BAR(header), TRUE);
    gtk_header_bar_set_title(GTK_HEADER_BAR(header), "Haber");
    gtk_header_bar_pack_start(GTK_HEADER_BAR(header), gtk_image_new_from_icon_name("oguzdows-news", GTK_ICON_SIZE_LARGE_TOOLBAR));
    gtk_header_bar_pack_end(GTK_HEADER_BAR(header), icon_button("audio-speakers-symbolic", "Haber okuyucusu rehberini dinle / durdur", G_CALLBACK(narrate)));
    gtk_window_set_titlebar(GTK_WINDOW(window), header);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8); gtk_container_add(GTK_CONTAINER(window), box);
    GtkWidget *toolbar = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 6); gtk_container_set_border_width(GTK_CONTAINER(toolbar), 8);
    sources = gtk_combo_box_text_new(); gtk_widget_set_hexpand(sources, TRUE);
    GList *cells = gtk_cell_layout_get_cells(GTK_CELL_LAYOUT(sources));
    for (GList *it = cells; it; it = it->next)
        g_object_set(it->data, "ellipsize", PANGO_ELLIPSIZE_END, "width-chars", 8, "max-width-chars", 24, NULL);
    g_list_free(cells);
    atk_object_set_name(gtk_widget_get_accessible(sources), "RSS kaynağı");
    g_signal_connect(sources, "changed", G_CALLBACK(source_changed), NULL);
    gtk_box_pack_start(GTK_BOX(toolbar), sources, TRUE, TRUE, 0);
    refresh_button = icon_button("view-refresh-symbolic", "Seçili kaynağı yenile · isteğe bağlı ağ", G_CALLBACK(refresh));
    add_button = icon_button("list-add-symbolic", "Kendi RSS kaynağını ekle", G_CALLBACK(add_source));
    remove_button = icon_button("list-remove-symbolic", "Kişisel RSS kaynağını kaldır", G_CALLBACK(remove_source));
    cancel_button = icon_button("process-stop-symbolic", "Haber isteğini durdur", G_CALLBACK(cancel));
    gtk_box_pack_start(GTK_BOX(toolbar), refresh_button, FALSE, FALSE, 0); gtk_box_pack_start(GTK_BOX(toolbar), add_button, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(toolbar), remove_button, FALSE, FALSE, 0); gtk_box_pack_start(GTK_BOX(toolbar), cancel_button, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(box), toolbar, FALSE, FALSE, 0);
    pages = gtk_stack_new(); gtk_stack_set_transition_type(GTK_STACK(pages), GTK_STACK_TRANSITION_TYPE_NONE);
    gtk_box_pack_start(GTK_BOX(box), pages, TRUE, TRUE, 0);
    GtkWidget *list_page = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
    empty_note = label("Henüz haber yok. Kaynağını seçip Yenile düğmesine bas. İndirilen RSS metinleri çevrimdışı da okunur. Arka planda otomatik yenileme yapılmaz.", "dim-label");
    gtk_label_set_max_width_chars(GTK_LABEL(empty_note), 44);
    gtk_widget_set_margin_start(empty_note, 16); gtk_widget_set_margin_end(empty_note, 16);
    gtk_widget_set_margin_top(empty_note, 16); gtk_widget_set_margin_bottom(empty_note, 16);
    gtk_box_pack_start(GTK_BOX(list_page), empty_note, FALSE, FALSE, 0);
    GtkWidget *scroll = gtk_scrolled_window_new(NULL, NULL); gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll), GTK_POLICY_NEVER, GTK_POLICY_AUTOMATIC);
    headlines = gtk_list_box_new(); gtk_list_box_set_selection_mode(GTK_LIST_BOX(headlines), GTK_SELECTION_SINGLE);
    g_signal_connect(headlines, "row-activated", G_CALLBACK(select_article), NULL);
    gtk_container_add(GTK_CONTAINER(scroll), headlines); gtk_box_pack_start(GTK_BOX(list_page), scroll, TRUE, TRUE, 0);
    gtk_stack_add_named(GTK_STACK(pages), list_page, "headlines");
    GtkWidget *reader = gtk_box_new(GTK_ORIENTATION_VERTICAL, 10); gtk_container_set_border_width(GTK_CONTAINER(reader), 16);
    article_title = label("", "reader-title"); gtk_label_set_max_width_chars(GTK_LABEL(article_title), 48);
    article_meta = label("", "dim-label"); gtk_label_set_max_width_chars(GTK_LABEL(article_meta), 48);
    gtk_box_pack_start(GTK_BOX(reader), article_title, FALSE, FALSE, 0); gtk_box_pack_start(GTK_BOX(reader), article_meta, FALSE, FALSE, 0);
    scroll = gtk_scrolled_window_new(NULL, NULL); gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll), GTK_POLICY_NEVER, GTK_POLICY_AUTOMATIC);
    article_text = gtk_text_view_new(); gtk_text_view_set_editable(GTK_TEXT_VIEW(article_text), FALSE); gtk_text_view_set_cursor_visible(GTK_TEXT_VIEW(article_text), FALSE);
    gtk_text_view_set_wrap_mode(GTK_TEXT_VIEW(article_text), GTK_WRAP_WORD_CHAR); gtk_text_view_set_left_margin(GTK_TEXT_VIEW(article_text), 8); gtk_text_view_set_right_margin(GTK_TEXT_VIEW(article_text), 8);
    gtk_text_view_set_pixels_above_lines(GTK_TEXT_VIEW(article_text), 6); gtk_text_view_set_pixels_below_lines(GTK_TEXT_VIEW(article_text), 6);
    reader_tag = gtk_text_buffer_create_tag(gtk_text_view_get_buffer(GTK_TEXT_VIEW(article_text)), "reader", "family", "sans-serif", NULL);
    gtk_container_add(GTK_CONTAINER(scroll), article_text); gtk_box_pack_start(GTK_BOX(reader), scroll, TRUE, TRUE, 0);
    GtkWidget *note = label("Yayıncının RSS metni / özeti · Tamamı akışta yoksa kaynak sitesini açabilirsin.", "dim-label");
    gtk_label_set_max_width_chars(GTK_LABEL(note), 48);
    gtk_box_pack_start(GTK_BOX(reader), note, FALSE, FALSE, 0);
    gtk_stack_add_named(GTK_STACK(pages), reader, "reader");
    GtkWidget *controls = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 6); gtk_container_set_border_width(GTK_CONTAINER(controls), 8);
    back_button = gtk_button_new_with_label("Liste"); g_signal_connect(back_button, "clicked", G_CALLBACK(show_list), NULL);
    gtk_box_pack_start(GTK_BOX(controls), back_button, FALSE, FALSE, 0);
    GtkWidget *minus = gtk_button_new_with_label("A−"), *plus = gtk_button_new_with_label("A+");
    g_signal_connect(minus, "clicked", G_CALLBACK(smaller), NULL); g_signal_connect(plus, "clicked", G_CALLBACK(larger), NULL);
    gtk_widget_set_tooltip_text(minus, "Yazıyı küçült"); gtk_widget_set_tooltip_text(plus, "Yazıyı büyüt");
    gtk_box_pack_start(GTK_BOX(controls), minus, FALSE, FALSE, 0); font_label = gtk_label_new(""); gtk_box_pack_start(GTK_BOX(controls), font_label, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(controls), plus, FALSE, FALSE, 0);
    open_button = gtk_button_new_with_label("Kaynakta aç"); g_signal_connect(open_button, "clicked", G_CALLBACK(open_source), NULL);
    gtk_box_pack_end(GTK_BOX(controls), open_button, FALSE, FALSE, 0); gtk_box_pack_start(GTK_BOX(box), controls, FALSE, FALSE, 0);
    GtkWidget *bottom = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8); gtk_container_set_border_width(GTK_CONTAINER(bottom), 10);
    spinner = gtk_spinner_new(); gtk_box_pack_start(GTK_BOX(bottom), spinner, FALSE, FALSE, 0);
    status_label = label("Çevrimdışı önbellek açılıyor…", "news-status"); gtk_label_set_max_width_chars(GTK_LABEL(status_label), 70);
    gtk_box_pack_start(GTK_BOX(bottom), status_label, TRUE, TRUE, 0); gtk_box_pack_start(GTK_BOX(box), bottom, FALSE, FALSE, 0);
    gtk_widget_show_all(window); gtk_widget_hide(empty_note); set_busy(FALSE); font_size(0);
    gtk_widget_set_sensitive(back_button, FALSE); gtk_widget_set_sensitive(open_button, FALSE);
    run_service("list", NULL, NULL); /* Cold launch never asks the worker to fetch a URL. */
}

#ifdef OGUZDOWS_NEWS_TEST
static void screenshot(const gchar *name) {
    GdkWindow *surface = gtk_widget_get_window(window);
    GdkPixbuf *pixels = gdk_pixbuf_get_from_window(surface, 0, 0, gtk_widget_get_allocated_width(window), gtk_widget_get_allocated_height(window));
    g_assert_nonnull(pixels);
    gchar *path = g_build_filename(smoke_directory, name, NULL);
    g_assert_true(gdk_pixbuf_save(pixels, path, "png", NULL, NULL)); g_free(path); g_object_unref(pixels);
}

static gboolean smoke(gpointer data) {
    (void)data;
    if (++smoke_wait > 200) g_error("Haber GTK testi 20 saniyede bitmedi.");
    if (busy) return G_SOURCE_CONTINUE;
    GdkDisplay *display = gtk_widget_get_display(window);
    GdkMonitor *monitor = gdk_display_get_primary_monitor(display); GdkRectangle area;
    if (!monitor) monitor = gdk_display_get_monitor(display, 0);
    g_assert_nonnull(monitor); gdk_monitor_get_geometry(monitor, &area);
    g_assert_cmpint(gtk_widget_get_allocated_width(window), <=, area.width);
    if (smoke_step == 0) {
        g_assert_cmpuint(articles->len, ==, 2); g_assert_null(worker);
        screenshot("news-list.png");
        select_article(GTK_LIST_BOX(headlines), gtk_list_box_get_row_at_index(GTK_LIST_BOX(headlines), 0), NULL);
        larger(NULL, NULL); g_assert_cmpint(points, ==, 17);
        smoke_step = 1; return G_SOURCE_CONTINUE;
    }
    if (smoke_step == 1) {
        g_assert_nonnull(current); g_assert_nonnull(strstr(current->body, "TEST"));
        screenshot("news-reader.png"); refresh(NULL, NULL); smoke_step = 2; return G_SOURCE_CONTINUE;
    }
    g_assert_cmpuint(articles->len, ==, 2); /* Failure / cancellation never clears cached reading. */
    g_assert_null(worker); g_assert_cmpuint(deadline_id, ==, 0);
    if (smoke_step == 2) {
        g_assert_nonnull(strstr(gtk_label_get_text(GTK_LABEL(status_label)), "Test bağlantı hatası"));
        run_service("cached", "test", NULL); g_assert_nonnull(worker);
        cancel(NULL, NULL); smoke_step = 3; return G_SOURCE_CONTINUE;
    }
    if (smoke_step == 3) {
        run_service("cached", "test", NULL); g_assert_nonnull(worker);
        /* Same production timeout callback, shortened only in the test build. */
        g_source_remove(deadline_id); deadline_id = g_timeout_add(30, timed_out, NULL);
        smoke_step = 4; return G_SOURCE_CONTINUE;
    }
    g_assert_cmpuint(smoke_step, ==, 4);
    for (guint i = 0; i < 40; i++) smaller(NULL, NULL);
    g_assert_cmpint(points, ==, 12);
    for (guint i = 0; i < 40; i++) larger(NULL, NULL);
    g_assert_cmpint(points, ==, 26);
    gchar *path = g_build_filename(smoke_directory, "news-native.json", NULL);
    g_file_set_contents(path, "{\"native_gtk\":true,\"fixture_not_network\":true,\"cold_start_fetch\":false,\"offline_after_error\":true,\"font_limits\":true,\"worker_exited\":true,\"cancellation\":true,\"deadline_callback\":true,\"physical_device\":false}\n", -1, NULL);
    g_free(path); gtk_widget_destroy(window); g_application_quit(G_APPLICATION(application)); return G_SOURCE_REMOVE;
}
#endif

int main(int argc, char **argv) {
    setlocale(LC_ALL, "");
    if (argc == 2 && !strcmp(argv[1], "--version")) {
        g_print("OğuzDows Haber · GTK %u.%u.%u\n", gtk_get_major_version(), gtk_get_minor_version(), gtk_get_micro_version()); return 0;
    }
#ifdef OGUZDOWS_NEWS_TEST
    gchar *private_home = NULL;
    if (argc == 3 && !strcmp(argv[1], "--smoke-test")) {
        smoke_directory = argv[2]; g_mkdir_with_parents(smoke_directory, 0700);
        private_home = g_dir_make_tmp("oguzdows-news-test-XXXXXX", NULL); g_assert_nonnull(private_home);
        g_setenv("XDG_CONFIG_HOME", private_home, TRUE);
        argc = 1; g_timeout_add(100, smoke, NULL);
    }
#else
    if (getuid() == 0) { g_printerr("Haber okuyucusu yönetici olarak çalıştırılmaz.\n"); return 2; }
#endif
    application = gtk_application_new("org.oguzdows.Haber", G_APPLICATION_DEFAULT_FLAGS);
    g_signal_connect(application, "activate", G_CALLBACK(activate), NULL);
    int result = g_application_run(G_APPLICATION(application), argc, argv);
    if (articles) g_ptr_array_unref(articles);
    g_free(source_name); g_free(selected_source); g_object_unref(application);
#ifdef OGUZDOWS_NEWS_TEST
    g_free(private_home);
#endif
    return result;
}
