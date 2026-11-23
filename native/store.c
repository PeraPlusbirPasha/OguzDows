/* OğuzDows Mağaza 1.1 — derlenen GTK 3 arayüzü.
 * Derleme: scripts/build-native.sh. HTML / webview / Python GTK kabuğu değildir.
 * Paket işlemleri kısa ömürlü, doğrulanmış JSON işçisinde; GTK asla beklemez.
 */
#include <gtk/gtk.h>
#include <json-glib/json-glib.h>
#include <locale.h>
#include <string.h>

#ifndef STORE_SERVICE
#define STORE_SERVICE "/usr/lib/oguzdows/store_service.py"
#endif

#define APP_ID "org.oguzdows.YerelMagaza"

typedef struct {
    gchar *id, *name, *summary, *category, *icon, *fallback_icon, *flatpak;
    gboolean installed, flatpak_installed;
} App;

typedef enum { CATALOG, SEARCH, DETAIL, PLAN, APPLY, SETUP, LAUNCH } Job;
typedef struct { Job job; GSubprocess *process; } Work;

static GtkApplication *application;
static GtkWidget *window, *stack, *sidebar, *search_entry, *apps_grid, *category;
static GtkWidget *status_label, *spinner, *content, *detail_title, *detail_summary;
static GtkWidget *detail_text, *source_combo, *install_button, *detail_icon;
static GtkWidget *remote_button, *source_status, *results_info, *no_results;
static GtkWidget *launch_button, *scope_note, *setup_button;
static GtkWidget *store_header, *voice_button, *toolbar, *filters;
static GtkWidget *nav_titles[4], *page_boxes[4];
static guint page_count;
static gboolean compact, catalog_dirty;
static GPtrArray *apps;
static gchar *selected_id, *query_folded;
static gboolean busy, installed_only, supports_apt, supports_updates, remote_available, user_flatpak_supported, advanced_available, filling_sources;
static gchar *current_source;
static const gchar *initial_page = "discover";
#ifdef OGUZDOWS_STORE_TEST
static const gchar *smoke_directory;
static guint smoke_step, smoke_wait;
#endif

static void run_service(Job job, const gchar *first, const gchar *second, const gchar *third, const gchar *fourth);
static void show_catalog(JsonObject *root);
static void view(const gchar *name);
static void show_app(GtkButton *button, gpointer user_data);

static const gchar *string_member(JsonObject *object, const gchar *key) {
    if (!json_object_has_member(object, key)) return "";
    JsonNode *node = json_object_get_member(object, key);
    if (!JSON_NODE_HOLDS_VALUE(node) || json_node_get_value_type(node) != G_TYPE_STRING) return "";
    const gchar *value = json_node_get_string(node);
    return value ? value : "";
}

static gboolean bool_member(JsonObject *object, const gchar *key) {
    if (!json_object_has_member(object, key)) return FALSE;
    JsonNode *node = json_object_get_member(object, key);
    return JSON_NODE_HOLDS_VALUE(node) && json_node_get_value_type(node) == G_TYPE_BOOLEAN && json_node_get_boolean(node);
}

static void app_free(gpointer data) {
    App *app = data;
    g_free(app->id); g_free(app->name); g_free(app->summary); g_free(app->category);
    g_free(app->icon); g_free(app->fallback_icon); g_free(app->flatpak); g_free(app);
}

static GtkWidget *label(const gchar *text, const gchar *css) {
    GtkWidget *widget = gtk_label_new(text);
    gtk_label_set_xalign(GTK_LABEL(widget), 0);
    gtk_label_set_line_wrap(GTK_LABEL(widget), TRUE);
    gtk_label_set_line_wrap_mode(GTK_LABEL(widget), PANGO_WRAP_WORD_CHAR);
    if (css) gtk_style_context_add_class(gtk_widget_get_style_context(widget), css);
    return widget;
}

static void status(const gchar *text) { gtk_label_set_text(GTK_LABEL(status_label), text); }

static void fit_message(GtkWidget *dialog) {
    if (!compact) return;
    GList *children = gtk_container_get_children(GTK_CONTAINER(gtk_message_dialog_get_message_area(GTK_MESSAGE_DIALOG(dialog))));
    for (GList *it = children; it; it = it->next) {
        if (!GTK_IS_LABEL(it->data)) continue;
        gtk_label_set_line_wrap(GTK_LABEL(it->data), TRUE);
        gtk_label_set_line_wrap_mode(GTK_LABEL(it->data), PANGO_WRAP_WORD_CHAR);
        gtk_label_set_max_width_chars(GTK_LABEL(it->data), 24);
    }
    g_list_free(children);
    gtk_window_set_default_size(GTK_WINDOW(dialog), 320, -1);
}

static void message(const gchar *title, const gchar *text, GtkMessageType type) {
    GtkWidget *dialog = gtk_message_dialog_new(GTK_WINDOW(window), GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        type, GTK_BUTTONS_CLOSE, "%s", title);
    gtk_message_dialog_format_secondary_text(GTK_MESSAGE_DIALOG(dialog), "%s", text);
    fit_message(dialog);
    gtk_dialog_run(GTK_DIALOG(dialog));
    gtk_widget_destroy(dialog);
}

static gboolean confirm(const gchar *title, const gchar *text) {
    GtkWidget *dialog = gtk_message_dialog_new(GTK_WINDOW(window), GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        GTK_MESSAGE_WARNING, GTK_BUTTONS_OK_CANCEL, "%s", title);
    gtk_message_dialog_format_secondary_text(GTK_MESSAGE_DIALOG(dialog), "%s", text);
    fit_message(dialog);
    gtk_dialog_set_default_response(GTK_DIALOG(dialog), GTK_RESPONSE_CANCEL);
    gboolean approved = gtk_dialog_run(GTK_DIALOG(dialog)) == GTK_RESPONSE_OK;
    gtk_widget_destroy(dialog);
    return approved;
}

static void set_busy(gboolean value) {
    busy = value;
    gtk_widget_set_sensitive(content, !value);
    if (value) gtk_spinner_start(GTK_SPINNER(spinner)); else gtk_spinner_stop(GTK_SPINNER(spinner));
}

static gboolean closing(GtkWidget *widget, GdkEvent *event, gpointer data) {
    (void)widget; (void)event; (void)data;
    if (busy) {
        status("İşlem devam ediyor. Kurulum / indirme yarıda kesilmedi; bitmesini bekleyin. Yönetici onay penceresini de kontrol edin.");
        return TRUE;
    }
    return FALSE;
}

