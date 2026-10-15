"""Does one knowledge base per expert help? On data/knowledge/questions.json (written blind, before any run), a hit is a
top-3 passage tagged with the question's topic (topics fixed in data/knowledge/topics.json before collection).
Compared, all with the federal + question-canton filter: the expert's own base ranked by EmbeddingGemma 2 (the
product), one global base with every expert's passages (no routing), BM25 on the expert's base.
python -m ordner.eval.knowledge_experts  ->  data/knowledge/results.json"""
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from ordner.tools import expert_kb
from ordner.tools.knowledge import tokens

QUESTIONS = Path("data/knowledge/questions.json")
OUT = Path("data/knowledge/results_repo_only.json" if os.environ.get("ORDNER_KB_REPO_ONLY") == "1" else "data/knowledge/results.json")


def hit(hits, topic):
    return any(topic in (h.get("topics") or []) for h in hits)


def main():
    from ordner.explain import retrieve
    qs = json.loads(QUESTIONS.read_text(encoding="utf-8"))["questions"]
    experts = expert_kb.experts()
    everyone = [p for e in experts for p in expert_kb.passages(e)]
    rows = []
    for q in qs:
        e, canton = q["expert"], (q.get("canton") if q.get("canton") != "CH" else None)
        own = expert_kb.search(q["q"], e, canton, k=3) if e in experts else []
        glob = [p for p in everyone if not canton or p.get("jurisdiction") in ("CH", canton)]
        gs = retrieve.scores(q["q"], [{"source_title": p.get("source_title", ""), "text": p["text"]} for p in glob]) if glob else []
        top_glob = [glob[i] for i in sorted(range(len(glob)), key=lambda i: -float(gs[i]))[:3]]
        bm = expert_kb.search(q["q"], e, canton, k=3, scorer=expert_kb.bm25) if e in experts else []
        rows.append({**q, "hit": {"expert_base": hit(own, q["topic"]), "global_base": hit(top_glob, q["topic"]),
                                  "bm25_expert_base": hit(bm, q["topic"])},
                     "global_top_experts": [p["expert"] for p in top_glob],
                     "top": [h["passage_id"] for h in own]})
    methods = ("expert_base", "global_base", "bm25_expert_base")
    rate = lambda rs, m: round(sum(r["hit"][m] for r in rs) / len(rs), 3) if rs else None  # noqa: E731
    by = defaultdict(list)
    for r in rows:
        by[("expert", r["expert"])].append(r)
        by[("lang", r["lang"])].append(r)
    coverage = {e: {"passages": len(expert_kb.passages(e)),
                    "in_repo": sum(1 for p in expert_kb.passages(e) if p.get("licence", "").startswith("official act")),
                    "jurisdictions": dict(Counter(p.get("jurisdiction") for p in expert_kb.passages(e))),
                    "topics": dict(Counter(t for p in expert_kb.passages(e) for t in p.get("topics") or []))}
                for e in experts}
    report = {"questions": len(rows), "experts_with_base": experts, "embed_model": "google/embeddinggemma-2",
              "overall": {m: rate(rows, m) for m in methods},
              "by": {f"{k}={v}": {m: rate(rs, m) for m in methods} | {"n": len(rs)} for (k, v), rs in sorted(by.items())},
              "global_routed_elsewhere": round(sum(any(x != r["expert"] for x in r["global_top_experts"]) for r in rows)
                                               / len(rows), 3),
              "coverage": coverage, "rows": rows}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("questions", "overall", "global_routed_elsewhere")}, indent=1))
    print(json.dumps(report["by"], indent=1))


if __name__ == "__main__":
    main()
