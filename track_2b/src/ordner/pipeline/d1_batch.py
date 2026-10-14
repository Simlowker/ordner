import argparse
import glob
import json
import time
from pathlib import Path

import torch

from ordner.models import d1


def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="work")
    ap.add_argument("--tag", default="apertus-base", help="extraction to validate; 'route' only routes")
    ap.add_argument("--bf16", action="store_true")
    args = ap.parse_args()
    work = Path(args.work)
    ocr = {r["page_id"]: r["text"] for f in glob.glob(str(work / "ocr.*.jsonl")) for r in read_jsonl(f)}
    d1.load(dtype=torch.bfloat16 if args.bf16 else torch.float32)

    if args.tag == "route":
        out = work / "route.jsonl"
        done = {r["page_id"] for r in read_jsonl(out)} if out.exists() else set()
        with open(out, "a") as f:
            for pid, text in sorted(ocr.items()):
                if pid in done:
                    continue
                t = time.time()
                probs = d1.route(text)
                f.write(json.dumps({"page_id": pid, "probs": probs, "label": max(probs, key=probs.get),
                                    "seconds": round(time.time() - t, 3)}) + "\n")
                f.flush()
        return

    out = work / f"d1.{args.tag}.jsonl"
    done = {r["page_id"] for r in read_jsonl(out)} if out.exists() else set()
    with open(out, "a") as f:
        for r in read_jsonl(work / f"extract.{args.tag}.jsonl"):
            pid = r["page_id"]
            if pid in done or pid not in ocr:
                continue
            values = {k: v for k, v in (r.get("fields") or {}).items() if v not in (None, "")}
            if not values:
                continue
            t = time.time()
            p = d1.validate_all(ocr[pid], values)
            secs = round(time.time() - t, 3)  # whole page (all fields in one pass)
            for field, p_yes in p.items():
                f.write(json.dumps({"page_id": pid, "field": field, "p_yes": p_yes, "seconds": secs}) + "\n")
            f.flush()
            done.add(pid)


if __name__ == "__main__":
    main()
