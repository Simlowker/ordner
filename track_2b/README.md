# Ordner: a sovereign Swiss paperwork assistant built on Apertus

**Team Meotis · Hack Apertus 2026 · Track 2B (Own Project)**

**Ordner is a local, sovereign assistant for Swiss paperwork: it knows which administrative procedures concern a person,
what is missing, what to do and why, and prepares everything; it never sends, files, signs or pays.**

It keeps the person's dossier on their own machine, reads the papers they receive, works out which of 18 Swiss
procedures apply (tax return, health insurance, debt collection, pension, unemployment, moving…), computes deadlines
from official rules quoted word for word, and prepares letters, document requests and payments. The person validates
and acts. Apertus 1.5 8B is its only general-purpose language model, in bf16 on one Apple Silicon Mac with 36 GB, offline.

## Two measured proofs

1. **Reading documents without silent errors.** A Swiss e-tax statement (eCH-0196) carries its own data in PDF417
   barcodes: a free, exact answer key. Apertus extracts the fields from the human-readable page (LoRA fine-tune); a
   probe on its hidden states, the d1-3B judge and rule checks flag the values a person should re-check.
2. **Tools and architecture make an 8B model useful as a coordinator.** Process tools (one per procedure) against
   generic tools; a deterministic rules engine first and Apertus for what rules cannot do (the "hybrid"); distillation
   from a larger teacher. All scored on the same scenario suite.

## Results so far

Scenario suite, **dev split** (43 scored scenarios, Apertus 1.5 8B bf16 served by `mlx_lm.server`). The test split
(24 scenarios) is run once; its results go to the [technical report](technical_report.md).

| System                                           | Pass (/43)    | Obligations (/39) | Missing info (/7) | Deadlines exact (/30) | Actions (/31) |
| ------------------------------------------------ | ------------- | ----------------- | ----------------- | --------------------- | ------------- |
| Rules engine only, no model                      | 46.5 %        | 76.9 %            | 0 %               | 50.0 %                | 77.4 %        |
| Apertus coordinator, generic tools               | 14.0 %        | 33.3 %            | 42.9 %            | 10.0 %                | 9.7 %         |
| Apertus coordinator, process tools (2 runs)      | 27.9 / 30.2 % | 59.0 / 56.4 %     | 71.4 / 42.9 %     | 30.0 / 33.3 %         | 29.0 / 32.3 % |
| Same, through DeepSeek Harness                   | 23.3 %        | 59.0 %            | 71.4 %            | 36.7 %                | 29.0 %        |
| **Hybrid: rules engine, then Apertus (process)** | **53.5 %**    | **79.5 %**        | **71.4 %**        | **53.3 %**            | **80.6 %**    |

- Apertus alone stays below the rules engine. Rules first, then Apertus on the same dossier keeps what the rules
  prove and adds the questions only the model can ask (5 of 7, against 0); its gain over rules alone (+3 scenarios)
  is within run-to-run noise. Neither triggers any of the 12 traps.
- No configuration executed anything (0 real-world effects). In 2 scenarios (a bill received by e-mail and by post)
  the hybrid ended with two prepared payments, the rules' generic step and the coordinator's concrete one; a
  double-payment guard was added to the dossier since, and the hybrid is being re-measured.
- Run-to-run noise: two identical runs at temperature 0 differ on 5 of 43 verdicts, so gaps under ~12 points are not
  evidence. Metrics are recall-oriented (extra procedures and dates are only penalised on traps), which favours the
  hybrid, a union of two outputs defined after seeing dev results: on test it is reported as exploratory.
- Teacher (GLM-5.3) on 400 synthetic variants of dev scenarios: 58.5 % pass with process tools, 26.3 % with generic
  tools; 113 trajectories kept after strict filtering; QLoRA distillation of Apertus under evaluation.
- Documents, dev (60 pages, the layout the regex was written for): OCR + regex 0.992 field exact match, zero-shot
  Apertus 0.938. Test (1,200 pages, two unseen layouts, pre-registered): see the report.
