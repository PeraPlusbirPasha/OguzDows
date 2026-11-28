#!/usr/bin/env python3
"""Local Pages-compatible preview. No API, cookies, telemetry or SPA fallback."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PREFIX = urlsplit(json.loads((ROOT / 'website/site.json').read_text())['base_url']).path


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(302)
            self.send_header('Location', PREFIX)
            self.end_headers()
            return
        if not self.path.startswith(PREFIX):
            self.send_error(404)
            return
        self.path = '/' + self.path[len(PREFIX):]
        super().do_GET()

    def do_HEAD(self):
        if not self.path.startswith(PREFIX):
            self.send_error(404)
            return
        self.path = '/' + self.path[len(PREFIX):]
        super().do_HEAD()

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Robots-Tag', 'noindex')  # Preview only, never a production Pages header.
        super().end_headers()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=4174)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), partial(Handler, directory=str(ROOT / 'docs')))
    print(f'Public site preview on port {args.port} at {PREFIX}', flush=True)
    server.serve_forever()
