# Ordner — a sovereign Swiss admin assistant built on Apertus

**Team Meotis · Hack Apertus 2026 · Track 2B (Own Project)**

Ordner keeps a person's administrative dossier on their own machine: it reads the papers they receive, knows which
Swiss procedures apply to them (tax return, health insurance, debt collection, pension, unemployment, moving…),
computes the deadlines from the official rules, lists what is missing, and prepares the next step (a letter, a
document request, a payment). **It never sends, files, signs or pays anything**: the person validates and acts.
Every rule cites an official source quoted word for word; anything Ordner cannot establish stays « à vérifier ».
Apertus 1.5 8B is the coordinator that drives the tools, the extractor of the measured tax-statement core, and the
writer of the explanations.

## Run it

```bash
make run          # from the repository root: Docker, CPU only, no GPU, no network, no API key
```

The container (about 1 min to build, 155 MB compressed, no torch, no model weights):

1. replays the evaluation of the tax-statement core from the recorded model outputs in `data/` (`ordner.eval.run`);
2. runs the scenario suite with the rules-only baseline (`ordner.eval.scenarios.run --agent rules_only --split all`);
3. seeds the fictional demo dossier (Noa Keller, 22, Lausanne) in a throw-away `ORDNER_HOME`, at the simulated date
   `ORDNER_TODAY=2026-02-20` (override: `ORDNER_TODAY=2026-10-14 make run`), and reviews it with the rules (no model);
4. serves the console on <http://localhost:8000>, cockpit first. Results land in `track_2b/data/results/`.

`make -C track_2b live` runs the local models (LightOnOCR-3, Apertus) on Apple Silicon through the project venv (Docker
cannot use the Mac GPU); see the [technical report](technical_report.md). To let « Demander à Ordner » call Apertus
live, serve it with any local OpenAI-compatible server (e.g. `mlx_lm.server`) and set `LLM_BASE_URL` / `LLM_NAME`
(`.env.example`); without them the panel replays recorded transcripts.

## What the console shows

| View                    | Content                                                                                                                                                                                                                                                             |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Où j'en suis** (home) | the next step; deadlines within 30 days with reminders; missing documents and information in plain words (fr/de/it); procedures still « à qualifier » with the questions that decide them; suspicious payment requests; securities wealth consolidated across banks |
| Pièces reçues           | every document with its read path: **barcode** (exact: eCH-0196, QR-bill) or **AI** (OCR + Apertus, with a doubt score)                                                                                                                                             |
| Démarches               | one case per procedure: state machine, deadline and how it was computed, prepared actions to validate, linked facts with provenance, event log, official sources                                                                                                    |
| Couverture              | domain × canton map of the catalogue: what is qualified, draft, or not covered (an empty cell is never « nothing to do »)                                                                                                                                           |
| Relevé fiscal           | the measured core: fields read from a bank tax statement, coloured by doubt, triage curve, grounded explanation, deduction checklist                                                                                                                                |
| Demander à Ordner       | the Apertus coordinator (live with `LLM_BASE_URL`, recorded transcripts otherwise)                                                                                                                                                                                  |

## Architecture

```
documents ──► connectors (local, barcode first) ──► DOSSIER (SQLite, append-only event log)
inbox · PDF share · photo/video                      subjects · documents · facts (proposed → confirmed by the person)
eCH-0196 · QR-bill · camt.053 · OFSP premiums        cases (10-state machine) · actions (prepared → validated by the person)
                                                     deadlines (superseded, never overwritten)
                                                          ▲                    ▲
CATALOGUE: 18 procedure cards ──► RULES ENGINE ───────────┘                    │ 11 bounded tools (JSON schema)
227 official sources, verified    applicability (3-valued) · deadlines          │
quotes (Fedlex, cantons, OFSP…)   (holidays, LP ferie, reception-by) ·   APERTUS COORDINATOR (tool loop)
                                  completeness · consolidation ·         side effects intercepted → prepared actions;
                                  phishing guard                          injection filter; date grounding check
                                          │                                    │
                                          └────────► COCKPIT (review without model) ◄───┘
```