static void open_advanced(GtkButton *button, gpointer data) {
    (void)button; (void)data;
    if (!advanced_available) { message("Gelişmiş merkez", "Bu cihazda ek GNOME paket merkezi yok. Yerel mağaza sabit uygulama planlarını kendi cihaz kaynağından sunar. Sistem kapsamı / paket kaldırma için cihazının paket yöneticisini kullan.", GTK_MESSAGE_INFO); return; }
    const gchar *argv[] = {"/usr/bin/python3", "-I", "/usr/lib/oguzdows/store.py", NULL};
    GError *error = NULL;
    GSubprocess *process = g_subprocess_newv(argv, G_SUBPROCESS_FLAGS_NONE, &error);
    if (!process) { message("Gelişmiş paket merkezi açılamadı", error->message, GTK_MESSAGE_ERROR); g_error_free(error); }
    else g_object_unref(process);
}

static void narrate(GtkButton *button, gpointer data) {
    (void)button; (void)data;
    const gchar *argv[] = {"/usr/local/bin/oguzdows-narrate", "store", NULL};
    GError *error = NULL;
    GSubprocess *process = g_subprocess_newv(argv, G_SUBPROCESS_FLAGS_NONE, &error);
    if (!process) { status(error->message); g_error_free(error); }
    else g_object_unref(process);
}

static void app_image(GtkWidget *image, App *app, gint size) {
    GtkIconTheme *theme = gtk_icon_theme_get_default();
    const gchar *name = *app->icon && gtk_icon_theme_has_icon(theme, app->icon) ? app->icon :
        *app->fallback_icon && gtk_icon_theme_has_icon(theme, app->fallback_icon) ? app->fallback_icon : "system-software-install";
    gtk_image_set_from_icon_name(GTK_IMAGE(image), name, GTK_ICON_SIZE_DIALOG);
    gtk_image_set_pixel_size(GTK_IMAGE(image), size);
    gtk_widget_set_tooltip_text(image, name == app->fallback_icon ? "Çevrimdışı özgün uygulama rozeti; üreticinin logosu değildir." : app->name);
}

static void app_card(App *app) {
    GtkWidget *button = gtk_button_new();
    gtk_style_context_add_class(gtk_widget_get_style_context(button), "app-card");
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 8);
    gtk_container_set_border_width(GTK_CONTAINER(box), 12);
    GtkWidget *line = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 12);
    GtkWidget *image = gtk_image_new();
    app_image(image, app, 64);
    gtk_style_context_add_class(gtk_widget_get_style_context(image), "app-icon");
    gtk_box_pack_start(GTK_BOX(line), image, FALSE, FALSE, 0);
    GtkWidget *name = label(app->name, "app-name");
    gtk_label_set_max_width_chars(GTK_LABEL(name), 18);
    gtk_box_pack_start(GTK_BOX(line), name, TRUE, TRUE, 0);
    gtk_box_pack_start(GTK_BOX(box), line, FALSE, FALSE, 0);
    GtkWidget *summary = label(app->summary, "dim-label");
    gtk_label_set_max_width_chars(GTK_LABEL(summary), 28);
    gtk_label_set_lines(GTK_LABEL(summary), 3);
    gtk_label_set_ellipsize(GTK_LABEL(summary), PANGO_ELLIPSIZE_END);
    gtk_box_pack_start(GTK_BOX(box), summary, TRUE, TRUE, 0);
    gtk_box_pack_start(GTK_BOX(box), label(app->flatpak_installed ? "● Bu hesapta kurulu" : app->installed ? "● Sistemde kurulu" : app->category, "source-chip"), FALSE, FALSE, 0);
    gtk_container_add(GTK_CONTAINER(button), box);
    gtk_widget_set_size_request(button, 212, 178);
    gtk_widget_set_tooltip_text(button, app->summary);
    gtk_container_add(GTK_CONTAINER(apps_grid), button);
    GtkWidget *child = gtk_widget_get_parent(button);
    g_object_set_data(G_OBJECT(child), "app", app);
    g_signal_connect(button, "clicked", G_CALLBACK(show_app), app);
}

static gboolean matches(App *app) {
    if (!app) return TRUE;
    if (installed_only && !app->installed && !app->flatpak_installed) return FALSE;
    const gchar *chosen = gtk_combo_box_get_active_id(GTK_COMBO_BOX(category));
    if (chosen && strcmp(chosen, "Tümü") && strcmp(chosen, app->category)) return FALSE;
    if (query_folded && *query_folded) {
        gchar *all = g_strjoin(" ", app->name, app->summary, app->id, app->flatpak, NULL);
        gchar *folded = g_utf8_casefold(all, -1);
        gboolean match = strstr(folded, query_folded) != NULL;
        g_free(all); g_free(folded);
        return match;
    }
    return TRUE;
}

static gboolean app_filter(GtkFlowBoxChild *child, gpointer data) {
    (void)data;
    return matches(g_object_get_data(G_OBJECT(child), "app"));
}

static void refilter(GtkWidget *widget, gpointer data) {
    (void)widget; (void)data;
    g_free(query_folded);
    query_folded = g_utf8_casefold(gtk_entry_get_text(GTK_ENTRY(search_entry)), -1);
    gtk_flow_box_invalidate_filter(GTK_FLOW_BOX(apps_grid));
    guint visible = 0;
    for (guint index = 0; index < apps->len; index++)
        if (matches(g_ptr_array_index(apps, index))) visible++;
    gchar *count = g_strdup_printf("Gösterilen: %u / %u%s", visible, apps->len, installed_only ? " · Yalnızca kurulu" : "");
    gtk_label_set_text(GTK_LABEL(results_info), count); g_free(count);
    gtk_widget_set_visible(no_results, !visible);
}

static void clear_apps(void) {
    GList *children = gtk_container_get_children(GTK_CONTAINER(apps_grid));
    for (GList *it = children; it; it = it->next) gtk_widget_destroy(GTK_WIDGET(it->data));
    g_list_free(children);
    g_ptr_array_set_size(apps, 0);
}

