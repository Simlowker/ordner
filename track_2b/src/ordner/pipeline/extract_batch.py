"""Batch field extraction with Apertus on MLX (macstudio), resumable. From track_2b/:
    PYTHONPATH=src ../.venv/bin/python -m ordner.pipeline.extract_batch --tag apertus-base
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

SPLIT_ORDER = {"train": 0, "dev": 1, "test": 2}


def read_ocr(work):
    return {r["page_id"]: r["text"] for f in sorted(Path(work).glob("ocr.*.jsonl")) for r in map(json.loads, open(f))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="apertus-base | apertus-lora")
    ap.add_argument("--adapter", help="mlx-lm adapter directory")
    ap.add_argument("--splits", default="train,dev,test")
    ap.add_argument("--shard", default="0/1", help="i/n: process every n-th page starting at i")
    ap.add_argument("--work", default="work")
    ap.add_argument("--limit", type=int, help="stop after this many new pages (timing)")
    a = ap.parse_args()
    from ordner.models import apertus_mlx as am

    work = Path(a.work)
    i, n = map(int, a.shard.split("/"))
    splits = a.splits.split(",")
    pages = [p for p in map(json.loads, open(work / "pages.jsonl")) if p["split"] in splits]
    pages.sort(key=lambda p: (SPLIT_ORDER[p["split"]], p["page_id"]))
    pages = pages[i::n]
    ocr = read_ocr(work)
    # One file per tag even when sharded (shards run on different machines; concatenate them afterwards).
    out = work / f"extract.{a.tag}.jsonl"
    done = {json.loads(l)["page_id"] for l in open(out)} if out.exists() else set()
    todo = [p["page_id"] for p in pages if p["page_id"] not in done and p["page_id"] in ocr][: a.limit]
    print(f"{len(pages)} pages, {len(done)} done, {sum(p['page_id'] not in ocr for p in pages)} without OCR, "
          f"{len(todo)} to do", flush=True)
    acts = work / "acts" / a.tag
    acts.mkdir(parents=True, exist_ok=True)
    am.load(a.adapter)
    t0 = time.time()
    with open(out, "a") as f:
        for j, pid in enumerate(todo, 1):
            try:
                ex = am.extract(ocr[pid])
                hs = am.hidden_states(ex["prompt_ids"], ex["answer_ids"], ex["spans"])
            except Exception as e:  # never stop the batch on one page; the page counts as wrong for every field
                print(f"ERROR {pid}: {type(e).__name__}: {e}", flush=True)
                f.write(json.dumps({"page_id": pid, "model": a.tag, "fields": {}, "raw": None, "doubt": {},
                                    "error": f"{type(e).__name__}: {e}"}) + "\n")
                f.flush()
                continue
            np.savez(acts / f"{pid}.npz", layers=np.array(hs["layers"]),
                     **{f"{k}_{pos}": v[pos] for k, v in hs["fields"].items() for pos in "AB"})
            f.write(json.dumps({"page_id": pid, "model": a.tag, "fields": ex["fields"], "raw": ex["raw"],
                                "doubt": ex["doubt"], "seconds": round(ex["seconds"], 2),
                                "seconds_hidden": round(hs["seconds"], 2), "n_prompt_tokens": len(ex["prompt_ids"]),
                                "n_answer_tokens": len(ex["answer_ids"])}, ensure_ascii=False) + "\n")
            f.flush()
            if j % 10 == 0 or j == len(todo):
                print(f"{j}/{len(todo)} {(time.time() - t0) / j:.2f} s/page", flush=True)


if __name__ == "__main__":
    main()
