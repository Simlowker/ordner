# Ordner architecture (hackathon build, 14-15.10.2026)

Product, results and how to run: `README.md` and `technical_report.md`. This file is the shared map for every parallel
workstream.
Contracts: `src/ordner/core/schema.py` (do not change without the coordinator).

**Shape: a local mixture of domain experts on one open model, for Swiss federalism.** A small model (d1-3B) picks the
expert; each expert is Apertus 1.5 8B with its domain's tools, its own knowledge base of official sources (federal + the
person's canton), and its own LoRA adapter only where it measurably helps; the rules engine computes what is computable;
nothing is sent. Route by domain, filter by canton (read from the dossier, never guessed by a model).

| Layer | Role | State (15.10, numbers recomputed from `data/`) |
|---|---|---|
| Router: d1-3B (`harness/router.py`), EmbeddingGemma 2 fallback | picks the expert from the first request; the coordinator when no expert is confident (p < 0.5) | 78.1 % correct on 201 scenario requests (EmbeddingGemma 2 alone: 64.7 %), `data/routing/results.json` |
| Expert: Apertus 1.5 8B + domain tools + prompt (`harness/experts.py`) | Impôts, Assurance maladie, Poursuites, Logement et ménage; the coordinator is the general expert | LoRA adapter only where it beat the base on dev: Poursuites and Logement (opt-in, `ORDNER_USE_ADAPTERS=1`) |
| Expert knowledge base (`tools/expert_kb.py`, `data/knowledge/`) | official passages of the expert's topics, federal + the dossier's canton, ranked by EmbeddingGemma 2 | 712 passages (Impôts 135, Assurance maladie 168, Poursuites 164, Logement 245), 436 from official acts in the repo; 89.6 % top-3 topic hit on 96 blind questions vs 81.2 % for one global base |
| Rules engine and dossier (shared) | applicability, deadlines, completeness, guards; facts, cases, actions, events | unchanged; every expert reads and writes the same dossier |

| Module | Owner | Responsibility |
|---|---|---|
| `ordner.case` | W1 | Durable local dossier (SQLite, `ORDNER_HOME`, default `~/.ordner`): subjects, documents, facts with provenance and status, cases (procedure instances) with states, actions, deadlines, append-only event log, resume |
| `ordner.procedures` | W2 | Catalogue of `ProcedureCard`s as JSON in `procedures/cards/`, loader, validator; every source quote verified verbatim |
| `ordner.rules` | W3 | Applicability evaluation (declarative conditions), deadline rules (cantonal tables, LP holidays, reception-by dates), reminders, `.ics` export |
| `ordner.tools` | W4 | Tool registry (`ToolSpec` + implementation) wrapping the other modules: 16 tools, 11 generic (document.read/decode, knowledge.search, decision.score, expert.run, rules.evaluate, dossier.check, schedule.plan, case.load/record, receipt.verify) and 5 process tools (`tools/processes/`: piece.recevoir, impots.preparer_declaration, lamal.revoir_franchise, poursuite.repondre, demenagement.annoncer); `tools/expert_kb.py`: one knowledge base per expert |
| `ordner.agent` | W5 | Apertus coordinator loop over the tool registry (Apertus tool-call syntax parsed exactly; local OpenAI-compatible server or in-process MLX) |
| `ordner.harness` | W10 | DeepSeek Harness as an optional runtime for the same loop: MCP server over the coordinator's dispatch, Apertus tool-call proxy, fail-closed tool allowlist (`docs/harness_integration.md`); web presets for the coordinator and four experts (`harness/experts.py`), d1-3B routing (`harness/router.py`) |
| `ordner.distill` | — | Distillation: dev-scenario variants, teacher runner (same loop), strict filter, training data in Apertus syntax, QLoRA training |
| `ordner.connectors` | W6 | Local-first inputs/outputs: watched inbox, PDF share, eCH-0196, QR-bill, camt.053, OFSP premiums + LAMal comparator, email drafts (.eml, never sent) |
| `ordner.app` | W7 | Cockpit UI (home: urgent, missing documents, next step; cases; timeline; coverage map) on top of the existing console |
| `ordner.eval.scenarios` | W8 | Scenario suite and metrics (obligations found/missed, wrong triggers, questions, deadlines, actions, forbidden actions, schema validity); agents `rules_only`, `coordinator`, `hybrid`, `harness` |
| existing | — | `gen/`, `models/`, `finetune/`, `eval/` (measured eCH-0196 core), `explain/` |