static void show_catalog(JsonObject *root) {
    if (!json_object_has_member(root, "apps") || !JSON_NODE_HOLDS_ARRAY(json_object_get_member(root, "apps"))) {
        status("Geçerli bir uygulama listesi alınamadı."); return;
    }
    clear_apps();
    if (json_object_has_member(root, "supports_apt")) {
        supports_apt = bool_member(root, "supports_apt");
        supports_updates = bool_member(root, "supports_updates");
        advanced_available = bool_member(root, "supports_advanced");
        remote_available = bool_member(root, "remote_ready");
        user_flatpak_supported = bool_member(root, "supports_user_flatpak");
        gtk_widget_set_sensitive(remote_button, user_flatpak_supported);
        gtk_widget_set_sensitive(setup_button, user_flatpak_supported);
        const gchar *arch = string_member(root, "flatpak_arch");
        gchar *text = g_strdup_printf("Sistem paketi planı: %s\nFlatpak mimarisi: %s\nFlathub kullanıcı kaynağı: %s\nKullanıcı kapsamı: %s\n\nSistem temel depoları değiştirilmez. Flathub uygulama kaynağıdır; bir başka dağıtımın çekirdeği / libc deposu değildir.",
            supports_apt ? "bu OğuzDows cihaz tabanında kullanılabilir" : "bu cihazda otomatik kurulum sunulmuyor", *arch ? arch : "yok",
            remote_available ? "hazır" : "henüz eklenmedi / doğrulanamadı",
            user_flatpak_supported ? "yönetici parolası olmadan bu hesaba kurulum" : "bu mimaride Flathub uygulamaları sunulmuyor (ARMv6 / armhf / i386 dahil)");
        gtk_label_set_text(GTK_LABEL(source_status), text); g_free(text);
    }
    JsonArray *array = json_object_get_array_member(root, "apps");
    guint count = MIN(json_array_get_length(array), 100u);
    for (guint index = 0; index < count; index++) {
        JsonNode *node = json_array_get_element(array, index);
        if (!JSON_NODE_HOLDS_OBJECT(node)) continue;
        JsonObject *item = json_node_get_object(node);
        const gchar *id = string_member(item, "id");
        if (!*id || strlen(id) > 220) continue;
        App *app = g_new0(App, 1);
        app->id = g_strdup(id); app->name = g_strdup(string_member(item, "name"));
        app->summary = g_strdup(string_member(item, "summary")); app->category = g_strdup(string_member(item, "category"));
        app->icon = g_strdup(string_member(item, "icon")); app->fallback_icon = g_strdup(string_member(item, "fallback_icon")); app->flatpak = g_strdup(string_member(item, "flatpak"));
        app->installed = bool_member(item, "installed"); app->flatpak_installed = bool_member(item, "flatpak_installed");
        g_ptr_array_add(apps, app); app_card(app);
    }
    gtk_widget_show_all(apps_grid);
    refilter(NULL, NULL);
}

static void show_plan(JsonObject *root) {
    const gchar *token = string_member(root, "token");
    if (strlen(token) != 64) { status("Doğrulanabilir plan özeti alınamadı. Kurulum yapılmadı."); return; }
    if (!json_object_has_member(root, "changes") || !JSON_NODE_HOLDS_ARRAY(json_object_get_member(root, "changes"))) {
        status("Paket değişikliği listesi alınamadı. Kurulum yapılmadı."); return;
    }
    if (!json_array_get_length(json_object_get_array_member(root, "changes"))) {
        message("Her şey yerinde", "Bu planda kurulacak veya güncellenecek paket yok.", GTK_MESSAGE_INFO); return;
    }
    GtkWidget *dialog = gtk_dialog_new_with_buttons("Önce incele · Sonra onayla", GTK_WINDOW(window), GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        "Vazgeç", GTK_RESPONSE_CANCEL, "Bu planı uygula", GTK_RESPONSE_ACCEPT, NULL);
    gtk_window_set_default_size(GTK_WINDOW(dialog), compact ? 320 : 650, 480);
    gtk_dialog_set_default_response(GTK_DIALOG(dialog), GTK_RESPONSE_CANCEL);
    GtkWidget *box = gtk_dialog_get_content_area(GTK_DIALOG(dialog));
    gtk_container_set_border_width(GTK_CONTAINER(box), 18);
    gtk_box_set_spacing(GTK_BOX(box), 12);
    gtk_box_pack_start(GTK_BOX(box), label("Paketler / bağımlılıklar değişecek. İnternet gerekir. Sistem paketlerinde yönetici onayı; kullanıcı Flatpak kurulumunda yalnızca bu plan onayı gerekir. İşlem sırasında kapatmayın. Plan değişmişse yeniden onay istenir.", NULL), FALSE, FALSE, 0);
    GtkWidget *scroll = gtk_scrolled_window_new(NULL, NULL);
    GtkWidget *text = gtk_text_view_new();
    gtk_text_view_set_editable(GTK_TEXT_VIEW(text), FALSE);
    gtk_text_view_set_wrap_mode(GTK_TEXT_VIEW(text), GTK_WRAP_WORD_CHAR);
    gtk_text_view_set_monospace(GTK_TEXT_VIEW(text), TRUE);
    gchar *description = g_strjoin("\n\n", string_member(root, "note"), string_member(root, "detail"), NULL);
    gtk_text_buffer_set_text(gtk_text_view_get_buffer(GTK_TEXT_VIEW(text)), description, -1); g_free(description);
    gtk_container_add(GTK_CONTAINER(scroll), text);
    gtk_box_pack_start(GTK_BOX(box), scroll, TRUE, TRUE, 0);
    gtk_widget_show_all(box);
    gchar *saved_token = g_strdup(token), *id = g_strdup(selected_id), *source = g_strdup(current_source);
    gint response = gtk_dialog_run(GTK_DIALOG(dialog));
    gtk_widget_destroy(dialog);
    if (response == GTK_RESPONSE_ACCEPT) run_service(APPLY, "apply", id, source, saved_token);
    else status("Plan iptal edildi. Hiçbir paket kurulmadı.");
    g_free(saved_token); g_free(id); g_free(source);
}

static void service_done(GObject *object, GAsyncResult *result, gpointer data) {
    Work *work = data;
    gchar *output = NULL, *errors = NULL;
    GError *error = NULL;
    gboolean ok = g_subprocess_communicate_utf8_finish(G_SUBPROCESS(object), result, &output, &errors, &error);
    set_busy(FALSE);
    JsonParser *parser = json_parser_new();
    if (!ok || !output || strlen(output) > 2 * 1024 * 1024 || !json_parser_load_from_data(parser, output, -1, NULL)
            || !JSON_NODE_HOLDS_OBJECT(json_parser_get_root(parser))) {
        status(error ? error->message : "Mağaza işçisinden geçerli yanıt alınamadı. İşlem başarılı sayılmadı.");
        if (errors && *errors) g_printerr("OğuzDows Mağaza: %.2500s\n", errors);
    } else {
        JsonObject *root = json_node_get_object(json_parser_get_root(parser));
        const gchar *failure = string_member(root, "error");
        if (*failure || !g_subprocess_get_successful(work->process)) {
            const gchar *text = *failure ? failure : "İşlem başarısız oldu. Kurulum tamamlandı sayılmadı.";
            status(text);
            if (work->job == DETAIL) gtk_text_buffer_set_text(gtk_text_view_get_buffer(GTK_TEXT_VIEW(detail_text)), text, -1);
        } else {
            const gchar *text = string_member(root, "message");
            status(*text ? text : "İşlem tamamlandı.");
            if (work->job == CATALOG) catalog_dirty = FALSE;
            if (work->job == CATALOG || work->job == SEARCH) show_catalog(root);
            if (work->job == DETAIL) {
                gtk_text_buffer_set_text(gtk_text_view_get_buffer(GTK_TEXT_VIEW(detail_text)), string_member(root, "detail"), -1);
                gtk_widget_set_sensitive(launch_button, bool_member(root, "installed") && bool_member(root, "can_launch"));
            }
            if (work->job == PLAN) show_plan(root);
            if (work->job == SETUP) run_service(CATALOG, "catalog", NULL, NULL, NULL);
            if (work->job == APPLY) {
                catalog_dirty = TRUE;
                message("İşlem tamamlandı", string_member(root, "message"), GTK_MESSAGE_INFO);
                if (selected_id && strcmp(selected_id, "@updates")) run_service(DETAIL, "detail", selected_id, current_source, NULL);
                else run_service(CATALOG, "catalog", NULL, NULL, NULL);
            }
        }
    }
    g_clear_error(&error); g_object_unref(parser); g_free(output); g_free(errors);
    g_object_unref(work->process); g_free(work);
    g_application_release(G_APPLICATION(application));
}

