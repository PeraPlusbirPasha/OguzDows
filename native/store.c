/* OğuzDows Mağaza 1.1 — derlenen GTK 3 arayüzü.
 * Derleme: scripts/build-native.sh. HTML / webview / Python GTK kabuğu değildir.
 * Paket işlemleri kısa ömürlü, doğrulanmış JSON işçisinde; GTK asla beklemez.
 */
#include <gtk/gtk.h>
#include <json-glib/json-glib.h>
#include <locale.h>
#include <glib/gstdio.h>
#include <string.h>
#include "ui.h"

#ifndef STORE_SERVICE
#define STORE_SERVICE "/usr/lib/oguzdows/store_service.py"
#endif

#define APP_ID "org.oguzdows.YerelMagaza"

typedef struct {
    gchar *id, *name, *summary, *category, *icon, *fallback_icon, *flatpak, *search, *version;
    gboolean installed, flatpak_installed, update_available, featured, available;
} App;

typedef enum { CATALOG, SEARCH, DETAIL, PLAN, APPLY, REMOVE_PLAN, REMOVE_APPLY, SETUP, LAUNCH, HEALTH, REFRESH, COMPARE, BUNDLE_PLAN, BUNDLE_APPLY } Job;
typedef struct { Job job; GSubprocess *process; } Work;

static GtkApplication *application;
static GtkWidget *window, *stack, *sidebar, *search_entry, *apps_grid, *category;
static GtkWidget *status_label, *spinner, *content, *detail_title, *detail_summary;
static GtkWidget *detail_text, *source_combo, *install_button, *detail_icon;
static GtkWidget *remote_button, *source_status, *results_info, *no_results;
static GtkWidget *launch_button, *scope_note, *setup_button, *remove_button, *featured_box, *catalog_title;
static gboolean current_installed, current_launchable, current_update, current_can_remove = TRUE, current_system_available = TRUE;
static GtkWidget *wishlist_button, *wishlist_filter;
static GKeyFile *wishlist;
static gboolean filling_wishlist, wishlist_only;
static GtkWidget *store_header, *voice_button, *toolbar, *filters, *filter_reset, *featured_stack, *apps_heading;
static GtkWidget *nav_titles[4], *page_boxes[4];
static guint page_count;
static gboolean compact, wide, catalog_dirty;
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
static void refilter(GtkWidget *widget, gpointer data);
static void bundle_clicked(GtkButton *button, gpointer data);

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
    g_free(app->icon); g_free(app->fallback_icon); g_free(app->flatpak);
    g_free(app->search); g_free(app->version); g_free(app);
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
    og_ui_setup(dialog);
    fit_message(dialog);
    gtk_dialog_run(GTK_DIALOG(dialog));
    gtk_widget_destroy(dialog);
}

static gboolean confirm(const gchar *title, const gchar *text) {
    GtkWidget *dialog = gtk_message_dialog_new(GTK_WINDOW(window), GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        GTK_MESSAGE_WARNING, GTK_BUTTONS_OK_CANCEL, "%s", title);
    gtk_message_dialog_format_secondary_text(GTK_MESSAGE_DIALOG(dialog), "%s", text);
    og_ui_setup(dialog);
    fit_message(dialog);
    gtk_dialog_set_default_response(GTK_DIALOG(dialog), GTK_RESPONSE_CANCEL);
    gboolean approved = gtk_dialog_run(GTK_DIALOG(dialog)) == GTK_RESPONSE_OK;
    gtk_widget_destroy(dialog);
    return approved;
}

static void update_actions(void) {
    gboolean user = !g_strcmp0(current_source, "flatpak");
    gtk_widget_set_sensitive(launch_button, !busy && current_installed && current_launchable);
    gtk_widget_set_sensitive(remove_button, !busy && current_installed && current_can_remove && (user ? user_flatpak_supported : supports_apt));
    gtk_widget_set_sensitive(install_button, !busy && (user ? remote_available && user_flatpak_supported : supports_apt && current_system_available));
    gtk_button_set_label(GTK_BUTTON(install_button), current_installed ? (current_update ? "Güncelle · planı incele…" : "Güncellemeyi denetle…") : "Yükle · planı incele…");
}

static void set_busy(gboolean value) {
    busy = value;
    /* Reading, scrolling, local filtering and navigation remain responsive.
       Only conflicting operations are gated; package jobs are never killed. */
    GtkWidget *controls[] = {source_combo, remote_button, setup_button};
    for (guint i = 0; i < G_N_ELEMENTS(controls); i++) gtk_widget_set_sensitive(controls[i], !value);
    if (!value) {
        gtk_widget_set_sensitive(remote_button, user_flatpak_supported);
        gtk_widget_set_sensitive(setup_button, user_flatpak_supported);
    }
    update_actions();
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
    if (busy) { status("Paket işlemi bitmeden başka paket merkezi açılmaz."); return; }
    if (!advanced_available) {
        if (confirm("GNOME Yazılımlar bileşenleri kurulsun / tamamlansın mı?", "Sabit GNOME Software + Flatpak eklentisi + PackageKit + ISO639 dil verisi demetinin gerçek paket planı gösterilecek. Henüz kurulum yapılmaz; plan ve yönetici onayı ayrıca gerekir. ARM dahil bu tabanın imzalı adayları doğrulanır. Otomatik başlangıç açılmaz."))
            bundle_clicked(NULL, "software-center");
        return;
    }
    const gchar *argv[] = {"/usr/bin/python3", "-I", "/usr/lib/oguzdows/store.py", NULL};
    GError *error = NULL;
    GSubprocess *process = g_subprocess_newv(argv, G_SUBPROCESS_FLAGS_NONE, &error);
    if (!process) { message("Gelişmiş paket merkezi açılamadı", error->message, GTK_MESSAGE_ERROR); g_error_free(error); }
    else g_object_unref(process);
}

