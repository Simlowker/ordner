"""expert.run: bounded Apertus expert tasks. Process tax_statement_extraction = the 8 eCH-0196 summary fields."""
import json
import urllib.request
from functools import lru_cache
from urllib.parse import urlsplit

from ordner.core.schema import ToolSpec

from .base import ToolError, mode, work
from .document import jsonl, ocr_cache, resolve, state_text

PROCESSES = ["tax_statement_extraction"]
TAGS = ["apertus-lora", "apertus-base"]


@lru_cache(maxsize=8)
def extract_cache(work_dir, tag) -> dict:
    f = work_dir / f"extract.{tag}.jsonl"
    return {r["page_id"]: r for r in jsonl(f) if not r.get("error")} if f.exists() else {}


def _endpoint(ctx, text, warnings):
    from ordner.models import apertus  # same prompt and lenient JSON parsing as the measured pipeline

    url = ctx["llm_url"].rstrip("/")
    if urlsplit(url).hostname not in ("localhost", "127.0.0.1", "::1"):
        warnings.append(f"model endpoint {urlsplit(url).hostname} is not this machine: document text left the device")
    body = {"model": ctx.get("llm_model", "apertus"), "messages": apertus.messages(text), "temperature": 0,
            "max_tokens": 256}
    req = urllib.request.Request(f"{url}/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        raw = json.load(r)["choices"][0]["message"]["content"]
    return apertus.parse_json(raw), None, {"source": "endpoint", "url": url, "model": body["model"]}


def _mlx(ctx, text):
    from ordner.models import apertus_mlx as am

    adapter = ctx["apertus_mlx"] if isinstance(ctx["apertus_mlx"], str) else None
    if am._model is None:
        am.load(adapter)
    ex = am.extract(text)
    return ex["fields"], ex["doubt"], {"source": "apertus_mlx", "model": str(am.MODEL), "adapter": adapter}


def run(args, ctx):
    w, warnings, rec = work(ctx), [], None
    if mode(ctx) == "replay" and not args.get("text") and args.get("doc"):
        ids = resolve(args["doc"], ctx)["page_ids"]
        for tag in ctx.get("expert_tags", TAGS):
            pid = next((p for p in ids if p in extract_cache(w, tag)), None)
            if pid:
                rec = extract_cache(w, tag)[pid]
                break
    if rec:
        text = ocr_cache(w).get(pid, {}).get("text")
        fields, doubt, prov = rec["fields"], rec.get("doubt"), {"source": "replay", "model": tag, "page_id": pid,
                                                                 "cache": f"work/extract.{tag}.jsonl"}
    else:
        text, pid, state = state_text(args, ctx)
        if mode(ctx) == "live" and ctx.get("llm_url"):
            fields, doubt, prov = _endpoint(ctx, text, warnings)
        elif mode(ctx) == "live" and ctx.get("apertus_mlx"):
            fields, doubt, prov = _mlx(ctx, text)
        elif mode(ctx) == "live":
            raise ToolError("live expert.run needs ctx['llm_url'] (OpenAI-compatible server) or ctx['apertus_mlx']")
        else:
            from ordner.eval import regex_baseline

            fields, doubt, prov = regex_baseline.extract(text), None, {"source": "regex_baseline"}
            warnings.append("replay mode without cached Apertus output: fields come from the rule-based baseline, "
                            "not from Apertus")
        prov.update(page_id=pid, state=state)
    from ordner.eval import rules

    checks = rules.check(fields, text)
    data = {"process": args["process"], "fields": fields, "checks": checks,
            "to_verify": [f for f, ok in checks.items() if ok is False or fields.get(f) in (None, "")]}
    if doubt:
        data["logprob_min"] = {f: round(d["lp_min"], 4) for f, d in doubt.items()}
    if data["to_verify"]:
        warnings.append(f"fields to verify against the original: {', '.join(data['to_verify'])}")
    return data, warnings, prov


TOOLS = [
    (ToolSpec(
        "expert.run",
        "Run a specialised Apertus expert on a document. tax_statement_extraction: the 8 summary fields of a Swiss "
        "tax statement, with consistency checks. A proposal: values are facts only once confirmed. If the document "
        "has an eCH-0196 barcode, document.decode is exact and wins.",
        {"type": "object", "properties": {
            "process": {"type": "string", "enum": PROCESSES},
            "doc": {"type": "string", "description": "dossier document id (doc_...), file path or page id"},
            "text": {"type": "string", "description": "page text instead of doc"}},
         "required": ["process"]},
        {"type": "object", "properties": {
            "fields": {"type": "object"},
            "checks": {"type": "object", "description": "{field: true consistent | false inconsistent | null}"},
            "to_verify": {"type": "array", "items": {"type": "string"}},
            "logprob_min": {"type": "object", "description": "lowest token log-prob per value; lower = more doubt"}}},
    ), run),
]
