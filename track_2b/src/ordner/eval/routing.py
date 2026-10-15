"""Routing accuracy of the general preset: d1-3B (router service) vs the EmbeddingGemma 2 fallback, same rule
(ordner.harness.router.decide), on the goal of every scored scenario in fr, de and it.

Gold expert: the expert whose card prefixes cover every procedure the scenario expects (ordner.distill.by_expert), or
"coordinateur" (general) when none does. The router's TEMP and MIN_P were fixed before this measurement.

    PYTHONPATH=src .venv/bin/python -m ordner.eval.routing [--router-url http://127.0.0.1:18091]   # -> data/routing/results.json
"""
import argparse
import json
import os
import time
from collections import Counter, defaultdict
from pathlib import Path

from ordner.distill.by_expert import expert_of, procedures
from ordner.eval.scenarios.run import load, resolve
from ordner.harness import router as R
from ordner.harness.experts import EXPERTS
from ordner.models import d1, embed

OUT = Path(__file__).resolve().parents[3] / "data" / "routing" / "results.json"


def report(rows, key):
    def acc(rs):
        return round(sum(r[key] == r["gold"] for r in rs) / len(rs), 3) if rs else None
    groups = lambda f: {k: acc([r for r in rows if r[f] == k]) for k in sorted({r[f] for r in rows})}  # noqa: E731
    confusion = defaultdict(Counter)
    for r in rows:
        confusion[r["gold"]][r[key]] += 1
    return {"accuracy": acc(rows), "by_lang": groups("lang"), "by_expert": groups("gold"),
            "confusion": {g: dict(c) for g, c in sorted(confusion.items())},
            "seconds_per_query": round(sum(r[key + "_s"] for r in rows) / len(rows), 4)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--router-url", default=os.environ.get("ORDNER_ROUTER_URL"), help="d1-3B service (--serve)")
    a = ap.parse_args(argv)
    scenarios = [s for s in load("all") if not s.get("needs_review")]
    rows = []
    R.embed_scores("warm-up")   # model load out of the timing (the d1 service warms up at start)
    for s in scenarios:
        gold = expert_of(procedures(s, resolve), EXPERTS) or "coordinateur"
        for lang in ("fr", "de", "it"):
            row = {"id": s["id"], "split": s["split"], "lang": lang, "gold": gold}
            t = time.time()
            e = R.decide(R.embed_scores(s["goal"][lang]), "EmbeddingGemma")
            row.update(emb=e["expert"] or "coordinateur", emb_p=max(e["p"].values()), emb_s=time.time() - t)
            if a.router_url:
                x = R.ask(s["goal"][lang], a.router_url, fallback=False)
                assert x.get("by") == "d1-3B", x   # never score the fallback as d1
                row.update(d1=x["expert"] or "coordinateur", d1_p=max(x["p"].values()), d1_s=x["seconds"])
            rows.append(row)
    systems = {"EmbeddingGemma": {"model": embed.MODEL_ID, "dtype": "bfloat16", "where": "in process (laptop, MPS)",
                                  "temp": R.TEMP, **report(rows, "emb")}}
    if a.router_url:
        systems["d1-3B"] = {"model": f"{d1.MODEL_ID}@{d1.REVISION[:7]}", "dtype": "bfloat16",
                            "where": "router service on the GPU host; seconds measured server side", **report(rows, "d1")}
    out = {"created": time.strftime("%Y-%m-%d %H:%M"), "queries": len(rows), "scenarios": len(scenarios),
           "splits": dict(Counter(s["split"] for s in scenarios)), "gold": dict(Counter(r["gold"] for r in rows)),
           "rule": {"min_p": R.MIN_P, "general_if": "top option is coordinateur or p < min_p"},
           "systems": systems, "rows": rows}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: {m: v[m] for m in ("accuracy", "by_lang", "by_expert", "seconds_per_query")}
                      for k, v in systems.items()}, indent=1))


if __name__ == "__main__":
    main()
