#!/usr/bin/env python3
"""Gerçek, yerleşmiş Xfce oturumunda ölçüm. Önbellek / swap zorlamaz."""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from maintenance import memory_report

DESKTOP = frozenset(('xfce4-session', 'xfwm4', 'xfce4-panel', 'xfdesktop'))
BUSY = frozenset(('firefox', 'firefox-esr', 'soffice.bin', 'vlc', 'gnome-software', 'oguzdows-store-native', 'oguzdows-store-native'[:15],
                  'packagekitd', 'apt-get', 'dpkg', 'calamares'))
PANELS = frozenset(('welcome.py', 'updater.py', 'culture.py', 'store.py', 'store_service.py', 'compatibility.py', 'devices.py', 'narration.py', 'rifki.py', 'install_launcher.py'))


def snapshot(uid=None, proc=Path('/proc'), sysfs=Path('/sys')):
    uid = os.getuid() if uid is None else uid
    memory = memory_report((proc / 'meminfo').read_text())
    cpu = list(map(int, (proc / 'stat').read_text().splitlines()[0].split()[1:9]))
    processes, desktop, busy = [], set(), set()
    for entry in proc.glob('[0-9]*'):
        try:
            lines = (entry / 'status').read_text().splitlines()
            fields = dict(line.split(':', 1) for line in lines if ':' in line)
            name, owner = fields['Name'].strip(), int(fields['Uid'].split()[0])
            rss = int(fields.get('VmRSS', '0 kB').split()[0])
            processes.append({'pid': int(entry.name), 'name': name, 'uid': owner, 'rss_kib': rss})
            if owner == uid and name in DESKTOP:
                desktop.add(name)
            if name in BUSY:
                busy.add(name)
            if owner == uid and name.startswith('python'):
                arguments = (entry / 'cmdline').read_bytes().decode(errors='replace').split('\0')
                busy.update(Path(argument).name for argument in arguments if Path(argument).name in PANELS)
        except (OSError, ValueError, KeyError):
            continue
    zram = []
    for block in sorted((sysfs / 'block').glob('zram*')):
        try:
            values = [int(value) for value in (block / 'mm_stat').read_text().split()]
            zram.append({'device': block.name, 'original_data_bytes': values[0],
                         'compressed_data_bytes': values[1], 'allocated_ram_bytes': values[2]})
        except (OSError, ValueError, IndexError):
            continue
    return {**memory, 'timestamp': datetime.now(timezone.utc).isoformat(),
            'cpu_total_ticks': sum(cpu), 'cpu_idle_ticks': sum(cpu[3:5]),
            'desktop_user': uid, 'desktop_processes': sorted(desktop),
            'graphical_xfce': DESKTOP <= desktop, 'known_foreground_or_package_work': sorted(busy),
            'top_processes_rss_not_system_total': sorted(processes, key=lambda row: row['rss_kib'], reverse=True)[:20],
            'zram': zram}


