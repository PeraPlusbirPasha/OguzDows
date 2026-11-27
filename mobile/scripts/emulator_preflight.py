"""Read-only observations for a disposable QEMU fixture, not native acceptance.

A loaded SIM property alone does not prove that the platform chose an SMS
subscription or brought up its default network. Never invent/select a line to
make a communications test pass. The application still checks the real SDK value.
"""
import re


def snapshot(sim_state, sms_setting, connectivity):
    sim = sim_state.strip().upper()
    sms = sms_setting.strip()
    network = re.search(r'^\s*Active default network:\s*(\d+)\s*$', connectivity, re.MULTILINE)
    value = int(sms) if re.fullmatch(r'-?\d{1,10}', sms) else None
    return {
        'sim_state': sim[:80],
        'default_sms_subscription_setting': value,
        'active_default_network': int(network[1]) if network else None,
        'ready': bool({'LOADED', 'READY'}.intersection(sim.split(',')))
                 and value is not None and 0 <= value <= 2147483647 and network is not None,
    }