static void run_service(Job job, const gchar *first, const gchar *second, const gchar *third, const gchar *fourth) {
    if (busy) return;
    const gchar *argv[] = {"/usr/bin/python3", "-I", STORE_SERVICE, first, second, third, fourth, NULL};
    GError *error = NULL;
    GSubprocess *process = g_subprocess_newv(argv, G_SUBPROCESS_FLAGS_STDOUT_PIPE | G_SUBPROCESS_FLAGS_STDERR_PIPE, &error);
    if (!process) { status(error->message); g_error_free(error); return; }
    if (job == DETAIL) gtk_widget_set_sensitive(launch_button, FALSE);
    Work *work = g_new0(Work, 1); work->job = job; work->process = process;
    set_busy(TRUE);
    status(job == CATALOG ? "Yerel katalog okunuyor… Ağ isteği yapılmıyor." :
           job == PLAN ? "Gerçek paket planı çözümleniyor… Henüz kurulum onayı verilmedi." :
           job == APPLY ? "Onayladığın işlem sürüyor… Bilgisayarı ve bu pencereyi kapatma." :
           job == SETUP ? "Flathub HTTPS tanımı ve imza ayarları denetleniyor…" :
           job == LAUNCH ? "Kurulu uygulamaya başlatma isteği gönderiliyor…" : "Uygulama bilgileri alınıyor…");
    g_application_hold(G_APPLICATION(application));
    g_subprocess_communicate_utf8_async(process, NULL, NULL, service_done, work);
}

static void source_changed(GtkComboBox *combo, gpointer data) {
    (void)data;
    if (filling_sources || !selected_id || busy) return;
    const gchar *source = gtk_combo_box_get_active_id(combo);
    if (!source) return;
    g_free(current_source); current_source = g_strdup(source);
    gboolean user_scope = !strcmp(source, "flatpak");
    gtk_widget_set_sensitive(install_button, user_scope ? remote_available && user_flatpak_supported : supports_apt);
    gtk_widget_set_sensitive(launch_button, FALSE);
    gtk_button_set_label(GTK_BUTTON(install_button), user_scope ? "Kur / güncelle · Parolasız planı incele…" : "Kur / güncelle · Sistem planını incele…");
    gtk_label_set_text(GTK_LABEL(scope_note), user_scope ?
        "Bu hesap · Yönetici parolası gerekmez. Önce izinleri / indirmeyi incele, planı onayla; kurulum bitince Aç’a bas. Diğer hesaplara kurulmaz." :
        "Sistem paketi · Yönetici onayı gerekir. Sınırsız parolasız yönetici yetkisi verilmez. Kurulu uygulamayı açmak yönetici parolası istemez.");
    gtk_text_buffer_set_text(gtk_text_view_get_buffer(GTK_TEXT_VIEW(detail_text)), "Uygulama bilgileri yükleniyor…", -1);
    run_service(DETAIL, "detail", selected_id, current_source, NULL);
}

static void show_app(GtkButton *button, gpointer user_data) {
    (void)button;
    if (busy) return;
    App *app = user_data;
    g_free(selected_id); selected_id = g_strdup(app->id);
    gtk_label_set_text(GTK_LABEL(detail_title), app->name);
    gtk_label_set_text(GTK_LABEL(detail_summary), app->summary);
    app_image(detail_icon, app, 80);
    filling_sources = TRUE;
    gtk_combo_box_text_remove_all(GTK_COMBO_BOX_TEXT(source_combo));
    if (!g_str_has_prefix(app->id, "flatpak:")) gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(source_combo), "system", "Sistem paketi · APT");
    if (*app->flatpak && user_flatpak_supported) gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(source_combo), "flatpak", "Flathub · Bu hesap");
    const gchar *preferred = app->flatpak_installed && user_flatpak_supported ? "flatpak" : app->installed ? "system" :
        *app->flatpak && user_flatpak_supported && remote_available ? "flatpak" : "system";
    gtk_combo_box_set_active_id(GTK_COMBO_BOX(source_combo), preferred);
    filling_sources = FALSE;
    view("detail");
    source_changed(GTK_COMBO_BOX(source_combo), NULL);
}

static void launch_clicked(GtkButton *button, gpointer data) {
    (void)button; (void)data;
    if (selected_id && current_source) run_service(LAUNCH, "launch", selected_id, current_source, NULL);
}

static void install_clicked(GtkButton *button, gpointer data) {
    (void)button; (void)data;
    if (selected_id && current_source) run_service(PLAN, "plan", selected_id, current_source, NULL);
}

static void updates_clicked(GtkButton *button, gpointer data) {
    (void)button;
    const gchar *source = data;
    g_free(selected_id); selected_id = g_strdup("@updates");
    g_free(current_source); current_source = g_strdup(source);
    if (!strcmp(source, "system") && !supports_updates) { status("Bu cihazda genel sistem güncellemesi cihazının paket yöneticisindendir. Mağazadaki sabit uygulama planları ayrı sunulur."); return; }
    run_service(PLAN, "plan", selected_id, source, NULL);
}

static void setup_clicked(GtkButton *button, gpointer data) {
    (void)button; (void)data;
    if (confirm("Flathub bu hesaba eklensin mi?", "Resmî https://dl.flathub.org/repo/flathub.flatpakrepo tanımı kullanılacak. GPG denetimi kapatılmaz. İlk anahtar edinimi HTTPS'e dayanır; bağımsız anahtar doğrulaması değildir. Sistem temel depoları değişmez. Hiçbir uygulama kendiliğinden kurulmaz."))
        run_service(SETUP, "setup", NULL, NULL, NULL);
}

static void remote_search(GtkButton *button, gpointer data) {
    (void)button; (void)data;
    const gchar *query = gtk_entry_get_text(GTK_ENTRY(search_entry));
    if (g_utf8_strlen(query, -1) < 2) { status("Flathub araması için en az iki karakter yaz."); return; }
    if (!user_flatpak_supported) { status("Bu mimaride kullanıcı Flathub uygulamaları sunulmuyor. İmzalı sistem paketlerini kullanabilirsin."); return; }
    if (!remote_available) { view("sources"); status("Önce Flathub kaynağını açık onayla ekleyin."); return; }
    gtk_combo_box_set_active(GTK_COMBO_BOX(category), 0);
    view("discover");
    run_service(SEARCH, "search", query, NULL, NULL);
}

