"""Export data/demo/demo.json (schema: src/ordner/app/README.md) from the real pipeline outputs: data/items.jsonl
(+ data/probe/A.npz), work/pages.jsonl (page images), work/route.jsonl (d1-3B) and the grounded explanations
(cached in work/explain/explanations.jsonl). `fixture` is dropped only when every part is real.
    python -m ordner.explain.export_demo              # export, reusing cached explanations
    python -m ordner.explain.export_demo --generate   # + generate the missing explanations with Apertus (MLX)"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from ordner.eval.metrics import FIELDS, read_jsonl

from . import explain

SYSTEM_PREF = ["apertus-lora", "apertus-base", "regex"]
MODEL_NAME = {"apertus-lora": "Apertus 1.5 8B (LoRA)", "apertus-base": "Apertus 1.5 8B (zero-shot)",
              "regex": "OCR + rules/regex (no LLM)"}
TARGETS = [("A", 0, "de"), ("A", 2, "fr"), ("A", 3, "it"), ("B", 2, None)]  # layout, degradation, language
CACHE = Path("work/explain/explanations.jsonl")
MAX_JPEG = 300_000


def pick_system(items, system="auto"):
    have = {it["system"] for it in items}
    return system if system != "auto" else next((s for s in SYSTEM_PREF if s in have), None)


def doubt_scores(data, system):
    """Combined P(wrong) per item (index in items.jsonl) with the replay's model (ordner.eval.run): out-of-fold on its
    fit rows (train+dev for apertus-base, dev otherwise, as in run.py), refit model for the test rows; plus probe A."""
    from sklearn.model_selection import GroupKFold, cross_val_predict

    from ordner.eval.run import COMBO_COLS, combo_model, fit_select, load, probe_scores
    col, probes = load(Path(data))
    sysm = col["system"] == system
    fit = sysm & (np.isin(col["split"], ["train", "dev"]) if system == "apertus-base" else col["split"] == "dev")
    test = sysm & (col["split"] == "test")
    probe = probe_scores(col, probes, "A", fit, test)[0] if system == "apertus-base" else np.full(len(sysm), np.nan)
    X = np.column_stack([col[c] for c in COMBO_COLS] + ([probe] if np.isfinite(probe).any() else []))
    y, groups = ~col["correct"][fit], col["stmt_id"][fit]
    combined = np.full(len(sysm), np.nan)
    try:
        model, C, _ = fit_select(X[fit], y, groups, combo_model)
        cv = GroupKFold(min(5, len(set(groups))))
        combined[fit] = cross_val_predict(combo_model(C), X[fit], y, groups=groups, cv=cv, method="predict_proba")[:, 1]
        if test.any():
            combined[test] = model.predict_proba(X[test])[:, 1]
    except ValueError as e:  # too few rows/errors (some CV fold has a single class): no combined model
        print(f"no combined doubt for {system}: {e}")
    if np.isnan(combined[sysm]).all():  # LoRA: 2 errors on dev, so d1-3B validation (best triage signal on test)
        combined = np.where(sysm, 1 - col["d1_p_yes"], np.nan)
    return combined, probe


def pick_pages(items, system):
    """One page per TARGET: layout A from dev (else test, else train = not real), layout B from test only. Within a
    target: degradation >= 2 prefers a page with at least one wrong field (shows the triage), else all-correct pages."""
    pages = {}
    for i, it in enumerate(items):
        if it["system"] == system:
            pages.setdefault(it["page_id"], []).append(i)
    chosen, missing = [], []
    for layout, deg, lang in TARGETS:
        pick = None
        for split in (["test"] if layout == "B" else ["dev", "test", "train"]):
            for want_lang in ([lang, None] if lang else [None]):
                cands = sorted(pid for pid, idx in pages.items() if pid not in [c[0] for c in chosen]
                               and items[idx[0]]["layout"] == layout and items[idx[0]]["split"] == split
                               and items[idx[0]]["degradation"] == deg
                               and (want_lang is None or items[idx[0]]["language"] == want_lang))
                if cands:
                    wrong = [p for p in cands if not all(items[i]["correct"] for i in pages[p])]
                    pref = wrong if deg >= 2 else [p for p in cands if p not in wrong]
                    pick = (pref or cands)[0]
                    break
            if pick:
                break
        if pick is None:
            missing.append(f"no {layout}{deg} page ({lang or 'any language'}) for {system}")
            continue
        if items[pages[pick][0]]["split"] == "train":
            missing.append(f"{pick}: train-split page (no dev/test outputs yet)")
        chosen.append((pick, pages[pick]))
    return chosen, missing


def fmt(v):
    if v is None:
        return None
    s = str(v)
    return s[:-2] if s.endswith(".0") else s


def rnd(v, n=3):
    return None if v is None or not np.isfinite(v) else round(float(v), n)


def export_image(src, dst):
    im = Image.open(src).convert("RGB")
    im.thumbnail((1600, 1600))
    for q in (85, 75, 65, 55, 45):
        im.save(dst, "JPEG", quality=q, optimize=True)
        if dst.stat().st_size < MAX_JPEG:
            return
    im.thumbnail((1200, 1200))
    im.save(dst, "JPEG", quality=60, optimize=True)


def cache_key(page_id, fields):
    sig = [page_id, [[f["field"], f["value"], explain.status(f["doubt"])] for f in fields]]
    return hashlib.sha1(json.dumps(sig).encode()).hexdigest()


def read_cache():
    return {r["key"]: r for r in read_jsonl(CACHE)} if CACHE.exists() else {}


def generate_missing(todo, generate=None):
    """todo: [(key, page_id, fields)]. Retrieval for all first, then EmbeddingGemma is unloaded before Apertus."""
    from ordner.models import embed
    passages = {k: {lang: explain.retrieve([{**f, "status": explain.status(f["doubt"])} for f in fields], lang)
                    for lang in explain.LANGS} for k, _, fields in todo}
    embed.unload()
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    for k, pid, fields in todo:
        ex = explain.explain_doc(fields, generate or explain.apertus_generate, passages=passages[k])
        with open(CACHE, "a") as f:
            f.write(json.dumps({"key": k, "page_id": pid, "explanation": ex}, ensure_ascii=False) + "\n")
        print(f"{pid}: {sum(c['verified'] for c in ex['citations'])} verified quotes, {len(ex['dropped'])} dropped",
              flush=True)


def build(data, work, out, system="auto", generate=False):
    data, work, out = Path(data), Path(work), Path(out)
    items = read_jsonl(data / "items.jsonl")
    system = pick_system(items, system)
    combined, probe = doubt_scores(data, system)
    chosen, missing = pick_pages(items, system)
    pages = {p["page_id"]: p for p in read_jsonl(work / "pages.jsonl")}
    route = {r["page_id"]: r for r in read_jsonl(work / "route.jsonl")} if (work / "route.jsonl").exists() else {}

    docs = []
    for pid, idx in chosen:
        by_field = {items[i]["field"]: i for i in idx}
        meta = items[idx[0]]
        fields = []
        for f in FIELDS:
            if f not in by_field:
                missing.append(f"{pid}: no item for {f}")
                continue
            i = by_field[f]
            it = items[i]
            fields.append({"field": f, "value": fmt(it["pred"]), "gold": fmt(it["gold"]),
                           "correct": it["correct"] if it["gold"] is not None else None,
                           "model": MODEL_NAME.get(system, system), "doubt": rnd(combined[i]),
                           "signals": {"probe": rnd(probe[i]), "d1_p_yes": rnd(it["d1_p_yes"]),
                                       "rule": "consistency" if it["rule_ok"] is not None else None,
                                       "rule_ok": it["rule_ok"], "lp_min": rnd(it["lp_min"])}})
        for what, bad in (("gold", [f["field"] for f in fields if f["gold"] is None]),
                          ("doubt score", [f["field"] for f in fields if f["doubt"] is None])):
            if bad:
                missing.append(f"{pid}: no {what} for {len(bad)} field(s)")
        doc = {"page_id": pid, "image": f"{pid}.jpg", "language": meta["language"], "layout": meta["layout"],
               "degradation": meta["degradation"], "split": meta["split"], "fields": fields, "explanation": None}
        if meta["layout"] == "B":
            doc["note"] = "Layout B (test split): unseen layout, display only (never used for training or tuning)."
        r = route.get(pid)
        if r:
            doc["route"] = {"model": "d1-3B", "label": r["label"], "p": rnd(r["probs"][r["label"]])}
        else:
            missing.append(f"{pid}: no route (work/route.jsonl)")
        png = Path(pages.get(pid, {}).get("png_path") or "")
        if png.is_file():
            out.mkdir(parents=True, exist_ok=True)
            export_image(png, out / doc["image"])
        else:
            missing.append(f"{pid}: no page image")
            doc["image"] = None
        docs.append(doc)

    cache = read_cache()
    keys = {d["page_id"]: cache_key(d["page_id"], d["fields"]) for d in docs}
    todo = [(keys[d["page_id"]], d["page_id"], d["fields"]) for d in docs if keys[d["page_id"]] not in cache]
    if generate and todo:
        generate_missing(todo, generate if callable(generate) else None)
        cache = read_cache()
    for d in docs:
        c = cache.get(keys[d["page_id"]])
        if c:
            e = c["explanation"]
            d["explanation"] = {"text": e["text"], "citations": e["citations"], "dropped": e["dropped"]}
            missing += [f"{d['page_id']}: no {lang} explanation" for lang in explain.LANGS if not e["text"].get(lang)]
        else:
            missing.append(f"{d['page_id']}: no explanation (run with --generate)")

    note = (f"Pipeline export ({MODEL_NAME.get(system, system)}). Pages: one per target {TARGETS} (layout, "
            "degradation, language); layout A from dev, layout B from test; within a target, degradation >= 2 prefers a "
            "page with an extraction error, otherwise an error-free page. Doubt = combined model of ordner.eval.run "
            "(out-of-fold on its fit rows), or 1 - d1-3B validation where the combined model is not estimable (LoRA). "
            "Explanations: Apertus 1.5 8B (base, MLX), quotes verified word for word.")
    demo = {**({"fixture": True} if missing else {}), "note": note + (" MISSING: " + "; ".join(missing) if missing else ""),
            "doubt_levels": explain.DOUBT_LEVELS, "documents": docs}
    out.mkdir(parents=True, exist_ok=True)
    (out / "demo.json").write_text(json.dumps(demo, indent=1, ensure_ascii=False))
    keep = {d["image"] for d in docs}
    for old in out.glob("*.jpg"):
        if old.name not in keep:
            old.unlink()
    return demo, missing


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--work", default="work")
    ap.add_argument("--out", default="data/demo")
    ap.add_argument("--system", default="auto", choices=["auto"] + SYSTEM_PREF)
    ap.add_argument("--generate", action="store_true", help="generate missing explanations with Apertus (MLX)")
    a = ap.parse_args()
    demo, missing = build(a.data, a.work, a.out, a.system, a.generate)
    print(f"{Path(a.out) / 'demo.json'}: {len(demo['documents'])} documents, fixture={demo.get('fixture', False)}")
    for m in missing:
        print("  missing:", m)
