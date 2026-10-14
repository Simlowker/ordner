# Spike: DeepSeek Harness as Ordner's agent runtime

Date 2026-10-14, about 10 min of a 2.5 h timebox. Harness `deepseek-harness` @ `d743267` (0.2.1-alpha.2, MIT, developer preview). Node 26.4.0, pnpm 11.28.5 (pinned by the repo), macOS arm64. All artefacts are under `track_2b/work/vendor/` (git-ignored). Nothing was installed globally and nothing was committed.

## Verdict

**Not for the hackathon.** Keep our Python loop as the product path. The harness works and runs our loop end to end. The two gaps that matter for Apertus (raw-text tool calls, and approval for side effects) are both bridged on _our_ side today. Adopting the harness would add work and risk without removing either gap.

## Did a loop run? Yes

`dsh --profile headless --json` drove a scripted OpenAI-compatible mock (`spike/mock_llm.py`, stdlib, SSE) and executed our tools over a hand-written MCP stdio server (`spike/ordner_mcp.py`, about 80 lines; the `mcp` Python lib is not in `.venv`).

- **Mock log** (`logs/llm_requests.jsonl`): 3 `POST /v1/chat/completions` calls, all `stream:true`.
  1. `[system,user,user]` → `mcp__ordner__case_load {"subject_id":"s1"}`
  2. `[...,assistant,tool]` → `mcp__ordner__action_prepare {...}`
  3. `[...,tool]` → final text
- **Extra calls:** one `GET /v1/models`, plus one title-generation call (no tools) unless `session-title-llm` is disabled.
- **MCP log** (`logs/mcp.jsonl`): `server/discover`, `initialize` (the client asked for 2025-11-25; we answered 2025-06-18 and it accepted), `tools/list`, then `tools/call case_load` and `tools/call action_prepare`.
- **Exit and timing:** exit 0, `turn_end.reason=completed`. Wall time is about 1.0–1.6 s per run, boot included.
- **Python SDK:** the same loop runs from Python (`spike/run_sdk.py`). It uses the SDK from source (`PYTHONPATH=python/sdk/src`, pydantic is already in `.venv`) and passes `dsh_bin=apps/cli/lib/bin.js`, so the runtime wheel is not needed. Result: `finish_reason=completed`, 2 tools executed.

Commands:

```sh
cd work/vendor/deepseek-harness && pnpm install --frozen-lockfile   # 25 s
pnpm run build                                                     # 2 min 53 s, OK
cd ../spike/workspace && DSH_HOME=../dsh-home ORDNER_SPIKE_DIR=.. ORDNER_LOCAL_KEY=dummy \
  node ../../deepseek-harness/apps/cli/lib/bin.js --profile headless \
  --patch ../ordner.patch.yml --patch ../trim.patch.yml [--patch ../approval.patch.yml] --json "Load dossier s1 and prepare a letter."
```

## Runtime and footprint

- **Stack:** TypeScript/Node (≥22.19) on the Cordis plugin framework. Everything is a plugin, composed from YAML profiles and patches.
- **Disk:** `node_modules` is 2.0 GB; the checkout is 2.4 GB after the build. The build also produces a native addon and the Vite web assets.
- **Ways to run it:** `headless` (one-shot CLI), `sdk` (JSON-RPC on stdio, plus a Python SDK), `web` (browser UI) and `acp`.

## Declaring a local OpenAI-compatible route (verified)

```yaml
- id: llm-pi-ai
  config:
    providers:
      ordner-local:
        api: openai-completions
        baseURL: http://127.0.0.1:18765/v1 # mlx_lm.server / vLLM
        apiKeyEnv: ORDNER_LOCAL_KEY # pi-ai demands a key even for a keyless server
        compat:
          {
            supportsDeveloperRole: false,
            supportsStore: false,
            supportsReasoningEffort: false,
          }
        models:
          [
            {
              id: apertus-mock,
              contextWindow: 65536,
              maxTokens: 4096,
              reasoningEfforts: false,
            },
          ]
- id: agent-default-model
  config: { provider: ordner-local, model: apertus-mock }
```

The request carries `max_completion_tokens`. For servers that only read `max_tokens`, set `compat.maxTokensField`.