static void reset_catalog(GtkButton *button, gpointer data) {
    (void)button; (void)data;
    gtk_entry_set_text(GTK_ENTRY(search_entry), "");
    view("discover");
    run_service(CATALOG, "catalog", NULL, NULL, NULL);
}

static void view(const gchar *name) {
    if (!strcmp(name, "installed") || !strcmp(name, "discover")) {
        installed_only = !strcmp(name, "installed");
        gtk_stack_set_visible_child_name(GTK_STACK(stack), "discover");
        refilter(NULL, NULL);
        if (catalog_dirty && !busy) run_service(CATALOG, "catalog", NULL, NULL, NULL);
    } else gtk_stack_set_visible_child_name(GTK_STACK(stack), name);
    const gchar *pages[] = {"discover", "installed", "updates", "sources"};
    for (guint index = 0; index < G_N_ELEMENTS(pages); index++) {
        if (strcmp(name, pages[index])) continue;
        GtkListBoxRow *row = gtk_list_box_get_row_at_index(GTK_LIST_BOX(sidebar), index);
        if (row != gtk_list_box_get_selected_row(GTK_LIST_BOX(sidebar))) gtk_list_box_select_row(GTK_LIST_BOX(sidebar), row);
        break;
    }
}

static void navigation(GtkListBox *box, GtkListBoxRow *row, gpointer data) {
    (void)box; (void)data;
    if (row) view(g_object_get_data(G_OBJECT(row), "page"));
}

static void back_clicked(GtkButton *button, gpointer data) { (void)button; (void)data; view("discover"); }

static GtkWidget *action(GtkWidget *box, const gchar *title, GCallback callback, gpointer data) {
    GtkWidget *button = gtk_button_new_with_label(title);
    GtkWidget *text = gtk_bin_get_child(GTK_BIN(button));
    gtk_label_set_line_wrap(GTK_LABEL(text), TRUE);
    gtk_label_set_max_width_chars(GTK_LABEL(text), 30);
    g_signal_connect(button, "clicked", callback, data);
    gtk_box_pack_start(GTK_BOX(box), button, FALSE, FALSE, 0);
    return button;
}

static GtkWidget *page(const gchar *title, const gchar *subtitle) {
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 16);
    gtk_container_set_border_width(GTK_CONTAINER(box), compact ? 12 : 24);
    if (page_count < G_N_ELEMENTS(page_boxes)) page_boxes[page_count++] = box;
    gtk_box_pack_start(GTK_BOX(box), label(title, "page-title"), FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(box), label(subtitle, "dim-label"), FALSE, FALSE, 0);
    return box;
}

static void add_page(GtkWidget *box, const gchar *name) {
    GtkWidget *scroll = gtk_scrolled_window_new(NULL, NULL);
    gtk_scrolled_window_set_policy(GTK_SCROLLED_WINDOW(scroll), GTK_POLICY_NEVER, GTK_POLICY_AUTOMATIC);
    gtk_scrolled_window_set_propagate_natural_width(GTK_SCROLLED_WINDOW(scroll), FALSE);
    gtk_container_add(GTK_CONTAINER(scroll), box);
    gtk_stack_add_named(GTK_STACK(stack), scroll, name);
}

static void fit_layout(gint width) {
    compact = width < 720;
    GtkStyleContext *style = gtk_widget_get_style_context(window);
    if (compact) gtk_style_context_add_class(style, "compact-store");
    else gtk_style_context_remove_class(style, "compact-store");
    gtk_widget_set_size_request(sidebar, compact ? 48 : 146, -1);
    for (guint index = 0; index < G_N_ELEMENTS(nav_titles); index++) {
        gtk_widget_set_no_show_all(nav_titles[index], compact);
        gtk_widget_set_visible(nav_titles[index], !compact);
    }
    for (guint index = 0; index < page_count; index++)
        gtk_container_set_border_width(GTK_CONTAINER(page_boxes[index]), compact ? 12 : 24);
    gtk_orientable_set_orientation(GTK_ORIENTABLE(toolbar), compact ? GTK_ORIENTATION_VERTICAL : GTK_ORIENTATION_HORIZONTAL);
    gtk_orientable_set_orientation(GTK_ORIENTABLE(filters), compact ? GTK_ORIENTATION_VERTICAL : GTK_ORIENTATION_HORIZONTAL);
    gtk_flow_box_set_max_children_per_line(GTK_FLOW_BOX(apps_grid), compact ? 1 : 3);
    gtk_header_bar_set_title(GTK_HEADER_BAR(store_header), compact ? "OğuzDows" : "OğuzDows Mağaza");
    gtk_header_bar_set_subtitle(GTK_HEADER_BAR(store_header), compact ? NULL : "Keşfet · İncele · Onayla");
    gtk_button_set_label(GTK_BUTTON(voice_button), compact ? "" : "Rıfkı’dan dinle");
    gtk_button_set_image(GTK_BUTTON(voice_button), compact ? gtk_image_new_from_icon_name("audio-volume-high-symbolic", GTK_ICON_SIZE_BUTTON) : NULL);
    gtk_button_set_always_show_image(GTK_BUTTON(voice_button), TRUE);
}

static gboolean configured(GtkWidget *widget, GdkEventConfigure *event, gpointer data) {
    (void)widget; (void)data;
    if (compact != (event->width < 720)) fit_layout(event->width);
    return FALSE;
}