static gboolean is_wished(const gchar *id) {
    return wishlist && id && g_key_file_get_boolean(wishlist, "Wishlist", id, NULL);
}
static void wishlist_changed(GtkToggleButton *button, gpointer data) {
    (void)data;
    if (filling_wishlist || !selected_id || !strcmp(selected_id, "@updates")) return;
    gboolean old = is_wished(selected_id), next = gtk_toggle_button_get_active(button);
    g_key_file_set_boolean(wishlist, "Wishlist", selected_id, next);
    gsize length = 0; gchar *contents = g_key_file_to_data(wishlist, &length, NULL);
    gchar *path = g_build_filename(g_get_user_config_dir(), "oguzdows/store/wishlist.ini", NULL);
    GError *error = NULL;
    if (length > 65536 || !og_ui_write_file(path, contents, (gssize)length, &error)) {
        g_key_file_set_boolean(wishlist, "Wishlist", selected_id, old);
        filling_wishlist = TRUE; gtk_toggle_button_set_active(button, old); filling_wishlist = FALSE;
        status(error ? error->message : "İstek listesi boyut sınırı doldu; önce bazı kayıtları kaldırın."); g_clear_error(&error);
    } else { status(next ? "İstek listesine eklendi · kurulum / ağ isteği yok." : "İstek listesinden çıkarıldı."); refilter(NULL, NULL); }
    g_free(path); g_free(contents);
}
static void wishlist_filter_changed(GtkToggleButton *button, gpointer data) {
    (void)data; wishlist_only = gtk_toggle_button_get_active(button); refilter(NULL, NULL);
}
static void show_report(const gchar *title, const gchar *text) {
    GtkWidget *dialog = gtk_dialog_new_with_buttons(title, GTK_WINDOW(window), GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        "Panoya kopyala", GTK_RESPONSE_APPLY, "Kapat", GTK_RESPONSE_CLOSE, NULL);
    og_ui_setup(dialog); gtk_window_set_default_size(GTK_WINDOW(dialog), compact ? 310 : 640, 440);
    GtkWidget *scroll = gtk_scrolled_window_new(NULL, NULL), *view = gtk_text_view_new();
    gtk_text_view_set_wrap_mode(GTK_TEXT_VIEW(view), GTK_WRAP_WORD_CHAR); gtk_text_view_set_editable(GTK_TEXT_VIEW(view), FALSE);
    gtk_text_view_set_left_margin(GTK_TEXT_VIEW(view), 12); gtk_text_view_set_right_margin(GTK_TEXT_VIEW(view), 12);
    gtk_text_buffer_set_text(gtk_text_view_get_buffer(GTK_TEXT_VIEW(view)), text, -1);
    gtk_container_add(GTK_CONTAINER(scroll), view); gtk_box_pack_start(GTK_BOX(gtk_dialog_get_content_area(GTK_DIALOG(dialog))), scroll, TRUE, TRUE, 0);
    gtk_widget_show_all(dialog);
    while (gtk_dialog_run(GTK_DIALOG(dialog)) == GTK_RESPONSE_APPLY)
        gtk_clipboard_set_text(gtk_clipboard_get(GDK_SELECTION_CLIPBOARD), text, -1);
    gtk_widget_destroy(dialog);
}
static void health_clicked(GtkButton *button, gpointer data) { (void)button; (void)data; run_service(HEALTH, "health", NULL, NULL, NULL); }
static void compare_clicked(GtkButton *button, gpointer data) {
    (void)button; (void)data;
    if (selected_id && !g_str_has_prefix(selected_id, "flatpak:")) run_service(COMPARE, "compare", selected_id, NULL, NULL);
    else status("Kaynak karşılaştırması gözden geçirilmiş sistem / Flatpak eşleri içindir.");
}
static void refresh_lists(GtkButton *button, gpointer data) {
    (void)button; (void)data;
    if (!busy && confirm("İmzalı paket listeleri yenilensin mi?", "Mevcut sistem depolarından yalnız paket listeleri alınır. Yönetici onayı / ağ gerekir; paket kurulmaz, depo eklenmez. Pi’nin kendi imzalı tabanı korunur."))
        run_service(REFRESH, "refresh", NULL, NULL, NULL);
}
static void bundle_clicked(GtkButton *button, gpointer data) {
    (void)button;
    if (busy) return;
    const gchar *id = data;
    run_service(BUNDLE_PLAN, "plan", id, "system", NULL);
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
    GtkWidget *line = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 12);
    gtk_container_set_border_width(GTK_CONTAINER(line), 10);
    GtkWidget *image = gtk_image_new(); app_image(image, app, 48);
    gtk_box_pack_start(GTK_BOX(line), image, FALSE, FALSE, 0);
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 5);
    GtkWidget *name = label(app->name, "app-name");
    gtk_label_set_max_width_chars(GTK_LABEL(name), 22);
    GtkWidget *summary = label(app->summary, "dim-label");
    gtk_label_set_max_width_chars(GTK_LABEL(summary), 26);
    gtk_label_set_lines(GTK_LABEL(summary), 2); gtk_label_set_ellipsize(GTK_LABEL(summary), PANGO_ELLIPSIZE_END);
    gtk_box_pack_start(GTK_BOX(box), name, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(box), summary, TRUE, TRUE, 0);
    gchar *state = g_strdup_printf("%s%s%s", app->update_available ? "↑ Güncelleme var" : app->flatpak_installed ? "● Bu hesapta kurulu" : app->installed ? "● Sistemde kurulu" : app->category,
        *app->version ? " · " : "", app->version);
    GtkWidget *state_label = label(state, "source-chip"); g_free(state);
    gtk_label_set_max_width_chars(GTK_LABEL(state_label), 26);
    gtk_label_set_lines(GTK_LABEL(state_label), 1); gtk_label_set_ellipsize(GTK_LABEL(state_label), PANGO_ELLIPSIZE_END);
    gtk_box_pack_start(GTK_BOX(box), state_label, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(line), box, TRUE, TRUE, 0);
    gtk_container_add(GTK_CONTAINER(button), line);
    gtk_widget_set_size_request(button, 212, 118);
    gtk_widget_set_tooltip_text(button, app->summary);
    gtk_container_add(GTK_CONTAINER(apps_grid), button);
    g_object_set_data(G_OBJECT(gtk_widget_get_parent(button)), "app", app);
    g_signal_connect(button, "clicked", G_CALLBACK(show_app), app);
}