Rules for every workstream: no network at runtime except explicit connectors; nothing is sent, filed, signed or paid
by Ordner (it prepares, the person acts); every legal rule cites an official source; unknown or unqualified → explicit
"to verify" state, never a silent guess; each module ships one runnable self-check.

## Module APIs (stable signatures — implement exactly, extend freely)

```python
# ordner.case.store
class Store:                      # Store(path=None) -> $ORDNER_HOME/ordner.db (sqlite3, JSON columns)
    def add_subject(self, s: Subject) -> Subject; def get_subject(self, id) -> Subject; def subjects(self) -> list[Subject]
    def add_document(self, d: Document) -> Document; def documents(self, subject_id, kind=None, year=None) -> list[Document]
    def propose_fact(self, f: Fact) -> Fact; def confirm_fact(self, fact_id, actor="user") -> Fact
    def reject_fact(self, fact_id, actor="user") -> Fact
    def facts(self, subject_id, key_prefix=None, status=None) -> list[Fact]
    def open_case(self, subject_id, card_id, period=None) -> Case; def get_case(self, id) -> Case
    def cases(self, subject_id=None, state=None) -> list[Case]; def set_state(self, case_id, state, reason="") -> Case
    def add_action(self, a: Action) -> Action; def update_action(self, action_id, status) -> Action
    def add_deadline(self, d: Deadline) -> Deadline
    def events(self, subject_id=None, case_id=None) -> list[Event]
    def snapshot(self, subject_id) -> dict   # everything needed to resume a conversation
    # extensions (see "Store" below): set_missing, get_document, complete_deadline, deadlines, close, actor= kwargs

# ordner.procedures.catalog
def load_cards(jurisdiction=None) -> list[ProcedureCard]; def get(card_id) -> ProcedureCard
def validate(card) -> list[str]           # empty list = valid

# ordner.rules
def applicable(card, subject, facts) -> dict   # {"status": "applicable"|"not_applicable"|"missing_info", "missing": [...], "why": [...]}
def compute_deadline(rule: DeadlineRule, subject, context: dict) -> dict  # {"due": "YYYY-MM-DD", "computed_from": {...}} or {"status": "missing_info", ...}
def reminders(due: str, policy="default") -> list[str]; def to_ics(deadlines: list[Deadline], subject) -> str

# ordner.tools.registry
SPECS: list[ToolSpec]; def call(name: str, args: dict, ctx: dict) -> dict; def openai_tools() -> list[dict]

# ordner.agent.coordinator
def run(goal: str, subject_id: str, llm, store, max_steps=12) -> dict   # {"transcript": [...], "actions": [...], "questions": [...]}
```

## Store (`ordner.case`, W1)

`Store(path=None)`: one SQLite file (`$ORDNER_HOME/ordner.db`, default `~/.ordner`), JSON columns, WAL, foreign keys on.
One `Store` per process is fine: writes go through a lock, each mutation and its event are a single transaction.
Self-check: `python -m ordner.case.selfcheck`. Demo persona: `python -m ordner.case.demo_seed` (see below).

**Extensions to the signatures above**

| Call | Effect |
|---|---|
| `actor=` on every mutation | Who acted (`user`, `ordner`, `connector`, `rule`, `model`), written to the event. Defaults: `add_subject` user, `add_document` connector, `confirm_fact`/`reject_fact` user, `open_case` rule, `set_state` ordner, `set_missing` rule, `add_action` ordner, `update_action` user, `add_deadline` rule, `complete_deadline` user |
| `set_missing(case_id, missing: list[str])` | Replace `Case.missing` (missing fact keys / document kinds); event `missing_updated` |
| `get_document(id)` | One document; `KeyError` if unknown |
| `complete_deadline(id)` | `active` → `done` (idempotent on `done`); event `deadline_done` |
| `deadlines(case_id, status=None)` | Every deadline of a case, history included |
| `snapshot(subject_id, today=None, last_events=20)` | `today` fixes `overdue` for tests |
| `close()` | Close the connection |

