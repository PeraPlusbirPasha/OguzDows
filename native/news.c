/* OğuzDows Haber — native GTK3, plain RSS text; no webview or resident worker. */
#define _POSIX_C_SOURCE 200809L
#define G_LOG_DOMAIN "OguzDows-Haber"
#include <gtk/gtk.h>
#include <json-glib/json-glib.h>
#include <glib/gstdio.h>
#include <locale.h>
#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "ui.h"

#ifndef NEWS_SERVICE
#define NEWS_SERVICE "/usr/lib/oguzdows/news_service.py"
#endif

typedef struct { gchar *title, *body, *link, *published, *category, *publisher, *search; GdkPixbuf *picture; gboolean publisher_image; } Article;
static GtkApplication *application;
static GtkWidget *window, *pages, *headlines, *sources, *refresh_button, *add_button, *remove_button;
static GtkWidget *status_label, *cancel_button, *spinner, *article_title, *article_meta, *article_text;
static GtkWidget *open_button, *back_button, *font_label, *empty_note, *reader_image, *image_caption, *images_button;
static gboolean compact, images_enabled = TRUE;
static GtkWidget *category_combo, *search_entry, *mode_note, *results_label, *news_toolbar;
static gchar *query, *feed_hash;
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
static Article *smoke_current;
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

static void save_preferences(void) {
    gchar *path = preference_path(), *parent = g_path_get_dirname(path);
    if (!g_file_test(path, G_FILE_TEST_IS_SYMLINK) && !g_file_test(parent, G_FILE_TEST_IS_SYMLINK) && g_mkdir_with_parents(parent, 0700) == 0) {
        gchar *contents = g_strdup_printf("[Reader]\nsize=%d\nimages=%s\n", points, images_enabled ? "true" : "false");
        GError *error = NULL;
        if (!g_file_set_contents_full(path, contents, -1, G_FILE_SET_CONTENTS_CONSISTENT, 0600, &error)) {
            status("Okuma tercihi bu oturumda değişti; tercih dosyaya kaydedilemedi.");
            g_clear_error(&error);
        }
        g_free(contents);
    }
    g_free(path); g_free(parent);
}

static void font_size(gint change) {
    points = CLAMP(points + change, 12, 26);
    g_object_set(reader_tag, "size-points", (gdouble)points, NULL);
    gchar *value = g_strdup_printf("%d", points); gtk_label_set_text(GTK_LABEL(font_label), value); g_free(value);
    if (change) save_preferences();
}
static void images_changed(GtkToggleButton *button, gpointer data) {
    (void)data; images_enabled = gtk_toggle_button_get_active(button); save_preferences();
}

static void smaller(GtkButton *button, gpointer data) { (void)button; (void)data; font_size(-1); }
static void larger(GtkButton *button, gpointer data) { (void)button; (void)data; font_size(1); }

static void article_free(gpointer data) {
    Article *article = data;
    g_free(article->title); g_free(article->body); g_free(article->link); g_free(article->published);
    g_free(article->category); g_free(article->publisher); g_free(article->search); g_clear_object(&article->picture); g_free(article);
}

/* The worker emits normalized 320x180 JPEGs, never arbitrary local paths.
 * Recheck the cache boundary / owner / type / bytes and decoder dimensions;
 * no synchronous web loading, SVG from feeds, or full-resolution decoding. */
