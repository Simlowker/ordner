"""Apertus 1.5 8B on MLX, with the same prompt, chat template call and parsing as models/apertus.py (transformers).

Validation against transformers (CPU, first page only), from track_2b/:
    PYTHONPATH=src ../.venv/bin/python -m ordner.models.apertus_mlx 2
"""
import gc
import json
import sys
import time
from pathlib import Path

import mlx.core as mx
import numpy as np
from mlx.utils import tree_unflatten
from mlx_lm import load as mlx_load
from mlx_lm.generate import generate_step
from mlx_lm.models.base import create_attention_mask

from . import FIELDS
from . import apertus as hf

MODEL = Path("~/ordner/models/apertus-v1.5-8b-text").expanduser()
EOS = {2, 68, 72}
LAYERS = hf.LAYERS

_model = None


def load(adapter_path=None):
    global _model
    _model, tok = mlx_load(str(MODEL) if MODEL.exists() else hf.MODEL_ID, adapter_path=adapter_path)
    hf._tok = tok._tokenizer
    if adapter_path:  # fuse LoRA into the weights (as mlx_lm.fuse): unfused adapters cost ~50 % more per page
        _model.update_modules(tree_unflatten([(n, m.fuse()) for n, m in _model.named_modules() if hasattr(m, "fuse")]))


def _float32(tokens, logits):
    # Log-softmax and greedy argmax in float32 like transformers (mlx-lm would do them in bf16).
    return logits.astype(mx.float32)


def extract(ocr_text, lang_hint=None, max_new_tokens=256) -> dict:
    prompt_ids = hf.build_prompt_ids(ocr_text, lang_hint)
    t = time.perf_counter()
    answer_ids, lp, ent = [], [], []
    for tok, logp in generate_step(mx.array(prompt_ids), _model, max_tokens=max_new_tokens,
                                   logits_processors=[_float32]):
        answer_ids.append(tok)
        lp.append(logp[tok])
        ent.append(-(mx.exp(logp) * logp).sum())
        if tok in EOS:
            break
    lp, ent = np.array(mx.stack(lp)), np.array(mx.stack(ent))
    seconds = time.perf_counter() - t
    text = hf._tok.decode(answer_ids, skip_special_tokens=True)
    spans = hf.token_spans(answer_ids, hf.value_char_spans(hf._tok.decode(answer_ids)))
    doubt = {k: {"lp_min": float(lp[s:e].min()), "lp_mean": float(lp[s:e].mean()),
                 "ent_mean": float(ent[s:e].mean()), "ent_first": float(ent[s])} for k, (s, e) in spans.items()}
    return {"fields": hf.parse_json(text), "raw": text, "prompt_ids": prompt_ids, "answer_ids": answer_ids,
            "spans": spans, "logprobs": {k: lp[s:e].tolist() for k, (s, e) in spans.items()}, "doubt": doubt,
            "seconds": seconds}


def _f16(a):
    b = a.astype(np.float16)
    return b if np.isfinite(b).all() else a


def hidden_states(prompt_ids, answer_ids, spans, layers=LAYERS) -> dict:
    """One teacher-forced pass; residual stream after each decoder layer in `layers` (1-based, as transformers'
    hidden_states). Per field: A = mean over value tokens, B = token before the value; [len(layers), 4096]."""
    t = time.perf_counter()
    p = len(prompt_ids)
    m = _model.model
    h = m.embed_tokens(mx.array(list(prompt_ids) + list(answer_ids))[None])
    mask = create_attention_mask(h)
    keep = []
    for i, layer in enumerate(m.layers, 1):
        h = layer(h, mask)
        if i in layers:
            keep.append(h[0, p - 1:])
    st = np.array(mx.stack(keep).astype(mx.float32))  # [L, 1 + len(answer), H]; index 0 = last prompt token
    fields = {k: {"A": _f16(st[:, 1 + s: 1 + e].mean(1)), "B": _f16(st[:, s])} for k, (s, e) in spans.items()}
    return {"layers": list(layers), "fields": fields, "seconds": time.perf_counter() - t}


def _cos(a, b):
    a, b = a.astype(np.float64), b.astype(np.float64)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


if __name__ == "__main__":
    from ordner.pipeline.extract_batch import read_ocr

    ocr = read_ocr("work")
    pages = list(ocr)[: int(sys.argv[1]) if len(sys.argv) > 1 else 2]
    load()
    runs = []
    for pid in pages:
        ex = extract(ocr[pid])
        hs = hidden_states(ex["prompt_ids"], ex["answer_ids"], ex["spans"])
        runs.append({"page": pid, "gen_s": round(ex["seconds"], 2), "hidden_s": round(hs["seconds"], 2),
                     "n_prompt": len(ex["prompt_ids"]), "n_answer": len(ex["answer_ids"]), "raw": ex["raw"],
                     "fields": ex["fields"], "doubt": ex["doubt"]})
        print(json.dumps(runs[-1], ensure_ascii=False), flush=True)
        if len(runs) == 1:
            ex0, hs0 = ex, hs
    _model = None
    gc.collect()
    mx.clear_cache()

    import torch
    from transformers import AutoModelForCausalLM

    # Same as hf.load("cpu") without device_map (accelerate is not installed on macstudio).
    hf._model = AutoModelForCausalLM.from_pretrained(str(MODEL), dtype=torch.bfloat16).eval()
    hf._model.config.tie_last_hidden_states = False
    ref = hf.extract(ocr[pages[0]])
    href = hf.hidden_states(ex0["prompt_ids"], ex0["answer_ids"], ex0["spans"])  # MLX tokens, teacher-forced
    same = ref["answer_ids"] == ex0["answer_ids"]
    div = next((i for i, (a, b) in enumerate(zip(ref["answer_ids"], ex0["answer_ids"])) if a != b),
               None if same else min(len(ref["answer_ids"]), len(ex0["answer_ids"])))
    cos = {}
    for li, layer in enumerate(LAYERS):
        c = {pos: [_cos(hs0["fields"][k][pos][li], href["fields"][k][pos][li]) for k in hs0["fields"]] for pos in "AB"}
        ratio = [float(np.linalg.norm(hs0["fields"][k]["A"][li].astype(np.float64))
                       / np.linalg.norm(href["fields"][k]["A"][li].astype(np.float64))) for k in hs0["fields"]]
        cos[layer] = {"A_min": round(min(c["A"]), 5), "A_mean": round(float(np.mean(c["A"])), 5),
                      "B_min": round(min(c["B"]), 5), "B_mean": round(float(np.mean(c["B"])), 5),
                      "normA_ratio_mean": round(float(np.mean(ratio)), 4)}
    lp_diff = (max(abs(a - b) for k in ex0["logprobs"] for a, b in zip(ex0["logprobs"][k], ref["logprobs"][k]))
               if same else None)
    report = {"page": pages[0], "same_answer_ids": same, "first_divergence": div, "raw_mlx": ex0["raw"],
              "raw_hf": ref["raw"], "fields_equal": {k: ex0["fields"][k] == ref["fields"][k] for k in FIELDS},
              "value_logprob_max_abs_diff": lp_diff, "hf_gen_s": round(ref["seconds"], 1), "cos": cos, "mlx": runs}
    Path("work/mlx_check.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print(json.dumps({k: v for k, v in report.items() if k != "mlx"}, indent=1, ensure_ascii=False))
