/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef OGUZDOWS_UI_H
#define OGUZDOWS_UI_H
#include <gtk/gtk.h>
gboolean og_ui_read_file(const char *path, gsize maximum, gchar **contents);
void og_ui_setup(GtkWidget *window);
GtkWidget *og_ui_action(const char *icon, const char *text);
void og_ui_feedback(void);
gboolean og_ui_launch_control(const char *action, GError **error);
#endif
