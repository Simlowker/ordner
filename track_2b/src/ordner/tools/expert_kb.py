"""One knowledge base per expert (ordner.harness.experts): official passages collected for that expert's topics
(data/knowledge/<expert>/passages.jsonl: official acts, in the repo; work/knowledge/<expert>/passages_local.jsonl:
authority pages, rebuilt locally), ranked by EmbeddingGemma 2 (explain/retrieve.py, embeddings cached per passage set).
Topics: data/knowledge/topics.json. Measured by ordner.eval.knowledge_experts."""
import json
from functools import lru_cache

from .base import ROOT

DATA, WORK = ROOT / "data" / "knowledge", ROOT / "work" / "knowledge"


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


@lru_cache(maxsize=8)
def passages(expert):
    """The expert's passages (repo first, then local), deduplicated by passage_id; [] when it has no base."""
    rows = _jsonl(DATA / expert / "passages.jsonl") + _jsonl(WORK / expert / "passages_local.jsonl")
    return list({r["passage_id"]: {**r, "expert": expert} for r in rows if r.get("text")}.values())


def experts():
    return sorted(p.name for p in DATA.iterdir() if p.is_dir() and passages(p.name)) if DATA.exists() else []


def search(query, expert, canton=None, lang=None, k=3, scorer=None):
    """Top-k passages of the expert's base for the query, federal + `canton` only; `lang` filters when it leaves any.
    scorer(query, passages) -> similarities (default: EmbeddingGemma 2, explain.retrieve.scores)."""
    ps = [p for p in passages(expert) if not canton or p.get("jurisdiction") in ("CH", canton)]
    if lang and any(p.get("lang") == lang for p in ps):
        ps = [p for p in ps if p.get("lang") == lang]
    if not ps:
        return []
    if scorer is None:
        from ordner.explain import retrieve
        scorer = retrieve.scores
    s = scorer(query, [{"source_title": p.get("source_title", ""), "text": p["text"]} for p in ps])
    order = sorted(range(len(ps)), key=lambda i: -float(s[i]))[:k]
    return [{**ps[i], "score": round(float(s[i]), 4)} for i in order]