static void image_size(GdkPixbufLoader *loader, gint width, gint height, gpointer data) {
    gboolean *valid = data; *valid = width == 320 && height == 180;
    gdk_pixbuf_loader_set_size(loader, *valid ? 320 : 1, *valid ? 180 : 1);
}
static GdkPixbuf *cached_picture(const gchar *path) {
    if (!path || !*path) return NULL;
    gchar *base = g_build_filename(g_get_user_cache_dir(), "oguzdows", "news", "thumbnails", NULL);
    gchar *name = g_path_get_basename(path), *expected = g_build_filename(base, name, NULL);
    GStatBuf directory;
    gboolean valid = !strcmp(path, expected) && g_regex_match_simple("^[a-f0-9]{64}\\.jpg$", name, 0, 0)
        && !g_lstat(base, &directory) && S_ISDIR(directory.st_mode) && directory.st_uid == getuid();
    g_free(name); g_free(expected); g_free(base);
    if (!valid) return NULL;
    int descriptor = open(path, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
    if (descriptor < 0) return NULL;
    struct stat info;
    if (fstat(descriptor, &info) || !S_ISREG(info.st_mode) || info.st_uid != getuid() || info.st_size <= 0 || info.st_size > 98304) {
        close(descriptor); return NULL;
    }
    gsize total = 0, length = (gsize)info.st_size; guchar *bytes = g_malloc(length);
    while (total < length) {
        ssize_t count = read(descriptor, bytes + total, length - total);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) break;
        total += (gsize)count;
    }
    close(descriptor);
    if (total != length || length < 3 || bytes[0] != 255 || bytes[1] != 216 || bytes[2] != 255) { g_free(bytes); return NULL; }
    GdkPixbufLoader *loader = gdk_pixbuf_loader_new_with_type("jpeg", NULL);
    if (!loader) { g_free(bytes); return NULL; }
    valid = FALSE;
    g_signal_connect(loader, "size-prepared", G_CALLBACK(image_size), &valid);
    gboolean decoded = gdk_pixbuf_loader_write(loader, bytes, length, NULL);
    decoded = gdk_pixbuf_loader_close(loader, NULL) && decoded;
    GdkPixbuf *picture = decoded && valid ? gdk_pixbuf_loader_get_pixbuf(loader) : NULL;
    if (picture) g_object_ref(picture);
    g_object_unref(loader); g_free(bytes); return picture;
}
static GdkPixbuf *category_picture(const gchar *category) {
    static GdkPixbuf *covers[6];
    const gchar *names[] = {"Gündem", "Dünya", "Bilim ve teknoloji", "Kültür", "Spor", "Rehber"};
    guint index = 0;
    for (guint i = 0; i < G_N_ELEMENTS(names); i++) if (!strcmp(category, names[i])) index = i;
    if (!covers[index]) {
        gchar *path = g_strdup_printf("/usr/share/oguzdows/ui/news-cover-%u.png", index);
        covers[index] = gdk_pixbuf_new_from_file_at_scale(path, 320, 180, FALSE, NULL); g_free(path);
    }
    return covers[index] ? g_object_ref(covers[index]) : NULL;
}
static void set_picture(GtkWidget *image, GdkPixbuf *picture, gint width, gint height) {
    if (!picture) { gtk_image_set_from_icon_name(GTK_IMAGE(image), "oguzdows-news", GTK_ICON_SIZE_DIALOG); return; }
    GdkPixbuf *scaled = gdk_pixbuf_scale_simple(picture, width, height, GDK_INTERP_BILINEAR);
    gtk_image_set_from_pixbuf(GTK_IMAGE(image), scaled); g_object_unref(scaled);
}

/* Change layout only at the breakpoint; keep articles, selection, search and
 * scroll/reader state. No feed reload, network request or per-frame resizing. */