static void feature(App *app) {
    const gchar *topic = !strcmp(app->category, "Görsel") ? "create" : !strcmp(app->category, "Ses ve video") ? "media" : "work";
    const gchar *tab = !strcmp(topic, "create") ? "Üret" : !strcmp(topic, "media") ? "Dinle" : "Çalış";
    const gchar *headline = !strcmp(topic, "create") ? "Fikirlerine alan aç." : !strcmp(topic, "media") ? "Sesi aç. Keyfine bak." : "Gününü kolaylaştır.";
    /* GtkOverlay does not paint a CSS box. A real GtkBox owns the opaque
     * editorial surface/padding; overlay art still contributes no minimum. */
    GtkWidget *hero = gtk_box_new(GTK_ORIENTATION_VERTICAL, 0), *overlay = gtk_overlay_new();
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 10);
    gtk_box_pack_start(GTK_BOX(hero), overlay, TRUE, TRUE, 0);
    gtk_widget_set_halign(box, GTK_ALIGN_START);
    gtk_style_context_add_class(gtk_widget_get_style_context(hero), "store-feature");
    gchar *css = g_strconcat("feature-", topic, NULL); gtk_style_context_add_class(gtk_widget_get_style_context(hero), css); g_free(css);
    gtk_box_pack_start(GTK_BOX(box), label("ÖNE ÇIKANLAR · AÇIK KAYNAK", "eyebrow"), FALSE, FALSE, 0);
    GtkWidget *title = label(headline, "feature-title"); gtk_label_set_max_width_chars(GTK_LABEL(title), 20);
    gtk_box_pack_start(GTK_BOX(box), title, FALSE, FALSE, 0);
    GtkWidget *name = label(app->name, "feature-app"); gtk_box_pack_start(GTK_BOX(box), name, FALSE, FALSE, 0);
    GtkWidget *summary = label(app->summary, "feature-summary"); gtk_label_set_max_width_chars(GTK_LABEL(summary), 28);
    gtk_box_pack_start(GTK_BOX(box), summary, FALSE, FALSE, 0);
    GtkWidget *button = gtk_button_new_with_label("Keşfet  →"); gtk_widget_set_halign(button, GTK_ALIGN_START);
    gtk_style_context_add_class(gtk_widget_get_style_context(button), "hero-cta");
    g_signal_connect(button, "clicked", G_CALLBACK(show_app), app);
    gtk_box_pack_start(GTK_BOX(box), button, FALSE, FALSE, 0); gtk_container_add(GTK_CONTAINER(overlay), box);
    gchar *path = g_strdup_printf("/usr/share/oguzdows/ui/store-%s.png", topic);
    GdkPixbuf *pixels = gdk_pixbuf_new_from_file_at_scale(path, 190, 150, TRUE, NULL); g_free(path);
    GtkWidget *art = pixels ? gtk_image_new_from_pixbuf(pixels) : gtk_image_new_from_icon_name(app->fallback_icon, GTK_ICON_SIZE_DIALOG);
    if (pixels) g_object_unref(pixels);
    gtk_widget_set_no_show_all(art, compact); gtk_widget_set_visible(art, !compact);
    gtk_widget_set_halign(art, GTK_ALIGN_END); gtk_widget_set_valign(art, GTK_ALIGN_CENTER);
    gtk_overlay_add_overlay(GTK_OVERLAY(overlay), art);
    gtk_overlay_set_overlay_pass_through(GTK_OVERLAY(overlay), art, TRUE); g_object_set_data(G_OBJECT(hero), "art", art);
    gtk_stack_add_titled(GTK_STACK(featured_stack), hero, app->id, tab);
    gtk_widget_show_all(hero); gtk_widget_set_visible(art, !compact);
}

static void category_shortcut(GtkButton *button, gpointer data) {
    (void)button; gtk_entry_set_text(GTK_ENTRY(search_entry), "");
    gtk_combo_box_set_active_id(GTK_COMBO_BOX(category), data);
    refilter(NULL, NULL);
}

static gboolean matches(App *app) {
    if (!app) return TRUE;
    if (wishlist_only && !is_wished(app->id)) return FALSE;
    if (installed_only && !app->installed && !app->flatpak_installed) return FALSE;
    const gchar *chosen = gtk_combo_box_get_active_id(GTK_COMBO_BOX(category));
    if (chosen && strcmp(chosen, "Tümü") && strcmp(chosen, app->category)) return FALSE;
    if (query_folded && *query_folded) {
        return strstr(app->search, query_folded) != NULL;
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
    gtk_widget_set_tooltip_text(results_info, count); atk_object_set_name(gtk_widget_get_accessible(results_info), count); g_free(count);
    count = g_strdup_printf("%u / %u", visible, apps->len);
    gtk_label_set_text(GTK_LABEL(results_info), count); g_free(count);
    gtk_widget_set_visible(no_results, !visible);
    const gchar *chosen = gtk_combo_box_get_active_id(GTK_COMBO_BOX(category));
    gtk_widget_set_visible(featured_box, !wishlist_only && !installed_only && (!query_folded || !*query_folded) && (!chosen || !strcmp(chosen, "Tümü")) && !catalog_dirty);
    gtk_label_set_text(GTK_LABEL(catalog_title), installed_only ? "Senin uygulamaların" : "Keşfet");
    gtk_widget_set_visible(catalog_title, installed_only);
    gtk_label_set_text(GTK_LABEL(apps_heading), installed_only ? "Kurulu uygulamalar" : "Bir sonraki favorini bul");
}

static void clear_apps(void) {
    GList *features = gtk_container_get_children(GTK_CONTAINER(featured_stack));
    for (GList *it = features; it; it = it->next) gtk_widget_destroy(it->data);
    g_list_free(features);
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
        app->update_available = bool_member(item, "update_available"); app->featured = bool_member(item, "featured");
        app->version = g_strdup(string_member(item, "version"));
        app->available = !json_object_has_member(item, "system_available") || bool_member(item, "system_available");
        gchar *searchable = g_strjoin(" ", app->name, app->summary, app->category, app->id, app->flatpak, NULL);
        app->search = g_utf8_casefold(searchable, -1); g_free(searchable);
        g_ptr_array_add(apps, app); app_card(app);
    }
    guint features = 0;
    for (guint index = 0; index < apps->len && features < 3; index++) {
        App *app = g_ptr_array_index(apps, index);
        if (app->featured) { feature(app); features++; }
    }
    gtk_widget_show_all(featured_box);

    gtk_widget_show_all(apps_grid);
    refilter(NULL, NULL);
}

