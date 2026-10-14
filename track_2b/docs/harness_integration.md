# DeepSeek Harness integration (W10, H8 plumbing)

Date 2026-10-14. Harness `deepseek-harness` @ `d743267` (0.2.1-alpha.2), the checkout and build from the spike
(`work/vendor/deepseek-harness`, git-ignored). Code: `src/ordner/harness/` (proxy, MCP server, runtime, patch,
selfcheck) and `--agent harness` in `ordner.eval.scenarios.run`. Nothing committed.

## Verdict for the A/B

The plumbing is equivalent. With the same scripted model, the harness and the coordinator send **identical model
inputs at every step**: same system prompt, same opening message, same tool schemas in the same order, same tool
results. This holds on all 50 dev scenarios (244/244 model calls), and the score rows are identical. The A/B
(PREREG addendum 3, H8) can therefore be run as specified.

One finding matters for the decision. Every coordinator rule the harness lacks lives in our proxy and our MCP server,
not in the harness:

- the Apertus tool-call parser;
- the step budget;
- the turn ending on `ask_user`;
- the stop after repeated duplicate calls;
- the bare tool names;
- the guard on which tools may be exposed.

In this setup the harness is a transport. It adds ~1.5 s per run with the mock and ~6 s per run with the real model,
plus a 2.4 GB alpha toolchain. Measured on this setup, it adds no capability.

## What changed vs the spike

| Spike | Now |
|---|---|
| 3 stub tools in `spike/ordner_mcp.py` | `ordner.harness.mcp_server` exposes the real tools by running the coordinator's own `_Run`. `tools/list` returns `_Run.tools`: the registry, including the process tools present at run time, with person-only ops hidden, plus `ask_user` and `prepare_action`. `tools/call` runs `_Run.dispatch`, so the semantics are the coordinator's: subject pinned, argument check, duplicate refusal, side-effect interception, injection filter, phishing warnings. The tool text is exactly the coordinator's tool message (`{"tool", "result"}`, clipped). The dossier is the scenario `Store` file. `today` and `mode` are passed in. `--tools` mirrors the caller's registry subset, i.e. the H6 `--toolset`. |
| Tools named `mcp__ordner__<name>` | The prefix is pinned in `dsh-mcp-client` and has no config option. The **proxy strips it** for the model and adds it back on the calls it returns, so Apertus sees the coordinator's bare names. A native TS plugin would also give bare names; it was not needed. |
| Raw Apertus text taken as the final answer (silent failure) | `ordner.harness.proxy` is an OpenAI `/v1/chat/completions` endpoint, SSE or JSON. It calls the backend **through the coordinator's own client** (`ordner.agent.llm`: `OpenAICompat` for mlx_lm.server/vLLM, `MLXLocal`, `MockLLM`), so the request body and the parser (`parse_tool_calls`, imported) are the same. It returns OpenAI `tool_calls`. Upstream is not streamed, so the completion is fully buffered before the SSE frames go out. A call with bad JSON, or one named outside the tool list, travels through `ask_user` with `__ordner_error__`/`__ordner_name__`. Dispatch then answers it exactly as the coordinator does, instead of the harness answering "unknown tool". A Python proxy was chosen over a TS `llm/stream` plugin: it reuses the parser and client without a copy, needs no rebuild, and is testable in Python. |
| Persona "You are an AI agent powered by DeepSeek Harness" plus ~600 chars of runtime context | The `system-prompt` row sets `includeHarnessIdentity: false`, `includeRuntimeContext: false` and `personaPrefix` = coordinator `SYSTEM`. The system message is now exactly `SYSTEM`. `dsh-persona` with `complete: true` cannot be mounted at the root: "deployment:persona-prefix is already registered". With the runtime context off, only the *required* working-directory line remains, as an extra user message. No config removes it, so the proxy drops it (`keep_context=False`). |
| No step budget, no way to end the turn from a tool | The agent loop has no step limit, and only a TS `agent/pre-step` hook can stop it. The proxy reads the history and applies the coordinator's exits, in its order: question asked, then `MAX_DUPLICATES` refused duplicates, then `max_steps` model calls. It then answers a marker text without calling the model. The marker is needed because an empty completion is an error for the harness (`EMPTY_RESPONSE`, then retries). `runtime.result` rebuilds the coordinator's `answer` and warnings from the log. |
| Hooks for approval (a crashing hook fails open) | **No hook plugin is mounted.** 25 rows are disabled in `ordner.patch.yml`; together they expose **30 built-in tools** (bash, read, write, edit, glob, grep, web_fetch, web_search, subagent, workflow, skill, todo_write, goals, jobs, MCP resources, plugin_manager, working_directory, …). The other disabled rows cover the title LLM call, repeat reminders, the tool-result pruner, AGENTS.md and the web providers. The approval policy stays at the default `ask`; no answerer exists, so it fails closed. The proxy refuses any request whose tool list is not exactly Ordner's (HTTP 400, the model is never called). The runtime also aborts on any harness `tool_call` outside `mcp__ordner__*`. |
| SDK and headless driven by hand | `ordner.harness.runtime.run()` has the coordinator's contract. Each run is one `dsh --profile headless --json` process (`Popen`). The proxy is served from the caller's thread, so an in-process `MLXLocal` works. MCP reconnect is off, because a restart would lose the run state. Telemetry is off (`DSH_TELEMETRY_DISABLED=1`). |