def summarize(samples, settled_seconds, interval, idle_confirmed):
    if not samples:
        raise ValueError('Ölçüm örneği yok.')
    reasons = []
    if not idle_confirmed:
        reasons.append('Kullanıcı uygulamaları kapattığını doğrulamadı.')
    if settled_seconds < 120 or len(samples) < 6 or interval < 5:
        reasons.append('En az 120 saniye yerleşme + 5 saniye aralıklı 6 örnek gerekli.')
    if not all(item['graphical_xfce'] for item in samples):
        reasons.append('Hedef kullanıcının tam Xfce oturumu doğrulanmadı.')
    if any(item['known_foreground_or_package_work'] for item in samples):
        reasons.append('Mağaza / tarayıcı / kurucu / paket işi veya OğuzDows paneli açık.')
    used = [item['used_bytes'] for item in samples]
    if max(used) - min(used) > 30_000_000:
        reasons.append('Bellek örnekleri henüz kararlı değil (fark > 30 MB).')
    total = samples[-1]['cpu_total_ticks'] - samples[0]['cpu_total_ticks']
    idle = samples[-1]['cpu_idle_ticks'] - samples[0]['cpu_idle_ticks']
    cpu_percent = round(100 * (1 - idle / total), 2) if total > 0 else None
    if cpu_percent is None or cpu_percent > 10:
        reasons.append('Örnekleme sırasında CPU boşta / sakin değil (> %10 veya veri yok).')
    valid = not reasons
    available = [item.get('available_bytes') for item in samples]
    available = available if all(type(value) is int and value >= 0 for value in available) else []
    return {'version': 1, 'scope': 'Bu çalışan sistem ve Xfce oturumu; fiziksel PC / diğer masaüstleri için genellenmez.',
            'method': samples[-1]['method'], 'target_bytes': 600_000_000,
            'settled_seconds': settled_seconds, 'sample_interval_seconds': interval, 'sample_count': len(samples),
            'idle_confirmed_by_operator': idle_confirmed, 'valid_idle_measurement': valid, 'invalid_reasons': reasons,
            'median_used_bytes': int(statistics.median(used)), 'max_used_bytes': max(used),
            'median_used_mb': round(statistics.median(used) / 1_000_000, 1),
            'max_used_mb': round(max(used) / 1_000_000, 1), 'busy_cpu_percent': cpu_percent,
            'reported_total_bytes': samples[-1].get('total_bytes'),
            'min_available_bytes': min(available) if available else None,
            'min_available_mb': round(min(available) / 1_000_000, 1) if available else None,
            'target_met': valid and max(used) <= 600_000_000, 'samples': samples,
            'limits': 'MemAvailable hesaplanır; RSS toplamı sistem RAM’i sayılmaz. Önbellek düşürülmez. Zram ayrıca gösterilir, RAM’den ikinci kez çıkarılmaz. Ekran kartı / donanım / güncellemeler sonucu değiştirebilir.'}


def collect(settle=120, count=6, interval=5, idle_confirmed=False, uid=None, wait_for_desktop=0, read=snapshot, sleep=time.sleep):
    started = time.monotonic()
    while True:
        first = read(uid=uid)
        if first['graphical_xfce'] or time.monotonic() - started >= wait_for_desktop:
            break
        sleep(2)
    sleep(settle)
    samples = []
    for index in range(count):
        if index:
            sleep(interval)
        samples.append(read(uid=uid))
    return summarize(samples, settle, interval, idle_confirmed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settle-seconds', type=int, default=120)
    parser.add_argument('--samples', type=int, default=6)
    parser.add_argument('--interval', type=int, default=5)
    parser.add_argument('--idle-confirmed', action='store_true', help='Ölçülecek oturumdaki uygulamaları kapattım')
    parser.add_argument('--user', type=int, default=os.getuid(), help='Ölçülen grafik oturumunun sayısal kullanıcı kimliği')
    parser.add_argument('--wait-for-desktop', type=int, default=0)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if (not 0 <= args.settle_seconds <= 1800 or not 1 <= args.samples <= 60
            or not 1 <= args.interval <= 60 or not 0 <= args.wait_for_desktop <= 300
            or args.user < 0 or (os.geteuid() != 0 and args.user != os.getuid())):
        parser.error('Ölçüm aralığı / kullanıcı kimliği geçersiz.')
    result = collect(args.settle_seconds, args.samples, args.interval, args.idle_confirmed, args.user, args.wait_for_desktop)
    try:
        result['build'] = json.loads(Path('/usr/share/oguzdows/build-info.json').read_text())
    except (OSError, ValueError):
        result['build'] = {'source_revision': 'unknown'}
    output = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', dir=args.output.parent, prefix='.oguzdows-ram-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(output)
        try:
            temporary.replace(args.output)
        finally:
            temporary.unlink(missing_ok=True)
    print(output, end='')


if __name__ == '__main__':
    main()
