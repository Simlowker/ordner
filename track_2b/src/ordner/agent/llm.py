"""LLM backends for the coordinator. Each exposes chat(messages, tools) -> {"content", "tool_calls", "raw"} with
OpenAI-format messages/tools in and tool_calls = [{"id", "name", "arguments": dict | None, "error": str | None}] out.

Apertus 1.5 (andreasmartin/apertus-v1.5-8b-text chat template, non-thinking mode) writes tool calls as raw text:
    <|tools_prefix|>[{"tool_name": {...args}}, ...]<|tools_suffix|>
and generation stops on <|tools_suffix|> (eos id 72). mlx_lm.server 0.32 has no parser for this syntax (it logs
"model does not support tool calling", still renders the tools, and returns the call as plain content), so the
client parses it; a server that already returns OpenAI `tool_calls` (e.g. a vLLM parser) is used as is.
"""
import json
import re
import urllib.request

TOOLS_PREFIX, TOOLS_SUFFIX = "<|tools_prefix|>", "<|tools_suffix|>"
APERTUS_4BIT = "m1rkocasu/Apertus-v1.5-8B-text-MLX-4bit-DWQ"
# Apertus sometimes "calls" an answer tool (cf. display_answers in its template) instead of writing the answer.
_ANSWER = re.compile(r'\[\s*\{\s*"(?:answer|display_answers|final_answer|response)"\s*:\s*("(?:[^"\\]|\\.)*")')


def _call(i, name, args, error=None):
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError as e:
            args, error = None, f"arguments are not valid JSON: {e}"
    if args is not None and not isinstance(args, dict):
        args, error = None, "arguments must be a JSON object"
    return {"id": f"call_{i}", "name": name, "arguments": args, "error": error}


def _repair(s):
    """Re-insert closers the model forgot or swapped (Apertus 4-bit often writes '}}]' after a nested object)."""
    out, stack, in_str, esc = [], [], False, False
    for ch in s:
        if in_str:
            esc, in_str = (False, True) if esc else (ch == "\\", ch != '"')
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            while stack and stack[-1] != ch:
                out.append(stack.pop())
            if not stack:
                break
            stack.pop()
        out.append(ch)
    return "".join(out + stack[::-1])


def parse_tool_calls(text, names=None):
    """Split a raw Apertus completion into (content, calls). Accepts [{"name": args}] (Apertus template) and
    [{"name": ..., "arguments": ...}] items; a bare list without special tokens counts only if its names are known."""
    i = text.find(TOOLS_PREFIX)
    if i >= 0:
        content, block = text[:i].strip(), text[i + len(TOOLS_PREFIX):].split(TOOLS_SUFFIX)[0].strip()
    elif text.lstrip().startswith(("[{", '{"')) and names:   # also {"tool": {...}}] without the list opener (seen live)
        content, block = "", text.strip()
    else:
        return text.strip(), []
    if not block.startswith(("[", "{")) and "[" in block:
        block = block[block.index("["):]
    if m := _ANSWER.match(block):
        return f"{content} {json.loads(m.group(1))}".strip(), []
    repaired = False
    try:
        items, _ = json.JSONDecoder().raw_decode(block)
    except json.JSONDecodeError as e:
        try:
            items, _ = json.JSONDecoder().raw_decode(_repair(block))
            repaired = True
        except json.JSONDecodeError:
            if i < 0:
                return text.strip(), []
            return content, [_call(0, None, None, f"tool call is not valid JSON ({e}): {block[:200]}")]
    if isinstance(items, dict):
        items = [items]
    calls = []
    for n, it in enumerate(items if isinstance(items, list) else []):
        if isinstance(it, dict) and "name" in it and ("arguments" in it or "parameters" in it):
            calls.append(_call(n, it["name"], it.get("arguments", it.get("parameters"))))
        elif isinstance(it, dict) and len(it) == 1:
            (name, args), = it.items()
            calls.append(_call(n, name, args))
        else:
            calls.append(_call(n, None, None, f"cannot read tool call item: {json.dumps(it)[:200]}"))
    if i < 0 and not all(c["name"] in names for c in calls):
        return text.strip(), []
    for c in calls:
        c["repaired"] = repaired
    return content, calls


def _names(tools):
    return {t["function"]["name"] for t in tools or []}


