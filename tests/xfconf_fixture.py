"""Tipli xfconf CLI taklidi; gerçek ekran testinin yerine geçmez."""
import subprocess


class Xfconf:
    def __init__(self, rows=()):
        self.calls = []
        self.values = {}
        self.types = {}
        for channel, path, kind, _value in rows:
            if path.startswith(('/panels/panel-90/', '/plugins/plugin-9')):
                continue
            if kind.endswith('-array'):
                value = ['1'] if path == '/panels' else ['1', '2', '3', '4', '5', '6', '7'] if path.endswith('plugin-ids') else ['0.1', '0.2', '0.3', '1']
            else:
                value = '82' if kind == 'double' else 'original'
            self.values[channel, path] = value
            self.types[channel, path] = kind

    def __call__(self, command):
        self.calls.append(command)
        assert command[0] == 'xfconf-query', command
        key = command[2], command[4]
        if len(command) == 5:
            if key not in self.values:
                return subprocess.CompletedProcess(command, 1, '', '')
            value = self.values[key]
            if self.types.get(key) == 'double':
                value = f'{float(value):.6f}'
            if isinstance(value, list):
                if self.types.get(key) == 'double-array':
                    value = [f'{float(item):.6f}' for item in value]
                value = f'Value is an array with {len(value)} items:\n\n' + '\n'.join(value)
            return subprocess.CompletedProcess(command, 0, value + '\n', '')
        if '--reset' in command:
            self.values.pop(key, None)
            self.types.pop(key, None)
        else:
            values = [command[index + 1] for index, value in enumerate(command) if value == '-s']
            assert values, command
            self.values[key] = values if '--force-array' in command else values[0]
            kind = command[command.index('-t') + 1]
            self.types[key] = kind + '-array' if '--force-array' in command else kind
        return subprocess.CompletedProcess(command, 0, '', '')
