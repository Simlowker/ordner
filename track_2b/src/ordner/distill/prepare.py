"""Kept trajectories -> mlx-lm LoRA data: one example per assistant turn, rendered exactly as the coordinator prompts
Apertus at inference (MLXLocal.prompt: chat template, tools, enable_thinking=False, add_generation_prompt=True) and with
the reply in Apertus' native syntax (content + <|tools_prefix|>[{"name": args}]<|tools_suffix|>, or content +
<|assistant_end|>).

    PYTHONPATH=src .venv/bin/python -m ordner.distill.prepare [--kept work/distill/kept.jsonl] [--out work/distill/lora_data]

Why not mlx-lm's {"messages"} format: the Apertus template writes tool outputs inside the assistant turn and continues
the next reply in that same turn, while at inference each reply follows add_generation_prompt, which closes the turn and
opens a new one; ChatDataset would train on sequences the model never sees, and its mask_prompt covers the last turn
only. So each turn is pre-rendered as {"prompt_text", "completion_text"}; distill/train.py tokenizes both raw (no
template on top, the text already starts with <s>) and masks the prompt: loss on the assistant reply and its end token.

Checks (1, 2, 4 abort on failure; 3 drops the turn and counts it):
 1. prompt_text == apply_chat_template(messages[:n], tools, enable_thinking=False, add_generation_prompt=True), with
    "Deliberation: disabled"
 2. completion_text is the template's own rendering of the assistant message, and the template re-rendering the whole
    conversation ends with it (first turn: equals prompt_text + completion_text)
 3. the runtime parser (parse_tool_calls) reads back the teacher's content and calls from completion_text, and the
    reply fits the student's generation budget (768 tokens, MLXLocal default)
 4. tokens(prompt + completion) == tokens(prompt) + tokens(completion), the completion ends on a token the runtime stops
    on, and decoding the completion tokens gives completion_text back
Train/valid split by variant (seeded hash). Writes train.jsonl, valid.jsonl, stats.json.
"""
import argparse
import hashlib
import json
from pathlib import Path

from ordner.agent.llm import TOOLS_SUFFIX, _names, parse_tool_calls

from . import OUT, read_jsonl, write_jsonl

BASE = Path("~/ordner/models/apertus-v1.5-8b-text").expanduser()   # macstudio; else the Hub cache
BASE_ID = "andreasmartin/apertus-v1.5-8b-text"
END = "<|assistant_end|>"


def tokenizer(path=None):
    from mlx_lm.utils import load_tokenizer
    if path is None and BASE.exists():
        path = BASE
    if path is None or not Path(path).exists():
        from huggingface_hub import snapshot_download
        path = snapshot_download(path or BASE_ID, allow_patterns=["*.json", "*.jinja"])
    return load_tokenizer(Path(path))


def render(tok, messages, tools, generation):
    return tok.apply_chat_template(messages, tools=tools or None, tokenize=False, enable_thinking=False,
                                   add_generation_prompt=generation)


def assistant_message(reply):
    """The message the coordinator appends to its history (same JSON for the arguments)."""
    m = {"role": "assistant", "content": reply.get("content") or ""}
    if reply.get("tool_calls"):
        m["tool_calls"] = [{"type": "function", "function": {"name": c["name"], "arguments": json.dumps(
            c["arguments"], ensure_ascii=False)}} for c in reply["tool_calls"]]
    return m


def completion_text(tok, reply, tools):
    base = [{"role": "user", "content": "x"}]
    head, full = render(tok, base, tools, True), render(tok, base + [assistant_message(reply)], tools, False)
    assert full.startswith(head), "template: assistant turn does not extend the generation prompt"
    return full[len(head):]


def examples(tok, traj, stops, max_completion=768):
    """[(example, n_tokens)] for every turn of a kept trajectory; drops turns the runtime parser would misread and
    replies longer than the student's generation budget (MLXLocal max_tokens), which it could never finish."""
    out, dropped = [], 0
    for ph in traj["phases"]:
        msgs, tools = ph["messages"], ph["tools"]
        for t in ph["turns"]:
            prompt_msgs, reply = msgs[: t["n"]], t["reply"]
            prompt = render(tok, prompt_msgs, tools, True)
            assert "Deliberation: disabled" in prompt and "Deliberation: enabled" not in prompt
            comp = completion_text(tok, reply, tools)
            again = render(tok, prompt_msgs + [assistant_message(reply)], tools, False)
            assert again.endswith(comp), (traj["variant_id"], "template renders the turn differently in context")
            if prompt_msgs[-1]["role"] == "user":
                assert again == prompt + comp, (traj["variant_id"], "first turn is not prompt + completion")
            runtime = comp[: -len(END)] if comp.endswith(END) else comp      # MLXLocal strips eos, keeps tools_suffix
            content, calls = parse_tool_calls(runtime, _names(tools))
            want = [(c["name"], c["arguments"]) for c in reply.get("tool_calls") or []]
            if content != (reply.get("content") or "").strip() or [(c["name"], c["arguments"]) for c in calls] != want:
                dropped += 1
                continue
            p, c = tok.encode(prompt, add_special_tokens=False), tok.encode(comp, add_special_tokens=False)
            assert tok.encode(prompt + comp, add_special_tokens=False) == p + c, (traj["variant_id"], "token boundary")
            assert c and c[-1] in stops, (traj["variant_id"], "completion does not end on a stop token")
            assert tok.decode(c) == comp, (traj["variant_id"], "completion does not decode back")
            if len(c) > max_completion:
                dropped += 1
                continue
            out.append(({"prompt_text": prompt, "completion_text": comp, "variant_id": traj["variant_id"],
                         "source_id": traj["source_id"], "teacher": traj["teacher"],
                         "kind": "tool_call" if want else "answer"}, len(p) + len(c)))
    return out, dropped