Side effects:

- No registry tool has `side_effect=True`.
- `prepare_action` only stores a `prepared` Action with `requires_validation`.
- `case_record` writes the local dossier only.
- Without fs, shell or web tools, the harness can neither write files nor reach the network for the model.

## Measured

`python -m ordner.harness.selfcheck`, about 20 s:

| Check | Result |
|---|---|
| Proxy units | Prefix and order, history arguments, context drop, stop rules, parse-error and unknown-name routing, foreign tool refused (400, 0 model calls) |
| Mock end to end: 5 dev scenarios (lp-03, lp-05, serafe-04, move-04 with 2 phases, tax-be-03), scripted Apertus raw-text policy | The script covers parallel calls, `ask_user`, `prepare_action`, a duplicate, a malformed call and an answer. Result: **6 runs, 24 model calls, identical model inputs at every step** (masking call ids and the random dossier ids), identical tool schemas, identical score rows. `silent_failures` 0, `prompt_parity` true, `harness_rejected` 0. Harness wall time 8.6–10.5 s in total, about 1.5 s per run. |
| Full dev split, same scripted policy (`work/harness_ab/full_dev_scripted.py`), `--toolset base` and `both` | 50 scenarios, 53 runs: **244/244 model calls with identical inputs, 50/50 identical score rows**. 0 errors, 0 silent failures, 0 harness-rejected calls. Harness wall time 95 s (base) and 109 s (both). `--agent harness --llm mock` on full dev gives metrics identical to `--agent coordinator --llm mock`. |
| Loop exits | Repeated duplicates and `max_steps=2` both stop at the same step with the same inputs as the coordinator |
| Without translation (spike setup, `raw=True`) | `silent_failures`=1, 0 tools executed: the counter detects it |
| Fail closed, all 25 rows re-enabled (scratch test) | The run aborts before any model call: "the harness exposed tools outside Ordner's set: [bash, create_goal, edit, …, write]" (30 tools) |
| Network | A harness run succeeds under `sandbox-exec` that denies all outbound traffic except localhost (telemetry opted out) |

**Real model, brief laptop smoke test.** Apertus 1.5 8B MLX 4-bit DWQ behind `mlx_lm.server` 0.32, no server
reachable elsewhere, unloaded afterwards. 3 dev scenarios × 2 runtimes. Raw data: `work/harness_ab/real_smoke.json`.

| | coordinator | harness |
|---|---|---|
| Model calls | 6 | 7 |
| Tool calls (valid) | 4 (4) | 5 (5) |
| Obligations / missing-info / deadline exact / actions | 0/3 · 1.0 · 0.5 · 0/1 | 0/3 · 1.0 · 0.5 · 0/1 |
| Forbidden actions / silent failures / errors | 0 / 0 / 0 | 0 / 0 / 0 |
| Wall time (model time) | 202.5 s (202.0 s) | 215.8 s (197.1 s) → about 6 s overhead per run |

The two runs diverge from step 0 (lp-03 takes one more step in the harness). The cause is not the runtime:

- The only difference in the step-0 prompts is a **random fact id** (`new_id` = uuid4), 10 hex chars in the snapshot.
- Replaying each step-0 prompt reproduces that runtime's own output byte for byte, so the server is deterministic.