static void build(void) {
    apps = g_ptr_array_new_with_free_func(app_free);
    window = gtk_application_window_new(application);
    gtk_window_set_title(GTK_WINDOW(window), "OğuzDows Mağaza");
    gtk_window_set_icon_name(GTK_WINDOW(window), "oguzdows-store");
    GdkDisplay *display = gtk_widget_get_display(window);
    GdkMonitor *monitor = gdk_display_get_primary_monitor(display);
    if (!monitor) monitor = gdk_display_get_monitor(display, 0);
    GdkRectangle workarea = {0, 0, 1024, 768};
    if (monitor) gdk_monitor_get_workarea(monitor, &workarea);
    compact = workarea.width < 720;
    gtk_window_set_default_size(GTK_WINDOW(window), MIN(1000, workarea.width - 24), MIN(710, workarea.height - 48));
    gtk_widget_set_size_request(window, 320, 400);
    g_signal_connect(window, "delete-event", G_CALLBACK(closing), NULL);
    GtkWidget *header = gtk_header_bar_new();
    store_header = header;
    gtk_header_bar_set_title(GTK_HEADER_BAR(header), "OğuzDows Mağaza");
    gtk_header_bar_set_subtitle(GTK_HEADER_BAR(header), "Keşfet · İncele · Onayla");
    gtk_header_bar_set_show_close_button(GTK_HEADER_BAR(header), TRUE);
    gtk_window_set_titlebar(GTK_WINDOW(window), header);
    voice_button = gtk_button_new_with_label("Rıfkı’dan dinle");
    gtk_widget_set_tooltip_text(voice_button, "Rıfkı’dan mağaza rehberini dinle");
    atk_object_set_name(gtk_widget_get_accessible(voice_button), "Rıfkı’dan mağaza rehberini dinle");
    g_signal_connect(voice_button, "clicked", G_CALLBACK(narrate), NULL);
    gtk_header_bar_pack_end(GTK_HEADER_BAR(header), voice_button);
    GtkWidget *root = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0);
    content = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 0);
    gtk_box_pack_start(GTK_BOX(root), content, TRUE, TRUE, 0);
    sidebar = gtk_list_box_new();
    gtk_widget_set_size_request(sidebar, 146, -1);
    gtk_style_context_add_class(gtk_widget_get_style_context(sidebar), "store-sidebar");
    const gchar *names[] = {"Keşfet", "Kurulu", "Güncellemeler", "Kaynaklar", NULL};
    const gchar *pages[] = {"discover", "installed", "updates", "sources"};
    const gchar *icons[] = {"view-grid-symbolic", "emblem-ok-symbolic", "software-update-available-symbolic", "network-server-symbolic"};
    for (guint index = 0; names[index]; index++) {
        GtkWidget *row = gtk_list_box_row_new(), *line = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
        GtkWidget *title = label(names[index], NULL);
        nav_titles[index] = title;
        gtk_container_set_border_width(GTK_CONTAINER(line), 12);
        gtk_box_pack_start(GTK_BOX(line), gtk_image_new_from_icon_name(icons[index], GTK_ICON_SIZE_MENU), FALSE, FALSE, 0);
        gtk_box_pack_start(GTK_BOX(line), title, TRUE, TRUE, 0);
        gtk_container_add(GTK_CONTAINER(row), line);
        gtk_widget_set_tooltip_text(row, names[index]);
        atk_object_set_name(gtk_widget_get_accessible(row), names[index]);
        g_object_set_data(G_OBJECT(row), "page", (gpointer)pages[index]);
        gtk_container_add(GTK_CONTAINER(sidebar), row);
    }
    g_signal_connect(sidebar, "row-selected", G_CALLBACK(navigation), NULL);
    gtk_box_pack_start(GTK_BOX(content), sidebar, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(content), gtk_separator_new(GTK_ORIENTATION_VERTICAL), FALSE, FALSE, 0);
    stack = gtk_stack_new();
    /* Sistem azaltılmış hareket / eski GPU tercihini geçersiz kılma. */
    gtk_stack_set_transition_type(GTK_STACK(stack), GTK_STACK_TRANSITION_TYPE_NONE);
    gtk_box_pack_start(GTK_BOX(content), stack, TRUE, TRUE, 0);

    GtkWidget *discover = page("Bir fikir, bir uygulamayla başlar.", "Günlük işler, üretkenlik ve biraz eğlence. Yerel seçkiyi çevrimdışı keşfet; daha fazlası için Flathub’da ara.");
    gtk_style_context_add_class(gtk_widget_get_style_context(discover), "discover-page");
    toolbar = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    search_entry = gtk_search_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(search_entry), "Uygulama veya işlev ara…");
    g_signal_connect(search_entry, "search-changed", G_CALLBACK(refilter), NULL);
    gtk_box_pack_start(GTK_BOX(toolbar), search_entry, TRUE, TRUE, 0);
    remote_button = action(toolbar, "Flathub’da ara", G_CALLBACK(remote_search), NULL);
    gtk_box_pack_start(GTK_BOX(discover), toolbar, FALSE, FALSE, 0);
    filters = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    category = gtk_combo_box_text_new();
    const gchar *categories[] = {"Tümü", "İnternet", "Ofis", "Görsel", "Ses ve video", "Geliştirme", "Oyun", "Araçlar", NULL};
    for (guint index = 0; categories[index]; index++) gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(category), categories[index], categories[index]);
    gtk_combo_box_set_active(GTK_COMBO_BOX(category), 0);
    g_signal_connect(category, "changed", G_CALLBACK(refilter), NULL);
    gtk_box_pack_start(GTK_BOX(filters), category, TRUE, TRUE, 0);
    action(filters, "Yerel kataloğa dön", G_CALLBACK(reset_catalog), NULL);
    gtk_box_pack_start(GTK_BOX(discover), filters, FALSE, FALSE, 0);
    results_info = label("Katalog okunuyor…", "dim-label");
    gtk_box_pack_start(GTK_BOX(discover), results_info, FALSE, FALSE, 0);
    no_results = label("Bu filtrelerle uygulama bulunamadı. Aramanı kısalt, başka kategori seç veya yerel kataloğa dön.", "dim-label");
    gtk_widget_set_no_show_all(no_results, TRUE);
    gtk_box_pack_start(GTK_BOX(discover), no_results, FALSE, FALSE, 0);
    apps_grid = gtk_flow_box_new(); gtk_flow_box_set_selection_mode(GTK_FLOW_BOX(apps_grid), GTK_SELECTION_NONE);
    gtk_flow_box_set_min_children_per_line(GTK_FLOW_BOX(apps_grid), 1);
    gtk_flow_box_set_max_children_per_line(GTK_FLOW_BOX(apps_grid), 3);
    gtk_flow_box_set_row_spacing(GTK_FLOW_BOX(apps_grid), 12); gtk_flow_box_set_column_spacing(GTK_FLOW_BOX(apps_grid), 12);
    gtk_flow_box_set_homogeneous(GTK_FLOW_BOX(apps_grid), TRUE);
    gtk_flow_box_set_filter_func(GTK_FLOW_BOX(apps_grid), app_filter, NULL, NULL);
    gtk_box_pack_start(GTK_BOX(discover), apps_grid, FALSE, FALSE, 0);
    add_page(discover, "discover");

    GtkWidget *details = page("Uygulamanı tanı.", "Geliştirici, kaynak ve izinler önemli. Bir uygulamanın mağazada bulunması zararsız olduğu anlamına gelmez.");
    action(details, "← Keşfet’e dön", G_CALLBACK(back_clicked), NULL);
    GtkWidget *heading = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 16);
    detail_icon = gtk_image_new_from_icon_name("application-x-executable", GTK_ICON_SIZE_DIALOG);
    gtk_image_set_pixel_size(GTK_IMAGE(detail_icon), 64);
    gtk_box_pack_start(GTK_BOX(heading), detail_icon, FALSE, FALSE, 0);
    detail_title = label("", "page-title"); gtk_box_pack_start(GTK_BOX(heading), detail_title, TRUE, TRUE, 0);
    gtk_box_pack_start(GTK_BOX(details), heading, FALSE, FALSE, 0);
    detail_summary = label("", "dim-label"); gtk_box_pack_start(GTK_BOX(details), detail_summary, FALSE, FALSE, 0);
    source_combo = gtk_combo_box_text_new(); g_signal_connect(source_combo, "changed", G_CALLBACK(source_changed), NULL);
    gtk_box_pack_start(GTK_BOX(details), source_combo, FALSE, FALSE, 0);
    scope_note = label("", "scope-note");
    gtk_box_pack_start(GTK_BOX(details), scope_note, FALSE, FALSE, 0);
    launch_button = action(details, "Aç · Kurulu uygulamayı başlat", G_CALLBACK(launch_clicked), NULL);
    gtk_widget_set_sensitive(launch_button, FALSE);
    install_button = action(details, "Kur / güncelle · planı incele…", G_CALLBACK(install_clicked), NULL);
    gtk_style_context_add_class(gtk_widget_get_style_context(install_button), "suggested-action");
    detail_text = gtk_text_view_new(); gtk_text_view_set_editable(GTK_TEXT_VIEW(detail_text), FALSE);
    gtk_text_view_set_wrap_mode(GTK_TEXT_VIEW(detail_text), GTK_WRAP_WORD_CHAR);
    gtk_text_view_set_left_margin(GTK_TEXT_VIEW(detail_text), 12); gtk_text_view_set_right_margin(GTK_TEXT_VIEW(detail_text), 12);
    gtk_widget_set_size_request(detail_text, -1, 230);
    gtk_box_pack_start(GTK_BOX(details), detail_text, TRUE, TRUE, 0);
    add_page(details, "detail");

    GtkWidget *updates = page("Güncel kal. Kontrol sende.", "Sistem ve kullanıcı Flatpak güncellemeleri ayrı planlanır. Açılışta arama veya otomatik indirme yoktur.");
    action(updates, "Sistem güncellemeleri · planı göster…", G_CALLBACK(updates_clicked), "system");
    action(updates, "Kullanıcı Flatpak güncellemeleri · planı göster…", G_CALLBACK(updates_clicked), "flatpak");
    gtk_box_pack_start(GTK_BOX(updates), label("Sistem paket listelerini OğuzDows Güncelleyici’den yenileyebilirsin. Bu mağaza paket kaldırmaz. Kullanıcı / sistem Flatpak kapsamları aynı değildir; sistem kapsamı ve kaldırma için gelişmiş merkezi kullan.", "dim-label"), FALSE, FALSE, 0);
    action(updates, "Gelişmiş paket merkezi", G_CALLBACK(open_advanced), NULL);
    add_page(updates, "updates");

    GtkWidget *sources = page("Kaynağını bil.", "OğuzDows arayüzü. İmzalı sistem paketleri + isteğe bağlı kullanıcı Flathub’u. Snap veya karışık dağıtım tabanları yok.");
    source_status = label("Kaynaklar okunuyor…", NULL);
    gtk_box_pack_start(GTK_BOX(sources), source_status, FALSE, FALSE, 0);
    setup_button = action(sources, "Flathub’u ekle / doğrula…", G_CALLBACK(setup_clicked), NULL);
    gtk_box_pack_start(GTK_BOX(sources), label("İlk anahtar edinimi resmî HTTPS tanımına dayanır. Farklı / imzasız bir kaynak sessizce değiştirilmez. Başka kaynak isteyen uygulamalar otomatik depo ekleyemez. Gerekli lisans, telif ve gerçek depo kimlikleri gizlenmez.", "dim-label"), FALSE, FALSE, 0);
    action(sources, "Gelişmiş paket merkezi · GNOME Software", G_CALLBACK(open_advanced), NULL);
    add_page(sources, "sources");

    GtkWidget *bottom = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 10);
    gtk_container_set_border_width(GTK_CONTAINER(bottom), 12);
    spinner = gtk_spinner_new(); gtk_box_pack_start(GTK_BOX(bottom), spinner, FALSE, FALSE, 0);
    status_label = label("Hazır", "dim-label"); gtk_label_set_max_width_chars(GTK_LABEL(status_label), 100);
    gtk_box_pack_start(GTK_BOX(bottom), status_label, TRUE, TRUE, 0);
    gtk_box_pack_start(GTK_BOX(root), gtk_separator_new(GTK_ORIENTATION_HORIZONTAL), FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(root), bottom, FALSE, FALSE, 0);
    gtk_container_add(GTK_CONTAINER(window), root);
    GtkCssProvider *css = gtk_css_provider_new();
    gtk_css_provider_load_from_data(css,
        ".store-sidebar row { padding: 0; border: 0; border-radius: 11px; margin: 3px 4px; }"
        ".page-title { font-size: 25px; font-weight: 800; } .compact-store .page-title { font-size: 20px; } .dim-label { opacity: 1; }"
        ".app-card { background-image: none; background-color: @theme_base_color; border: 1px solid @borders; border-radius: 12px; }"
        ".app-card .app-icon { padding: 4px; } .scope-note { padding: 12px; border: 1px solid @borders; border-radius: 8px; }"
        ".app-card:hover { border-color: #278f92; } .app-name { font-size: 15px; font-weight: bold; }"
        ".source-chip { font-size: 11px; color: @theme_fg_color; font-weight: 600; }", -1, NULL);
    gtk_style_context_add_provider_for_screen(gtk_widget_get_screen(window), GTK_STYLE_PROVIDER(css), GTK_STYLE_PROVIDER_PRIORITY_APPLICATION);
    g_object_unref(css);
    fit_layout(workarea.width - 24);
    g_signal_connect(window, "configure-event", G_CALLBACK(configured), NULL);
    gtk_widget_show_all(window);
    gtk_list_box_select_row(GTK_LIST_BOX(sidebar), gtk_list_box_get_row_at_index(GTK_LIST_BOX(sidebar), 0));
    view(initial_page);
    run_service(CATALOG, "catalog", NULL, NULL, NULL);
}