static void show_plan(JsonObject *root, gboolean bundle) {
    const gchar *token = string_member(root, "token");
    if (strlen(token) != 64) { status("Doğrulanabilir plan özeti alınamadı. Kurulum yapılmadı."); return; }
    if (!json_object_has_member(root, "changes") || !JSON_NODE_HOLDS_ARRAY(json_object_get_member(root, "changes"))) {
        status("Paket değişikliği listesi alınamadı. Kurulum yapılmadı."); return;
    }
    if (!json_array_get_length(json_object_get_array_member(root, "changes"))) {
        message("Her şey yerinde", "Bu planda değişecek paket yok.", GTK_MESSAGE_INFO); return;
    }
    GtkWidget *dialog = gtk_dialog_new_with_buttons("Önce incele · Sonra onayla", GTK_WINDOW(window), GTK_DIALOG_MODAL | GTK_DIALOG_DESTROY_WITH_PARENT,
        "Vazgeç", GTK_RESPONSE_CANCEL, "Bu planı uygula", GTK_RESPONSE_ACCEPT, NULL);
    og_ui_setup(dialog);
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
    gboolean removing = !strcmp(string_member(root, "intent"), "remove");
    gchar *saved_token = g_strdup(token), *id = g_strdup(*string_member(root, "identifier") ? string_member(root, "identifier") : selected_id), *source = g_strdup(*string_member(root, "source") ? string_member(root, "source") : current_source);
    gint response = gtk_dialog_run(GTK_DIALOG(dialog));
    gtk_widget_destroy(dialog);
    if (response == GTK_RESPONSE_ACCEPT) run_service(bundle ? BUNDLE_APPLY : removing ? REMOVE_APPLY : APPLY, removing ? "remove-apply" : "apply", id, source, saved_token);
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
            if (work->job == SEARCH) catalog_dirty = TRUE;
            if (work->job == CATALOG || work->job == SEARCH) show_catalog(root);
            if (work->job == DETAIL) {
                gtk_text_buffer_set_text(gtk_text_view_get_buffer(GTK_TEXT_VIEW(detail_text)), string_member(root, "detail"), -1);
                current_installed = bool_member(root, "installed"); current_launchable = bool_member(root, "can_launch");
                current_update = bool_member(root, "update_available");
                current_can_remove = !json_object_has_member(root, "can_remove") || bool_member(root, "can_remove"); update_actions();
            }
            if (work->job == PLAN || work->job == REMOVE_PLAN || work->job == BUNDLE_PLAN) show_plan(root, work->job == BUNDLE_PLAN);
            if (work->job == HEALTH || work->job == COMPARE) show_report(work->job == HEALTH ? "Mağaza · Yerel teşhis" : "APT / Flatpak · Kaynak karşılaştırması", string_member(root, "detail"));
            if (work->job == SETUP || work->job == REFRESH || work->job == BUNDLE_APPLY) run_service(CATALOG, "catalog", NULL, NULL, NULL);
            if (work->job == APPLY || work->job == REMOVE_APPLY) {
                catalog_dirty = TRUE;
                if (selected_id && strcmp(selected_id, "@updates") && strcmp(selected_id, "flatpak-support") && strcmp(selected_id, "software-center")) run_service(DETAIL, "detail", selected_id, current_source, NULL);
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
           (job == PLAN || job == REMOVE_PLAN || job == BUNDLE_PLAN) ? "Gerçek paket planı çözümleniyor… Henüz kurulum onayı verilmedi." :
           (job == APPLY || job == REMOVE_APPLY || job == BUNDLE_APPLY) ? "Onayladığın işlem sürüyor… Bilgisayarı ve bu pencereyi kapatma." :
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
    current_installed = FALSE; current_launchable = FALSE; current_update = FALSE; current_can_remove = TRUE; update_actions();
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
    current_system_available = app->available;
    filling_wishlist = TRUE; gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(wishlist_button), is_wished(app->id)); filling_wishlist = FALSE;
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

static void remove_clicked(GtkButton *button, gpointer data) {
    (void)button; (void)data;
    if (!busy && current_installed && selected_id && current_source)
        run_service(REMOVE_PLAN, "remove-plan", selected_id, current_source, NULL);
}

static void updates_clicked(GtkButton *button, gpointer data) {
    (void)button;
    if (busy) return;
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
    if (busy) return;
    const gchar *query = gtk_entry_get_text(GTK_ENTRY(search_entry));
    if (g_utf8_strlen(query, -1) < 2) { status("Flathub araması için en az iki karakter yaz."); return; }
    if (!user_flatpak_supported) { status("Bu mimaride kullanıcı Flathub uygulamaları sunulmuyor. İmzalı sistem paketlerini kullanabilirsin."); return; }
    if (!remote_available) { view("sources"); status("Önce Flathub kaynağını açık onayla ekleyin."); return; }
    gtk_combo_box_set_active(GTK_COMBO_BOX(category), 0);
    gboolean dirty = catalog_dirty; catalog_dirty = FALSE;
    view("discover"); catalog_dirty = dirty;
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
    gtk_label_set_line_wrap_mode(GTK_LABEL(text), PANGO_WRAP_WORD_CHAR);
    gtk_label_set_max_width_chars(GTK_LABEL(text), 30);
    g_signal_connect(button, "clicked", callback, data);
    gtk_box_pack_start(GTK_BOX(box), button, FALSE, FALSE, 0);
    return button;
}

static GtkWidget *page(const gchar *title, const gchar *subtitle) {
    GtkWidget *box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 16);
    gtk_container_set_border_width(GTK_CONTAINER(box), compact ? 8 : 24);
    if (page_count < G_N_ELEMENTS(page_boxes)) page_boxes[page_count++] = box;
    gtk_box_pack_start(GTK_BOX(box), label(title, "page-title"), FALSE, FALSE, 0);
    if (subtitle && *subtitle) gtk_box_pack_start(GTK_BOX(box), label(subtitle, "dim-label"), FALSE, FALSE, 0);
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
    compact = width < 720; wide = width >= 1140;
    GtkStyleContext *style = gtk_widget_get_style_context(window);
    if (compact) gtk_style_context_add_class(style, "compact-store");
    else gtk_style_context_remove_class(style, "compact-store");
    gtk_widget_set_size_request(sidebar, compact ? 48 : 146, -1);
    for (guint index = 0; index < G_N_ELEMENTS(nav_titles); index++) {
        gtk_widget_set_no_show_all(nav_titles[index], compact);
        gtk_widget_set_visible(nav_titles[index], !compact);
    }
    for (guint index = 0; index < page_count; index++)
        gtk_container_set_border_width(GTK_CONTAINER(page_boxes[index]), compact ? 8 : 24);
    gtk_entry_set_width_chars(GTK_ENTRY(search_entry), compact ? 8 : 20);
    gtk_button_set_label(GTK_BUTTON(remote_button), compact ? "Flathub" : "Flathub’da ara");
    gtk_button_set_label(GTK_BUTTON(filter_reset), compact ? "Temizle" : "Yerel kataloğa dön");
    gtk_flow_box_set_max_children_per_line(GTK_FLOW_BOX(apps_grid), compact ? 1 : width >= 1140 ? 3 : 2);
    GList *heroes = gtk_container_get_children(GTK_CONTAINER(featured_stack));
    for (GList *it = heroes; it; it = it->next) {
        GtkWidget *art = g_object_get_data(G_OBJECT(it->data), "art");
        if (art) { gtk_widget_set_no_show_all(art, compact); gtk_widget_set_visible(art, !compact); }
    }
    g_list_free(heroes);
    gtk_header_bar_set_title(GTK_HEADER_BAR(store_header), compact ? "OğuzDows" : "OğuzDows Mağaza");
    gtk_header_bar_set_subtitle(GTK_HEADER_BAR(store_header), compact ? NULL : "Keşfet · İncele · Onayla");
    gtk_button_set_label(GTK_BUTTON(voice_button), compact ? "" : "Rıfkı’dan dinle");
    gtk_button_set_image(GTK_BUTTON(voice_button), compact ? gtk_image_new_from_icon_name("audio-volume-high-symbolic", GTK_ICON_SIZE_BUTTON) : NULL);
    gtk_button_set_always_show_image(GTK_BUTTON(voice_button), TRUE);
}

