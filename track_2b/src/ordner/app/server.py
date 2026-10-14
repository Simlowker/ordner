"""Demo console (stdlib only, no network needed at runtime).

    PYTHONPATH=src python -m ordner.app.server      # http://localhost:8000

GET  /                      console (static/index.html)
GET  /static/<file>         console assets
GET  /data/demo/<file>      demo pages + demo.json (precomputed pipeline outputs)
GET  /data/results/<file>   outputs of `python -m ordner.eval.run` (results.json, table.md, figures)
GET  /api/health            liveness, model endpoint (LLM_*), importable workstream modules, agent live or demo, today,
                            conversation_url (harness conversation, when ordner.harness.web runs)
                            (ORDNER_TODAY=YYYY-MM-DD simulates the date for the demo)
POST /api/deductions        {profile} -> triggered deduction rules (data/rules/deductions_<year>.json)

Cockpit (ordner.app.cockpit; 503 {"error": "unavailable", "module"} while a workstream module is missing):
GET  /api/subjects                   subjects of the local dossier (seeds the demo persona when empty)
GET  /api/overview?subject=<id>      home: urgent, missing, next step, pieces to review, coverage; inbox; cases
GET  /api/case?id=<id>               case detail: card, state, facts, actions, deadlines, events, sources
GET  /api/coverage                   domain x canton grid of the procedure catalogue
GET  /api/calendar.ics?subject=<id>  deadlines as iCalendar (ordner.rules.to_ics)
POST /api/actions/validate           {case_id, action_id} -> records the validation, never sends anything
GET  /api/actions/eml?case_id=&action_id=   .eml draft of a validated request (X-Unsent, never sent by Ordner)
POST /api/ask                        {subject, question} -> ordner.agent.coordinator.run (live mode only)
POST /api/review                     {subject} -> deterministic review: opens expected cases, deadlines, missing pieces
"""
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from ordner.app import cockpit, deductions

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
ID = re.compile(r"[A-Za-z0-9_.:-]{1,80}")
MAX_BODY = 8192
MAX_QUESTION = 1000


def ident(value):
    """Trust boundary: ids come from the browser."""
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError("invalid id")
    return value


def health():
    llm, reason = cockpit.llm_client()
    return {"ok": True, "llm_name": os.environ.get("LLM_NAME") or None, "llm_configured": bool(os.environ.get("LLM_BASE_URL")),
            "modules": cockpit.modules(), "agent_live": llm is not None, "agent_reason": reason,
            "today": cockpit.today_().isoformat(), "simulated": bool(cockpit.SIMULATED),
            "conversation_url": conversation_url()}


def conversation_url():
    """URL of the harness conversation (ordner.harness.web writes it while dsh runs, same ORDNER_HOME), else None."""
    f = Path(os.environ.get("ORDNER_HOME", "~/.ordner")).expanduser() / "harness" / "url.txt"
    try:
        url = f.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return url if url.startswith(("http://", "https://")) else None


def ask(body):
    q = body.get("question")
    if not isinstance(q, str) or not q.strip() or len(q) > MAX_QUESTION:
        raise ValueError("question must be 1..1000 characters")
    return cockpit.ask(ident(body.get("subject")), q.strip())


def calendar(sid):
    return cockpit.calendar(sid).encode(), "text/calendar; charset=utf-8", f"ordner-{sid}.ics"


GET_API = {
    "/api/health": lambda q: health(),
    "/api/subjects": lambda q: cockpit.subjects(),
    "/api/overview": lambda q: cockpit.overview(ident(q.get("subject"))),
    "/api/case": lambda q: cockpit.case_detail(ident(q.get("id"))),
    "/api/coverage": lambda q: cockpit.coverage_map(),
    "/api/calendar.ics": lambda q: calendar(ident(q.get("subject"))),
    "/api/actions/eml": lambda q: cockpit.eml(ident(q.get("case_id")), ident(q.get("action_id"))),
}
POST_API = {
    "/api/deductions": lambda b: deductions.evaluate(b, RULES),
    "/api/actions/validate": lambda b: cockpit.validate_action(ident(b.get("case_id")), ident(b.get("action_id"))),
    "/api/ask": ask,
    "/api/review": lambda b: cockpit.review(ident(b.get("subject"))),
}


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

    def _send(self, code, body, ctype, headers=()):
        self.send_response(code)
        for h in headers:
            self.send_header(*h)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json")

    def _api(self, fn, arg):
        try:
            out = fn(arg)
        except cockpit.Unavailable as e:
            return self._json(503, {"error": "unavailable", "module": str(e)})
        except cockpit.NotFound:
            return self._json(404, {"error": "not found"})
        except ValueError as e:
            return self._json(400, {"error": str(e)[:200] or "invalid input"})
        except Exception as e:  # never leak a stack trace to the page
            sys.stderr.write(f"error: {e!r}\n")
            return self._json(500, {"error": "internal error"})
        if isinstance(out, tuple):  # (bytes, content type, filename)
            body, ctype, name = out
            return self._send(200, body, ctype, [("Content-Disposition", f'attachment; filename="{name}"')])
        self._json(200, out)

    def do_GET(self):
        url = urlsplit(self.path)
        try:
            q = {k: v[0] for k, v in parse_qs(url.query, max_num_fields=8).items()}
        except ValueError:
            return self._json(400, {"error": "too many parameters"})
        if url.path in GET_API:
            return self._api(GET_API[url.path], q)
        f = resolve(self.path)
        if f is None:
            return self._json(404, {"error": "not found"})
        self._send(200, f.read_bytes(), TYPES[f.suffix])

    def do_POST(self):
        fn = POST_API.get(urlsplit(self.path).path)
        if fn is None:
            return self._json(404, {"error": "not found"})
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            # forces a CORS preflight (never answered) on cross-site posts to this local server
            return self._json(415, {"error": "Content-Type must be application/json"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = -1
        if not 0 < n <= MAX_BODY:
            return self._json(413, {"error": "request too large or empty"})
        try:
            body = json.loads(self.rfile.read(n))
        except (ValueError, UnicodeDecodeError):
            return self._json(400, {"error": "invalid JSON"})
        if not isinstance(body, dict):
            return self._json(400, {"error": "a JSON object is expected"})
        self._api(fn, body)


def main():
    host, port = os.environ.get("HOST", "0.0.0.0"), int(os.environ.get("PORT", "8000"))
    print(f"Ordner console on http://localhost:{port}  (data: {DATA})", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