static void fit_news(gint width) {
    compact = width < 720;
    GtkStyleContext *style = gtk_widget_get_style_context(window);
    if (compact) gtk_style_context_add_class(style, "compact-news");
    else gtk_style_context_remove_class(style, "compact-news");
    gtk_orientable_set_orientation(GTK_ORIENTABLE(news_toolbar), compact ? GTK_ORIENTATION_VERTICAL : GTK_ORIENTATION_HORIZONTAL);
    GList *rows = gtk_container_get_children(GTK_CONTAINER(headlines));
    for (GList *it = rows; it; it = it->next) {
        GtkWidget *row = it->data;
        Article *article = g_object_get_data(G_OBJECT(row), "article");
        set_picture(g_object_get_data(G_OBJECT(row), "image"), article->picture, compact ? 88 : 144, compact ? 50 : 81);
        gtk_box_set_spacing(GTK_BOX(gtk_bin_get_child(GTK_BIN(row))), compact ? 10 : 18);
        gtk_label_set_max_width_chars(g_object_get_data(G_OBJECT(row), "title"), compact ? 22 : 52);
        gtk_label_set_max_width_chars(g_object_get_data(G_OBJECT(row), "date"), compact ? 18 : 48);
        gtk_label_set_max_width_chars(g_object_get_data(G_OBJECT(row), "summary"), compact ? 22 : 52);
    }
    g_list_free(rows);
    if (current) set_picture(reader_image, current->picture, compact ? 160 : 224, compact ? 90 : 126);
    gtk_label_set_max_width_chars(GTK_LABEL(article_title), compact ? 22 : 48);
    gtk_label_set_max_width_chars(GTK_LABEL(article_meta), compact ? 24 : 48);
    gtk_label_set_max_width_chars(GTK_LABEL(image_caption), compact ? 24 : 42);
}
static gboolean configured(GtkWidget *widget, GdkEventConfigure *event, gpointer data) {
    (void)widget; (void)data;
    if (compact != (event->width < 720)) fit_news(event->width);
    return FALSE;
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
    set_picture(reader_image, current->picture, compact ? 160 : 224, compact ? 90 : 126);
    gtk_label_set_text(GTK_LABEL(image_caption), current->publisher_image ? "Yayıncının RSS görseli · çevrimdışı önbellek" : "Özgün kategori çizimi · haber fotoğrafı değildir");
    gchar *meta = g_strdup_printf("%s · %s\n%s", current->publisher, current->category, *current->published ? current->published : "Yayın tarihi belirtilmedi · tarih uydurulmaz");
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
    gtk_widget_set_sensitive(images_button, !value);
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

static gboolean article_filter(GtkListBoxRow *row, gpointer data) {
    (void)data;
    Article *article = g_object_get_data(G_OBJECT(row), "article");
    const gchar *chosen = gtk_combo_box_get_active_id(GTK_COMBO_BOX(category_combo));
    return article && (!chosen || !strcmp(chosen, "Tümü") || !strcmp(chosen, article->category)) &&
        (!query || !*query || strstr(article->search, query));
}

static void filter_articles(GtkWidget *widget, gpointer data) {
    (void)widget; (void)data;
    if (filling) return;
    g_free(query); query = g_utf8_casefold(gtk_entry_get_text(GTK_ENTRY(search_entry)), -1);
    gtk_list_box_invalidate_filter(GTK_LIST_BOX(headlines));
    guint visible = 0;
    GList *rows = gtk_container_get_children(GTK_CONTAINER(headlines));
    for (GList *it = rows; it; it = it->next) if (article_filter(it->data, NULL)) visible++;
    g_list_free(rows);
    gchar *text = g_strdup_printf("%u başlık · kategoriler ve arama bu cihazda filtrelenir", visible);
    gtk_label_set_text(GTK_LABEL(results_label), text); g_free(text);
    gtk_widget_set_visible(empty_note, visible == 0);
}

static gboolean load_feed(JsonObject *root) {
    JsonArray *feed_sources = array_member(root, "sources"), *items = array_member(root, "items");
    if (!feed_sources || !items || json_array_get_length(feed_sources) > 16 || json_array_get_length(items) > 60) return FALSE;
    gchar *serialized = json_to_string(json_object_get_member(root, "items"), FALSE);
    gchar *identity = g_strconcat(text_member(root, "selected"), text_member(root, "source"), serialized, NULL);
    gchar *hash = g_compute_checksum_for_string(G_CHECKSUM_SHA256, identity, -1);
    gboolean unchanged = !g_strcmp0(feed_hash, hash);
    g_free(serialized); g_free(identity);
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
    if (!unchanged) {
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
        article->category = g_strdup(*text_member(item, "category") ? text_member(item, "category") : "Gündem");
        article->publisher = g_strdup(*text_member(item, "publisher") ? text_member(item, "publisher") : source_name);
        gchar *searchable = g_strjoin(" ", article->title, article->body, article->category, NULL);
        article->search = g_utf8_casefold(searchable, -1); g_free(searchable);
        if (g_utf8_strlen(article->body, -1) > 8192 || g_utf8_strlen(article->title, -1) > 240) { article_free(article); return FALSE; }
        article->picture = cached_picture(text_member(item, "image_path"));
        article->publisher_image = article->picture != NULL;
        if (!article->picture) article->picture = category_picture(article->category);
        g_ptr_array_add(articles, article);
        GtkWidget *row = gtk_list_box_row_new(), *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 6);
        gtk_style_context_add_class(gtk_widget_get_style_context(row), "news-item");
        GtkWidget *title = label(article->title, "news-headline");
        gtk_label_set_max_width_chars(GTK_LABEL(title), compact ? 22 : 52);
        gtk_label_set_lines(GTK_LABEL(title), 3); gtk_label_set_ellipsize(GTK_LABEL(title), PANGO_ELLIPSIZE_END);
        gtk_box_pack_start(GTK_BOX(box), title, FALSE, FALSE, 0);
        gchar *byline = g_strdup_printf("%s · %s%s%s", article->publisher, article->category, *article->published ? " · " : "", article->published);
        GtkWidget *date = label(byline, "dim-label"); g_free(byline);
        gtk_label_set_max_width_chars(GTK_LABEL(date), compact ? 18 : 48);
        gtk_label_set_lines(GTK_LABEL(date), 1); gtk_label_set_ellipsize(GTK_LABEL(date), PANGO_ELLIPSIZE_END);
        gtk_box_pack_start(GTK_BOX(box), date, FALSE, FALSE, 0);
        gchar *excerpt = g_utf8_substring(article->body, 0, MIN((glong)110, g_utf8_strlen(article->body, -1)));
        GtkWidget *summary = label(excerpt, NULL); g_free(excerpt);
        gtk_label_set_max_width_chars(GTK_LABEL(summary), compact ? 22 : 52);
        gtk_label_set_lines(GTK_LABEL(summary), 2); gtk_label_set_ellipsize(GTK_LABEL(summary), PANGO_ELLIPSIZE_END);
        gtk_box_pack_start(GTK_BOX(box), summary, FALSE, FALSE, 0);
        GtkWidget *line = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, compact ? 10 : 18);
        GtkWidget *image = gtk_image_new(); set_picture(image, article->picture, compact ? 88 : 144, compact ? 50 : 81);
        gtk_widget_set_valign(image, GTK_ALIGN_START);
        gtk_widget_set_tooltip_text(image, article->publisher_image ? "Yayıncının RSS görseli" : "Kategori çizimi · haber fotoğrafı değildir");
        gtk_box_pack_start(GTK_BOX(line), image, FALSE, FALSE, 0);
        gtk_box_pack_start(GTK_BOX(line), box, TRUE, TRUE, 0);
        GtkWidget *read = label("Haberi oku  ›", "news-read-link"); gtk_box_pack_start(GTK_BOX(box), read, FALSE, FALSE, 0);
        gtk_widget_set_tooltip_text(row, "Habere tıklayıp RSS metnini oku; Kaynakta aç ile yayıncının sitesine git.");
        gtk_container_add(GTK_CONTAINER(row), line); g_object_set_data(G_OBJECT(row), "article", article);
        g_object_set_data(G_OBJECT(row), "image", image); g_object_set_data(G_OBJECT(row), "title", title);
        g_object_set_data(G_OBJECT(row), "date", date); g_object_set_data(G_OBJECT(row), "summary", summary);
        gtk_container_add(GTK_CONTAINER(headlines), row);
    }
    gtk_widget_show_all(headlines);
    gtk_widget_set_sensitive(open_button, FALSE);
    show_list(NULL, NULL);
    g_free(feed_hash); feed_hash = g_strdup(hash);
    }
    g_free(hash);
    filter_articles(NULL, NULL);
    const gchar *note = text_member(root, "note");
    gchar *banner = g_strjoin("\n", *note ? note : "RSS / Atom · Yayıncı metni, reklam ve webview olmadan.", text_member(root, "warning"), NULL);
    gtk_label_set_text(GTK_LABEL(mode_note), banner); g_free(banner);
    GtkStyleContext *mode_style = gtk_widget_get_style_context(mode_note);
    if (!strcmp(text_member(root, "mode"), "example")) gtk_style_context_add_class(mode_style, "example");
    else gtk_style_context_remove_class(mode_style, "example");
    gchar *info = g_strdup_printf("%u başlık · %s%s · Yayıncı metni / özeti; tam makale garantisi yok.", articles->len,
        *text_member(root, "cached_at") ? "Önbellek: " : "Henüz yayıncıdan indirme yok", text_member(root, "cached_at"));
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
        if (ok && output && strlen(output) <= 2 * 1024 * 1024 && json_parser_load_from_data(parser, output, -1, &error) && json_parser_get_root(parser) && JSON_NODE_HOLDS_OBJECT(json_parser_get_root(parser))) {
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
    status(!strcmp(first, "refresh") ? "RSS ve seçtiysen küçük görseller alınıyor… Eski metin okunabilir." : "Yerel kaynak / önbellek okunuyor; ağ isteği yok…");
    deadline_id = g_timeout_add_seconds(24, timed_out, NULL);
    g_application_hold(G_APPLICATION(application));
    g_subprocess_communicate_utf8_async(worker, NULL, NULL, service_done, NULL);
}