static gboolean configured(GtkWidget *widget, GdkEventConfigure *event, gpointer data) {
    (void)widget; (void)data;
    if (compact != (event->width < 720) || wide != (event->width >= 1140)) fit_layout(event->width);
    return FALSE;
}

static void build(void) {
    wishlist = g_key_file_new();
    gchar *wish_path = g_build_filename(g_get_user_config_dir(), "oguzdows/store/wishlist.ini", NULL), *wish_data = NULL;
    if (og_ui_read_file(wish_path, 65536, &wish_data)) g_key_file_load_from_data(wishlist, wish_data, -1, G_KEY_FILE_NONE, NULL);
    g_free(wish_path); g_free(wish_data);
    apps = g_ptr_array_new_with_free_func(app_free);
    window = gtk_application_window_new(application);
    gtk_window_set_title(GTK_WINDOW(window), "OğuzDows Mağaza");
    gtk_window_set_icon_name(GTK_WINDOW(window), "oguzdows-store");
    og_ui_setup(window);
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
    og_ui_stack_setup(stack);
    gtk_box_pack_start(GTK_BOX(content), stack, TRUE, TRUE, 0);

    GtkWidget *discover = page("Keşfet", NULL);
    gtk_box_set_spacing(GTK_BOX(discover), 12);
    GList *discover_children = gtk_container_get_children(GTK_CONTAINER(discover));
    catalog_title = discover_children->data; g_list_free(discover_children);
    gtk_widget_set_no_show_all(catalog_title, TRUE);
    gtk_style_context_add_class(gtk_widget_get_style_context(discover), "discover-page");
    toolbar = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    search_entry = gtk_search_entry_new(); gtk_entry_set_placeholder_text(GTK_ENTRY(search_entry), "Uygulama veya işlev ara…");
    g_signal_connect(search_entry, "search-changed", G_CALLBACK(refilter), NULL);
    gtk_box_pack_start(GTK_BOX(toolbar), search_entry, TRUE, TRUE, 0);
    remote_button = action(toolbar, "Flathub’da ara", G_CALLBACK(remote_search), NULL);
    gtk_widget_set_tooltip_text(remote_button, "Flathub’da açık ağ araması yap");
    atk_object_set_name(gtk_widget_get_accessible(remote_button), "Flathub’da ara");
    gtk_box_pack_start(GTK_BOX(discover), toolbar, FALSE, FALSE, 0);
    filters = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    category = gtk_combo_box_text_new();
    const gchar *categories[] = {"Tümü", "İnternet", "Ofis", "Görsel", "Ses ve video", "Geliştirme", "Oyun", "Araçlar", NULL};
    for (guint index = 0; categories[index]; index++) gtk_combo_box_text_append(GTK_COMBO_BOX_TEXT(category), categories[index], categories[index]);
    gtk_combo_box_set_active(GTK_COMBO_BOX(category), 0);
    g_signal_connect(category, "changed", G_CALLBACK(refilter), NULL);
    gtk_box_pack_start(GTK_BOX(filters), category, TRUE, TRUE, 0);
    filter_reset = action(filters, "Yerel kataloğa dön", G_CALLBACK(reset_catalog), NULL);
    gtk_widget_set_tooltip_text(filter_reset, "Arama ve filtreleri temizle, yerel kataloğa dön");
    gtk_box_pack_start(GTK_BOX(discover), filters, FALSE, FALSE, 0);
    wishlist_filter = gtk_toggle_button_new_with_label("★ İstek listem");
    gtk_widget_set_tooltip_text(wishlist_filter, "Yalnız bu hesapta kaydettiğin uygulamalar · ağ / kurulum yok");
    g_signal_connect(wishlist_filter, "toggled", G_CALLBACK(wishlist_filter_changed), NULL);
    gtk_box_pack_start(GTK_BOX(discover), wishlist_filter, FALSE, FALSE, 0);
    featured_box = gtk_box_new(GTK_ORIENTATION_VERTICAL, 10);
    featured_stack = gtk_stack_new(); og_ui_stack_setup(featured_stack);
    gtk_stack_set_homogeneous(GTK_STACK(featured_stack), TRUE);
    GtkWidget *switcher = gtk_stack_switcher_new(); gtk_stack_switcher_set_stack(GTK_STACK_SWITCHER(switcher), GTK_STACK(featured_stack));
    gtk_style_context_add_class(gtk_widget_get_style_context(switcher), "feature-tabs");
    gtk_widget_set_halign(switcher, GTK_ALIGN_START);
    gtk_box_pack_start(GTK_BOX(featured_box), featured_stack, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(featured_box), switcher, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(discover), featured_box, FALSE, FALSE, 0);
    GtkWidget *quick_categories = gtk_flow_box_new();
    gtk_flow_box_set_selection_mode(GTK_FLOW_BOX(quick_categories), GTK_SELECTION_NONE);
    gtk_flow_box_set_max_children_per_line(GTK_FLOW_BOX(quick_categories), 4);
    const gchar *quick_names[] = {"Üretkenlik", "Yaratıcılık", "Oyun zamanı", "Günlük araçlar"};
    const gchar *quick_values[] = {"Ofis", "Görsel", "Oyun", "Araçlar"};
    for (guint i = 0; i < G_N_ELEMENTS(quick_names); i++) {
        GtkWidget *chip = gtk_button_new_with_label(quick_names[i]);
        gtk_style_context_add_class(gtk_widget_get_style_context(chip), "category-chip");
        g_signal_connect(chip, "clicked", G_CALLBACK(category_shortcut), (gpointer)quick_values[i]);
        gtk_container_add(GTK_CONTAINER(quick_categories), chip);
    }
    gtk_box_pack_start(GTK_BOX(discover), quick_categories, FALSE, FALSE, 0);
    GtkWidget *app_heading_line = gtk_box_new(GTK_ORIENTATION_HORIZONTAL, 8);
    apps_heading = label("Bir sonraki favorini bul", "section-title");
    gtk_box_pack_start(GTK_BOX(app_heading_line), apps_heading, TRUE, TRUE, 0);
    results_info = label("", "dim-label");
    gtk_box_pack_end(GTK_BOX(app_heading_line), results_info, FALSE, FALSE, 0);
    gtk_box_pack_start(GTK_BOX(discover), app_heading_line, FALSE, FALSE, 0);
    no_results = label("Bu filtrelerle uygulama bulunamadı. Aramanı kısalt, başka kategori seç veya yerel kataloğa dön.", "dim-label");
    gtk_widget_set_no_show_all(no_results, TRUE);
    gtk_box_pack_start(GTK_BOX(discover), no_results, FALSE, FALSE, 0);
    apps_grid = gtk_flow_box_new(); gtk_flow_box_set_selection_mode(GTK_FLOW_BOX(apps_grid), GTK_SELECTION_NONE);
    gtk_flow_box_set_min_children_per_line(GTK_FLOW_BOX(apps_grid), 1);
    gtk_flow_box_set_max_children_per_line(GTK_FLOW_BOX(apps_grid), 2);
    gtk_flow_box_set_row_spacing(GTK_FLOW_BOX(apps_grid), 4); gtk_flow_box_set_column_spacing(GTK_FLOW_BOX(apps_grid), 12);
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
    wishlist_button = gtk_toggle_button_new_with_label("★ İstek listeme ekle / çıkar");
    g_signal_connect(wishlist_button, "toggled", G_CALLBACK(wishlist_changed), NULL);
    gtk_box_pack_start(GTK_BOX(details), wishlist_button, FALSE, FALSE, 0);
    action(details, "Sistem / Flatpak kaynaklarını karşılaştır…", G_CALLBACK(compare_clicked), NULL);
    detail_summary = label("", "dim-label"); gtk_box_pack_start(GTK_BOX(details), detail_summary, FALSE, FALSE, 0);
    source_combo = gtk_combo_box_text_new(); g_signal_connect(source_combo, "changed", G_CALLBACK(source_changed), NULL);
    gtk_box_pack_start(GTK_BOX(details), source_combo, FALSE, FALSE, 0);
    scope_note = label("", "scope-note");
    gtk_box_pack_start(GTK_BOX(details), scope_note, FALSE, FALSE, 0);
    launch_button = action(details, "Aç · Kurulu uygulamayı başlat", G_CALLBACK(launch_clicked), NULL);
    gtk_widget_set_sensitive(launch_button, FALSE);
    install_button = action(details, "Kur / güncelle · planı incele…", G_CALLBACK(install_clicked), NULL);
    gtk_style_context_add_class(gtk_widget_get_style_context(install_button), "suggested-action");
    remove_button = action(details, "Kaldır · önce planı incele…", G_CALLBACK(remove_clicked), NULL);
    gtk_style_context_add_class(gtk_widget_get_style_context(remove_button), "destructive-action");
    gtk_widget_set_sensitive(remove_button, FALSE);
    detail_text = gtk_text_view_new(); gtk_text_view_set_editable(GTK_TEXT_VIEW(detail_text), FALSE);
    gtk_text_view_set_wrap_mode(GTK_TEXT_VIEW(detail_text), GTK_WRAP_WORD_CHAR);
    gtk_text_view_set_left_margin(GTK_TEXT_VIEW(detail_text), 12); gtk_text_view_set_right_margin(GTK_TEXT_VIEW(detail_text), 12);
    gtk_widget_set_size_request(detail_text, -1, 230);
    gtk_box_pack_start(GTK_BOX(details), detail_text, TRUE, TRUE, 0);
    add_page(details, "detail");

    GtkWidget *updates = page("Güncel kal. Kontrol sende.", "Sistem ve kullanıcı Flatpak güncellemeleri ayrı planlanır. Açılışta arama veya otomatik indirme yoktur.");
    action(updates, "Sistem güncellemeleri · planı göster…", G_CALLBACK(updates_clicked), "system");
    action(updates, "Kullanıcı Flatpak güncellemeleri · planı göster…", G_CALLBACK(updates_clicked), "flatpak");
    gtk_box_pack_start(GTK_BOX(updates), label("Sistem paket listelerini OğuzDows Güncelleyici’den yenileyebilirsin. Kaldırma uygulama ayrıntılarından plan / onay ile yapılır. Kişisel dosyalar korunur; başka sistem paketi gerektiriyorsa kaldırma reddedilir. Kullanıcı / sistem Flatpak kapsamları aynı değildir.", "dim-label"), FALSE, FALSE, 0);
    action(updates, "Gelişmiş paket merkezi", G_CALLBACK(open_advanced), NULL);
    add_page(updates, "updates");

    GtkWidget *sources = page("Kaynağını bil.", "OğuzDows arayüzü. İmzalı sistem paketleri + isteğe bağlı kullanıcı Flathub’u. Snap veya karışık dağıtım tabanları yok.");
    action(sources, "Flatpak bileşenlerini kur / tamamla…", G_CALLBACK(bundle_clicked), "flatpak-support");
    action(sources, "GNOME Yazılımlar’ı kur / tamamla…", G_CALLBACK(bundle_clicked), "software-center");
    action(sources, "Paket listelerini yenile…", G_CALLBACK(refresh_lists), NULL);
    action(sources, "Yerel bileşen teşhisi / raporu…", G_CALLBACK(health_clicked), NULL);
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
    fit_layout(workarea.width - 24);
    g_signal_connect(window, "configure-event", G_CALLBACK(configured), NULL);
    gtk_widget_show_all(window);
    update_actions();
    gtk_list_box_select_row(GTK_LIST_BOX(sidebar), gtk_list_box_get_row_at_index(GTK_LIST_BOX(sidebar), 0));
    view(initial_page);
    run_service(CATALOG, "catalog", NULL, NULL, NULL);
}

