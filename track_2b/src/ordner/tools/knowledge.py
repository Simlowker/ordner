"""knowledge.search: BM25 over the official corpus (always), fused with EmbeddingGemma 2 (explain/retrieve.py) in live mode."""
import math
import re
import unicodedata
from collections import Counter
from functools import lru_cache
from urllib.parse import urlsplit

from ordner.core.schema import ToolSpec

from .base import ROOT, mode
from .document import jsonl

CANTONS = set("AG AI AR BE BL BS FR GE GL GR JU LU NE NW OW SG SH SO SZ TG TI UR VD VS ZG ZH".split())
RRF_K = 60


def tokens(s):
    s = "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))
    # ponytail: 5-letter prefixes as a crude de/fr/it stemmer (Steuerwert/Steuerwerte, titre/titres); numbers exact.
    return [t if t.isdigit() else t[:5] for t in re.findall(r"\w+", s)]


def jurisdiction(url):
    m = re.search(r"\.([a-z]{2})\.ch$", urlsplit(url).hostname or "")
    return m.group(1).upper() if m and m.group(1).upper() in CANTONS else "CH"


@lru_cache(maxsize=1)
def corpus():
    d = ROOT / "data" / "corpus"
    path = d / "passages.jsonl" if (d / "passages.jsonl").exists() else d / "passages_public.jsonl"
    ps = list(jsonl(path))
    docs = [Counter(tokens(f"{p['source_title']} {p['text']}")) for p in ps]
    lens = [sum(c.values()) for c in docs]
    return path, ps, docs, lens, Counter(t for c in docs for t in c)


def bm25(query, k1=1.5, b=0.75):
    _, _, docs, lens, df = corpus()
    n, avg, q = len(docs), sum(lens) / len(lens), set(tokens(query))
    idf = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in q}
    return [sum(idf[t] * c[t] * (k1 + 1) / (c[t] + k1 * (1 - b + b * dl / avg)) for t in q if t in c)
            for c, dl in zip(docs, lens)]


def search(args, ctx):
    path, ps, *_ = corpus()
    query, k, lang, canton = args["query"], min(args.get("k", 3), 8), args.get("lang"), args.get("canton")
    warnings, prov = [], {"corpus": str(path.relative_to(ROOT)), "method": "bm25"}
    lex = bm25(query)
    ranks = [{i: r for r, i in enumerate(sorted((i for i, s in enumerate(lex) if s > 0), key=lambda i: -lex[i]))}]
    if mode(ctx) == "live":
        try:
            from ordner.explain import retrieve  # relative paths: run from track_2b/

            ids = {p["passage_id"]: i for i, p in enumerate(ps)}
            ranks.append({ids[r["passage_id"]]: j for j, r in enumerate(retrieve.top_k(query, None, k=len(ps)))
                          if r["passage_id"] in ids})
            prov.update(method="bm25 + EmbeddingGemma 2 (reciprocal rank fusion)", embed_model="google/embeddinggemma-2")
        except Exception as e:
            warnings.append(f"semantic search unavailable, lexical only ({type(e).__name__}: {e})")
    score = {i: sum(1 / (RRF_K + r[i]) for r in ranks if i in r) for r in ranks for i in r}
    keep = [i for i in sorted(score, key=lambda i: -score[i])
            if (not lang or ps[i]["lang"] == lang) and (not canton or jurisdiction(ps[i]["url"]) in ("CH", canton))][:k]
    if not keep:
        warnings.append("no passage matched: rephrase with the official terms, or the corpus does not cover this")
    hits = [{"passage_id": ps[i]["passage_id"], "title": ps[i]["source_title"], "url": ps[i]["url"],
             "page": ps[i].get("page"), "lang": ps[i]["lang"], "jurisdiction": jurisdiction(ps[i]["url"]),
             "score": round(score[i], 4), "text": ps[i]["text"]} for i in keep]
    return {"passages": hits}, warnings, prov


TOOLS = [
    (ToolSpec(
        "knowledge.search",
        "Search official Swiss sources (federal/cantonal tax guides, eCH-0196 standard) for passages to cite. "
        "A passage found is not proof that a rule applies: read it, cite its url.",
        {"type": "object", "properties": {
            "query": {"type": "string", "description": "question or official terms, any of de/fr/it"},
            "lang": {"type": "string", "enum": ["de", "fr", "it"], "description": "passage language filter"},
            "canton": {"type": "string", "description": "two-letter canton: keeps federal + that canton's sources"},
            "k": {"type": "integer", "description": "number of passages, default 3, max 8"}},
         "required": ["query"]},
        {"type": "object", "properties": {"passages": {"type": "array", "items": {"type": "object", "properties": {
            "passage_id": {"type": "string"}, "title": {"type": "string"}, "url": {"type": "string"},
            "page": {"type": "integer"}, "lang": {"type": "string"}, "jurisdiction": {"type": "string"},
            "score": {"type": "number"}, "text": {"type": "string"}}}}}},
    ), search),
]
