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
