"""OpenAI-compatible /v1/chat/completions endpoint (SSE or JSON) in front of an Ordner LLM backend, for DeepSeek Harness.

Apertus writes tool calls as raw text (<|tools_prefix|>[{"name": {...}}]<|tools_suffix|>) and mlx_lm.server returns
them as plain content: the harness then takes them for the final answer (silent failure, docs/harness_spike.md). The
proxy calls the backend through the coordinator's own client (ordner.agent.llm: OpenAICompat for mlx_lm.server/vLLM,
MLXLocal, MockLLM), i.e. the same request body and the same parser, and answers with OpenAI `tool_calls`. Upstream is
not streamed, so the whole completion is buffered before the SSE frames are written.

It also makes the harness request what the coordinator would send:
- names: the harness calls MCP tools `mcp__ordner__<name>`; the prefix is stripped for the model and added back on
  the calls it returns (the model sees the coordinator's bare names);
- tool order (`order`), message shapes (text parts joined, empty/invalid history arguments as the coordinator writes
  them), and the harness's runtime-context user message dropped (`keep_context=False`): with includeRuntimeContext
  off only the *required* working-directory line is left ("Current runtime context. ... Current working directory:
  <empty temp dir>"), which no harness config removes and no Ordner tool uses;
- turn control, read from the history (the harness has no step budget nor a tool that ends the turn): after an
  ask_user, after MAX_DUPLICATES refused duplicates, or once max_steps model calls were made, it answers a final
  marker text without calling the model (runtime.result rebuilds the coordinator's answer from the log);
- fail closed: a request carrying a tool outside `allowed` is refused (HTTP 400), the model is never asked;
- experts (web UI, `experts=True`): the marker on the system prompt (ordner.harness.experts) gives the request's
  allowlist (the expert's tools) and, on an MLX backend (ORDNER_BACKEND=mlx, default), its LoRA adapter sent as the
  `adapters` body field; no marker, an unknown expert or no adapter directory -> base model (`adapter: none`).
Every exchange is kept in `Proxy.log` (normalized messages and tools, backend reply, stop reason; expert and adapter in
experts mode) and summarized as a JSON line in `log_file` when given.

    python -m ordner.harness.proxy --upstream http://127.0.0.1:8080/v1 [--port 18765] [--max-steps 12] [--raw]
"""
import argparse
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from ordner.agent.coordinator import MAX_DUPLICATES
from ordner.agent.llm import TOOLS_PREFIX, parse_tool_calls

from . import experts as E
from .mcp_server import ERROR_KEY, NAME_KEY

PREFIX = "mcp__ordner__"
ASKED = '{"tool": "ask_user", "result": {"status": "asked"'
RUNTIME_CONTEXT = "Current runtime context."
CARRIER = "ask_user"   # listed tool that carries a call named outside the list (see mcp_server.NAME_KEY)
DUPLICATE = '"error": "this exact call was already made'


def _text(content):
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return content or ""


def _strip(name, prefix):
    return name[len(prefix):] if prefix and name and name.startswith(prefix) else name


def _hist_call(c, prefix):
    """A history call as the coordinator writes it: real name (or invalid_call), arguments with its template
    workaround (empty or unreadable -> {"_": "invalid"})."""
    name = _strip(c["function"]["name"], prefix)
    try:
        args = json.loads(c["function"].get("arguments") or "{}")
    except json.JSONDecodeError:
        args = None
    if isinstance(args, dict) and NAME_KEY in args:
        name = args.pop(NAME_KEY)
    if not isinstance(args, dict) or ERROR_KEY in args:
        args = None
    return {"id": c["id"], "type": "function", "function": {
        "name": name or "invalid_call", "arguments": json.dumps(args or {"_": "invalid"}, ensure_ascii=False)}}


