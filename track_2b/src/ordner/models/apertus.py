import json
import re
import time

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from . import DEVICE, FIELDS, NUMERIC_FIELDS, free_memory

MODEL_ID = "andreasmartin/apertus-v1.5-8b-text"
N_LAYERS = 32
# hidden_states index: 0 = embeddings, i = output of decoder layer i (raw residual stream, see load()).
LAYERS = [4, 8, 12, 16, 20, 24, 28, 32]

SYSTEM = ("You extract data from Swiss tax statements (eCH-0196 Steuerauszug). "
          "You answer with one JSON object and nothing else.")

_model = _tok = None


def load(device=DEVICE, dtype=torch.bfloat16):
    global _model, _tok
    _tok = AutoTokenizer.from_pretrained(MODEL_ID)
    _model = AutoModelForCausalLM.from_pretrained(MODEL_ID, dtype=dtype, device_map=device).eval()
    # Keep the last layer's raw output instead of the final-norm output in hidden_states[-1].
    _model.config.tie_last_hidden_states = False


def unload():
    global _model, _tok
    _model = _tok = None
    free_memory()


def build_prompt_ids(ocr_text, lang_hint=None):
    fields = "\n".join(f"- {k}: {d}" for k, d in FIELDS.items())
    lang = f"The document is written in {lang_hint}.\n" if lang_hint else ""
    user = (
        "Extract these fields from the OCR text of the summary page of a Swiss tax statement.\n\n"
        f"Fields:\n{fields}\n\n"
        "Rules:\n"
        "- Return one JSON object with exactly these keys, in this order.\n"
        "- Numbers as plain decimals: no thousands separators, no currency, '.' as decimal point (e.g. 39351.02).\n"
        "- taxPeriod as a number, canton as its two-letter code, names copied as written.\n"
        "- null if the value is not on the page.\n"
        f"{lang}\n"
        f'OCR text:\n"""\n{ocr_text}\n"""'
    )
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    # enable_thinking=False (also the template default) renders "Deliberation: disabled" in the developer block.
    return _tok.apply_chat_template(messages, add_generation_prompt=True, enable_thinking=False,
                                    tokenize=True, return_dict=False)