#ifdef OGUZDOWS_STORE_TEST
static void capture_window(GtkWidget *target, const gchar *name) {
    GdkWindow *native = gtk_widget_get_window(target);
    gint width, height; gtk_window_get_size(GTK_WINDOW(target), &width, &height);
    GdkPixbuf *image = gdk_pixbuf_get_from_window(native, 0, 0, width, height);
    g_assert_nonnull(image);
    gchar *path = g_build_filename(smoke_directory, name, NULL);
    GError *error = NULL;
    g_assert_true(gdk_pixbuf_save(image, path, "png", &error, NULL));
    g_assert_no_error(error); g_object_unref(image); g_free(path);
    GdkMonitor *monitor = gdk_display_get_monitor_at_window(gtk_widget_get_display(target), native);
    g_assert_nonnull(monitor);
    GdkRectangle workarea; gdk_monitor_get_workarea(monitor, &workarea);
    g_print("GTK yerleşim %s: %dx%d, çalışma alanı %dx%d\n", name, width, height, workarea.width, workarea.height);
    g_assert_cmpint(width, <=, workarea.width);
    g_assert_cmpint(height, <=, workarea.height);
}
static void capture(const gchar *name) { capture_window(window, name); }

static gboolean cancel_test_plan(gpointer data) {
    const gchar *image_name = data ? (const gchar *)data : "store-native-confirmation.png";
    GList *windows = gtk_window_list_toplevels();
    gboolean found = FALSE;
    for (GList *it = windows; it; it = it->next) {
        if (it->data == window || !GTK_IS_DIALOG(it->data)) continue;
        GtkDialog *dialog = GTK_DIALOG(it->data);
        GtkWidget *button = gtk_window_get_default_widget(GTK_WINDOW(dialog));
        g_assert_nonnull(button);
        g_assert_cmpint(gtk_dialog_get_response_for_widget(dialog, button), ==, GTK_RESPONSE_CANCEL);
        capture_window(GTK_WIDGET(dialog), image_name);
        gtk_dialog_response(dialog, GTK_RESPONSE_CANCEL);
        found = TRUE;
    }
    g_list_free(windows);
    return found ? G_SOURCE_REMOVE : G_SOURCE_CONTINUE;
}