#ifdef OGUZDOWS_STORE_TEST
static void width_diagnostic(GtkWidget *widget, gpointer depth) {
    gint minimum, natural; gtk_widget_get_preferred_width(widget, &minimum, &natural);
    if (minimum > 220) g_print("Minimum width %u %s / %s: %d (natural %d)\n", GPOINTER_TO_UINT(depth), G_OBJECT_TYPE_NAME(widget), gtk_widget_get_name(widget), minimum, natural);
    if (GTK_IS_CONTAINER(widget)) gtk_container_foreach(GTK_CONTAINER(widget), width_diagnostic, GUINT_TO_POINTER(GPOINTER_TO_UINT(depth) + 1));
}
static void assert_feature_background(void) {
    GtkWidget *hero = gtk_stack_get_visible_child(GTK_STACK(featured_stack));
    gint x, y;
    g_assert_true(gtk_widget_translate_coordinates(hero, window, gtk_widget_get_allocated_width(hero) - 18, 18, &x, &y));
    GdkPixbuf *sample = gdk_pixbuf_get_from_window(gtk_widget_get_window(window), x, y, 1, 1);
    g_assert_nonnull(sample);
    guchar *rgb = gdk_pixbuf_get_pixels(sample);
    /* All three original editorial gradients are dark; white hero text must
     * never be painted directly on the light application's page surface. */
    g_assert_cmpuint(MAX(rgb[0], MAX(rgb[1], rgb[2])), <, 200);
    g_object_unref(sample);
}
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
    if (width > workarea.width) width_diagnostic(target, NULL);
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

