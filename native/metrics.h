/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef OGUZDOWS_METRICS_H
#define OGUZDOWS_METRICS_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define OGUZ_NET_LIMIT 128

typedef struct { char name[32]; uint64_t received, sent; } OgNetwork;
typedef struct {
    uint64_t cpu_total, cpu_idle, memory_total, memory_available;
    bool cpu_valid, memory_valid, network_valid;
    OgNetwork network[OGUZ_NET_LIMIT];
    size_t network_count;
    double seconds;
} OgSnapshot;
typedef struct {
    double cpu_percent, memory_percent, receive_rate, send_rate;
    uint64_t memory_used, memory_total;
    bool cpu_valid, memory_valid, network_valid;
} OgUsage;

/* Salt okunur /proc. Önceki örnek yoksa CPU/ağ uydurulmaz. */
void og_metrics_read(OgSnapshot *snapshot, const char *proc_root);
void og_metrics_usage(const OgSnapshot *previous, const OgSnapshot *current, OgUsage *usage);
#endif
