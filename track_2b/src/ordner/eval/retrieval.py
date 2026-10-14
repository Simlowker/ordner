"""Does EmbeddingGemma 2 help knowledge.search? BM25 alone vs embedding alone vs their RRF fusion (the live tool),
over the same passages (corpus + verified card quotes), on data/retrieval/queries.json (gold = the procedure card).
python -m ordner.eval.retrieval [queries.json]  ->  data/retrieval/results[_<set>].json"""
import sys
import json
import random
from collections import Counter
from pathlib import Path

from ordner.tools.knowledge import RRF_K, bm25, corpus

QUERIES = Path("data/retrieval/queries.json")


def order(scores):
    return sorted(range(len(scores)), key=lambda i: -scores[i])


def fuse(*orders):
    s = Counter()
    for o in orders:
        for r, i in enumerate(o):
            s[i] += 1 / (RRF_K + r)
    return [i for i, _ in s.most_common()]


def first_hit(o, gold):
    return next((r for r, i in enumerate(o) if i in gold), None)


def bootstrap_diff(a, b, n=10000, seed=0):
    rnd, d = random.Random(seed), [x - y for x, y in zip(a, b)]
    m = sorted(sum(rnd.choice(d) for _ in d) / len(d) for _ in range(n))
    return round(m[int(0.025 * n)], 3), round(m[int(0.975 * n)], 3)


def main(queries=QUERIES):
    from ordner.explain import retrieve

    _, ps, *_ = corpus()
    qs = json.loads(Path(queries).read_text())["queries"]
    gold_of, local = {}, {}
    for q in qs:
        card = q["card"]
        urls = {p["url"] for p in ps if p.get("card_id") == card}
        gold_of[card] = {i for i, p in enumerate(ps) if p.get("card_id") == card or (not p.get("card_id") and p["url"] in urls)}
        local[card] = Counter(ps[i]["lang"] for i in gold_of[card]).most_common(1)[0][0]
    rows = []
    for q in qs:
        lex = bm25(q["q"])
        lex_o = [i for i in order(lex) if lex[i] > 0]  # as in knowledge.search: zero-score passages are not ranked
        sem_o = [int(i) for i in retrieve.scores(q["q"], ps).argsort()[::-1]]
        ranks = {m: first_hit(o, gold_of[q["card"]]) for m, o in
                 (("bm25", lex_o), ("embed", sem_o), ("fusion", fuse(lex_o, sem_o)))}
        rows.append({**q, "cross_lingual": q["lang"] != local[q["card"]], "first_hit_rank": ranks})
    hit = lambda rs, m, k: [int(r["first_hit_rank"][m] is not None and r["first_hit_rank"][m] < k) for r in rs]  # noqa: E731
    mrr = lambda rs, m: sum(1 / (r["first_hit_rank"][m] + 1) for r in rs if r["first_hit_rank"][m] is not None and r["first_hit_rank"][m] < 10) / len(rs)  # noqa: E731,E501
    groups = {"all": rows, "same_language": [r for r in rows if not r["cross_lingual"]],
              "cross_lingual": [r for r in rows if r["cross_lingual"]]}
    metrics = {g: {"n": len(rs), **{m: {"hit@3": round(sum(hit(rs, m, 3)) / len(rs), 3), "mrr@10": round(mrr(rs, m), 3)}
                                    for m in ("bm25", "embed", "fusion")}} for g, rs in groups.items() if rs}
    metrics["all"]["fusion_minus_bm25_hit@3_ci95"] = bootstrap_diff(hit(rows, "fusion", 3), hit(rows, "bm25", 3))
    report = {"queries": str(queries), "passages": len(ps), "embed_model": "google/embeddinggemma-2", "rrf_k": RRF_K, "metrics": metrics, "rows": rows}
    out = Path(queries).with_name(Path(queries).stem.replace("queries", "results") + ".json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(metrics, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