## Tool registration

| Option                                                                  | Status                                                                                                                                                             |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| MCP stdio server (any language) via a `@deepseek-ai/dsh-mcp-client` row | **Worked.** Tools appear as `mcp__ordner__<name>`: the prefix changes the names Apertus would see.                                                                 |
| Native TS plugin (`ctx.tools.register(defineTool(...))`)                | Documented, not tried. Gives bare names, typed args and UI cards.                                                                                                  |
| Python SDK                                                              | Drives sessions only. The protocol is just `session/prompt`, `session/wait` and working-directory get/set: **no Python tool registration, no approval answering.** |

The base composition exposes **28 built-in tools** (bash, write, edit, web_fetch, subagent, …). For Ordner they must be disabled. `trim.patch.yml` disables 18 rows, which leaves exactly our 3 tools (verified). We would also have to override the persona (`system-prompt.personaPrefix`) and live with an injected "runtime context" user message (about 600 chars: cwd, sandbox policy, approval policy).

## Approval and policy for side-effect tools

- **Mechanism:** `tools/pre-execute` waterfall (allow/deny/ask, TS) → `ctx.tools.guard()` (monotonic deny) → `approval/request` answerers (`dsh-user-approval`, default policy `ask`, fails closed).
- **Who can answer:** the Web UI has an approval answerer. Headless and the SDK have none, so `ask` resolves to `unavailable`.
- **Verified without TS:** the experimental `dsh-hooks-claude-code` runs a Python `PreToolUse` hook (`approval_hook.py`, matcher `mcp__ordner__action_prepare`). Result:
  - the hook returned `ask`, logged as `approval/asked` then `approval/decided: unavailable`;
  - the tool result was "requires approval, but no approval channel is available";
  - only `case_load` reached the MCP server.
- **Pitfalls seen:**
  1. A crashing hook (exit 1) is recorded as `pass`, i.e. it **fails open**.
  2. With the package-name form, the hook plugin "failed to import" because `dsh-hook-protocol` is not in the CLI's runtime closure. That is only a warning, and the run continued **without the gate**. It worked when loaded by absolute path.
  3. Hooks run inside the workspace-write sandbox.
- **Our design already covers this:** `action_prepare` never executes anything. Validation happens in the Ordner UI, so no harness approval is needed for the core safety property.

## Apertus risk: raw-text tool calls

When the mock is set to Apertus mode (`MOCK_RAW=1`: `<|tools_prefix|>[{"mcp__ordner__case_load": {...}}]<|tools_suffix|>` as plain content), the harness treats it as the **final answer**. Result: 0 tools executed, exit 0, `completed`. The failure is silent.

There is no declarative parser: the pi-ai `compat` switches have no tool-call-format option. The hooks that would work are:

- **TS, inside the harness:**
  - an `llm/stream` waterfall listener (`(options, next) => transform(next())`) that rewrites text chunks into tool-call blocks, or
  - a custom `LlmAdapter`.
- **Outside the harness:** a proxy in front of `mlx_lm.server` that rewrites the SSE stream into OpenAI `tool_calls`. The harness always streams, so the proxy must buffer until it reaches the suffix.

## Effort to integrate (estimate)

| Item                                                                                           | Hours                                             |
| ---------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| MCP wrapper around the real Ordner tools, plus patches                                         | 2–3                                               |
| Apertus tool-call proxy (SSE, Python) or TS `llm/stream` plugin                                | 3–5                                               |
| Human approval wired to the Ordner UI (TS answerer plugin, or adopt the harness Web UI)        | 4–8                                               |
| Driving sessions from the Ordner app via the SDK, and mapping events to our UI                 | 3–5                                               |
| Prompt hygiene (persona, runtime-context noise, `mcp__` prefix vs trained names), eval re-runs | 2–3                                               |
| **Total**                                                                                      | **≈14–24 h**, on an alpha with a 2.4 GB toolchain |

Freeze is Thu 15.10 18:00. **Recommendation: do not adopt now. Revisit after the hackathon.**

Two things are reusable for that later revisit:

- the MCP-server shape for our tools;
- the knowledge that Apertus needs a server-side tool-call parser for _any_ OpenAI-compatible runtime.
