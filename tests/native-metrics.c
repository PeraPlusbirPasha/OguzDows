/* SPDX-License-Identifier: GPL-3.0-or-later
 * Gerçek metrics.c: salt /proc fixture + gerçek host sayaçlarının şekli.
 * Ağ trafiği üretmez, root istemez, fiziksel cihaz / hız garantisi değildir.
 */
#define _POSIX_C_SOURCE 200809L
#include "metrics.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

static void file(const char *root, const char *name, const char *value) {
    char path[4096];
    int length = snprintf(path, sizeof path, "%s/%s", root, name);
    assert(length > 0 && (size_t)length < sizeof path);
    FILE *out = fopen(path, "w"); assert(out);
    assert(fputs(value, out) >= 0); assert(!fclose(out));
}
static void near(double actual, double expected) { assert(fabs(actual - expected) < .00001); }

int main(int argc, char **argv) {
    assert(argc == 2);
    const char *root = argv[1]; char path[4096];
    assert(snprintf(path, sizeof path, "%s/net", root) > 0); assert(!mkdir(path, 0700));
    file(root, "stat", "cpu 100 20 30 400 10 5 3 2 99 33\ncpu0 9 9 9 9\n");
    file(root, "meminfo", "MemTotal: 1000 kB\nMemAvailable: 250 kB\n");
    file(root, "net/dev", "Inter-| Receive | Transmit\n face |bytes packets errs drop fifo frame compressed multicast|bytes packets errs drop fifo colls carrier compressed\n  lo: 9999 0 0 0 0 0 0 0 9999 0 0 0 0 0 0 0\n eth0: 1000 0 0 0 0 0 0 0 2000 0 0 0 0 0 0 0\n bad: no\n");
    OgSnapshot first, second; OgUsage usage;
    og_metrics_read(&first, root);
    assert(first.cpu_valid && first.memory_valid && first.network_valid);
    assert(first.cpu_total == 570); assert(first.cpu_idle == 410);  /* guest iki defa yok */
    assert(first.memory_total == 1024000 && first.memory_available == 256000);
    assert(first.network_count == 1 && !strcmp(first.network[0].name, "eth0"));
    og_metrics_usage(NULL, &first, &usage);
    assert(!usage.cpu_valid && !usage.network_valid && usage.memory_valid);
    near(usage.memory_percent, 75);
    first.seconds = 10;
    second = first; second.seconds = 12; second.cpu_total += 200; second.cpu_idle += 50;
    second.network[0].received += 4096; second.network[0].sent += 2048;
    og_metrics_usage(&first, &second, &usage);
    assert(usage.cpu_valid && usage.network_valid); near(usage.cpu_percent, 75);
    near(usage.receive_rate, 2048); near(usage.send_rate, 1024);
    second.network[0].received = 10; /* NIC reset: uint64 underflow yok */
    og_metrics_usage(&first, &second, &usage); near(usage.receive_rate, 0); near(usage.send_rate, 1024);
    strcpy(second.network[0].name, "new0");
    og_metrics_usage(&first, &second, &usage); near(usage.receive_rate, 0); near(usage.send_rate, 0);
    second.seconds = 1000;
    og_metrics_usage(&first, &second, &usage); assert(!usage.network_valid);
    second.cpu_total = 1;
    og_metrics_usage(&first, &second, &usage); assert(!usage.cpu_valid);
    file(root, "meminfo", "MemTotal: 1000 kB\nMemFree: 100 kB\nBuffers: 20 kB\nCached: 80 kB\nSReclaimable: 30 kB\nShmem: 10 kB\n");
    og_metrics_read(&second, root); assert(second.memory_valid && second.memory_available == 220 * 1024);
    file(root, "meminfo", "MemTotal: 1000 kB\nMemAvailable: 2000 kB\n");
    og_metrics_read(&second, root); assert(second.memory_available == second.memory_total);
    file(root, "stat", "cpu 18446744073709551615 1 0 0 0\n");
    file(root, "meminfo", "MemTotal: 999 GB\nMemFree: 42 kB\n");
    og_metrics_read(&second, root); assert(!second.cpu_valid && !second.memory_valid);
    og_metrics_read(&second, "/does-not-exist");
    assert(!second.cpu_valid && !second.memory_valid && !second.network_valid);
    og_metrics_read(&second, "/proc");
    assert(second.cpu_valid && second.memory_valid && second.cpu_total > second.cpu_idle);
    assert(second.seconds > 0);
    puts("native metrics: deltas, guest, memory fallback, hotplug, reset, overflow, missing files OK");
    return 0;
}