def drift(trajs):
    """Tools or system prompt recorded at generation time that differ from the current coordinator: the student would
    be trained on a prompt it never gets at evaluation."""
    from ordner.agent import coordinator as C
    from ordner.eval.scenarios.agents import _DatedRegistry
    tools = {ts: C._Run("", "x", None, _DatedRegistry(C._registry(), "", ts), {}).tools
             for ts in {t.get("toolset", "base") for t in trajs}}
    issues = set()
    for t in trajs:
        now = tools[t.get("toolset", "base")]
        for ph in t["phases"]:
            if ph["tools"] != now:
                diff = {x["function"]["name"] for x in now} ^ {x["function"]["name"] for x in ph["tools"]}
                issues.add("tools: " + (", ".join(sorted(diff)) or "descriptions/schemas"))
            if ph["messages"][0]["content"] != C.SYSTEM:
                issues.add("system prompt")
    return sorted(issues)


def in_valid(variant_id, share, seed="ordner-distill-2026"):
    return int(hashlib.sha256(f"{seed}:{variant_id}".encode()).hexdigest(), 16) % 100 < share


def prepare(trajs, tok, out, valid_share=10, max_tokens=8192, allow_drift=False, max_completion=768):
    issues = drift(trajs)
    assert allow_drift or not issues, f"tool/prompt drift since generation: {issues} (regenerate, or --allow-drift)"
    stops = {tok.convert_tokens_to_ids(t) for t in (END, TOOLS_SUFFIX)}
    rows, lens, dropped, too_long = {"train": [], "valid": []}, [], 0, 0
    for t in trajs:
        exs, d = examples(tok, t, stops, max_completion)
        dropped += d
        for ex, n in exs:
            if n > max_tokens:
                too_long += 1
                continue
            rows["valid" if in_valid(t["variant_id"], valid_share) else "train"].append(ex)
            lens.append(n)
    for split, name in (("train", "train"), ("valid", "valid")):
        write_jsonl(Path(out) / f"{name}.jsonl", rows[split])
    stats = {"trajectories": len(trajs), "train": len(rows["train"]), "valid": len(rows["valid"]),
             "train_variants": len({r["variant_id"] for r in rows["train"]}),
             "valid_variants": len({r["variant_id"] for r in rows["valid"]}),
             "tool_call_turns": sum(r["kind"] == "tool_call" for s in rows.values() for r in s),
             "answer_turns": sum(r["kind"] == "answer" for s in rows.values() for r in s),
             "dropped_parser_mismatch_or_long_reply": dropped, "max_completion_tokens": max_completion, "dropped_too_long": too_long, "max_tokens": max_tokens,
             "tokens_max": max(lens, default=0), "tokens_mean": round(sum(lens) / len(lens)) if lens else 0,
             "drift": issues, "checks": "prompt == MLXLocal prompt (thinking off); completion == template rendering; "
                                        "parser round trip; token boundary; stop token; decode round trip"}
    (Path(out) / "stats.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kept", default=str(OUT / "kept.jsonl"))
    ap.add_argument("--out", default=str(OUT / "lora_data"))
    ap.add_argument("--tokenizer", help=f"default {BASE} if present, else {BASE_ID} (Hub cache)")
    ap.add_argument("--valid-share", type=int, default=10, help="percent of variants")
    ap.add_argument("--max-tokens", type=int, default=8192, help="= max_seq_length of the LoRA config")
    ap.add_argument("--max-completion-tokens", type=int, default=768, help="student budget (MLXLocal max_tokens)")
    ap.add_argument("--allow-drift", action="store_true")
    a = ap.parse_args(argv)
    stats = prepare(read_jsonl(a.kept), tokenizer(a.tokenizer), a.out, a.valid_share, a.max_tokens, a.allow_drift, a.max_completion_tokens)
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
