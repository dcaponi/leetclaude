"""Local micro-app server: serves ui/ and a tiny JSON API. Binds to 127.0.0.1 only."""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .common import PID_FILE, REPO, load_config
from . import engine, stats

UI = REPO / "ui"
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".svg": "image/svg+xml", ".ico": "image/x-icon", ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8",
         ".md": "text/markdown; charset=utf-8"}
LAST_POLL = {"t": 0.0}


class Handler(BaseHTTPRequestHandler):
    server_version = "LeetClaude/1.0"  # also serves LeetCodex; the page picks the name per ticket

    def log_message(self, fmt, *args):
        if os.environ.get("LEETCLAUDE_DEBUG"):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _origin_ok(self) -> bool:
        # Block cross-site POSTs from other pages in the browser (CSRF): only same-origin or no Origin header.
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        return origin is None or origin in (f"http://{host}", f"http://127.0.0.1:{self.server.server_port}",
                                            f"http://localhost:{self.server.server_port}")

    def do_GET(self):
        path = self.path.split("?")[0]
        try:
            if path == "/api/state":
                LAST_POLL["t"] = time.time()
                return self._json(engine.view())
            if path == "/api/ping":
                return self._json({"ok": True, "pid": os.getpid(), "rev": os.environ.get("LEETCLAUDE_REV"),
                                   "last_poll_age": time.time() - LAST_POLL["t"]})
            if path == "/api/stats":
                return self._json(stats.summary())
            name = "index.html" if path in ("/", "") else path.lstrip("/")
            f = (UI / name).resolve()
            if UI.resolve() not in f.parents or not f.is_file():
                return self._json({"error": "not found"}, 404)
            body = f.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", TYPES.get(f.suffix, "application/octet-stream"))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:  # keep the server alive no matter what
            traceback.print_exc()
            self._json({"error": str(e)}, 500)

    def do_POST(self):
        if not self._origin_ok():
            return self._json({"error": "cross-origin request refused"}, 403)
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            path = self.path.split("?")[0]
            if path == "/api/run":
                return self._json(engine.submit(body.get("code", ""), body.get("lang", ""), bool(body.get("submit"))))
            if path == "/api/exchange":
                return self._json(engine.exchange())
            if path == "/api/bail":
                return self._json(engine.bail())
            if path == "/api/quiz":
                return self._json(engine.quiz_answer(body.get("choice"), body.get("text")))
            if path == "/api/dismiss-parked":
                from .common import locked_state
                with locked_state() as st:
                    st["parked_prompt"] = None
                return self._json({"ok": True})
            return self._json({"error": "not found"}, 404)
        except engine.GateError as e:
            return self._json({"error": str(e)}, 400)
        except Exception as e:
            traceback.print_exc()
            return self._json({"error": f"{type(e).__name__}: {e}"}, 500)


def main():
    cfg = load_config()
    port = int(os.environ.get("LEETCLAUDE_PORT") or cfg["port"])
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    httpd.daemon_threads = True
    PID_FILE.write_text(str(os.getpid()))
    print(f"LeetClaude listening on http://127.0.0.1:{port}/", flush=True)
    try:
        httpd.serve_forever()
    finally:
        try:
            if PID_FILE.read_text().strip() == str(os.getpid()):
                PID_FILE.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