static void refresh(GtkButton *button, gpointer data) { (void)button; (void)data; if (selected_source) run_service("refresh", selected_source, images_enabled ? NULL : "text-only"); }

static void add_source(GtkButton *button, gpointer data) {
    (void)button; (void)data;
    GtkWidget *dialog = gtk_dialog_new_with_buttons("Kendi RSS / Atom kaynağın", GTK_WINDOW(window), GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        "Vazgeç", GTK_RESPONSE_CANCEL, "Ekle", GTK_RESPONSE_OK, NULL);
    og_ui_setup(dialog);
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
    og_ui_setup(dialog);
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
            if (g_key_file_has_key(prefs, "Reader", "images", NULL)) images_enabled = g_key_file_get_boolean(prefs, "Reader", "images", NULL);
        }
        g_key_file_unref(prefs);
    }
    g_free(path);
    window = gtk_application_window_new(app);
    gtk_window_set_title(GTK_WINDOW(window), "OğuzDows Haber");
    gtk_window_set_icon_name(GTK_WINDOW(window), "oguzdows-news");
    og_ui_setup(window);
    GdkDisplay *display = gtk_widget_get_display(window);
    GdkMonitor *monitor = gdk_display_get_primary_monitor(display);
    if (!monitor) monitor = gdk_display_get_monitor(display, 0);
    GdkRectangle area = {0, 0, 1024, 768}; if (monitor) gdk_monitor_get_workarea(monitor, &area);
    compact = area.width < 720;
    if (compact) gtk_style_context_add_class(gtk_widget_get_style_context(window), "compact-news");
    gtk_window_set_default_size(GTK_WINDOW(window), MIN(920, area.width - 24), MIN(660, area.height - 48));
    gtk_widget_set_size_request(window, 296, 300);
    g_signal_connect(window, "delete-event", G_CALLBACK(on_close), NULL);
    GtkWidget *header = gtk_header_bar_new(); gtk_header_bar_set_show_close_button(GTK_HEADER_BAR(header), TRUE);
    gtk_header_bar_set_title(GTK_HEADER_BAR(header), "Haber");
    gtk_header_bar_pack_start(GTK_HEADER_BAR(header), gtk_image_new_from_icon_name("oguzdows-news", GTK_ICON_SIZE_LARGE_TOOLBAR));
    gtk_header_bar_pack_end(GTK_HEADER_BAR(header), icon_button("audio-speakers-symbolic", "Haber okuyucusu rehberini dinle / durdur", G_CALLBACK(narrate)));
    gtk_window_set_titlebar(GTK_WINDOW(window), header);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0); gtk_container_add(GTK_CONTAINER(window), box);
    GtkWidget *toolbar = gtk_box_new(compact ? GTK_ORIENTATION_VERTICAL : GTK_ORIENTATION_HORIZONTAL, 6); gtk_container_set_border_width(GTK_CONTAINER(toolbar), 12);
    news_toolbar = toolbar;
    sources = gtk_combo_box_text_new(); gtk_widget_set_hexpand(sources, TRUE);
    GList *cells = gtk_cell_layout_get_cells(GTK_CELL_LAYOUT(sources));
    for (GList *it = cells; it; it = it->next)
        g_object_set(it->data, "ellipsize", PANGO_ELLIPSIZE_END, "width-chars", 8, "max-width-chars", 24, NULL);
    g_list_free(cells);
    atk_object_set_name(gtk_widget_get_accessible(sources), "RSS kaynağı");
    g_signal_connect(sources, "changed", G_CALLBACK(source_changed), NULL);
    gtk_box_pack_start(GTK_BOX(toolbar), sources, TRUE, TRUE, 0);
    GtkWidget *tools = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 6);
    gtk_box_pack_start(GTK_BOX(toolbar), tools, FALSE, FALSE, 0);
    refresh_button = icon_button("view-refresh-symbolic", "Yayıncıdan yenile · RSS ve açıksa en fazla 6 küçük görsel", G_CALLBACK(refresh));
    add_button = icon_button("list-add-symbolic", "Kendi RSS kaynağını ekle", G_CALLBACK(add_source));
    remove_button = icon_button("list-remove-symbolic", "Kişisel RSS kaynağını kaldır", G_CALLBACK(remove_source));
    images_button = gtk_toggle_button_new();
    gtk_button_set_image(GTK_BUTTON(images_button), gtk_image_new_from_icon_name("image-x-generic-symbolic", GTK_ICON_SIZE_BUTTON));
    gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(images_button), images_enabled);
    gtk_widget_set_tooltip_text(images_button, "Yenilemede küçük görselleri indir · kapalıysa yalnız metin");
    atk_object_set_name(gtk_widget_get_accessible(images_button), "Yenilemede görselleri indir");
    g_signal_connect(images_button, "toggled", G_CALLBACK(images_changed), NULL);
    cancel_button = icon_button("process-stop-symbolic", "Haber isteğini durdur", G_CALLBACK(cancel));
    gtk_box_pack_start(GTK_BOX(tools), refresh_button, FALSE, FALSE, 0); gtk_box_pack_start(GTK_BOX(tools), add_button, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(tools), remove_button, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(tools), images_button, FALSE, FALSE, 0); gtk_box_pack_start(GTK_BOX(tools), cancel_button, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(box), toolbar, FALSE, FALSE, 0);
    mode_note = label("Yerel akış hazırlanıyor…", "news-banner");
    gtk_label_set_max_width_chars(GTK_LABEL(mode_note), 68);
    gtk_box_pack_start(GTK_BOX(box), mode_note, FALSE, FALSE, 0);
    GtkWidget *filters = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    gtk_container_set_border_width(GTK_CONTAINER(filters), 12);
    category_combo = gtk_combo_box_text_new();
    const gchar *categories[] = {"Tümü", "Gündem", "Dünya", "Bilim ve teknoloji", "Kültür", "Spor", "Rehber"};
    for (guint i = 0; i < G_N_ELEMENTS(categories); i++) gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(category_combo), categories[i], categories[i]);
    gtk_combo_box_set_active(GTK_COMBO_BOX(category_combo), 0);
    atk_object_set_name(gtk_widget_get_accessible(category_combo), "Haber kategorisi");
    GList *category_cells = gtk_cell_layout_get_cells(GTK_CELL_LAYOUT(category_combo));
    for (GList *it = category_cells; it; it = it->next) g_object_set(it->data, "ellipsize", PANGO_ELLIPSIZE_END, "width-chars", 5, "max-width-chars", 10, NULL);
    g_list_free(category_cells);
    search_entry = gtk_search_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(search_entry), "Başlıklarda ara…");
    gtk_entry_set_width_chars(GTK_ENTRY(search_entry), 8);
    gtk_widget_set_hexpand(search_entry, TRUE);
    gtk_box_pack_start(GTK_BOX(filters), category_combo, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(filters), search_entry, TRUE, TRUE, 0);
    gtk_box_pack_start(GTK_BOX(box), filters, FALSE, FALSE, 0);
    g_signal_connect(category_combo, "changed", G_CALLBACK(filter_articles), NULL);
    g_signal_connect(search_entry, "search-changed", G_CALLBACK(filter_articles), NULL);
    pages = gtk_stack_new(); og_ui_stack_setup(pages);
    gtk_box_pack_start(GTK_BOX(box), pages, TRUE, TRUE, 0);
    GtkWidget *list_page = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
    results_label = label("Başlıklar hazırlanıyor…", "dim-label");
    gtk_widget_set_margin_start(results_label, 20); gtk_widget_set_margin_end(results_label, 20);
    gtk_box_pack_start(GTK_BOX(list_page), results_label, FALSE, FALSE, 0);
    empty_note = label("Bu filtreyle başlık yok. Aramayı temizle veya Tümü kategorisini seç. Yayıncıdan yeni başlıklar için Yenile’yi kullan; çevrimdışı örnekler gerçek haber değildir.", "dim-label");
    gtk_label_set_max_width_chars(GTK_LABEL(empty_note), 44);
    gtk_widget_set_margin_start(empty_note, 16); gtk_widget_set_margin_end(empty_note, 16);
    gtk_widget_set_margin_top(empty_note, 16); gtk_widget_set_margin_bottom(empty_note, 16);
    gtk_box_pack_start(GTK_BOX(list_page), empty_note, FALSE, FALSE, 0);
    GtkWidget *scroll = gtk_scrolled_window_new(NULL, NULL); gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll), GTK_POLICY_NEVER, GTK_POLICY_AUTOMATIC);
    headlines = gtk_list_box_new();
    gtk_style_context_add_class(gtk_widget_get_style_context(headlines), "news-list");
    gtk_list_box_set_filter_func(GTK_LIST_BOX(headlines), article_filter, NULL, NULL);
    gtk_list_box_set_selection_mode(GTK_LIST_BOX(headlines), GTK_SELECTION_SINGLE);
    gtk_list_box_set_activate_on_single_click(GTK_LIST_BOX(headlines), TRUE);
    g_signal_connect(headlines, "row-activated", G_CALLBACK(select_article), NULL);
    gtk_container_add(GTK_CONTAINER(scroll), headlines); gtk_box_pack_start(GTK_BOX(list_page), scroll, TRUE, TRUE, 0);
    gtk_stack_add_named(GTK_STACK(pages), list_page, "headlines");
    GtkWidget *reader = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8); gtk_container_set_border_width(GTK_CONTAINER(reader), 16);
    article_title = label("", "reader-title"); gtk_label_set_max_width_chars(GTK_LABEL(article_title), 48);
    article_meta = label("", "dim-label"); gtk_label_set_max_width_chars(GTK_LABEL(article_meta), 48);
    gtk_box_pack_start(GTK_BOX(reader), article_title, FALSE, FALSE, 0); gtk_box_pack_start(GTK_BOX(reader), article_meta, FALSE, FALSE, 0);
    reader_image = gtk_image_new(); gtk_widget_set_halign(reader_image, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(reader), reader_image, FALSE, FALSE, 0);
    image_caption = label("", "news-image-caption"); gtk_label_set_max_width_chars(GTK_LABEL(image_caption), 42);
    gtk_box_pack_start(GTK_BOX(reader), image_caption, FALSE, FALSE, 0);
    scroll = gtk_scrolled_window_new(NULL, NULL);
    /* NEVER propagates GtkTextView's last laid-out width as the window's
     * minimum (800px after zoom). EXTERNAL permits reflow without a horizontal
     * scrollbar; wrapping and the vertical scrollbar remain native GTK. */
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll), GTK_POLICY_EXTERNAL, GTK_POLICY_AUTOMATIC);
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
    open_button = gtk_button_new_with_label("Kaynakta aç ↗"); g_signal_connect(open_button, "clicked", G_CALLBACK(open_source), NULL);
    gtk_box_pack_end(GTK_BOX(controls), open_button, FALSE, FALSE, 0); gtk_box_pack_start(GTK_BOX(box), controls, FALSE, FALSE, 0);
    GtkWidget *bottom = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8); gtk_container_set_border_width(GTK_CONTAINER(bottom), 10);
    spinner = gtk_spinner_new(); gtk_box_pack_start(GTK_BOX(bottom), spinner, FALSE, FALSE, 0);
    status_label = label("Çevrimdışı önbellek açılıyor…", "news-status"); gtk_label_set_max_width_chars(GTK_LABEL(status_label), 70);
    gtk_box_pack_start(GTK_BOX(bottom), status_label, TRUE, TRUE, 0); gtk_box_pack_start(GTK_BOX(box), bottom, FALSE, FALSE, 0);
    fit_news(area.width - 24);
    g_signal_connect(window, "configure-event", G_CALLBACK(configured), NULL);
    gtk_widget_show_all(window); gtk_widget_hide(empty_note); set_busy(FALSE); font_size(0);
    gtk_widget_set_sensitive(back_button, FALSE); gtk_widget_set_sensitive(open_button, FALSE);
    run_service("list", NULL, NULL); /* Cold launch never asks the worker to fetch a URL. */
}

