# Ordner architecture (hackathon build, 14-15.10.2026)

Vision: `hack-apertus/docs/vision/` (private QG). This file is the shared map for every parallel workstream.
Contracts: `src/ordner/core/schema.py` (do not change without the coordinator).

| Module | Owner | Responsibility |
|---|---|---|
| `ordner.case` | W1 | Durable local dossier (SQLite, `ORDNER_HOME`, default `~/.ordner`): subjects, documents, facts with provenance and status, cases (procedure instances) with states, actions, deadlines, append-only event log, resume |
| `ordner.procedures` | W2 | Catalogue of `ProcedureCard`s as JSON in `procedures/cards/`, loader, validator; every source quote verified verbatim |
| `ordner.rules` | W3 | Applicability evaluation (declarative conditions), deadline rules (cantonal tables, LP holidays, reception-by dates), reminders, `.ics` export |
| `ordner.tools` | W4 | Tool registry (`ToolSpec` + implementation) wrapping the other modules: document.read/decode, knowledge.search, decision.score, expert.run, rules.evaluate, case.load/record, schedule.plan, receipt.verify |
| `ordner.agent` | W5 | Apertus coordinator loop over the tool registry (OpenAI-compatible tool calls; local server), DeepSeek Harness spike |
| `ordner.connectors` | W6 | Local-first inputs/outputs: watched inbox, PDF share, eCH-0196, QR-bill, camt.053, OFSP premiums + LAMal comparator, email drafts (.eml, never sent) |
| `ordner.app` | W7 | Cockpit UI (home: urgent, missing documents, next step; cases; timeline; coverage map) on top of the existing console |
| `ordner.eval.scenarios` | W8 | Scenario suite and metrics for the coordinator (obligations found/missed, wrong triggers, deadlines, schema validity) |
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
| `mode` | `replay` (default): cached model outputs from `work/` (OCR `ocr.*.jsonl`, Apertus `extract.*.jsonl`, d1 `route.jsonl`), labelled fallbacks (rule-based extraction, heuristics) otherwise. `live`: LightOnOCR-3, d1-3B, EmbeddingGemma 2, Apertus are loaded/called |
| `store`, `subject_id` | Dossier session: `subject_id` args are forced to it, `doc_...` ids resolve through the store (other subjects refused), file paths outside `track_2b/` refused |
| `actor` | `model` (default) or `user`: `confirm_fact`/`reject_fact` and `result_verified` without proof are refused to the model (the coordinator also hides these ops from the schema it shows) |
| `llm_url`, `llm_model` / `apertus_mlx` | `expert.run` live: OpenAI-compatible endpoint (warning if not localhost) / in-process MLX (`True` or adapter path) |
| `today` | Scenario date (YYYY-MM-DD, default the machine date): `on` of `rules.applicable` (ages, card validity), `today` of deadlines and `reminders` |
| `expert_tags`, `work` | Replay tags (default `apertus-lora`, `apertus-base`), work dir |

`dossier.check(subject_id, period, card_id?)` (read only) exposes `ordner.rules.completeness` (with a card: missing
documents per declared institution, wrong year, duplicates, missing facts) and `ordner.rules.consolidate` (tax cards or
no card: totals per measure, `final`/`provisional`/`incomplete`).

`knowledge.search` indexes the corpus plus the verified quotes of every procedure card; with a dossier in ctx it defaults to
the subject's canton (+ federal) and language, and boosts the cards of the open cases (or `card_id`).
`ordner.rules.payment_check` (phishing guard) runs in the coordinator on every document read and every prepared payment.

No tool has `side_effect=True`: none sends, files or pays; `case.record` writes the local dossier only and actions are
prepared by the coordinator. `receipt.verify` is `established` only with a proof event (action moved to `verified` by
the person or a connector, or a `receipt_recorded`/`decision_received`/`payment_confirmed` event), else `unknown`.
