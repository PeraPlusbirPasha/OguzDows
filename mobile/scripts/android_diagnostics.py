"""Narrow emulator DropBox attribution, not an ANR waiver or a device-health assertion."""
import re


def anr_threads(raw, package):
    """Newest matching app record/trace only; never label the stock launcher's main as ours.

    DropBox can concatenate stock boot ANRs and app ANRs, each with other process
    snapshots too. Both the record owner (when present) and exact Cmd line must
    match. Missing/unknown traces stay unknown instead of taking the first main.
    """
    wanted = re.compile(r'^Cmd line:\s*' + re.escape(package) + r'\s*$', re.MULTILINE)
    records = re.split(r'^={5,}[^\S\n]*$', raw, flags=re.MULTILINE)
    for record in reversed(records):
        owner = re.search(r'^Process:\s*(\S+)[^\S\n]*$', record, re.MULTILINE)
        if owner and owner[1] != package:
            continue
        snapshots = re.split(r'(?=^----- pid \d+ at [^\n]+-----[^\S\n]*$)', record, flags=re.MULTILINE)
        for snapshot in reversed(snapshots):
            if not wanted.search(snapshot):
                continue
            pid = re.search(r'^----- pid (\d+) at ', snapshot, re.MULTILINE)
            headers = list(re.finditer(r'^"([^"\n]+)"[^\n]*\n', snapshot, re.MULTILINE))
            stacks = {}
            for index, header in enumerate(headers):
                name = header[1]
                if name not in ('main', 'RenderThread', 'VizCompositorThread'):
                    continue
                end = headers[index + 1].start() if index + 1 < len(headers) else len(snapshot)
                stacks[name] = snapshot[header.start():end].strip()[:2800]
            if stacks:
                return {'process': package, 'pid': int(pid[1]) if pid else None, 'threads': stacks}
    return {}