- Knowledge search, top-3 hit on 2 × 36 everyday questions: EmbeddingGemma 2 80.6 % / 77.8 %, BM25 52.8 % / 38.9 %,
  RRF fusion 61.1 % / 50.0 % (`data/retrieval/`). The gain is cross-lingual (held-out cross-lingual: 70 % vs 5 %).

## Run it

```bash
make run          # from the repository root: Docker, CPU only, no GPU, no network, no API key
```

The container (no torch, no model weights):

1. replays the document evaluation from the recorded model outputs and hidden-state features in `data/`
   (`ordner.eval.run`: refits the probe and the doubt combination, recomputes every number, writes `data/results/`);
2. runs the scenario suite with the rules engine (`ordner.eval.scenarios.run --agent rules_only --split all`);
3. seeds the fictional demo dossier (Noa Keller, 22, Lausanne) in a throw-away `ORDNER_HOME` at the simulated date
   `ORDNER_TODAY=2026-02-20` (override: `ORDNER_TODAY=2026-10-14 make run`) and reviews it with the rules (no model);
4. serves the console on <http://localhost:8000>.

Status 14.10.2026: the explanations in the « Relevé fiscal » view and the « Demander à Ordner » transcripts are not
yet recorded Apertus outputs; both are labelled « Fixture » in the console until they are.

### Replay vs live

|                       | `make run` (replay, Docker)                                    | Live (Apple Silicon Mac, 36 GB, local weights)                    |
| --------------------- | -------------------------------------------------------------- | ----------------------------------------------------------------- |
| Documents             | recorded OCR, Apertus, d1-3B outputs and hidden-state features | batch pipeline: LightOnOCR-3 → Apertus (+ LoRA) → probe, d1-3B, checks |
| Procedures            | rules engine on the dossier                                    | same, then the Apertus coordinator on the same dossier            |
| « Demander à Ordner » | fixture transcripts                                            | Apertus coordinator through `LLM_BASE_URL` (e.g. `mlx_lm.server`); its tools use cached outputs |
| Knowledge search      | BM25 (no weights in the image)                                 | EmbeddingGemma 2 (live tools or `ORDNER_EMBED=1`)                 |

### Live commands (Apple Silicon, project venv; Docker cannot use the Mac GPU)

Setup and pinned versions: [technical report](technical_report.md), §7. Model revisions: `docs/model_revisions.txt`.

```bash
cd track_2b && PY=.venv/bin/python && export PYTHONPATH=src
# Proof 1: documents
$PY -m ordner.gen.build --out work/ && $PY -m ordner.gen.build_c --out work/   # 600 statements (seed 7), layouts A, B, C
make live                                                                    # OCR + zero-shot Apertus with hidden states
$PY -m ordner.pipeline.d1_batch --tag route && $PY -m ordner.pipeline.d1_batch --tag apertus-base
PY=$PY src/ordner/finetune/train.sh                                          # extraction LoRA
$PY -m ordner.pipeline.extract_batch --tag apertus-lora --adapter work/adapters/lora-v1 --splits dev,test
$PY -m ordner.pipeline.d1_batch --tag apertus-lora && $PY -m ordner.eval.regex_baseline --work work
$PY -m ordner.eval.build_items --work work --data data && $PY -m ordner.eval.probe --work work --data data
$PY -m ordner.explain.corpus --download && $PY -m ordner.explain.eval_explain --n 30 && $PY -m ordner.explain.export_demo --generate

# Proof 2: Apertus behind a local OpenAI-compatible server (same server for every system)
.venv/bin/mlx_lm.server --model <apertus-v1.5-8b-text, bf16> --port 8080 &
export LLM_BASE_URL=http://127.0.0.1:8080/v1 LLM_NAME=<same path or id> ORDNER_EMBED=1
$PY -m ordner.eval.scenarios.run --agent rules_only --split dev               # --split test once, after dev is frozen
$PY -m ordner.eval.scenarios.run --agent coordinator --toolset base --split dev
$PY -m ordner.eval.scenarios.run --agent coordinator --toolset process --split dev
$PY -m ordner.eval.scenarios.run --agent hybrid --toolset process --split dev
$PY -m ordner.eval.scenarios.run --agent harness --toolset process --split dev  # setup: docs/harness_integration.md

# Distillation (development time; the teacher only sees fictional variants of dev scenarios)
$PY -m ordner.distill.variants --n 400 --seed 7
$PY -m ordner.distill.teacher --teacher glm                                   # generic tools (comparison); OpenRouter key in .env
$PY -m ordner.distill.teacher --teacher glm --toolset process --out work/distill/traj.glm.process.jsonl
$PY -m ordner.distill.filter work/distill/traj.glm.process.jsonl && $PY -m ordner.distill.prepare
.venv/bin/mlx_lm.convert --hf-path <bf16 base> -q --mlx-path <4-bit base>         # 4-bit copy for QLoRA
PY=$PY src/ordner/distill/train.sh --model <4-bit base> --num-layers 16 --val-batches 10   # QLoRA, as run
.venv/bin/mlx_lm.server --model <bf16 base> --adapter-path work/adapters/coordinator-distill-v1 --port 8080 &
$PY -m ordner.eval.scenarios.run --agent coordinator --toolset process --split dev      # distilled coordinator

# Knowledge search
$PY -m ordner.eval.retrieval data/retrieval/queries.json && $PY -m ordner.eval.retrieval data/retrieval/queries_heldout.json
```