def to_model(req, prefix=PREFIX, order=None, keep_context=False):
    """Harness request -> (messages, tools) in the coordinator's shapes."""
    tools = [{"type": "function", "function": {**t["function"], "name": _strip(t["function"]["name"], prefix)}}
             for t in req.get("tools") or []]
    if order:
        tools.sort(key=lambda t: order.index(t["function"]["name"]) if t["function"]["name"] in order else len(order))
    msgs = []
    for m in req.get("messages", []):
        if not keep_context and m["role"] == "user" and _text(m.get("content")).startswith(RUNTIME_CONTEXT):
            continue
        out = {"role": "system" if m["role"] == "developer" else m["role"], "content": _text(m.get("content"))}
        if m.get("tool_calls"):
            out["tool_calls"] = [_hist_call(c, prefix) for c in m["tool_calls"]]
        if m["role"] == "tool":
            out["tool_call_id"] = m.get("tool_call_id")
        msgs.append(out)
    return msgs, tools


def stop_reason(msgs, max_steps):
    """The coordinator's loop exits, in its order: question asked, repeated duplicates, step budget spent."""
    results = [m["content"] for m in msgs if m["role"] == "tool"]
    if any(r.startswith(ASKED) for r in results):
        return "asked"
    if sum(DUPLICATE in r for r in results) >= MAX_DUPLICATES:
        return "duplicates"
    if sum(m["role"] == "assistant" for m in msgs) >= max_steps:
        return "max_steps"
    return None


def to_calls(reply, prefix, step, names):
    """Parsed calls -> OpenAI tool_calls. A call with a parse error carries it (ERROR_KEY); a call named outside
    `names` (or unnamed) travels through CARRIER with its real name (NAME_KEY): the MCP server reports both to the
    model exactly as the coordinator does."""
    out = []
    for i, c in enumerate(reply["tool_calls"]):
        name, args = c.get("name"), dict(c.get("arguments") or {})
        if c.get("error"):
            args = {ERROR_KEY: c["error"]}
        if name not in names:
            name, args = CARRIER, {**args, NAME_KEY: name}
        out.append({"index": i, "id": f"call_{step}_{i}", "type": "function",
                    "function": {"name": prefix + name, "arguments": json.dumps(args, ensure_ascii=False)}})
    return out


def route(messages, adapters_ok):
    """Expert of a request from the marker on the system message; its tools (model-side names) and, MLX only, its
    LoRA adapter."""
    sys_text = next((m.get("content") or "" for m in messages if m.get("role") == "system"), "")
    eid = E.marker(sys_text)
    if eid is None:
        return {"expert": None, "allowed": None, "adapter": None}
    allowed = [t.replace(".", "_") for t in E.EXPERTS[eid].tools] + ["ask_user", "prepare_action"]
    return {"expert": eid, "allowed": allowed, "adapter": E.adapter_path(eid) if adapters_ok else None}