class OpenAICompat:
    """Any OpenAI-compatible /v1/chat/completions server (mlx_lm.server, vLLM, LM Studio...).
    Start locally, e.g.: .venv/bin/mlx_lm.server --model m1rkocasu/Apertus-v1.5-8B-text-MLX-4bit-DWQ --port 8080"""

    def __init__(self, base_url="http://127.0.0.1:8080/v1", model="default", api_key=None, max_tokens=768,
                 timeout=600):
        self.url, self.model, self.api_key = base_url.rstrip("/") + "/chat/completions", model, api_key
        self.max_tokens, self.timeout = max_tokens, timeout

    def chat(self, messages, tools=None, extra=None):
        """extra: more body fields, e.g. {"adapters": <LoRA dir>} for mlx_lm.server."""
        body = {"model": self.model, "messages": messages, "temperature": 0, "max_tokens": self.max_tokens,
                "chat_template_kwargs": {"enable_thinking": False}}
        if tools:
            body["tools"] = tools
        body.update(extra or {})
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(self.url, json.dumps(body).encode(), headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            msg = json.load(r)["choices"][0]["message"]
        raw = msg.get("content") or ""
        if msg.get("tool_calls"):
            calls = [_call(n, c["function"]["name"], c["function"].get("arguments") or "{}")
                     for n, c in enumerate(msg["tool_calls"])]
            return {"content": raw.strip(), "tool_calls": calls, "raw": raw}
        content, calls = parse_tool_calls(raw, _names(tools))
        return {"content": content, "tool_calls": calls, "raw": raw}


class MLXLocal:
    """In-process mlx_lm, greedy, thinking off. After a tool output the template's add_generation_prompt path closes
    the assistant turn and opens a new one (what mlx_lm.server renders too); continue_after_tool=True instead ends
    the prompt at <|tool_output_end|> inside the same turn. 4-bit probe, 8 goals: both 100 % valid calls; the
    new-turn default asked fewer needless questions (work/agent_probe.mlx-v3*.json)."""

    def __init__(self, path=APERTUS_4BIT, max_tokens=768, continue_after_tool=False):
        from mlx_lm import load
        self.model, self.tok = load(path)
        for t in ("<|assistant_end|>", TOOLS_SUFFIX):
            self.tok.add_eos_token(t)
        self.max_tokens, self.continue_after_tool = max_tokens, continue_after_tool

    def prompt(self, messages, tools=None):
        cont = self.continue_after_tool and messages[-1]["role"] == "tool"
        return self.tok.apply_chat_template(messages, tools=tools or None, tokenize=False, enable_thinking=False,
                                            add_generation_prompt=not cont, continue_assistant_message=cont)

    def chat(self, messages, tools=None, extra=None):   # extra: server body fields, nothing to do in process
        from mlx_lm import stream_generate
        ids = self.tok.encode(self.prompt(messages, tools), add_special_tokens=False)
        out = [r.token for r in stream_generate(self.model, self.tok, ids, max_tokens=self.max_tokens)]
        raw = self.tok.decode([t for t in out if t not in self.tok.eos_token_ids])
        if out and out[-1] == self.tok.convert_tokens_to_ids(TOOLS_SUFFIX):
            raw += TOOLS_SUFFIX
        content, calls = parse_tool_calls(raw, _names(tools))
        return {"content": content, "tool_calls": calls, "raw": raw}

    def unload(self):
        import gc

        import mlx.core as mx
        self.model = None
        gc.collect()
        mx.clear_cache()


class MockLLM:
    """Deterministic scripted model. Each step is raw Apertus text or a callable(messages) -> raw text; the output
    goes through the same parser as the real model. After the script ends it answers 'done'."""

    def __init__(self, steps):
        self.steps, self.calls = list(steps), []

    def chat(self, messages, tools=None, extra=None):
        self.calls.append(messages)
        step = self.steps.pop(0) if self.steps else "done"
        raw = step(messages) if callable(step) else step
        content, calls = parse_tool_calls(raw, _names(tools))
        return {"content": content, "tool_calls": calls, "raw": raw}


def tool_text(name, **args):
    """Apertus syntax for one tool call (used by mock scripts)."""
    return f"{TOOLS_PREFIX}[{json.dumps({name: args}, ensure_ascii=False)}]{TOOLS_SUFFIX}"