#ifdef OGUZDOWS_NEWS_TEST
static void width_diagnostic(GtkWidget *widget, gpointer depth) {
    gint minimum, natural; gtk_widget_get_preferred_width(widget, &minimum, &natural);
    if (minimum > 200) g_print("News minimum %u %s: %d (natural %d)\n", GPOINTER_TO_UINT(depth), G_OBJECT_TYPE_NAME(widget), minimum, natural);
    if (GTK_IS_CONTAINER(widget)) gtk_container_foreach(GTK_CONTAINER(widget), width_diagnostic, GUINT_TO_POINTER(GPOINTER_TO_UINT(depth) + 1));
}
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
    g_assert_cmpint(gtk_widget_get_allocated_height(window), <=, area.height);
    if (smoke_step == 0) {
        g_assert_cmpuint(articles->len, ==, 2); g_assert_null(worker);
        g_assert_true(((Article *)g_ptr_array_index(articles, 0))->publisher_image);
        g_assert_nonnull(((Article *)g_ptr_array_index(articles, 0))->picture);
        g_assert_false(((Article *)g_ptr_array_index(articles, 1))->publisher_image);
        screenshot("news-list.png");
        gtk_combo_box_set_active_id(GTK_COMBO_BOX(category_combo), "Dünya");
        g_assert_true(gtk_widget_get_visible(empty_note));
        gtk_combo_box_set_active_id(GTK_COMBO_BOX(category_combo), "Tümü");
        g_assert_false(gtk_widget_get_visible(empty_note));
        gtk_entry_set_text(GTK_ENTRY(search_entry), "__missing__"); filter_articles(NULL, NULL);
        g_assert_true(gtk_widget_get_visible(empty_note));
        gtk_entry_set_text(GTK_ENTRY(search_entry), ""); filter_articles(NULL, NULL);
        g_assert_true(gtk_list_box_get_activate_on_single_click(GTK_LIST_BOX(headlines)));
        g_signal_emit_by_name(headlines, "row-activated", gtk_list_box_get_row_at_index(GTK_LIST_BOX(headlines), 0));
        larger(NULL, NULL); g_assert_cmpint(points, ==, 17);
        smoke_step = 1; return G_SOURCE_CONTINUE;
    }
    if (smoke_step == 1) {
        g_assert_nonnull(current); g_assert_nonnull(strstr(current->body, "TEST"));
        screenshot("news-reader.png");
        gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(images_button), FALSE); g_assert_false(images_enabled);
        refresh(NULL, NULL); smoke_step = 2; return G_SOURCE_CONTINUE;
    }
    if (smoke_step < 5) g_assert_cmpuint(articles->len, ==, 2); /* Failure / cancellation never clears cached reading. */
    g_assert_null(worker); g_assert_cmpuint(deadline_id, ==, 0);
    if (smoke_step == 2) {
        g_assert_nonnull(strstr(gtk_label_get_text(GTK_LABEL(status_label)), "Test bağlantı hatası"));
        g_assert_nonnull(strstr(gtk_label_get_text(GTK_LABEL(status_label)), "text-only verified"));
        run_service("cached", "test", NULL); g_assert_nonnull(worker);
        cancel(NULL, NULL); smoke_step = 3; return G_SOURCE_CONTINUE;
    }
    if (smoke_step == 3) {
        run_service("cached", "test", NULL); g_assert_nonnull(worker);
        /* Same production timeout callback, shortened only in the test build. */
        g_source_remove(deadline_id); deadline_id = g_timeout_add(30, timed_out, NULL);
        smoke_step = 4; return G_SOURCE_CONTINUE;
    }
    if (smoke_step == 4) {
        run_service("cached", "example", NULL); smoke_step = 5; return G_SOURCE_CONTINUE;
    }
    if (smoke_step == 5) {
        g_assert_cmpuint(articles->len, ==, 6);
        g_assert_true(gtk_style_context_has_class(gtk_widget_get_style_context(mode_note), "example"));
        g_assert_nonnull(strstr(gtk_label_get_text(GTK_LABEL(mode_note)), "Gerçek haber değildir"));
        screenshot("news-example.png");
        gtk_combo_box_set_active_id(GTK_COMBO_BOX(category_combo), "Rehber");
        guint visible = 0;
        GList *rows = gtk_container_get_children(GTK_CONTAINER(headlines));
        for (GList *it = rows; it; it = it->next) if (article_filter(it->data, NULL)) visible++;
        g_list_free(rows); g_assert_cmpuint(visible, ==, 1);
        for (guint i = 0; i < 40; i++) smaller(NULL, NULL);
        g_assert_cmpint(points, ==, 12);
        for (guint i = 0; i < 40; i++) larger(NULL, NULL);
        g_assert_cmpint(points, ==, 26);
        rows = gtk_container_get_children(GTK_CONTAINER(headlines));
        for (GList *it = rows; it; it = it->next)
            if (article_filter(it->data, NULL)) { g_signal_emit_by_name(headlines, "row-activated", it->data); break; }
        g_list_free(rows); g_assert_nonnull(current); smoke_current = current;
        gtk_window_resize(GTK_WINDOW(window), MIN(680, area.width - 24), MIN(680, area.height - 48));
        smoke_step = 6; return G_SOURCE_CONTINUE;
    }
    if (smoke_step == 6) {
        if (!compact) {
            g_print("News requested compact size; actual %dx%d\n", gtk_widget_get_allocated_width(window), gtk_widget_get_allocated_height(window));
            width_diagnostic(window, NULL);
        }
        g_assert_true(compact);
        gtk_window_resize(GTK_WINDOW(window), MIN(360, area.width - 24), MIN(680, area.height - 48));
        smoke_step = 7; return G_SOURCE_CONTINUE;
    }
    g_assert_cmpuint(smoke_step, ==, 7); g_assert_true(compact);
    g_assert_cmpint(gtk_widget_get_allocated_width(window), <=, 480);
    g_assert_true(current == smoke_current); /* No reload / lost reading state on resize. */
    g_assert_cmpstr(gtk_combo_box_get_active_id(GTK_COMBO_BOX(category_combo)), ==, "Rehber");
    g_assert_cmpuint(articles->len, ==, 6);
    screenshot("news-compact.png");
    gchar *path = g_build_filename(smoke_directory, "news-native.json", NULL);
    gchar *receipt = g_strdup_printf("{\"native_gtk\":true,\"fixture_not_network\":true,\"cold_start_fetch\":false,\"offline_after_error\":true,\"category_filter\":true,\"local_search\":true,\"honest_example_fallback\":true,\"cached_thumbnail\":true,\"single_click_reader\":true,\"text_only_option\":true,\"dynamic_compact_resize\":true,\"resize_preserves_reader_filter\":true,\"font_limits\":true,\"worker_exited\":true,\"cancellation\":true,\"deadline_callback\":true,\"physical_device\":false,\"screen_width\":%d,\"screen_height\":%d,\"window_width\":%d}", area.width, area.height, gtk_widget_get_allocated_width(window));
    g_assert_true(g_file_set_contents(path, receipt, -1, NULL));
    g_print("::notice title=C Haber GTK::%s\n", receipt);
    g_free(receipt); g_free(path); gtk_widget_destroy(window); g_application_quit(G_APPLICATION(application)); return G_SOURCE_REMOVE;
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
        g_setenv("XDG_CACHE_HOME", private_home, TRUE);
        argc = 1; g_timeout_add(100, smoke, NULL);
    }
#else
    if (getuid() == 0) { g_printerr("Haber okuyucusu yönetici olarak çalıştırılmaz.\n"); return 2; }
#endif
    application = gtk_application_new("org.oguzdows.Haber", G_APPLICATION_DEFAULT_FLAGS);
    g_signal_connect(application, "activate", G_CALLBACK(activate), NULL);
    int result = g_application_run(G_APPLICATION(application), argc, argv);
    if (articles) g_ptr_array_unref(articles);
    g_free(source_name); g_free(selected_source); g_free(query); g_free(feed_hash); g_object_unref(application);
#ifdef OGUZDOWS_NEWS_TEST
    g_free(private_home);
#endif
    return result;
}
