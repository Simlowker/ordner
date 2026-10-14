"""mlx-lm LoRA data (chat format) from the train split; dev -> valid. From track_2b/:
    PYTHONPATH=src ../.venv/bin/python -m ordner.finetune.prepare

Target = oracle values as displayed on the page (oracle_page: layout A rounds totals to whole CHF), serialised in
the JSON shape the extraction prompt asks for. Every example is checked against parse_json and against the exact
token sequence of the extraction prompt, rendered through mlx-lm's own ChatDataset.
"""
import argparse
import json
import re
from pathlib import Path

from mlx_lm.tuner.datasets import ChatDataset
from mlx_lm.utils import load_tokenizer

from ordner.finetune.train import thinking_off
from ordner.models import FIELDS, NUMERIC_FIELDS
from ordner.models import apertus as hf
from ordner.models.apertus_mlx import MODEL
from ordner.pipeline.extract_batch import read_ocr

NUMBER = re.compile(r"-?(0|[1-9]\d*)(\.\d+)?")


def gold(doc):
    v = {**doc["oracle"], **doc["oracle_page"]}
    parts = []
    for k in FIELDS:
        x = v.get(k)
        if x is None:
            s = "null"
        elif k in NUMERIC_FIELDS or k == "taxPeriod":
            assert NUMBER.fullmatch(x), (doc["doc_id"], k, x)
            s = x
        else:
            s = json.dumps(x, ensure_ascii=False)
        parts.append(f'  "{k}": {s}')
    expected = {k: None if v.get(k) is None else float(v[k]) if k in NUMERIC_FIELDS
                else int(v[k]) if k == "taxPeriod" else str(v[k]).strip() for k in FIELDS}
    return "{\n" + ",\n".join(parts) + "\n}", expected  # same layout as the base model's answers


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="work")
    ap.add_argument("--model", default=str(MODEL))
    ap.add_argument("--allow-missing", action="store_true", help="skip pages without OCR (dry runs)")
    a = ap.parse_args()
    work = Path(a.work)
    docs = {d["doc_id"]: d for d in map(json.loads, open(work / "docs.jsonl"))}
    pages = sorted(map(json.loads, open(work / "pages.jsonl")), key=lambda p: p["page_id"])
    ocr = read_ocr(work)
    thinking_off()
    tok = load_tokenizer(Path(a.model))
    hf._tok = tok._tokenizer
    out = work / "lora_data"
    out.mkdir(exist_ok=True)
    for split, name in (("train", "train"), ("dev", "valid")):
        rows, lens = [], []
        split_pages = [p for p in pages if p["split"] == split]
        for p in split_pages:
            if p["page_id"] not in ocr:
                assert a.allow_missing, f"no OCR for {p['page_id']} (OCR incomplete? use --allow-missing for a dry run)"
                continue
            answer, expected = gold(docs[p["doc_id"]])
            assert hf.parse_json(answer) == expected, (p["page_id"], answer)
            assert set(hf.value_char_spans(answer)) == set(FIELDS), answer
            row = {"messages": hf.messages(ocr[p["page_id"]]) + [{"role": "assistant", "content": answer}]}
            tokens, offset = ChatDataset([row], tok, mask_prompt=True).process(row)
            assert tokens[:offset] == hf.build_prompt_ids(ocr[p["page_id"]]), p["page_id"]
            assert hf._tok.decode(tokens[offset:]) == answer + "<|assistant_end|>", p["page_id"]
            rows.append(row)
            lens.append(len(tokens))
        with open(out / f"{name}.jsonl", "w") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        print(f"{name}: {len(rows)}/{len(split_pages)} pages with OCR"
              + (f", tokens max {max(lens)} mean {sum(lens) / len(lens):.0f}" if lens else ""))


if __name__ == "__main__":
    main()
