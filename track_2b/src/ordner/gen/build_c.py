"""Add layout C (test split, degradation 0 and 2) to an existing build. Idempotent.

python -m ordner.gen.build_c --out work/
Existing non-C lines of docs.jsonl / pages.jsonl are kept byte for byte and in order; C lines are (re)appended.
"""

import argparse
import json
import os
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

import pypdfium2 as pdfium

from . import build, layout_c, synth
from .degrade import degrade

LEVELS = (0, 2)


def process(job):
    a, out = job
    sid = a["stmt_id"]
    doc_id = f"{sid}-C"
    pdf_path = Path(out) / "pdf" / f"{doc_id}.pdf"
    style = layout_c.render(a["xml_path"], pdf_path, a["language"], key=f"{a['seed']}:{sid}:C")
    pdf = pdfium.PdfDocument(str(pdf_path))
    text = pdf[0].get_textpage().get_text_range()
    img = pdf[0].render(scale=build.DPI / 72, grayscale=True).to_pil().convert("L")
    pdf.close()
    disp = {k: layout_c.fmt(a["oracle"][k], style) for k in synth.NUMERIC}
    doc = {**a, "doc_id": doc_id, "layout": "C", "pdf_path": str(pdf_path), "n_pages": 1,
           "oracle_page": build.at_page_precision("C", a["oracle"]), "oracle_display": disp,
           # pdfium extracts the no-break space as a plain space
           "page_check": {k: v.replace("\xa0", " ") in text for k, v in disp.items()},
           "meta": {**a["meta"], "number_format": style}, "render_seconds": None}
    pages = []
    for lvl in LEVELS:
        page_id = f"{doc_id}-p1-d{lvl}"
        png = Path(out) / "png" / f"{page_id}.png"
        degrade(img, lvl, page_id).save(png)
        pages.append({"page_id": page_id, "doc_id": doc_id, "stmt_id": sid, "split": a["split"], "layout": "C",
                      "page_no": 1, "png_path": str(png), "degradation": lvl})
    return doc, pages


def _rewrite(path, kept, new):
    tmp = path.with_suffix(".jsonl.tmp")
    with open(tmp, "w") as f:
        f.writelines(kept)
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in new)
    os.replace(tmp, path)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="work/")
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args(argv)
    out = Path(args.out)

    doc_lines = [l for l in open(out / "docs.jsonl") if json.loads(l)["layout"] != "C"]
    page_lines = [l for l in open(out / "pages.jsonl") if json.loads(l)["layout"] != "C"]
    tests = [d for d in map(json.loads, doc_lines) if d["split"] == "test" and d["layout"] == "A"]
    with Pool(args.workers) as pool:
        results = pool.map(process, [(a, str(out)) for a in tests], chunksize=1)
    docs = [r[0] for r in results]
    pages = [p for r in results for p in r[1]]
    _rewrite(out / "docs.jsonl", doc_lines, docs)
    _rewrite(out / "pages.jsonl", page_lines, pages)

    print(f"layout C: docs={len(docs)} pages={len(pages)}")
    print("number formats:", dict(Counter(d["meta"]["number_format"] for d in docs)))
    print("languages:", dict(Counter(d["language"] for d in docs)))
    fails = Counter(k for d in docs for k, ok in d["page_check"].items() if not ok)
    print("totals not found in page text:", dict(fails) or "none")
    return docs, pages


if __name__ == "__main__":
    main()