static gboolean smoke(gpointer data) {
    (void)data;
    if (++smoke_wait > 100) g_error("Yerel mağaza GTK kontrolü zaman aşımı");
    if (busy) return G_SOURCE_CONTINUE;
    switch (smoke_step++) {
        case 0:
            g_assert_cmpuint(apps->len, ==, 27); capture("store-native.png");
            gtk_combo_box_set_active_id(GTK_COMBO_BOX(category), "Görsel"); break;
        case 1: capture("store-native-category.png"); gtk_combo_box_set_active(GTK_COMBO_BOX(category), 0);
            show_app(NULL, g_ptr_array_index(apps, 0)); break;
        case 2: capture("store-native-detail.png");
            g_assert_true(gtk_widget_get_sensitive(launch_button));
            launch_clicked(NULL, NULL); view("sources"); break;
        case 3: g_assert_nonnull(strstr(gtk_label_get_text(GTK_LABEL(status_label)), "gerçek uygulama çalıştırılmadı"));
            capture("store-native-sources.png"); view("updates"); break;
        case 4: capture("store-native-updates.png"); view("installed"); break;
        case 5: {
            capture("store-native-installed.png"); view("discover");
            GdkMonitor *monitor = gdk_display_get_monitor_at_window(gtk_widget_get_display(window), gtk_widget_get_window(window));
            GdkRectangle workarea; gdk_monitor_get_workarea(monitor, &workarea);
            gtk_window_resize(GTK_WINDOW(window), MIN(420, workarea.width - 24), MIN(680, workarea.height - 48)); break;
        }
        case 6: {
            gint width, height; gtk_window_get_size(GTK_WINDOW(window), &width, &height);
            (void)height;
            g_assert_true(compact); g_assert_cmpint(width, <=, 480);
            g_assert_false(gtk_widget_get_visible(nav_titles[0]));
            capture("store-native-compact.png");
            show_app(NULL, g_ptr_array_index(apps, 0)); break;
        }
        case 7: capture("store-native-compact-detail.png");
            view("discover"); gtk_entry_set_text(GTK_ENTRY(search_entry), "__bulunamayan_uygulama__"); refilter(NULL, NULL); break;
        case 8: {
            g_assert_true(gtk_widget_get_visible(no_results)); capture("store-native-empty.png");
            JsonObject *plan = json_object_new();
            JsonArray *changes = json_array_new();
            json_array_add_string_element(changes, "Güvenli test; paket kurulmaz");
            json_object_set_array_member(plan, "changes", changes);
            json_object_set_string_member(plan, "token", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
            json_object_set_string_member(plan, "detail", "Yalnızca GTK / varsayılan Vazgeç testi. APT / Flatpak motoru çağrılmaz.");
            g_timeout_add(100, cancel_test_plan, NULL);
            show_plan(plan);
            g_assert_false(busy);
            g_assert_nonnull(strstr(gtk_label_get_text(GTK_LABEL(status_label)), "Plan iptal edildi"));
            json_object_unref(plan);
            view("sources"); break;
        }
        case 9:
            g_timeout_add(100, cancel_test_plan, (gpointer)"store-native-source-confirmation.png");
            setup_clicked(NULL, NULL);
            g_assert_false(busy);
            g_print("Gerçek GTK: ekran sınırları, masaüstü / kompakt görünüm, boş sonuç, plan / kaynak varsayılan iptalleri geçti. Kaynak eklenmedi, paket kurulmadı.\n");
            g_application_quit(G_APPLICATION(application)); return G_SOURCE_REMOVE;
    }
    return G_SOURCE_CONTINUE;
}
#endif

static void activate(GApplication *app, gpointer data) {
    (void)app; (void)data;
    if (!window) build();
    gtk_window_present(GTK_WINDOW(window));
}

static gint command_line(GApplication *app, GApplicationCommandLine *line, gpointer data) {
    (void)data;
    gint argc; gchar **argv = g_application_command_line_get_arguments(line, &argc);
    if (argc == 2 && !strcmp(argv[1], "--quit")) {
        if (busy) { g_application_command_line_printerr(line, "Paket işi sürüyor; iptal edilmedi.\n"); g_strfreev(argv); return 1; }
        g_application_quit(app); g_strfreev(argv); return 0;
    }
    if (argc == 2 && !strcmp(argv[1], "--updates")) initial_page = "updates";
    else if (argc == 2 && !strcmp(argv[1], "--setup")) initial_page = "sources";
#ifdef OGUZDOWS_STORE_TEST
    else if (argc == 3 && !strcmp(argv[1], "--smoke-test")) {
        smoke_directory = g_strdup(argv[2]); g_mkdir_with_parents(smoke_directory, 0700);
    }
#endif
    else if (argc != 1) { g_application_command_line_printerr(line, "Kullanım: oguzdows-store [--updates|--setup|--quit]\n"); g_strfreev(argv); return 2; }
    g_application_activate(app);
    view(initial_page);
#ifdef OGUZDOWS_STORE_TEST
    if (smoke_directory) g_timeout_add(300, smoke, NULL);
#endif
    g_strfreev(argv); return 0;
}

int main(int argc, char **argv) {
    /* Başsız ABI / bağımlılık raporu; pencere, D-Bus veya paket işçisi açmaz. */
    if (argc == 2 && !strcmp(argv[1], "--version")) {
        /* GTK henüz locale başlatmadı; g_print C locale'inde Türkçeyi bozar. */
        setlocale(LC_ALL, "");
        g_print("OğuzDows Mağaza · GTK %u.%u.%u\n", gtk_get_major_version(), gtk_get_minor_version(), gtk_get_micro_version());
        return 0;
    }
    application = gtk_application_new(APP_ID, G_APPLICATION_HANDLES_COMMAND_LINE);
    g_signal_connect(application, "activate", G_CALLBACK(activate), NULL);
    g_signal_connect(application, "command-line", G_CALLBACK(command_line), NULL);
    gint result = g_application_run(G_APPLICATION(application), argc, argv);
    if (apps) g_ptr_array_unref(apps);
    g_free(selected_id); g_free(query_folded); g_free(current_source);
    g_object_unref(application); return result;
}