The result files `data/results/scenarios_<agent>.json` carry no split in their name: copy each one after its run.

## Architecture

```
documents ─► READ: barcode first (eCH-0196, QR-bill: exact)
             otherwise LightOnOCR-3 ─► APERTUS 1.5 8B + LoRA ─► fields + rule checks
             doubt (evaluated batch pipeline): probe on Apertus hidden states + d1-3B judge + rule checks
               │ facts enter as "proposed"; only the person confirms them
               ▼
DOSSIER      local SQLite, append-only event log: documents · facts · cases · deadlines · prepared actions
               │
   1. RULES ENGINE (no model)                    2. APERTUS COORDINATOR (same dossier, ≤ 12 steps)
   18 procedure cards, 227 official sources      free text, missing information, questions to the
   quoted verbatim: applicability, deadlines,    person, explanations in fr/de/it; process toolset
   completeness, prepared steps, phishing and    (9 tools) + ask_user + prepare_action; knowledge
   double-payment guards                         search with EmbeddingGemma 2
               └──────────────────┬─────────────────┘
                                  ▼
COCKPIT      what concerns me · what is missing · next step · why (quoted sources) ─► the person validates and acts
```

### Models

| Model                                    | Role                                                                                                                                    | When loaded                                          | Licence                                    |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------ |
| **Apertus 1.5 8B** (text backbone), bf16 | extracts document fields (LoRA); hidden states feed the doubt probe; coordinator; explanations                                          | live mode                                            | Apache-2.0                                 |
| LightOnOCR-3-1B                          | photo or scan → text                                                                                                                    | on demand                                            | Apache-2.0                                 |
| d1-3B                                    | judge: P(the extracted value is right), one doubt signal                                                                                | on demand (fp32, 14.1 GB: not together with Apertus) | LFM Open License 1.0, **not OSI-approved** |
| EmbeddingGemma 2                         | knowledge search over official sources (BM25 only as fallback)                                                                          | on demand                                            | Apache-2.0                                 |
| GLM-5.3                                  | **development time only**: distillation teacher, via OpenRouter, on fictional scenarios. Not part of the product; no personal data sent | never at runtime                                     | licence not verified here                  |

Apertus (inference, LoRA and QLoRA training) and d1-3B ran on a Mac Studio M4 Max with 36 GB, one large model at a time.

### Tools

16 tools are registered in `ordner.tools.registry` (`len(registry.SPECS)`):

- 11 generic tools: `document.read`, `document.decode`, `knowledge.search`, `decision.score`, `expert.run`,
  `rules.evaluate`, `dossier.check`, `schedule.plan`, `case.load`, `case.record`, `receipt.verify`;
- 5 process tools, one per procedure family: `piece.recevoir` (document intake), `impots.preparer_declaration`
  (tax return), `lamal.revoir_franchise` (health-insurance deductible), `poursuite.repondre` (payment order),
  `demenagement.annoncer` (moving).

