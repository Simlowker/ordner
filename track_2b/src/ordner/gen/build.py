"""Build the P0 dataset: python -m ordner.gen.build --n 600 --seed 7 --out work/"""

import argparse
import json
import logging
import random
import time
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from multiprocessing import Pool
from pathlib import Path

import pypdfium2 as pdfium
from opensteuerauszug.calculate.base import CalculationMode
from opensteuerauszug.calculate.total import TotalCalculator
from opensteuerauszug.model.ech0196 import TaxStatement
from opensteuerauszug.render.render import format_currency_2dp, format_currency_rounded, render_tax_statement

from . import layout_b, oracle, synth
from .degrade import degrade

DPI = 200
# Decimals shown on the summary page for each layout (OSA rounds the totals to whole francs).
PREC = {"A": {"totalTaxValue": 0, "totalGrossRevenueA": 0, "totalGrossRevenueB": 0, "totalWithHoldingTaxClaim": 2},
        "B": dict.fromkeys(synth.NUMERIC, 2), "C": dict.fromkeys(synth.NUMERIC, 2)}


def render_a(xml_path, pdf_path, lang):
    st = TaxStatement.from_xml_file(str(xml_path))
    check = TotalCalculator(mode=CalculationMode.VERIFY)
    check.calculate(st)
    if check.errors:
        raise ValueError(f"{xml_path}: inconsistent totals {check.errors}")
    TotalCalculator(mode=CalculationMode.FILL).calculate(st)
    render_tax_statement(st, pdf_path, language=lang)


def display(layout, values):
    if layout == "B":
        return {k: layout_b.fmt(values[k]) for k in synth.NUMERIC}
    return {k: (format_currency_2dp if PREC["A"][k] else format_currency_rounded)(Decimal(values[k]))
            for k in synth.NUMERIC}


def at_page_precision(layout, values):
    return {k: str(Decimal(values[k]).quantize(Decimal(1).scaleb(-PREC[layout][k]), ROUND_HALF_UP))
            for k in synth.NUMERIC}


def split_of(n, seed):
    order = list(range(n))
    random.Random(seed).shuffle(order)
    n_test, n_dev = max(1, round(0.2 * n)), max(1, round(0.1 * n))
    return {i: "test" if r < n_test else "dev" if r < n_test + n_dev else "train" for r, i in enumerate(order)}


def process(job):
    seed, idx, split, out = job
    out = Path(out)
    sid = f"s{idx:04d}"
    xml_path = out / "xml" / f"{sid}.xml"
    pdf_a = out / "pdf" / f"{sid}-A.pdf"
    t0 = time.time()
    # ponytail: pdf417gen raises "Not enough space in the barcode" for ~0.3 % of payload sizes; redraw the statement.
    for attempt in range(5):
        xml, truth, meta = synth.make_statement(seed, idx, attempt)
        xml_path.write_bytes(xml)
        try:
            render_a(xml_path, pdf_a, meta["language"])
            break
        except ValueError as e:
            if "Not enough space" not in str(e) or attempt == 4:
                raise
    lang = meta["language"]
    t_render = time.time() - t0
    orc = oracle.fields_from_xml(oracle.decode_pdf417(pdf_a))
    bad = oracle.mismatches(orc, truth)

    docs, pages = [], []
    for layout in (["A", "B"] if split == "test" else ["A"]):
        doc_id = f"{sid}-{layout}"
        pdf_path = pdf_a if layout == "A" else out / "pdf" / f"{doc_id}.pdf"
        if layout == "B":
            layout_b.render(xml_path, pdf_path, lang)
        pdf = pdfium.PdfDocument(str(pdf_path))
        n_pages = len(pdf)
        text = pdf[0].get_textpage().get_text_range()
        img = pdf[0].render(scale=DPI / 72, grayscale=True).to_pil().convert("L")
        pdf.close()
        disp = display(layout, orc)
        docs.append({
            "doc_id": doc_id, "stmt_id": sid, "split": split, "layout": layout, "seed": seed, "language": lang,
            "xml_path": str(xml_path), "pdf_path": str(pdf_path), "n_pages": n_pages, "oracle": orc,
            "oracle_page": at_page_precision(layout, orc), "oracle_display": disp,
            "page_check": {k: v in text for k, v in disp.items()}, "oracle_mismatches": bad, "meta": meta,
            "render_seconds": round(t_render, 3) if layout == "A" else None})
        levels = [0, 1, 2, 3] if split == "test" else [random.Random(f"{seed}:{idx}:level").randint(0, 3)]
        for lvl in levels:
            page_id = f"{doc_id}-p1-d{lvl}"
            png = out / "png" / f"{page_id}.png"
            degrade(img, lvl, page_id).save(png, optimize=False)
            pages.append({"page_id": page_id, "doc_id": doc_id, "stmt_id": sid, "split": split, "layout": layout,
                          "page_no": 1, "png_path": str(png), "degradation": lvl})
    return docs, pages


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="work/")
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args(argv)
    logging.getLogger("opensteuerauszug").setLevel(logging.ERROR)

    out = Path(args.out)
    for d in ("xml", "pdf", "png"):
        (out / d).mkdir(parents=True, exist_ok=True)
    splits = split_of(args.n, args.seed)
    jobs = [(args.seed, i, splits[i], str(out)) for i in range(args.n)]

    t0 = time.time()
    with Pool(args.workers) as pool:
        results = pool.map(process, jobs, chunksize=1)
    docs = [d for r in results for d in r[0]]
    pages = [p for r in results for p in r[1]]
    with open(out / "docs.jsonl", "w") as f:
        f.writelines(json.dumps(d, ensure_ascii=False) + "\n" for d in docs)
    with open(out / "pages.jsonl", "w") as f:
        f.writelines(json.dumps(p, ensure_ascii=False) + "\n" for p in pages)
    elapsed = time.time() - t0

    stmts = {d["stmt_id"]: d for d in docs}
    print(f"statements={len(stmts)} docs={len(docs)} pages={len(pages)} seconds={elapsed:.1f}")
    print("statements per split:", dict(Counter(d["split"] for d in stmts.values())))
    print("languages:", dict(Counter(d["language"] for d in stmts.values())))
    print("pages per split/layout/level:", dict(sorted(Counter((p["split"], p["layout"], p["degradation"]) for p in pages).items())))
    print("oracle mismatches:", sum(bool(d["oracle_mismatches"]) for d in stmts.values()))
    fails = Counter(k for d in docs for k, ok in d["page_check"].items() if not ok)
    print("totals not found in page text:", dict(fails) or "none")
    return docs, pages


if __name__ == "__main__":
    main()