| Module (`src/ordner/`)                              | Role                                                                                                                                                                                                     |
| --------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `case/`                                             | Durable local dossier (`ORDNER_HOME`): facts with provenance and status, cases with states, actions, deadlines, append-only events, resume                                                               |
| `procedures/`                                       | 18 `ProcedureCard`s (16 qualified, 2 draft): applicability, required facts and documents, deadline rule, steps, 227 sources whose quotes were checked verbatim                                           |
| `rules/`                                            | Applicability, deadline rules (fixed date, days after notification, LP debt collection, reception-by, cantonal tables), reminders, `.ics`, completeness per declared bank, consolidation, phishing guard |
| `tools/`                                            | 11 tools shown to Apertus: `document.read`/`decode`, `knowledge.search`, `decision.score`, `expert.run`, `rules.evaluate`, `dossier.check`, `schedule.plan`, `case.load`/`record`, `receipt.verify`      |
| `agent/`                                            | Apertus coordinator: bounded loop, subject pinned, person-only operations hidden and refused, side-effect tools turned into prepared actions                                                             |
| `connectors/`                                       | Watched inbox, PDF share, video capture, eCH-0196, QR-bill (SIX IG v2.3), camt.053, OFSP premiums + LAMal comparator, e-mail drafts (`.eml`, never sent)                                                 |
| `app/`                                              | Stdlib HTTP server + vanilla JS cockpit, no build step, no CDN (CSP `default-src 'self'`)                                                                                                                |
| `core/`                                             | Shared contracts (`schema.py`) and human labels fr/de/it (`labels.py`)                                                                                                                                   |
| `gen/`, `models/`, `finetune/`, `eval/`, `explain/` | Measured tax-statement core: synthetic eCH-0196 statements with a barcode oracle, local model wrappers, LoRA, replay, grounded explanations                                                              |
| `eval/scenarios/`                                   | 76 administrative scenarios (67 scored) with official-source deadlines and traps                                                                                                                         |

## What is real, what is replayed

| Real in `make run` (deterministic code, no model)                            | Replayed or fictional                                                                                   |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Dossier, state machine, event log                                            | Model outputs (OCR, Apertus extraction, d1-3B judge, hidden-state features) recorded in `data/`         |
| Catalogue and its verified quotes                                            | « Demander à Ordner » transcripts (`data/demo/transcripts.json`, marked fixture) without `LLM_BASE_URL` |
| Applicability, deadlines, reminders, `.ics`, completeness, consolidation     | `data/demo/demo.json` (relevé view)                                                                     |
| Phishing guard, retrieval over official sources, `.eml` drafts               | The persona Noa Keller and her documents (fictional)                                                    |
| Probe re-training and every metric of the report, from the recorded features |                                                                                                         |
| Scenario suite with the rules-only baseline                                  |                                                                                                         |

## Results

- **Tax-statement core** (eCH-0196, barcodes as free ground truth, unseen layouts, phone-photo degradations, three
  languages, pre-registered in [`PREREG.md`](PREREG.md)): `data/results/table.md` and the
  [technical report](technical_report.md).
- **Scenarios, rules-only baseline** (`data/results/scenarios_rules_only.md`, recomputed by `make run`): 47/61
  obligations found, 0 wrong triggers on 24 traps, 56 % deadlines exact, no date given when it cannot be proven, 0
  executed effects. The coordinator is scored on the same suite with `--agent coordinator --llm-url …`.

## Safety by design

- Prepares, never executes: actions start `prepared`; only the person can validate; payments are made by the person.
- Facts read by a model stay `proposed` until the person confirms them; the coordinator does not even see the
  confirm/reject operations.
- Tool outputs are data: instruction-like passages are removed, and any side-effect tool call is intercepted.
- Payment requests from an IBAN or creditor never seen in the dossier, or urgent text with a link, are flagged
  « possible hameçonnage — vérifiez l'expéditeur »; a payment can only be prepared with that warning attached.
- Dates in the coordinator's answer that no tool returned are flagged « to verify ».

## Limitations

- 18 procedures; tax returns for VD, GE, ZH, BE and TI only. Elsewhere the coverage map says « non couverte ».
- The coordinator is an 8B model: it can miss a step or pick the wrong tool; the scenario suite measures this, and the
  deterministic review (« Revoir le dossier ») does not depend on it.
- Cantonal rules change yearly: each card carries its access date and must be re-verified.
- Heuristics with known ceilings: phishing phrase list, language of a source guessed from stop words, 5-letter stems
  for search.
- Not legal or tax advice: Ordner informs and cites, the person decides.

Code: Apache-2.0 · documentation: CC-BY-4.0 · data: CDLA-Permissive-2.0 (third-party components and licences: see the
technical report).