That noise exists between two coordinator runs too. Plan a coordinator-vs-coordinator run to measure the noise floor
before reading "not worse".

`--llm mlx` in-process also works through the harness: lp-05, one step, `ask_user`, 28.7 s.

## Remaining gaps

- **Product path:** not integrated. Driving the harness from the Ordner app needs either the SDK or the headless CLI per
  turn, plus a mapping of harness events to the cockpit. Our `prepare_action` already removes the need for harness
  approval answerers.
- **Proxy-side normalisations:** the A/B measures the harness *with* these, which a reader of the H8 result must know.
  Bare names, tool order (the native `system-prompt.toolOrder` exists but is unused), runtime-context drop, stop rules
  and the marker text all live in the proxy. `keep_context=True` (harness context kept) is available in
  `runtime.run`/`scenario_agent` but not exposed on the CLI, and it was not measured.
- **Malformed calls:** an unnamed malformed call travels through `ask_user`, so the harness logs show it as
  `mcp__ordner__ask_user` with `__ordner_*` arguments (cosmetic).
- **Reproducibility:** random dossier ids make eval runs non-reproducible at the token level, for both runtimes.
- **Alpha risk:** developer preview, 2.4 GB checkout, Node ≥ 22.19. One process per phase, sequential. Session JSONL
  files accumulate in `work/vendor/harness-home/sessions`, about 1 MB so far.

## Commands (macstudio, full A/B)

Setup, once. Either copy the built arm64 checkout from the laptop, or rebuild it (Node ≥ 22.19, pnpm 11.28.5,
about 3 min):

```sh
cd track_2b
rsync -a laptop:hack-apertus/soumission/track_2b/work/vendor/deepseek-harness work/vendor/
# or: git clone https://github.com/deepseek-ai/deepseek-harness work/vendor/deepseek-harness && cd work/vendor/deepseek-harness \
#     && git checkout d743267 && pnpm install --frozen-lockfile && pnpm run build && cd -
PYTHONPATH=src .venv/bin/python -m ordner.harness.selfcheck     # must print "harness selfcheck: OK"
```

Model server. Use the same one for both runtimes. `LLM_NAME` must be the served model id: with mlx_lm.server 0.32,
`default` gives a 404.

```sh
.venv/bin/mlx_lm.server --model <apertus-1.5-8b path or HF id> --port 8080 &
export PYTHONPATH=src LLM_BASE_URL=http://127.0.0.1:8080/v1 LLM_NAME=<same path or id>
```

Runs. The result file names carry no split, so copy each file after its run.

```sh
R=data/results
for split in dev test; do                       # dev = integration; test = once, after dev is frozen
  for agent in coordinator harness coordinator; do   # second coordinator run = noise floor
    .venv/bin/python -m ordner.eval.scenarios.run --agent $agent --split $split --llm openai
    n=1; while [ -e $R/ab_${agent}_${split}_$n.json ]; do n=$((n+1)); done
    cp $R/scenarios_$agent.json $R/ab_${agent}_${split}_$n.json; cp $R/scenarios_$agent.md $R/ab_${agent}_${split}_$n.md
  done
done
```

(`--llm mlx` works for both runtimes too. Add the same `--toolset`, `--max-steps`, `--mlx-model` or `--adapter` to
both agents.)

Compare against the decision rule:

```sh
.venv/bin/python - <<'EOF'
import json
k = ["deadline_exact", "obligations_recall", "missing_info_recall", "unneeded_questions", "forbidden_actions",
     "silent_failures", "tool_call_validity", "pass_rate", "errors"]
for split in ("dev", "test"):
    runs = {f"{a}_{i}": json.load(open(f"data/results/ab_{a}_{split}_{i}.json"))["metrics"]
            for a, i in (("coordinator", 1), ("coordinator", 2), ("harness", 1))}
    print(split, *runs)
    for x in k:
        print(f"  {x:22}", *(f"{m[x]!s:>14}" for m in runs.values()))
EOF
```

Adopt the harness only if all of the following hold:

- it is not worse than the coordinator beyond the coordinator-vs-coordinator spread on deadline exact match,
  obligations recall and questions (missing-info recall, unneeded questions);
- `forbidden_actions` is 0;
- `silent_failures` is 0;
- `errors` is 0.