**Rules enforced**

- Facts enter as `proposed` (with `actor`, `source_doc`). A `model` cannot confirm. `confirm_fact` sets `confirmed_at`/`confirmed_by` and supersedes the confirmed fact with the same subject + key + period (old one → `superseded`, new `supersedes` = old id). `reject_fact` works from `proposed` or `confirmed`; `confirmed_at`/`confirmed_by` then record the rejection. Nothing is deleted.
- Subjects are isolated: `documents()`/`facts()` require an existing subject (no "all subjects" via `None`); a fact's `source_doc` must belong to the same subject; the same file for two subjects is two documents.
- Actions enter as `prepared`. Every kind except `reminder` must keep `requires_validation=True`. Path: `prepared → validated → done_by_user → verified`, `cancelled` from `prepared`/`validated`; only `actor="user"` can validate. A `reminder` without validation may go `prepared → done_by_user`.
- `Case.deadlines` (and the snapshot) only carry `active` deadlines; use `deadlines(case_id)` for history.
- The `events` table is append-only (SQLite triggers reject UPDATE and DELETE).

**Idempotency**

| Call | Same input again returns the existing row, no event |
|---|---|
| `add_document` | same `subject_id` + `sha256` (callers must use the returned `id`, it may differ from the one passed) |
| `open_case` | same subject + `card_id` + `period` while the case is not `closed` |
| `add_action` | same case + `kind` + `payload` while pending (`prepared`/`validated`/`done_by_user`) |
| `add_action` (payment) | double-payment guard: a pending payment of the same case and amount is returned (same case and amount, not a bill identity); a concrete payment cancels the case's generic payment step prepared by the rules engine (event `action_cancelled`) |
| `add_deadline` | same case + `rule_id` + `due` (active or done). Same rule with another date = recomputation: the active one becomes `superseded` (event `deadline_superseded`) |
| `set_state` / `set_missing` | same value: no-op |

**Case transitions** (`NEXT` in `store.py`)

```
to_qualify → missing_documents | ready_to_prepare (nothing missing)
missing_documents → ready_to_prepare → ready_to_validate → action_engaged
action_engaged → awaiting_response | result_verified (no response expected, e.g. payment receipt)
awaiting_response → complement_requested | decision_received
complement_requested → missing_documents | ready_to_prepare | awaiting_response
decision_received → result_verified → closed
```
Any move to an earlier state (including reopening a closed case) or closing early needs a non-empty `reason`, stored
in the `state_changed` event. Anything else raises `ValueError`.

**Event types**: `subject_added`, `document_received`, `fact_proposed`, `fact_confirmed`, `fact_rejected`,
`fact_superseded`, `case_opened`, `state_changed`, `missing_updated`, `action_prepared`, `action_updated`,
`deadline_added`, `deadline_superseded`, `deadline_done`.

**Snapshot keys**: `as_of`, `subject`, `documents`, `facts` (by status), `open_cases` (with `missing`, active
`deadlines`, `actions`), `closed_cases`, `upcoming_deadlines` (active, sorted, with `card_id` and `overdue`),
`pending_actions` (with `card_id`), `last_events`.

**Demo persona** `subj_noa_keller` (fictional): `demo_seed.seed(store, cases=())` is idempotent and opens no case
unless asked. Its 2025 tax statements are versioned in `data/demo/noa/` with `manifest.json` (truth from the barcode,
totals as printed): Morvessa Banque SA as a clean PDF (barcode path), Zelfeld Courtage SA as a level-2 photo (AI path).
Talbruck Banque Privée SA is declared in `finance.institutions` but has no statement, on purpose (completeness check).
Salary certificates and the LAMal 2027 notice are `placeholder:` documents. Regenerate the files with
`python -m ordner.case.demo_docs` (generator deps needed; the PDF bytes change with the render timestamp, the manifest
follows).

## Tools (`ordner.tools`, W4)

