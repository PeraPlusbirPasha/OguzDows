/* SPDX-License-Identifier: GPL-3.0-or-later */
#define _POSIX_C_SOURCE 200809L
#include "metrics.h"
#include <ctype.h>
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static FILE *open_proc(const char *root, const char *name) {
    char path[4096];
    int length = snprintf(path, sizeof path, "%s/%s", root, name);
    return length > 0 && (size_t)length < sizeof path ? fopen(path, "r") : NULL;
}

static bool add(uint64_t *target, uint64_t value) {
    if (UINT64_MAX - *target < value) return false;
    *target += value;
    return true;
}

static void cpu_read(OgSnapshot *snapshot, const char *root) {
    FILE *stream = open_proc(root, "stat");
    if (!stream) return;
    char line[1024], name[8];
    uint64_t fields[8] = {0};
    if (fgets(line, sizeof line, stream)) {
        int count = sscanf(line, "%7s %"SCNu64" %"SCNu64" %"SCNu64" %"SCNu64" %"SCNu64" %"SCNu64" %"SCNu64" %"SCNu64,
            name, &fields[0], &fields[1], &fields[2], &fields[3], &fields[4], &fields[5], &fields[6], &fields[7]);
        if (count >= 5 && !strcmp(name, "cpu")) {
            bool valid = true;
            /* guest/guest_nice ilk iki alana DAHİLDİR: ikinci kez ekleme. */
            for (int i = 0; i < 8; i++) valid = add(&snapshot->cpu_total, fields[i]) && valid;
            snapshot->cpu_idle = fields[3];
            valid = add(&snapshot->cpu_idle, fields[4]) && valid;
            snapshot->cpu_valid = valid && snapshot->cpu_total > 0;
        }
    }
    fclose(stream);
}

static void memory_read(OgSnapshot *snapshot, const char *root) {
    FILE *stream = open_proc(root, "meminfo");
    if (!stream) return;
    char line[256], key[64], unit[16];
    uint64_t total = 0, available = 0, free_value = 0, buffers = 0, cached = 0, reclaim = 0, shared = 0;
    bool have_available = false, have_free = false;
    while (fgets(line, sizeof line, stream)) {
        uint64_t value;
        if (sscanf(line, "%63s %"SCNu64" %15s", key, &value, unit) != 3 || strcmp(unit, "kB")) continue;
        if (!strcmp(key, "MemTotal:")) total = value;
        else if (!strcmp(key, "MemAvailable:")) { available = value; have_available = true; }
        else if (!strcmp(key, "MemFree:")) { free_value = value; have_free = true; }
        else if (!strcmp(key, "Buffers:")) buffers = value;
        else if (!strcmp(key, "Cached:")) cached = value;
        else if (!strcmp(key, "SReclaimable:")) reclaim = value;
        else if (!strcmp(key, "Shmem:")) shared = value;
    }
    fclose(stream);
    if (!total || total > UINT64_MAX / 1024 || (!have_available && !have_free)) return;
    if (!have_available) {
        available = free_value;
        if (!add(&available, buffers) || !add(&available, cached) || !add(&available, reclaim)) return;
        available = available > shared ? available - shared : 0;
    }
    if (available > total) available = total;
    snapshot->memory_total = total * 1024;
    snapshot->memory_available = available * 1024;
    snapshot->memory_valid = true;
}

static void network_read(OgSnapshot *snapshot, const char *root) {
    FILE *stream = open_proc(root, "net/dev");
    if (!stream) return;
    char line[2048];
    while (fgets(line, sizeof line, stream)) {
        char *separator = strchr(line, ':');
        if (!separator) continue;
        *separator = '\0';
        char *name = line;
        while (isspace((unsigned char)*name)) name++;
        size_t length = strlen(name);
        while (length && isspace((unsigned char)name[length - 1])) name[--length] = '\0';
        if (!length || length >= sizeof snapshot->network[0].name || !strcmp(name, "lo") || snapshot->network_count >= OGUZ_NET_LIMIT) continue;
        uint64_t fields[16];
        char *cursor = separator + 1;
        bool valid = true;
        for (int i = 0; i < 16; i++) {
            while (isspace((unsigned char)*cursor)) cursor++;
            if (!isdigit((unsigned char)*cursor)) { valid = false; break; }
            errno = 0;
            char *end;
            fields[i] = strtoull(cursor, &end, 10);
            if (errno || cursor == end) { valid = false; break; }
            cursor = end;
        }
        if (!valid) continue;
        OgNetwork *network = &snapshot->network[snapshot->network_count++];
        memcpy(network->name, name, length + 1);
        network->received = fields[0]; network->sent = fields[8];
    }
    snapshot->network_valid = !ferror(stream);
    fclose(stream);
}

void og_metrics_read(OgSnapshot *snapshot, const char *proc_root) {
    memset(snapshot, 0, sizeof *snapshot);
    struct timespec now;
    if (!clock_gettime(CLOCK_MONOTONIC, &now)) snapshot->seconds = now.tv_sec + now.tv_nsec / 1e9;
    cpu_read(snapshot, proc_root);
    memory_read(snapshot, proc_root);
    network_read(snapshot, proc_root);
}

void og_metrics_usage(const OgSnapshot *previous, const OgSnapshot *current, OgUsage *usage) {
    memset(usage, 0, sizeof *usage);
    if (current->memory_valid && current->memory_total > 0) {
        usage->memory_total = current->memory_total;
        usage->memory_used = current->memory_total - current->memory_available;
        usage->memory_percent = (double)usage->memory_used * 100.0 / usage->memory_total;
        usage->memory_valid = true;
    }
    if (!previous) return;
    if (previous->cpu_valid && current->cpu_valid && current->cpu_total > previous->cpu_total && current->cpu_idle >= previous->cpu_idle) {
        uint64_t total = current->cpu_total - previous->cpu_total;
        uint64_t idle = current->cpu_idle - previous->cpu_idle;
        if (idle <= total) {
            usage->cpu_percent = (double)(total - idle) * 100.0 / total;
            usage->cpu_valid = true;
        }
    }
    double elapsed = current->seconds - previous->seconds;
    if (previous->network_valid && current->network_valid && elapsed >= 0.05 && elapsed <= 120) {
        /* NIC başına fark: hotplug / sayaç sıfırlanması 4 EiB/s sıçraması yapmaz. */
        for (size_t i = 0; i < current->network_count; i++) {
            const OgNetwork *now = &current->network[i];
            for (size_t j = 0; j < previous->network_count; j++) {
                const OgNetwork *old = &previous->network[j];
                if (strcmp(now->name, old->name)) continue;
                if (now->received >= old->received) usage->receive_rate += (now->received - old->received) / elapsed;
                if (now->sent >= old->sent) usage->send_rate += (now->sent - old->sent) / elapsed;
                break;
            }
        }
        usage->network_valid = true;
    }
}
