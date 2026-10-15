"""knowledge.search over the official corpus and the verified quotes of the procedure cards: EmbeddingGemma 2
(explain/retrieve.py) in live mode or with ORDNER_EMBED=1; BM25 only as the fallback (replay without the model, Docker). RRF fusion of the two was
dropped: BM25 matches same-language distractors and diluted the cross-lingual gain (data/retrieval/results*.json). With a dossier in ctx: the subject's canton and language filter the
passages (unless given), and the cards of the subject's open cases (or `card_id`) rank first."""
import math
import os
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
PREFER = 2.0  # BM25 boost of the procedure in context
PREFER_COS = 0.05  # ponytail: fixed cosine boost for the same; untuned (the retrieval eval has no dossier context)
# ponytail: language from the canton (bilingual cantons: majority language); subject.attrs["lang"] wins
CANTON_LANG = {"VD": "fr", "GE": "fr", "NE": "fr", "JU": "fr", "FR": "fr", "VS": "fr", "TI": "it"}
STOP = {"fr": set("le la les des du de et est un une pour que qui dans au aux sur par pas doit être sont "
                  "je j me mon ma mes vous votre nous ai suis avez quand comment quoi dois".split()),
        "de": set("der die das und ist ein eine für nicht mit von zu den dem des sich auf im bei oder wird "
                  "ich mich mir mein meine meinen habe hat haben bin sie ihr wir einen wie was wann kann muss bis".split()),
        "it": set("il lo gli dei del della di è un una per che non con nel alla sono deve "
                  "io mi mio mia ho lei suo cosa come quando posso devo entro ricevuto".split())}   # people's messages too


def tokens(s):
    s = "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))
    # ponytail: 5-letter prefixes as a crude de/fr/it stemmer (Steuerwert/Steuerwerte, titre/titres); numbers exact.
    return [t if t.isdigit() else t[:5] for t in re.findall(r"\w+", s)]


def jurisdiction(url):
    m = re.search(r"\.([a-z]{2})\.ch$", urlsplit(url).hostname or "")
    return m.group(1).upper() if m and m.group(1).upper() in CANTONS else "CH"


def lang_of(text):
    words = re.findall(r"\w+", text.lower())
    return max(STOP, key=lambda lg: sum(w in STOP[lg] for w in words))


def card_passages():
    """The verified quotes of the procedure cards, as passages (the deadline and procedure rules themselves)."""
    try:
        from ordner.procedures.catalog import load_cards
        cards = load_cards()
    except Exception:  # catalogue missing or mid-edit: corpus only
        return []
    return [{"passage_id": f"{c.id}#{i}", "source_title": s.title, "url": s.url, "page": None, "lang": lang_of(s.quote),
             "text": s.quote, "card_id": c.id, "jurisdiction": c.jurisdiction if c.jurisdiction != "CH" else jurisdiction(s.url)}
            for c in cards for i, s in enumerate(c.sources) if s.verified and s.quote]


@lru_cache(maxsize=1)
def corpus():
    d = ROOT / "data" / "corpus"
    path = d / "passages.jsonl" if (d / "passages.jsonl").exists() else d / "passages_public.jsonl"
    ps = list(jsonl(path)) + card_passages()
    docs = [Counter(tokens(f"{p['source_title']} {p['text']}")) for p in ps]
    lens = [sum(c.values()) for c in docs]
    return path, ps, docs, lens, Counter(t for c in docs for t in c)


def bm25(query, k1=1.5, b=0.75):
    _, _, docs, lens, df = corpus()
    n, avg, q = len(docs), sum(lens) / len(lens), set(tokens(query))
    idf = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for t in q}
    return [sum(idf[t] * c[t] * (k1 + 1) / (c[t] + k1 * (1 - b + b * dl / avg)) for t in q if t in c)
            for c, dl in zip(docs, lens)]


def _context(ctx):
    """(subject or None, card ids of its open cases) when a dossier session is in ctx; never opens a default store."""
    st, sid = ctx.get("store"), ctx.get("subject_id")
    if st is None or not sid:
        return None, set()
    try:
        return st.get_subject(sid), {c.card_id for c in st.cases(sid) if c.state != "closed"}
    except KeyError:
        return None, set()


