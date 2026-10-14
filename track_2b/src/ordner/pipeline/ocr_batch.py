import argparse
import json
import time
from pathlib import Path

import torch

from ordner.models import ocr

SPLIT_ORDER = {"train": 0, "dev": 1, "test": 2}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="work")
    ap.add_argument("--longest-edge", type=int, default=1280)
    ap.add_argument("--shard", default="0/1", help="i/n: process every n-th page starting at i")
    args = ap.parse_args()
    work = Path(args.work)
    i, n = map(int, args.shard.split("/"))
    pages = [json.loads(l) for l in open(work / "pages.jsonl")]
    pages.sort(key=lambda p: (SPLIT_ORDER[p["split"]], p["page_id"]))
    pages = pages[i::n]
    out = work / f"ocr.{i}of{n}.jsonl"
    done = {json.loads(l)["page_id"] for l in open(out)} if out.exists() else set()
    ocr.load(dtype=torch.bfloat16, longest_edge=args.longest_edge)
    with open(out, "a") as f:
        for p in pages:
            if p["page_id"] in done:
                continue
            t = time.time()
            text = ocr.ocr_page(p["png_path"])
            f.write(json.dumps({"page_id": p["page_id"], "model": "LightOnOCR-3-1B", "longest_edge": args.longest_edge,
                                "text": text, "seconds": round(time.time() - t, 2)}, ensure_ascii=False) + "\n")
            f.flush()


if __name__ == "__main__":
    main()
