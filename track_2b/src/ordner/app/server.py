"""Demo console (stdlib only, no network needed at runtime).

    PYTHONPATH=src python -m ordner.app.server      # http://localhost:8000

GET  /                      console (static/index.html)
GET  /static/<file>         console assets
GET  /data/demo/<file>      demo pages + demo.json (precomputed pipeline outputs)
GET  /data/results/<file>   outputs of `python -m ordner.eval.run` (results.json, table.md, figures)
GET  /api/health            liveness + whether a model endpoint (LLM_*) is configured
POST /api/deductions        {profile} -> triggered deduction rules (data/rules/deductions_<year>.json)
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from ordner.app import deductions

DATA = Path(os.environ.get("ORDNER_DATA", deductions.DATA)).resolve()
STATIC = Path(__file__).resolve().parent / "static"
MOUNTS = {"/static/": STATIC, "/data/demo/": DATA / "demo", "/data/results/": DATA / "results"}
TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".md": "text/markdown; charset=utf-8",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
}
RULES = deductions.load_rules(data=DATA)


def resolve(url_path):
    path = unquote(urlsplit(url_path).path)
    if path in ("/", "/index.html"):
        return STATIC / "index.html"
    for prefix, root in MOUNTS.items():
        if path.startswith(prefix):
            f = (root / path[len(prefix):]).resolve()
            if f.is_relative_to(root) and f.is_file() and f.suffix in TYPES:
                return f
    return None


class Handler(BaseHTTPRequestHandler):
    timeout = 30

    def log_message(self, fmt, *args):
        sys.stderr.write("%s\n" % (fmt % args))

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json")

    def do_GET(self):
        if self.path == "/api/health":
            return self._json(200, {"ok": True, "llm_name": os.environ.get("LLM_NAME") or None,
                                    "llm_configured": bool(os.environ.get("LLM_BASE_URL"))})
        f = resolve(self.path)
        if f is None:
            return self._json(404, {"error": "not found"})
        self._send(200, f.read_bytes(), TYPES[f.suffix])

    def do_POST(self):
        if self.path != "/api/deductions":
            return self._json(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if not 0 < n <= 4096:
                return self._json(413, {"error": "request too large or empty"})
            self._json(200, deductions.evaluate(json.loads(self.rfile.read(n)), RULES))
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "invalid JSON"})
        except Exception as e:  # never leak a stack trace to the page
            sys.stderr.write(f"error: {e!r}\n")
            self._json(500, {"error": "internal error"})


def main():
    host, port = os.environ.get("HOST", "0.0.0.0"), int(os.environ.get("PORT", "8000"))
    print(f"Ordner console on http://localhost:{port}  (data: {DATA})", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
