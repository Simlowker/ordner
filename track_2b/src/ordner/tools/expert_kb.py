"""One knowledge base per expert (ordner.harness.experts): official passages collected for that expert's topics
(data/knowledge/<expert>/passages.jsonl: official acts, in the repo; work/knowledge/<expert>/passages_local.jsonl:
authority pages, rebuilt locally), ranked by EmbeddingGemma 2 (explain/retrieve.py, embeddings cached per passage set).
Topics: data/knowledge/topics.json. Measured by ordner.eval.knowledge_experts."""
import json
import os
from functools import lru_cache

from .base import ROOT

DATA, WORK = ROOT / "data" / "knowledge", ROOT / "work" / "knowledge"


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


@lru_cache(maxsize=8)
def passages(expert):
    """The expert's passages (repo first, then local), deduplicated by passage_id; [] when it has no base."""
    local = [] if os.environ.get("ORDNER_KB_REPO_ONLY") == "1" else _jsonl(WORK / expert / "passages_local.jsonl")
    rows = _jsonl(DATA / expert / "passages.jsonl") + local   # ORDNER_KB_REPO_ONLY=1: what a clean clone has
    return list({r["passage_id"]: {**r, "expert": expert} for r in rows if r.get("text")}.values())


def experts():
    return sorted(p.name for p in DATA.iterdir() if p.is_dir() and passages(p.name)) if DATA.exists() else []


def bm25(query, ps, k1=1.5, b=0.75):
    """Lexical fallback scorer (no model: Docker replay without the EmbeddingGemma weights)."""
    import math
    from collections import Counter
    from .knowledge import tokens
    docs = [Counter(tokens(f"{p['source_title']} {p['text']}")) for p in ps]
    lens = [sum(d.values()) for d in docs]
    avg, n, q = sum(lens) / max(len(lens), 1), len(docs), set(tokens(query))
    df = Counter(t for d in docs for t in d)
    idf = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in q}
    return [sum(idf[t] * d[t] * (k1 + 1) / (d[t] + k1 * (1 - b + b * dl / avg)) for t in q if t in d)
            for d, dl in zip(docs, lens)]


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
