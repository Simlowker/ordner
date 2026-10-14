"""Join gold, predictions and doubt signals into data/items.jsonl (one row per page x field x system).
python -m ordner.eval.build_items --work work --data data"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from . import rules
from .metrics import FIELDS, field_correct, gold_fields, read_jsonl
from .regex_baseline import load_ocr

SYSTEM_ORDER = ["regex", "apertus-base", "apertus-lora"]
DOUBT_KEYS = ("lp_min", "lp_mean", "ent_mean", "ent_first")


def systems_in(work):
    found = sorted(p.name[len("extract."):-len(".jsonl")] for p in Path(work).glob("extract.*.jsonl"))
    return [s for s in SYSTEM_ORDER if s in found] + [s for s in found if s not in SYSTEM_ORDER]


def stats(seconds):
    v = np.array(seconds, float)
    if not len(v):
        return {"n_pages": 0}
    return {"n_pages": len(v), "mean": round(float(v.mean()), 4), "median": round(float(np.median(v)), 4),
            "p95": round(float(np.percentile(v, 95)), 4)}


def costs(work, systems):
    """Seconds per page and per stage, from the `seconds` recorded by each step (all splits: no labels involved),
    plus the end-to-end total per page for each system (pages that have every stage)."""
    ocr = load_ocr(work)
    per = {"ocr": {p: r["seconds"] for p, r in ocr.items() if r.get("seconds") is not None}}
    totals = {}
    for system in systems:
        rows = {r["page_id"]: r for r in read_jsonl(work / f"extract.{system}.jsonl")}
        per[system] = {p: r["seconds"] for p, r in rows.items() if r.get("seconds") is not None}
        hidden = {p: r["seconds_hidden"] for p, r in rows.items() if r.get("seconds_hidden") is not None}
        if hidden:
            per[f"{system} hidden-state pass"] = hidden
        d1_path = work / f"d1.{system}.jsonl"
        if d1_path.exists():
            d1 = {}
            for r in read_jsonl(d1_path):
                if r.get("seconds") is not None:
                    d1.setdefault(r["page_id"], r["seconds"])  # page-level time, repeated on each field row
            if d1:
                per[f"d1 ({system})"] = d1
        parts = [k for k in ("ocr", system, f"{system} hidden-state pass", f"d1 ({system})") if per.get(k)]
        common = set.intersection(*(set(per[k]) for k in parts))
        totals[f"total {system}"] = {**stats([sum(per[k][p] for k in parts) for p in common]), "components": parts}
    out = {k: stats(list(v.values())) for k, v in per.items()}
    out["ocr"]["model"] = sorted({str(r.get("model")) for r in ocr.values()})
    return {**out, **totals}


def build(work, data):
    work, data = Path(work), Path(data)
    docs = {d["doc_id"]: d for d in read_jsonl(work / "docs.jsonl")}
    pages = {p["page_id"]: p for p in read_jsonl(work / "pages.jsonl")}
    ocr = load_ocr(work)
    items, log = [], Counter()
    for system in systems_in(work):
        rows = {}
        for r in read_jsonl(work / f"extract.{system}.jsonl"):
            log[(system, "duplicate rows")] += r["page_id"] in rows
            rows[r["page_id"]] = r
        d1_path = work / f"d1.{system}.jsonl"
        d1 = {(r["page_id"], r["field"]): r["p_yes"] for r in read_jsonl(d1_path)} if d1_path.exists() else {}
        for pid in sorted(rows):
            if pid not in pages:
                log[(system, "unknown page_id (dropped)")] += 1
                continue
            p, r = pages[pid], rows[pid]
            doc = docs[p["doc_id"]]
            gold = gold_fields(doc)
            fields = r.get("fields") or {}
            text = ocr[pid]["text"] if pid in ocr else None
            log[(system, "pages without OCR text (rule_ok on fields only)")] += text is None
            log[(system, "extraction error rows (all fields wrong)")] += bool(r.get("error"))
            ok = rules.check(fields, text)
            for f in FIELDS:
                doubt = (r.get("doubt") or {}).get(f) or {}
                item = {"page_id": pid, "stmt_id": p["stmt_id"], "split": p["split"], "layout": p["layout"],
                        "degradation": p["degradation"], "language": doc["language"], "system": system, "field": f,
                        "pred": fields.get(f), "gold": gold[f], "correct": field_correct(f, fields.get(f), gold[f]),
                        **{k: doubt.get(k) for k in DOUBT_KEYS}, "d1_p_yes": d1.get((pid, f)), "rule_ok": ok[f],
                        "error": r.get("error")}
                items.append(item)
                log[(system, f"items {p['split']}")] += 1
                log[(system, "items without lp_min")] += item["lp_min"] is None
                log[(system, "items without d1_p_yes")] += item["d1_p_yes"] is None
                log[(system, "items with rule_ok None")] += item["rule_ok"] is None
    data.mkdir(parents=True, exist_ok=True)
    with open(data / "items.jsonl", "w") as fh:
        fh.writelines(json.dumps(i, ensure_ascii=False) + "\n" for i in items)
    cost = {"hardware": "Apple M4 Max 36 GB", "unit": "seconds per page", "stages": costs(work, systems_in(work))}
    (data / "costs.json").write_text(json.dumps(cost, indent=1))
    print(f"wrote {len(items)} items to {data / 'items.jsonl'}, costs to {data / 'costs.json'}")
    for (system, what), n in sorted(log.items()):
        print(f"  {system:14s} {what}: {n}")
    return items


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="work")
    ap.add_argument("--data", default="data")
    args = ap.parse_args(argv)
    build(args.work, args.data)


if __name__ == "__main__":
    main()