def search(args, ctx):
    if ctx.get("expert"):   # an expert's own knowledge base (ordner.tools.expert_kb), when it has one
        from . import expert_kb
        if expert_kb.passages(ctx["expert"]):
            subject, _ = _context(ctx)
            canton = args.get("canton") or (subject and subject.canton)
            n, method, warn = min(args.get("k", 3), 8), "EmbeddingGemma 2", []
            try:
                hits = expert_kb.search(args["query"], ctx["expert"], canton, args.get("lang"), n)
            except Exception as e:   # no embedding model (e.g. Docker replay without weights): lexical fallback
                hits, method = expert_kb.search(args["query"], ctx["expert"], canton, args.get("lang"), n,
                                                scorer=expert_kb.bm25), "bm25 (EmbeddingGemma unavailable)"
                warn = [f"semantic search unavailable, lexical only ({type(e).__name__})"]
            return ({"passages": [{"passage_id": h["passage_id"], "title": h.get("source_title"), "url": h.get("url"),
                                   "page": None, "lang": h.get("lang"), "jurisdiction": h.get("jurisdiction"),
                                   "card_id": None, "score": h["score"], "text": h["text"]} for h in hits]},
                    warn + ([] if hits else ["no passage in this expert's knowledge base"]),
                    {"corpus": f"data/knowledge/{ctx['expert']} (expert base)", "method": method})
    path, ps, *_ = corpus()
    subject, open_cards = _context(ctx)
    canton = args.get("canton") or (subject and subject.canton)
    lang = args.get("lang") or (subject and ((subject.attrs or {}).get("lang") or CANTON_LANG.get(subject.canton, "de")))
    query, k = args["query"], min(args.get("k", 3), 8)
    preferred = {args["card_id"]} if args.get("card_id") else open_cards
    warnings, prov = [], {"corpus": f"{path.relative_to(ROOT)} + procedure card sources", "method": "bm25"}
    lex = [x * PREFER if ps[i].get("card_id") in preferred else x for i, x in enumerate(bm25(query))]
    ranks = [{i: r for r, i in enumerate(sorted((i for i, s in enumerate(lex) if s > 0), key=lambda i: -lex[i]))}]
    if mode(ctx) == "live" or os.environ.get("ORDNER_EMBED") == "1":  # ORDNER_EMBED=1: also in replay (scenario evals)
        try:
            from ordner.explain import retrieve  # relative paths: run from track_2b/

            sem = [s + PREFER_COS * (ps[i].get("card_id") in preferred) for i, s in enumerate(retrieve.scores(query, ps))]
            ranks = [{i: r for r, i in enumerate(sorted(range(len(ps)), key=lambda i: -sem[i]))}]
            prov.update(method="EmbeddingGemma 2", embed_model="google/embeddinggemma-2")
        except Exception as e:
            warnings.append(f"semantic search unavailable, lexical only ({type(e).__name__}: {e})")
    score = {i: sum(1 / (RRF_K + r[i]) for r in ranks if i in r) for r in ranks for i in r}
    where = lambda i: ps[i].get("jurisdiction") or jurisdiction(ps[i]["url"])
    ranked = [i for i in sorted(score, key=lambda i: -score[i]) if not canton or where(i) in ("CH", canton)]
    keep = [i for i in ranked if not lang or ps[i]["lang"] == lang][:k]
    if not keep and lang and not args.get("lang"):
        keep = ranked[:k]
        warnings.append(f"no passage in the subject's language ({lang}): other languages shown")
    if not keep:
        warnings.append("no passage matched: rephrase with the official terms, or the corpus does not cover this")
    hits = [{"passage_id": ps[i]["passage_id"], "title": ps[i]["source_title"], "url": ps[i]["url"],
             "page": ps[i].get("page"), "lang": ps[i]["lang"], "jurisdiction": where(i), "card_id": ps[i].get("card_id"),
             "score": round(score[i], 4), "text": ps[i]["text"]} for i in keep]
    return {"passages": hits}, warnings, prov


TOOLS = [
    (ToolSpec(
        "knowledge.search",
        "Search official Swiss sources (federal/cantonal tax guides, eCH-0196 standard, and the verified legal "
        "sources of every procedure card: deadlines, laws, official guides) for passages to cite. Defaults to the "
        "person's canton and language. A passage found is not proof that a rule applies: read it, cite its url.",
        {"type": "object", "properties": {
            "query": {"type": "string", "description": "question or official terms, any of de/fr/it"},
            "lang": {"type": "string", "enum": ["de", "fr", "it"], "description": "passage language filter"},
            "canton": {"type": "string", "description": "two-letter canton: keeps federal + that canton's sources"},
            "card_id": {"type": "string", "description": "procedure card in context: its own sources rank first"},
            "k": {"type": "integer", "description": "number of passages, default 3, max 8"}},
         "required": ["query"]},
        {"type": "object", "properties": {"passages": {"type": "array", "items": {"type": "object", "properties": {
            "passage_id": {"type": "string"}, "title": {"type": "string"}, "url": {"type": "string"},
            "page": {"type": "integer"}, "lang": {"type": "string"}, "jurisdiction": {"type": "string"},
            "card_id": {"type": ["string", "null"]}, "score": {"type": "number"}, "text": {"type": "string"}}}}}},
    ), search),
]