static gboolean approve_fixture_plan(gpointer data) {
    GList *windows = gtk_window_list_toplevels(); gboolean found = FALSE;
    for (GList *it = windows; it; it = it->next) {
        if (it->data == window || !GTK_IS_DIALOG(it->data)) continue;
        GtkDialog *dialog = GTK_DIALOG(it->data);
        const gchar *title = gtk_window_get_title(GTK_WINDOW(dialog));
        if (!title || strcmp(title, "Önce incele · Sonra onayla")) continue;
        GtkWidget *button = gtk_window_get_default_widget(GTK_WINDOW(dialog));
        g_assert_cmpint(gtk_dialog_get_response_for_widget(dialog, button), ==, GTK_RESPONSE_CANCEL);
        capture_window(GTK_WIDGET(dialog), data ? data : "store-native-removal-plan.png");
        /* Test build + fixture path only. No real service is reachable here. */
        gtk_dialog_response(dialog, GTK_RESPONSE_ACCEPT); found = TRUE;
    }
    g_list_free(windows); return found ? G_SOURCE_REMOVE : G_SOURCE_CONTINUE;
}

static gboolean dismiss_report(gpointer data) {
    GList *windows = gtk_window_list_toplevels(); gboolean found = FALSE;
    for (GList *it = windows; it; it = it->next) {
        if (it->data == window || !GTK_IS_DIALOG(it->data)) continue;
        capture_window(it->data, data); gtk_dialog_response(GTK_DIALOG(it->data), GTK_RESPONSE_CLOSE); found = TRUE;
    }
    g_list_free(windows); return found ? G_SOURCE_REMOVE : G_SOURCE_CONTINUE;
}