`call(name, args, ctx)` accepts `document.read` or the OpenAI alias `document_read` and always returns plain JSON
`{"ok", "data", "warnings", "provenance"}` (+ `"error"` when `ok` is false; exceptions never escape). Arguments are
checked against `input_schema` (type, enum, required, nested `items`); unknown arguments are an error.
Self-check: `python -m ordner.tools.selfcheck` (replay, no model, temporary dossier with the demo persona).

| ctx key | Effect |
|---|---|
| `mode` | `replay` (default): cached model outputs from `work/` (OCR `ocr.*.jsonl`, Apertus `extract.*.jsonl`, d1 `route.jsonl`), labelled fallbacks (rule-based extraction, heuristics) otherwise. `live`: LightOnOCR-3, d1-3B, EmbeddingGemma 2, Apertus are loaded on demand and called (not all at once on a 36 GB Mac) |
| `store`, `subject_id` | Dossier session: `subject_id` args are forced to it, `doc_...` ids resolve through the store (other subjects refused), file paths outside `track_2b/` refused |
| `actor` | `model` (default) or `user`: `confirm_fact`/`reject_fact` and `result_verified` without proof are refused to the model (the coordinator also hides these ops from the schema it shows) |
| `llm_url`, `llm_model` / `apertus_mlx` | `expert.run` live: OpenAI-compatible endpoint (warning if not localhost) / in-process MLX (`True` or adapter path) |
| `today` | Scenario date (YYYY-MM-DD, default the machine date): `on` of `rules.applicable` (ages, card validity), `today` of deadlines and `reminders` |
| `expert_tags`, `work` | Replay tags (default `apertus-lora`, `apertus-base`), work dir |

`dossier.check(subject_id, period, card_id?)` (read only) exposes `ordner.rules.completeness` (with a card: missing
documents per declared institution, wrong year, duplicates, missing facts) and `ordner.rules.consolidate` (tax cards or
no card: totals per measure, `final`/`provisional`/`incomplete`).

`knowledge.search` with an expert in ctx (`ctx["expert"]`: the harness MCP server's `--expert`) ranks that expert's own
base (`ordner.tools.expert_kb`: `data/knowledge/<expert>/passages.jsonl`, official acts, plus
`work/knowledge/<expert>/passages_local.jsonl`, authority pages kept locally) with EmbeddingGemma 2, federal + the
canton from the args or the dossier; `ORDNER_KB_REPO_ONLY=1` keeps the acts only (what a clean clone has). The proxy
injects the expert's top 3 passages after the question the same way (`harness/proxy.py: expert_sources`, with
`ORDNER_EMBED=1`; without weights the expert answers without them). Evaluation: `python -m ordner.eval.knowledge_experts`
(`data/knowledge/results.json`). Without an expert, `knowledge.search` indexes the corpus plus the verified quotes of every procedure card; with a dossier in ctx it defaults to
the subject's canton (+ federal) and language, and boosts the cards of the open cases (or `card_id`).
It ranks with EmbeddingGemma 2 in `live` mode or with `ORDNER_EMBED=1` (every scenario run since 14.10 17:00); BM25 is only the fallback when the weights are absent (Docker replay). On 2 × 36 everyday questions (`python -m ordner.eval.retrieval`, `data/retrieval/`) the right card's source is in the top 3 for 80.6 % / 77.8 % of questions with EmbeddingGemma 2, 52.8 % / 38.9 % with BM25 and 61.1 % / 50.0 % with their RRF fusion, which was therefore dropped: on cross-lingual questions BM25 ranks same-language distractors first (held-out cross-lingual: 70 % embedding, 5 % BM25, 15 % fusion).
`ordner.rules.payment_check` (phishing guard) runs in the coordinator on every document read and every prepared payment.

No tool has `side_effect=True`: none sends, files or pays; `case.record` writes the local dossier only and actions are
prepared by the coordinator. `receipt.verify` is `established` only with a proof event (action moved to `verified` by
the person or a connector, or a `receipt_recorded`/`decision_received`/`payment_confirmed` event), else `unknown`.

## Agent architecture (measured)