class Handler(BaseHTTPRequestHandler):
    server: "Proxy"

    def _json(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            return self._json(200, {"object": "list", "data": [{"id": "apertus", "object": "model", "owned_by": "ordner"}]})
        self._json(404, {"error": {"message": "not found"}})

    def do_POST(self):
        p = self.server
        req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        msgs, tools = to_model(req, p.prefix, p.order, p.keep_context)
        names = [t["function"]["name"] for t in tools]
        entry = {"t": time.time(), "messages": msgs, "tools": tools, "stop": None, "reply": None, "sent": None}
        allowed, extra = p.allowed, None
        if p.experts:
            r = route(msgs, p.adapters_ok)
            entry.update(expert=r["expert"], adapter=r["adapter"] or "none")
            allowed = r["allowed"] if r["allowed"] is not None else allowed
            extra = {"adapters": r["adapter"]} if r["adapter"] else None
        foreign = sorted(set(names) - set(allowed)) if allowed is not None else []
        if foreign:
            entry["refused"] = foreign
            p.record(entry)
            return self._json(400, {"error": {"message": f"ordner proxy: tools outside Ordner's set refused: {foreign}"}})
        entry["stop"] = stop_reason(msgs, p.max_steps)
        if entry["stop"]:   # the harness rejects an empty completion (EMPTY_RESPONSE, then retries): a marker
            content, calls = f"[ordner: turn ended, {entry['stop']}]", []
        else:
            try:
                with p.lock:   # extra only when set: any chat(messages, tools) backend keeps working
                    reply = p.llm.chat(msgs, tools, extra=extra) if extra else p.llm.chat(msgs, tools)
            except Exception as e:   # backend down or refusing: a visible error for the harness, never a fake answer
                entry["error"] = f"{type(e).__name__}: {e}"
                p.record(entry)
                return self._json(502, {"error": {"message": f"ordner proxy: backend error: {entry['error']}"}})
            entry["reply"] = reply
            step = sum(m["role"] == "assistant" for m in msgs)
            content, calls = (reply["raw"], []) if p.raw else (reply["content"], to_calls(reply, p.prefix, step, names))
        entry["sent"] = {"content": content, "tool_calls": calls}
        entry["text_calls"] = bool(content and (TOOLS_PREFIX in content or parse_tool_calls(content, set(names))[1]))
        p.record(entry)
        self._answer(req, content, calls)

    def _answer(self, req, content, calls):
        cid, now = f"chatcmpl-{time.time_ns()}", int(time.time())
        finish, usage = ("tool_calls" if calls else "stop"), {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        if not req.get("stream"):
            msg = {"role": "assistant", "content": content or None}
            if calls:
                msg["tool_calls"] = [{k: v for k, v in c.items() if k != "index"} for c in calls]
            return self._json(200, {"id": cid, "object": "chat.completion", "created": now, "model": req.get("model"),
                                    "choices": [{"index": 0, "message": msg, "finish_reason": finish}], "usage": usage})

        def frame(delta, fin=None, **extra):
            return {"id": cid, "object": "chat.completion.chunk", "created": now, "model": req.get("model"),
                    "choices": [{"index": 0, "delta": delta, "finish_reason": fin}], **extra}
        frames = [frame({"role": "assistant", "content": ""})]
        frames += [frame({"content": content})] if content else []
        frames += [frame({"tool_calls": calls})] if calls else []
        frames.append(frame({}, finish))
        if (req.get("stream_options") or {}).get("include_usage"):
            frames.append({**frame({}), "choices": [], "usage": usage})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(b"".join(f"data: {json.dumps(f)}\n\n".encode() for f in frames) + b"data: [DONE]\n\n")
        self.wfile.flush()

    def log_message(self, fmt, *args):
        pass


class Proxy(HTTPServer):
    """Single-threaded on purpose: runtime.run serves it from the caller's thread (handle_request), so an in-process
    backend (MLXLocal: MLX streams are per thread) runs where it was loaded. `with Proxy(...)` serves from a thread."""

    def __init__(self, llm, port=0, max_steps=12, order=None, allowed=None, prefix=PREFIX, raw=False, keep_context=False,
                 experts=False, log_file=None):
        super().__init__(("127.0.0.1", port), Handler)
        self.llm, self.max_steps, self.order, self.allowed, self.prefix = llm, max_steps, order, allowed, prefix
        self.raw, self.keep_context, self.experts, self.log_file = raw, keep_context, experts, log_file
        self.adapters_ok = os.environ.get("ORDNER_BACKEND", "mlx") == "mlx"   # `adapters` is an mlx_lm.server field
        self.log, self.lock, self.timeout = [], threading.Lock(), 0.2

    def record(self, entry):
        self.log.append(entry)
        if self.log_file:
            sent = entry.get("sent") or {}
            line = {"t": round(entry["t"], 3), "expert": entry.get("expert"), "adapter": entry.get("adapter"),
                    "tools": [t["function"]["name"] for t in entry["tools"]], "refused": entry.get("refused"),
                    "stop": entry["stop"], "error": entry.get("error"),
                    "calls": [c["function"]["name"] for c in sent.get("tool_calls") or []],
                    "status": 400 if entry.get("refused") else 502 if entry.get("error") else 200}
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_address[1]}/v1"

    def __enter__(self):
        threading.Thread(target=self.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.shutdown()
        self.server_close()


def main(argv=None):
    from ordner.agent.llm import OpenAICompat
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--upstream", default="http://127.0.0.1:8080/v1")
    ap.add_argument("--model", default="default")
    ap.add_argument("--port", type=int, default=18765)
    ap.add_argument("--max-steps", type=int, default=12)
    ap.add_argument("--raw", action="store_true", help="no translation (reproduces the silent failure)")
    a = ap.parse_args(argv)
    p = Proxy(OpenAICompat(a.upstream, a.model), a.port, a.max_steps, raw=a.raw)
    print(f"ordner proxy on {p.url} -> {a.upstream}", flush=True)
    p.serve_forever()


if __name__ == "__main__":
    main()
