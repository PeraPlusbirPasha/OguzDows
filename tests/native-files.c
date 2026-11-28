/* SPDX-License-Identifier: GPL-3.0-or-later
 * Real FD / atomic I/O tests. No display, package transaction or user's files. */
#define _POSIX_C_SOURCE 200809L
#include "ui.h"
#include <glib/gstdio.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <string.h>

static gchar *root;
static void expect_rejected(const gchar *path) {
    GError *error = NULL;
    g_assert_false(og_ui_write_file(path, "must not write", -1, &error));
    g_assert_nonnull(error); g_clear_error(&error);
}
static void atomic_private(void) {
    gchar *path = g_build_filename(root, "library", "data.ini", NULL);
    GError *error = NULL;
    g_assert_true(og_ui_write_file(path, "önce", -1, &error)); g_assert_no_error(error);
    struct stat before, after;
    g_assert_cmpint(lstat(path, &before), ==, 0);
    g_assert_cmpint(before.st_mode & 0777, ==, 0600);
    g_assert_true(og_ui_write_file(path, "sonra", -1, &error)); g_assert_no_error(error);
    g_assert_cmpint(lstat(path, &after), ==, 0);
    g_assert_cmpuint(before.st_ino, !=, after.st_ino);
    gchar *text = NULL; g_assert_true(og_ui_read_file(path, 100, &text));
    g_assert_cmpstr(text, ==, "sonra"); g_free(text);
    gchar *large = g_malloc0(2 * 1024 * 1024 + 2);
    memset(large, 'x', 2 * 1024 * 1024 + 1);
    g_assert_false(og_ui_write_file(path, large, -1, &error)); g_assert_nonnull(error); g_clear_error(&error); g_free(large);
    g_assert_true(og_ui_read_file(path, 100, &text)); g_assert_cmpstr(text, ==, "sonra"); g_free(text);
    gchar *parent = g_path_get_dirname(path); g_assert_cmpint(g_unlink(path), ==, 0); g_assert_cmpint(g_rmdir(parent), ==, 0);
    g_free(parent); g_free(path);
}
static void no_redirect_or_special_file(void) {
    gchar *target = g_build_filename(root, "original.txt", NULL), *link = g_build_filename(root, "redirect", NULL);
    g_assert_true(og_ui_write_file(target, "preserve", -1, NULL));
    g_assert_cmpint(symlink(target, link), ==, 0); expect_rejected(link); g_assert_cmpint(g_unlink(link), ==, 0);
    g_assert_cmpint(mkfifo(link, 0600), ==, 0); expect_rejected(link); g_assert_cmpint(g_unlink(link), ==, 0);
    g_assert_cmpint(g_mkdir(link, 0700), ==, 0); expect_rejected(link); g_assert_cmpint(g_rmdir(link), ==, 0);
    g_assert_cmpint(symlink(root, link), ==, 0);
    gchar *child = g_build_filename(link, "not-created", "data.ini", NULL); expect_rejected(child); g_free(child);
    g_assert_cmpint(g_unlink(link), ==, 0);
    gchar *text = NULL; g_assert_true(og_ui_read_file(target, 100, &text)); g_assert_cmpstr(text, ==, "preserve"); g_free(text);
    expect_rejected("relative.ini");
    child = g_strconcat(root, "/../escaped", NULL); expect_rejected(child); g_free(child);
    child = g_strconcat(root, "/", NULL); expect_rejected(child); g_free(child);
    g_assert_cmpint(g_unlink(target), ==, 0); g_free(target); g_free(link);
}
static void ownership_and_parent(void) {
    gchar *directory = g_build_filename(root, "shared", NULL), *path = g_build_filename(directory, "data", NULL);
    g_assert_cmpint(g_mkdir(directory, 0700), ==, 0);
    g_assert_cmpint(g_chmod(directory, 0777), ==, 0); expect_rejected(path);
    g_assert_cmpint(g_chmod(directory, 0700), ==, 0);
    g_assert_true(og_ui_write_file(path, "private", -1, NULL));
    if (getuid() == 0) {
        g_assert_cmpint(chown(path, 65534, 65534), ==, 0); expect_rejected(path);
        g_assert_cmpint(chown(path, 0, 0), ==, 0);
    }
    g_assert_cmpint(g_unlink(path), ==, 0); g_assert_cmpint(g_rmdir(directory), ==, 0);
    g_free(path); g_free(directory);
}
static guint descriptor_count(void) {
    GDir *directory = g_dir_open("/proc/self/fd", 0, NULL); g_assert_nonnull(directory);
    guint count = 0; while (g_dir_read_name(directory)) count++;
    g_dir_close(directory); return count;
}
static void descriptors_and_temporary_files(void) {
    gchar *path = g_build_filename(root, "repeated.ini", NULL);
    guint before = descriptor_count();
    for (guint i = 0; i < 64; i++) {
        g_assert_true(og_ui_write_file(path, "data", -1, NULL));
        expect_rejected("relative.ini");
    }
    g_assert_cmpuint(descriptor_count(), ==, before);
    g_assert_cmpint(g_unlink(path), ==, 0); g_free(path);
    GDir *directory = g_dir_open(root, 0, NULL); g_assert_nonnull(directory);
    g_assert_null(g_dir_read_name(directory)); g_dir_close(directory);
}
int main(int argc, char **argv) {
    g_test_init(&argc, &argv, NULL);
    root = g_dir_make_tmp("oguzdows-native-files-XXXXXX", NULL); g_assert_nonnull(root);
    g_test_add_func("/files/01-atomic-private-and-bounded", atomic_private);
    g_test_add_func("/files/02-no-redirect-or-special-files", no_redirect_or_special_file);
    g_test_add_func("/files/03-owned-private-parent", ownership_and_parent);
    g_test_add_func("/files/04-no-fd-or-temporary-leak", descriptors_and_temporary_files);
    gint result = g_test_run();
    g_assert_cmpint(g_rmdir(root), ==, 0); g_free(root); return result;
}
