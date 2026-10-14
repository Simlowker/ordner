"""decision.score: closed questions answered by d1-3B (live), or by cached d1 routing and labelled heuristics (replay)."""
import re
from functools import lru_cache

from ordner.core.schema import ToolSpec

from .base import ToolError, mode, work
from .document import jsonl, state_text
from .knowledge import tokens


@lru_cache(maxsize=4)
def route_cache(work_dir) -> dict:
    f = work_dir / "route.jsonl"
    return {r["page_id"]: r["probs"] for r in jsonl(f)} if f.exists() else {}


def _yes(p, source):
    return {"answer": "yes" if p >= 0.5 else "no", "p_yes": round(p, 4), "source": source}


def _pick(probs, source):
    z = sum(probs.values()) or 1
    probs = {k: round(v / z, 4) for k, v in probs.items()}
    return {"answer": max(probs, key=probs.get), "probabilities": probs, "source": source}


def _squash(s):
    return re.sub(r"[\s'’`]", "", str(s)).lower()


def _live(qs, text):
    from ordner.models import d1

    if d1._model is None:
        d1.load()
    spec = {}
    for q in qs:
        if q["type"] == "yes_no":
            spec[q["id"]] = {"type": "noul", "instructions": q["question"]}
        else:
            spec[q["id"]] = {"type": "choice", "instructions": q.get("question") or "What kind of document is this?",
                             "criteria": d1.DOC_TYPES if q["type"] == "doc_type" else q["choices"]}
    got = d1._model.system_one(text, spec, images=None)["answers"]
    answers = {q["id"]: _yes(got[q["id"]]["noul"], "d1-3B") if q["type"] == "yes_no"
               else _pick(got[q["id"]]["probabilities"], "d1-3B") for q in qs}
    return answers, {"source": "d1-3B", "model": d1.MODEL_ID, "revision": d1.REVISION}


def _replay(q, text, cached):
    if q["type"] == "doc_type":
        if cached:
            return _pick(cached, "replay: d1-3B routing cache (work/route.jsonl)")
        return {"answer": "unknown", "probabilities": None, "source": "no cached d1 routing for this document"}
    if q["type"] == "yes_no":
        if q.get("value") in (None, ""):
            return {"answer": "unknown", "p_yes": None, "source": "heuristic: d1 not run in replay"}
        found = _squash(q["value"]) in _squash(text)
        return _yes(0.7 if found else 0.3, f"heuristic: value {'found' if found else 'not found'} in text")
    words = set(tokens(text))
    overlap = {c: len(words & set(tokens(f"{c} {d}"))) for c, d in q["choices"].items()}
    if not any(overlap.values()):
        return {"answer": "unknown", "probabilities": None, "source": "heuristic: no keyword overlap"}
    return _pick({c: float(n) for c, n in overlap.items()}, "heuristic: keyword overlap")


def score(args, ctx):
    qs = args["questions"]
    for q in qs:
        if q["type"] == "choice" and len(q.get("choices") or {}) < 2:
            raise ToolError(f"question '{q['id']}': type choice needs 'choices' with at least 2 options")
        if q["type"] in ("yes_no", "choice") and not q.get("question"):
            raise ToolError(f"question '{q['id']}': 'question' is required")
    text, page_id, src = state_text(args, ctx)
    if mode(ctx) == "live":
        answers, prov = _live(qs, text)
        return {"answers": answers}, [], {**prov, "state": src}
    cached = route_cache(work(ctx)).get(page_id) if page_id else None
    answers = {q["id"]: _replay(q, text, cached) for q in qs}
    warnings = (["replay mode: answers whose source starts with 'heuristic' are NOT d1-3B outputs"]
                if any(a["source"].startswith("heuristic") for a in answers.values()) else [])
    return {"answers": answers}, warnings, {"source": "replay", "state": src, "page_id": page_id}


TOOLS = [
    (ToolSpec(
        "decision.score",
        "Answer closed questions about a document in one pass (d1-3B): yes/no with P(yes), a choice with "
        "probabilities, or the document type. Probabilities are signals to check, never permission to act.",
        {"type": "object", "properties": {
            "doc": {"type": "string", "description": "dossier document id (doc_...), file path or page id; or give text"},
            "text": {"type": "string", "description": "state to judge, e.g. OCR text"},
            "questions": {"type": "array", "items": {"type": "object", "properties": {
                "id": {"type": "string"},
                "type": {"type": "string", "enum": ["yes_no", "choice", "doc_type"]},
                "question": {"type": "string", "description": "not needed for doc_type"},
                "choices": {"type": "object", "description": "choice only: {key: description}"},
                "value": {"type": "string", "description": "yes_no only: the value being checked, if any"}},
                "required": ["id", "type"]}}},
         "required": ["questions"]},
        {"type": "object", "properties": {"answers": {"type": "object", "description": "{id: {answer, p_yes | "
                                                       "probabilities, source}}; answer may be 'unknown'"}}},
    ), score),
]