static gboolean smoke(gpointer data) {
    (void)data;
    if (++smoke_wait > 100) g_error("Yerel mağaza GTK kontrolü zaman aşımı");
    if (busy) return G_SOURCE_CONTINUE;
    switch (smoke_step++) {
        case 0:
            g_assert_cmpuint(apps->len, ==, 29); g_assert_true(gtk_widget_get_visible(featured_box)); capture("store-native.png"); assert_feature_background();
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
            gtk_window_resize(GTK_WINDOW(window), MIN(680, workarea.width - 24), MIN(680, workarea.height - 48)); break;
        }
        case 6: {
            g_assert_true(compact);
            GdkMonitor *monitor = gdk_display_get_monitor_at_window(gtk_widget_get_display(window), gtk_widget_get_window(window));
            GdkRectangle workarea; gdk_monitor_get_workarea(monitor, &workarea);
            gtk_window_resize(GTK_WINDOW(window), MIN(420, workarea.width - 24), MIN(680, workarea.height - 48)); break;
        }
        case 7: {
            gint width, height; gtk_window_get_size(GTK_WINDOW(window), &width, &height);
            (void)height;
            g_assert_true(compact);
            if (width > 480) width_diagnostic(window, NULL);
            g_assert_cmpint(width, <=, 480);
            g_assert_false(gtk_widget_get_visible(nav_titles[0]));
            capture("store-native-compact.png"); assert_feature_background();
            show_app(NULL, g_ptr_array_index(apps, 0)); break;
        }
        case 8: capture("store-native-compact-detail.png");
            view("discover"); gtk_entry_set_text(GTK_ENTRY(search_entry), "__bulunamayan_uygulama__"); refilter(NULL, NULL); break;
        case 9: {
            g_assert_true(gtk_widget_get_visible(no_results)); capture("store-native-empty.png");
            JsonObject *plan = json_object_new();
            JsonArray *changes = json_array_new();
            json_array_add_string_element(changes, "Güvenli test; paket kurulmaz");
            json_object_set_array_member(plan, "changes", changes);
            json_object_set_string_member(plan, "token", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
            json_object_set_string_member(plan, "detail", "Yalnızca GTK / varsayılan Vazgeç testi. APT / Flatpak motoru çağrılmaz.");
            g_timeout_add(100, cancel_test_plan, NULL);
            show_plan(plan, FALSE);
            g_assert_false(busy);
            g_assert_nonnull(strstr(gtk_label_get_text(GTK_LABEL(status_label)), "Plan iptal edildi"));
            json_object_unref(plan);
            view("sources"); break;
        }
        case 10:
            g_timeout_add(100, cancel_test_plan, (gpointer)"store-native-source-confirmation.png");
            setup_clicked(NULL, NULL);
            g_assert_false(busy);
            show_app(NULL, g_ptr_array_index(apps, 0)); break;
        case 11:
            g_assert_true(current_installed); g_assert_true(gtk_widget_get_sensitive(remove_button));
            g_timeout_add(100, approve_fixture_plan, NULL); remove_clicked(NULL, NULL); break;
        case 12:
            g_assert_false(current_installed); g_assert_false(gtk_widget_get_sensitive(remove_button));
            g_assert_false(gtk_widget_get_sensitive(launch_button));
            g_assert_true(gtk_widget_get_sensitive(install_button));
            capture("store-native-after-fixture-removal.png");
            g_timeout_add(100, approve_fixture_plan, NULL); install_clicked(NULL, NULL); break;
        case 13:
            g_assert_true(current_installed); g_assert_true(gtk_widget_get_sensitive(launch_button));
            gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(wishlist_button), TRUE);
            g_assert_true(is_wished(selected_id));
            gtk_entry_set_text(GTK_ENTRY(search_entry), ""); refilter(NULL, NULL);
            gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(wishlist_filter), TRUE);
            g_assert_true(matches(g_ptr_array_index(apps, 0))); g_assert_false(matches(g_ptr_array_index(apps, 1)));
            gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(wishlist_filter), FALSE);
            g_timeout_add(100, dismiss_report, "store-native-health.png"); health_clicked(NULL, NULL); break;
        case 14:
            g_assert_nonnull(strstr(gtk_label_get_text(GTK_LABEL(status_label)), "TEST health"));
            g_timeout_add(100, dismiss_report, "store-native-compare.png"); compare_clicked(NULL, NULL); break;
        case 15:
            g_assert_nonnull(strstr(gtk_label_get_text(GTK_LABEL(status_label)), "TEST compare"));
            g_timeout_add(100, approve_fixture_plan, "store-native-flatpak-plan.png"); bundle_clicked(NULL, "flatpak-support"); break;
        case 16: {
            gchar *state = g_strconcat(g_getenv("OGUZDOWS_STORE_FIXTURE_STATE"), ".bundle", NULL), *value = NULL;
            g_assert_true(g_file_get_contents(state, &value, NULL, NULL)); g_assert_cmpstr(value, ==, "flatpak-support"); g_free(state); g_free(value);
            g_timeout_add(100, approve_fixture_plan, "store-native-software-plan.png"); bundle_clicked(NULL, "software-center"); break;
        }
        case 17: {
            gchar *state = g_strconcat(g_getenv("OGUZDOWS_STORE_FIXTURE_STATE"), ".bundle", NULL), *value = NULL;
            g_assert_true(g_file_get_contents(state, &value, NULL, NULL)); g_assert_cmpstr(value, ==, "software-center"); g_free(state); g_free(value);
            g_assert_cmpstr(selected_id, ==, "firefox");
            g_print("::notice title=C Store action wiring::{\"native_gtk\":true,\"fixture_not_packages\":true,\"install_remove_apply_wiring\":true,\"cancel_default\":true,\"wishlist_filter\":true,\"offline_comparison\":true,\"engine_bundle_plan_apply_wiring\":true,\"health_dialog\":true,\"physical_gpu\":false}\n");
            g_print("Gerçek GTK: ekran sınırları, masaüstü / kompakt görünüm, boş sonuç, plan / kaynak varsayılan iptalleri geçti. Kaynak eklenmedi, paket kurulmadı.\n");
            g_application_quit(G_APPLICATION(application)); return G_SOURCE_REMOVE;
        }
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
        gchar *state_path = g_build_filename(smoke_directory, ".fixture-only-state", NULL);
        g_unlink(state_path); g_setenv("OGUZDOWS_STORE_FIXTURE_STATE", state_path, TRUE); g_free(state_path);
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
#ifdef OGUZDOWS_STORE_TEST
    if (argc == 3 && !strcmp(argv[1], "--smoke-test")) {
        gchar *absolute = g_canonicalize_filename(argv[2], NULL), *home = g_build_filename(absolute, ".private-config", NULL);
        g_mkdir_with_parents(home, 0700); g_setenv("XDG_CONFIG_HOME", home, TRUE); g_free(home); g_free(absolute);
    }
#endif
    application = gtk_application_new(APP_ID, G_APPLICATION_HANDLES_COMMAND_LINE);
    g_signal_connect(application, "activate", G_CALLBACK(activate), NULL);
    g_signal_connect(application, "command-line", G_CALLBACK(command_line), NULL);
    gint result = g_application_run(G_APPLICATION(application), argc, argv);
    if (apps) g_ptr_array_unref(apps);
    g_free(selected_id); g_free(query_folded); g_free(current_source);
    if (wishlist) g_key_file_unref(wishlist);
    g_object_unref(application); return result;
}