**Rules first, Apertus second, same dossier.** The deterministic rules engine runs first: from confirmed facts and
known events it opens the applicable cases, computes the deadlines it can prove and prepares the card steps. The
Apertus coordinator then works on the same dossier for what rules cannot do: read free text and documents, ask the
person for missing information (`ask_user`), explain, and prepare concrete actions (`prepare_action`). It sees the rules'
cases through `case.load`. In the scenario suite this is the `hybrid` agent (`eval/scenarios/agents.py`: rules output +
coordinator output, merged); in the console, the deterministic review runs on the dossier and « Demander à Ordner » calls
the coordinator on it (the console currently exposes all 16 registry tools, not the evaluated process toolset).

**Toolsets.** 16 tools are registered (`len(registry.SPECS)`), 11 generic and 5 process tools; the loop adds `ask_user`
and `prepare_action`. `--toolset base` shows the 11 generic tools; `--toolset process` shows the 5 process tools plus
`knowledge.search`, `rules.evaluate`, `case.load` and `case.record` (9); `both` shows all 16. Same system prompt in
every toolset.

**Dev results** (43 scored dev scenarios; Apertus 1.5 8B bf16 behind `mlx_lm.server`, temperature 0; EmbeddingGemma 2
for knowledge search; test split not yet run):

| System                                           | Pass    | Obligations | Missing info (7 items) | Deadlines exact | Actions |
| ------------------------------------------------ | ------- | ----------- | ---------------------- | --------------- | ------- |
| `rules_only` (no model)                          | 46.5 %  | 76.9 %      | 0 %                    | 50.0 %          | 77.4 %  |
| `coordinator --toolset base`                     | 14.0 %  | 33.3 %      | 42.9 %                 | 10.0 %          | 9.7 %   |
| `coordinator --toolset process`, run 1 / run 2   | 27.9 / 30.2 % | 59.0 / 56.4 % | 71.4 / 42.9 %   | 30.0 / 33.3 %   | 29.0 / 32.3 % |
| `harness --toolset process`                      | 23.3 %  | 59.0 %      | 71.4 %                 | 36.7 %          | 29.0 %  |
| `hybrid --toolset process`                       | 53.5 %  | 79.5 %      | 71.4 %                 | 53.3 %          | 80.6 %  |

- `rules_only` and `hybrid` trigger none of the 12 traps (precision is computed on traps only). No configuration
  executed an effect (send, pay, file, sign). Metrics are recall-oriented: extra procedures and dates are not
  penalised outside the traps, which favours the `hybrid` (union of two outputs); its gain over `rules_only`
  (+3 scenarios; +5 questions, +1 obligation, +1 deadline, +1 action) is within noise.
- Two identical `coordinator --toolset process` runs differ on 5 of 43 verdicts: read dev gaps
  under ~12 points of pass rate as noise.
- Scoring credits obligations and deadlines found in tool results; process tools return code-computed deadlines, so
  process vs base measures whether the model calls the right tool with the right arguments.
- The hybrid was defined after these dev results; on test it is reported as exploratory (PREREG Addendum 4).

**Double-payment guard.** On dev, in 2 scenarios (`inst-02`, `serafe-02`, a bill received by e-mail and by post) the
hybrid ended with two prepared payments: the rules engine's generic payment step and the coordinator's concrete payment
(2 forbidden actions, none executed). `Store.add_action` now cancels the case's generic payment step when a concrete
payment arrives, and returns the pending payment of the same case and amount instead of adding a second one (commit
`4245539`). The guard applies to every agent; the hybrid is being re-measured. Note for the re-run: the scorer unions
the dossier read-back with the agents' outputs and `_matches` (`eval/scenarios/run.py`) does not look at the action
status, so a cancelled generic step may still be counted.

**Runtime.** DeepSeek Harness runs the same loop (MCP server over the coordinator's dispatch, proxy reusing our parser)
and reaches parity within the run-to-run spread (pass 23.3 % against 27.9 / 30.2 %, obligations 59.0 % against
59.0 / 56.4 %, deadlines 36.7 % against 30.0 / 33.3 %). It stays an optional runtime, not the default: it adds about 6 s
per run in the smoke test and a 2.4 GB alpha toolchain, and every rule that matters lives in our proxy and MCP server
(`docs/harness_integration.md`).