The coordinator loop adds `ask_user` and `prepare_action`. Evaluated toolsets: **generic** = the 11 generic tools;
**process** = the 5 process tools + `knowledge.search`, `rules.evaluate`, `case.load`, `case.record` (9). No tool
sends, files, signs or pays.

### Modules (`src/ordner/`)

| Module                                                           | Role                                                                                                                                                         |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `case/`                                                          | Local dossier (`ORDNER_HOME`): facts with provenance and status, cases, actions (double-payment guard), deadlines, append-only events                        |
| `procedures/`                                                    | 18 procedure cards (16 qualified, 2 draft), 227 sources whose quotes were checked verbatim                                                                   |
| `rules/`                                                         | Applicability, deadlines (holidays, debt-collection holidays, reception-by, cantonal tables), reminders, `.ics`, completeness, consolidation, phishing guard |
| `tools/`                                                         | The 16 tools above (JSON schema, argument checks, replay or live mode)                                                                                       |
| `agent/`                                                         | Apertus coordinator: bounded loop, subject pinned, person-only operations hidden, prepared actions only, injection filter                                    |
| `harness/`                                                       | DeepSeek Harness integration (MCP server, Apertus tool-call proxy, fail-closed tool allowlist); optional runtime, not the default                            |
| `distill/`                                                       | Scenario variants, teacher runner, strict filter, training data in Apertus's tool-call syntax, QLoRA training                                                |
| `connectors/`                                                    | Watched inbox, PDF share, eCH-0196, QR-bill, camt.053, OFSP premiums, e-mail drafts (`.eml`, never sent)                                                     |
| `app/`                                                           | Stdlib HTTP server + vanilla JS cockpit, no build step, no CDN (CSP `default-src 'self'`)                                                                    |
| `gen/`, `models/`, `pipeline/`, `finetune/`, `eval/`, `explain/` | Proof 1: synthetic statements with barcode oracle, local model wrappers, batches, LoRA, replay, grounded explanations                                        |
| `eval/scenarios/`                                                | 76 scenarios (67 scored: 43 dev, 24 test), runner, metrics; agents `rules_only`, `coordinator`, `hybrid`, `harness`                                          |

More: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/harness_integration.md`](docs/harness_integration.md),
pre-registration [`PREREG.md`](PREREG.md) (frozen in commit `f52d2c3`, deviations in its Addendum 4).

## Safety by design

- Prepares, never executes: actions start `prepared`; only the person validates; payments are made by the person.
- Facts read by a model stay `proposed` until the person confirms them; the coordinator does not see the confirm or
  reject operations.
- Tool outputs are data: instruction-like passages are removed.
- Payment requests from an unseen IBAN or creditor, or urgent text with a link, are flagged « possible hameçonnage »;
  a second pending payment of the same case and amount is not added.
- Dates in the coordinator's answer that no tool returned are flagged « à vérifier ».

## Limitations

- Scenarios were written by the team in parallel with the procedure cards: the rules engine is not an independent
  baseline. Small n (43 dev, 24 test) and run-to-run noise (5 of 43 verdicts).
- 18 procedures; tax returns for VD, ZH, BE (qualified), GE and TI (draft). Elsewhere the coverage map says
  « non couverte ». Cantonal rules change yearly; each card carries its access date.
- The console's « Demander à Ordner » shows the coordinator all 16 tools (on cached tool outputs), not the evaluated
  process toolset.
- d1-3B's licence is not OSI-approved. All documents are synthetic. Not legal or tax advice: Ordner informs and cites,
  the person decides.

Full list: [technical report](technical_report.md), §6.

## Declarations

Code, procedure cards and scenarios were written with an AI coding assistant (Claude Code) and reviewed by the team.
GLM-5.3 was used at development time only, through OpenRouter, as a distillation teacher on fictional synthetic
scenarios; no personal data was sent and the product never calls it. Third-party components and licences: technical
report, « License ».

Code: Apache-2.0 · documentation: CC-BY-4.0 · data: CDLA-Permissive-2.0.