def _num(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[\s'’`]|CHF", "", str(v))
    if "," in s and "." in s:
        s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", "." if re.fullmatch(r"-?\d+,\d{1,2}", s) else "")
    try:
        return float(s)
    except ValueError:
        return None


def parse_json(text):
    """Robust parse of the model answer into the 8 fields (missing -> None, numbers -> float)."""
    raw = {}
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            raw = json.loads(re.sub(r",\s*}", "}", m.group(0)))
        except json.JSONDecodeError:
            raw = {}
    if not isinstance(raw, dict) or not raw:
        raw = {}
        for k in FIELDS:
            mv = re.search(rf'"{k}"\s*:\s*("(?:[^"\\]|\\.)*"|null|-?\d+(?:[.,\'’]\d+)*)', text)
            if mv:
                v = mv.group(1)
                raw[k] = json.loads(v) if v[0] in '"n' else v
    out = {}
    for k in FIELDS:
        v = raw.get(k)
        if k in NUMERIC_FIELDS:
            v = _num(v)
        elif k == "taxPeriod":
            v = _num(v)
            v = int(v) if v is not None else None
        elif v is not None:
            v = str(v).strip() or None
        out[k] = v
    return out


def value_char_spans(text):
    """Char span [start, end) of each field's value in the raw answer (string values without quotes)."""
    spans = {}
    for k in FIELDS:
        m = re.search(rf'"{k}"\s*:\s*', text)
        if not m:
            continue
        i = m.end()
        if text.startswith('"', i):
            mv = re.match(r'"((?:[^"\\]|\\.)*)"', text[i:])
            spans[k] = (i + 1, i + 1 + len(mv.group(1))) if mv else (i, i)
        else:
            mv = re.match(r"null|-?\d+(?:[.,'’]\d+)*", text[i:])
            spans[k] = (i, i + len(mv.group(0))) if mv else (i, i)
    return spans


def token_spans(answer_ids, char_spans):
    """Map char spans to token index spans [start, end) over answer_ids."""
    ends = [len(_tok.decode(answer_ids[: i + 1])) for i in range(len(answer_ids))]
    starts = [0] + ends[:-1]
    out = {}
    for k, (s, e) in char_spans.items():
        idx = [i for i in range(len(answer_ids)) if starts[i] < e and ends[i] > s]
        if idx:
            out[k] = (idx[0], idx[-1] + 1)
    return out


@torch.inference_mode()
def extract(ocr_text, lang_hint=None, max_new_tokens=256) -> dict:
    if _model is None:
        load()
    prompt_ids = build_prompt_ids(ocr_text, lang_hint)
    inp = torch.tensor([prompt_ids], device=_model.device)
    t = time.perf_counter()
    out = _model.generate(inp, attention_mask=torch.ones_like(inp), max_new_tokens=max_new_tokens,
                          do_sample=False, output_logits=True, return_dict_in_generate=True)
    seconds = time.perf_counter() - t
    answer_ids = out.sequences[0, len(prompt_ids):].tolist()
    logp = torch.log_softmax(torch.stack(out.logits)[:, 0].float(), -1)
    tok_logprob = logp.gather(1, torch.tensor(answer_ids, device=logp.device)[:, None])[:, 0].cpu().numpy()
    tok_entropy = (-(logp.exp() * logp).sum(-1)).cpu().numpy()
    text = _tok.decode(answer_ids, skip_special_tokens=True)
    spans = token_spans(answer_ids, value_char_spans(_tok.decode(answer_ids)))
    return {
        "fields": parse_json(text),
        "raw": text,
        "prompt_ids": prompt_ids,
        "answer_ids": answer_ids,
        "spans": spans,
        "logprobs": {k: tok_logprob[s:e].tolist() for k, (s, e) in spans.items()},
        "entropy": {k: tok_entropy[s:e].tolist() for k, (s, e) in spans.items()},
        "seconds": seconds,
        "n_prompt_tokens": len(prompt_ids),
        "n_answer_tokens": len(answer_ids),
    }


@torch.inference_mode()
def forward_hidden(ids, layers=None):
    """One teacher-forced pass; returns {layer: [seq, hidden] tensor} (all 33 states if layers is None)."""
    out = _model.model(input_ids=torch.tensor([ids], device=_model.device), output_hidden_states=True,
                       use_cache=False)
    hs = out.hidden_states
    return {i: hs[i][0] for i in (layers if layers is not None else range(len(hs)))}


def _f16(t):
    # Apertus has massive activations (|x| up to ~1.2e5 at BOS, ~3.5e4 elsewhere): keep fp32 if fp16 would overflow.
    a = t.cpu().numpy()
    return a.astype(np.float16) if np.abs(a).max() < 65000 else a


@torch.inference_mode()
def hidden_states(prompt_ids, answer_ids, spans, layers=LAYERS) -> dict:
    """Per field: A = mean over value tokens, B = state at the token before the value; [len(layers), 4096] float16
    (float32 if a value would overflow fp16).
    Also returns the per-layer mean L2 norm of answer tokens over all 33 states (norm_profile)."""
    t = time.perf_counter()
    hs = forward_hidden(list(prompt_ids) + list(answer_ids))
    stacked = torch.stack([hs[i] for i in layers]).float()  # [L, seq, H]
    p = len(prompt_ids)
    fields = {}
    for k, (s, e) in spans.items():
        fields[k] = {"A": _f16(stacked[:, p + s: p + e].mean(1)), "B": _f16(stacked[:, p + s - 1])}
    ans = slice(p, p + len(answer_ids))
    norm_profile = [hs[i][ans].float().norm(dim=-1).mean().item() for i in range(len(hs))]
    max_abs = [hs[i].float().abs().max().item() for i in range(len(hs))]
    max_abs_no_bos = [hs[i][1:].float().abs().max().item() for i in range(len(hs))]
    if _model.device.type == "mps":
        torch.mps.synchronize()
    return {"layers": list(layers), "fields": fields, "norm_profile": norm_profile, "max_abs": max_abs,
            "max_abs_no_bos": max_abs_no_bos, "seconds": time.perf_counter() - t}


if __name__ == "__main__":  # parser self-check, no model needed
    f = parse_json('```json\n{"totalTaxValue": "39\'351.02", "totalGrossRevenueA": 0, "taxPeriod": "2025", '
                   '"canton": "ZH",}\n```')
    assert f["totalTaxValue"] == 39351.02 and f["totalGrossRevenueA"] == 0.0 and f["taxPeriod"] == 2025
    assert f["canton"] == "ZH" and f["institution"] is None
    f = parse_json('{"totalTaxValue": 1234,50 "canton": "VD"')  # broken JSON -> regex fallback
    assert f["totalTaxValue"] == 1234.5 and f["canton"] == "VD"
    assert value_char_spans('{"canton": "ZH", "taxPeriod": 2025}') == {"canton": (12, 14), "taxPeriod": (30, 34)}
    print("ok")
