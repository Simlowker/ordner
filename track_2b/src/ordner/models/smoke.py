"""Smoke test of the 4 model wrappers. From track_2b/: PYTHONPATH=src .venv/bin/python -m ordner.models.smoke

Each model runs in its own subprocess (one model in memory at a time, memory fully released after).
Raw outputs and one JSON per stage go to work/smoke/.
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import psutil
import torch
from PIL import Image, ImageFilter

from . import DEVICE, FIELDS, NUMERIC_FIELDS

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "work" / "smoke"
DEFAULT_IMAGE = "/private/tmp/claude-501/rendertest/p1.png"
STAGES = ["ocr", "apertus", "d1", "embed"]

# Values as printed on the sample page (amounts are rounded to CHF there; oracle: 39351.02 / 137.45).
EXPECTED = {"totalTaxValue": 39351.02, "totalGrossRevenueA": 0.0, "totalGrossRevenueB": 137.45,
            "totalWithHoldingTaxClaim": 0.0, "institution": "Interactive Brokers", "canton": "ZH",
            "taxPeriod": 2025, "client_last_name": "Muster"}
# Hard negatives taken from other cells of the same page.
WRONG = {"totalTaxValue": "17000", "totalGrossRevenueA": "115", "totalGrossRevenueB": "23",
         "totalWithHoldingTaxClaim": "17", "institution": "UBS", "canton": "BE", "taxPeriod": "2024",
         "client_last_name": "Meier"}


def correct(field, got):
    want = EXPECTED[field]
    if got is None:
        return False
    if field in NUMERIC_FIELDS:
        return abs(float(got) - want) < 1.0  # page shows integers
    return str(got).strip().lower() == str(want).lower()


class Meter:
    """Wall time + peak MPS driver memory + peak process RSS (sampled every 50 ms)."""

    def __enter__(self):
        self.peak_mps = self.peak_rss = 0
        self._stop = threading.Event()
        self._th = threading.Thread(target=self._run, daemon=True)
        self.t0 = time.perf_counter()
        self._th.start()
        return self

    def _run(self):
        proc = psutil.Process()
        while not self._stop.is_set():
            if torch.backends.mps.is_available():
                self.peak_mps = max(self.peak_mps, torch.mps.driver_allocated_memory())
            self.peak_rss = max(self.peak_rss, proc.memory_info().rss)
            self._stop.wait(0.05)

    def __exit__(self, *exc):
        self._stop.set()
        self._th.join()
        self.seconds = time.perf_counter() - self.t0

    def dict(self):
        return {"seconds": round(self.seconds, 2), "peak_mps_gb": round(self.peak_mps / 1e9, 2),
                "peak_rss_gb": round(self.peak_rss / 1e9, 2)}


def images(image):
    return {"clean": image, "degraded": str(OUT / "degraded.png")}


def make_degraded(src, dst):
    im = Image.open(src).convert("RGB").filter(ImageFilter.GaussianBlur(1.6))
    im.rotate(2.0, resample=Image.BICUBIC, expand=True, fillcolor="white").save(dst)


def ocr_text(name):
    p = OUT / f"ocr_{name}_fp32.md"
    return (p if p.exists() else OUT / f"ocr_{name}_bf16.md").read_text()


def stage_ocr(image, device):
    from . import ocr

    res = {}
    variants = {"fp32": (torch.float32, 1540), "bf16": (torch.bfloat16, 1540), "bf16_1024": (torch.bfloat16, 1024)}
    if device != "mps":
        variants = {"bf16": variants["bf16"]}
    for dname, (dtype, edge) in variants.items():
        with Meter() as m_load:
            ocr.load(device, dtype, longest_edge=edge)
        ocr.ocr_page(image, max_new_tokens=8)  # warm-up (MPS kernel compilation)
        runs = {}
        with Meter() as m:
            for name, path in images(image).items():
                t = time.perf_counter()
                text = ocr.ocr_page(path)
                dt = time.perf_counter() - t
                (OUT / f"ocr_{name}_{dname}.md").write_text(text)
                n = len(ocr._processor.tokenizer(text).input_ids)
                runs[name] = {"seconds": round(dt, 2), "tokens": n, "tok_s": round(n / dt, 1),
                              "has_totals": {v: v in text for v in ["39'351", "137", "0.00", "ZH", "Muster", "Interactive Brokers"]}}
        ocr.unload()
        res[dname] = {"load": m_load.dict(), "run": m.dict(), "pages": runs}
    if "fp32" in res:
        res["fp32_eq_bf16"] = {n: ocr_text_pair(n) for n in images(image)}
    return res


def ocr_text_pair(name):
    a, b = (OUT / f"ocr_{name}_fp32.md").read_text(), (OUT / f"ocr_{name}_bf16.md").read_text()
    return a == b


def compare(a, b, ans_start):
    """a = MPS, b = CPU, [seq, H]; BOS excluded except cos_bos."""
    cos = torch.nn.functional.cosine_similarity(a[1:], b[1:], dim=-1)
    ans = cos[ans_start - 1:]
    return {"cos_mean": round(cos.mean().item(), 5), "cos_min": round(cos.min().item(), 5),
            "worst_pos": int(cos.argmin()) + 1, "n_tokens_cos_below_0.99": int((cos < 0.99).sum()),
            "answer_cos_mean": round(ans.mean().item(), 5), "answer_cos_min": round(ans.min().item(), 5),
            "cos_bos": round(torch.nn.functional.cosine_similarity(a[:1], b[:1], dim=-1).item(), 5),
            "norm_mps": round(a[1:].norm(dim=-1).mean().item(), 2), "norm_cpu": round(b[1:].norm(dim=-1).mean().item(), 2),
            "rel_l2": round(((a - b)[1:].norm(dim=-1) / b[1:].norm(dim=-1)).mean().item(), 5),
            "nan_inf_mps": int((~torch.isfinite(a)).sum()), "nan_inf_cpu": int((~torch.isfinite(b)).sum())}


def stage_apertus(image, device):
    from . import apertus

    val_layers = [8, 16, 24, 32]
    res = {"device": device}
    with Meter() as m:
        apertus.load(device)
    res["load"] = m.dict()
    apertus.extract("warm-up", max_new_tokens=4)
    with Meter() as m:
        for name in images(image):
            ex = apertus.extract(ocr_text(name), lang_hint="German")
            hs = apertus.hidden_states(ex["prompt_ids"], ex["answer_ids"], ex["spans"])
            arrays = {f"{k}_{pos}": v[pos] for k, v in hs["fields"].items() for pos in ("A", "B")}
            np.savez(OUT / f"acts_{name}.npz", layers=np.array(hs["layers"]), **arrays)
            res[name] = {
                "fields": ex["fields"], "correct": {k: correct(k, ex["fields"][k]) for k in FIELDS},
                "raw": ex["raw"], "spans": ex["spans"],
                "value_tokens": {k: apertus._tok.decode(ex["answer_ids"][s:e]) for k, (s, e) in ex["spans"].items()},
                "logprobs": ex["logprobs"], "entropy": ex["entropy"],
                "n_prompt_tokens": ex["n_prompt_tokens"], "n_answer_tokens": ex["n_answer_tokens"],
                "gen_seconds": round(ex["seconds"], 2), "gen_tok_s": round(ex["n_answer_tokens"] / ex["seconds"], 1),
                "forward_seconds": round(hs["seconds"], 2),
                "fp16_nonfinite": int(sum((~np.isfinite(a)).sum() for a in arrays.values())),
                "norm_profile": [round(x, 1) for x in hs["norm_profile"]],
                "max_abs": [round(x, 1) for x in hs["max_abs"]],
                "max_abs_no_bos": [round(x, 1) for x in hs["max_abs_no_bos"]],
            }
            if name == "clean":
                ex_clean, ids = ex, ex["prompt_ids"] + ex["answer_ids"]
                ref = {k: v.float().cpu() for k, v in apertus.forward_hidden(ids, val_layers).items()}
    res["run"] = m.dict()
    apertus.unload()
    if device == "mps":
        with Meter() as m:
            apertus.load("cpu")
            t = time.perf_counter()
            cpu = {k: v.float() for k, v in apertus.forward_hidden(ids, val_layers).items()}
            cpu_s = time.perf_counter() - t
        layers = {str(k): compare(ref[k], cpu[k], len(ids) - len(ex_clean["answer_ids"])) for k in val_layers}
        for v in layers.values():
            v["worst_token"] = apertus._tok.decode([ids[v["worst_pos"]]])
        apertus.unload()
        res["cpu_validation"] = {"forward_seconds": round(cpu_s, 1), "n_tokens": len(ids), **m.dict(),
                                 "layers": layers}
    return res


def stage_d1(image, device):
    from . import d1

    res = {"device": device}
    with Meter() as m:
        d1.load(device)
    res["load"] = m.dict()
    right = {k: str(int(v)) if k in NUMERIC_FIELDS else str(v) for k, v in EXPECTED.items()}
    with Meter() as m:
        for name, path in images(image).items():
            text = ocr_text(name)
            r = {}
            for state_kind, state, imgs in [("text", text, None), ("image", None, [path])]:
                d1.route(state, imgs)  # warm-up
                t = time.perf_counter()
                route = d1.route(state, imgs)
                route_ms = (time.perf_counter() - t) * 1000
                t = time.perf_counter()
                one = d1.validate(state, "totalTaxValue", right["totalTaxValue"], imgs)
                one_ms = (time.perf_counter() - t) * 1000
                t = time.perf_counter()
                ok = d1.validate_all(state, right, imgs)
                all_ms = (time.perf_counter() - t) * 1000
                bad = d1.validate_all(state, WRONG, imgs)
                r[state_kind] = {
                    "route": {k: round(v, 4) for k, v in route.items()}, "route_ms": round(route_ms),
                    "validate_one_ms": round(one_ms), "validate_all_8_ms": round(all_ms),
                    "ms_per_question_in_batch": round(all_ms / len(right)),
                    "p_yes_right": {k: round(v, 3) for k, v in ok.items()},
                    "p_yes_wrong": {k: round(v, 3) for k, v in bad.items()},
                    "pairs_ranked_ok": sum(ok[k] > bad[k] for k in right), "single_p_yes": round(one, 3),
                }
            res[name] = r
    res["run"] = m.dict()
    d1.unload()
    return res


def stage_embed(image, device):
    from . import embed

    sents = ["Der Steuerwert aller Wertschriften beträgt 39'351 Franken.",
             "La valeur fiscale de tous les titres s'élève à 39'351 francs.",
             "Die Verrechnungssteuer kann zurückgefordert werden.",
             "L'impôt anticipé peut être récupéré.",
             "Die Katze schläft auf dem Sofa.",
             "Le train pour Genève part à huit heures."]
    res = {"device": device}
    for dname, dtype in {"bf16": torch.bfloat16, "fp32": torch.float32}.items():
        with Meter() as m:
            embed.load(device, dtype)
        load = m.dict()
        with Meter() as m:
            e = embed.embed(sents, "SentenceSimilarity")
            t = time.perf_counter()
            embed.embed([ocr_text("clean")] * 16, "Document")
            batch_ms = (time.perf_counter() - t) * 1000
        sim = e @ e.T
        res[dname] = {"load": load, "run": m.dict(), "nan": int(np.isnan(e).sum()),
                      "sim": np.round(sim, 3).tolist(),
                      "de_fr_pairs": [round(float(sim[0, 1]), 3), round(float(sim[2, 3]), 3)],
                      "max_unrelated": round(float(max(sim[0, 4], sim[0, 5], sim[1, 4], sim[1, 5], sim[2, 5], sim[3, 4])), 3),
                      "ms_per_page_doc_16": round(batch_ms / 16, 1)}
        res[dname]["sanity_ok"] = min(res[dname]["de_fr_pairs"]) > res[dname]["max_unrelated"]
        res[dname]["_emb"] = e
        embed.unload()
    res["bf16_vs_fp32_cos_min"] = round(float((res["bf16"].pop("_emb") * res["fp32"].pop("_emb")).sum(1).min()), 5)
    return res


def run_stage(stage, image, device):
    res = globals()[f"stage_{stage}"](image, device)
    (OUT / f"{stage}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))


def summary():
    rows = []
    for st in STAGES:
        p = OUT / f"{st}.json"
        if not p.exists():
            rows.append((st, "FAILED", "", "", "", "", "see work/smoke/" + st + ".log"))
            continue
        r = json.loads(p.read_text())
        if st == "ocr":
            for d in [k for k in r if k != "fp32_eq_bf16"]:
                if d in r:
                    pg = r[d]["pages"]
                    rows.append((f"ocr {d}", "ok", r[d]["load"]["seconds"],
                                 " / ".join(f"{pg[n]['seconds']}s" for n in pg), r[d]["run"]["peak_mps_gb"],
                                 r[d]["run"]["peak_rss_gb"],
                                 "totals found: " + " / ".join(str(sum(pg[n]["has_totals"].values())) + "/6" for n in pg)))
        elif st == "apertus":
            acc = " / ".join(f"{sum(r[n]['correct'].values())}/8" for n in ("clean", "degraded"))
            val = r.get("cpu_validation", {}).get("layers", {})
            rows.append(("apertus", "ok", r["load"]["seconds"],
                         " / ".join(f"{r[n]['gen_seconds']}s ({r[n]['gen_tok_s']} tok/s)" for n in ("clean", "degraded")),
                         r["run"]["peak_mps_gb"], r["run"]["peak_rss_gb"],
                         f"fields {acc}; MPS-vs-CPU cos min " + ",".join(str(v["cos_min"]) for v in val.values())))
        elif st == "d1":
            c = r["clean"]
            rows.append(("d1", "ok", r["load"]["seconds"],
                         f"text {c['text']['validate_one_ms']}ms/q, img {c['image']['validate_one_ms']}ms/q",
                         r["run"]["peak_mps_gb"], r["run"]["peak_rss_gb"],
                         f"route text={max(c['text']['route'], key=c['text']['route'].get)} "
                         f"img={max(c['image']['route'], key=c['image']['route'].get)}; "
                         f"right>wrong text {c['text']['pairs_ranked_ok']}/8 img {c['image']['pairs_ranked_ok']}/8"))
        elif st == "embed":
            b = r["bf16"]
            rows.append(("embed bf16", "ok", b["load"]["seconds"], f"{b['ms_per_page_doc_16']}ms/page",
                         b["run"]["peak_mps_gb"], b["run"]["peak_rss_gb"],
                         f"sanity {b['sanity_ok']} pairs {b['de_fr_pairs']} vs {b['max_unrelated']}; "
                         f"bf16~fp32 cos {r['bf16_vs_fp32_cos_min']}"))
    head = ("stage", "status", "load s", "per item", "peak MPS GB", "peak RSS GB", "notes")
    w = [max(len(str(x[i])) for x in rows + [head]) for i in range(len(head))]
    for row in [head] + rows:
        print(" | ".join(str(x).ljust(w[i]) for i, x in enumerate(row)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", default=DEFAULT_IMAGE)
    ap.add_argument("--stage", help="run a single stage in this process")
    ap.add_argument("--stages", default=",".join(STAGES))
    ap.add_argument("--device", default=DEVICE)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.stage:
        return run_stage(a.stage, a.image, a.device)
    make_degraded(a.image, OUT / "degraded.png")
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "TOKENIZERS_PARALLELISM": "false"}
    for st in a.stages.split(","):
        (OUT / f"{st}.json").unlink(missing_ok=True)
        (OUT / f"{st}.log").unlink(missing_ok=True)
        for dev in dict.fromkeys([a.device, "cpu"]):  # MPS first, CPU fallback
            print(f"== {st} on {dev}", flush=True)
            with open(OUT / f"{st}.log", "a") as log:
                rc = subprocess.run([sys.executable, "-m", "ordner.models.smoke", "--stage", st, "--image", a.image,
                                     "--device", dev], env=env, stdout=log, stderr=subprocess.STDOUT).returncode
            if rc == 0:
                break
            print(f"   {st} failed on {dev} (rc={rc}), see {OUT / (st + '.log')}", flush=True)
    summary()


if __name__ == "__main__":
    main()
