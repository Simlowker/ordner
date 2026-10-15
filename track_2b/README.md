# Ordner: a sovereign Swiss paperwork assistant built on Apertus

**Team Meotis · Hack Apertus 2026 · Track 2B (Own Project)**

**Ordner is a local, sovereign assistant for Swiss paperwork: it knows which administrative procedures concern a person,
what is missing, what to do and why, and prepares everything; it never sends, files, signs or pays.**

**Ordner is a local mixture of domain experts on one open model, for Swiss federalism:** a small model (d1-3B) picks the
expert; each expert is Apertus 1.5 8B with its domain's tools, its own knowledge base of official sources (federal + the
person's canton), and its own LoRA adapter only where it measurably helps; the rules engine computes what is computable;
nothing is sent. It routes by domain and filters by canton, read from the dossier: one expert per domain scales, one per
canton would not.

It keeps the person's dossier on their own machine, reads the papers they receive, works out which of 18 Swiss
procedures apply (tax return, health insurance, debt collection, pension, unemployment, moving…), computes deadlines
from official rules quoted word for word, and prepares letters, document requests and payments. The person validates
and acts. Apertus 1.5 8B (bf16) is its only general-purpose language model. Tested configuration: Apertus served on a
Mac Studio M4 Max 36 GB, clients and UI on a second Mac (M4 Max 36 GB) over the local network; nothing leaves the LAN
at run time.

## Two measured proofs

1. **Reading documents and flagging most errors.** A Swiss e-tax statement (eCH-0196) carries its own data in PDF417
   barcodes: a free, exact answer key. Apertus extracts the fields from the human-readable page (LoRA fine-tune); a
   probe on its hidden states, the d1-3B judge and rule checks flag the values a person should re-check.
2. **Process tools make Apertus 8B a usable component, not a replacement for rules.** Process tools (one per
   procedure) against generic tools; a deterministic rules engine first and Apertus for what rules cannot do (the
   "hybrid"); distillation from a larger teacher. All scored on the same scenario suite.

## Results (frozen test splits; details in the [technical report](technical_report.md))

Documents (1,200 test pages, 9,600 fields, two of three layouts unseen in training): field exact match 66.9 % for
OCR + rules/regex, 92.1 % for zero-shot Apertus, 98.0 % with LoRA (96.9 % on unseen layouts; H1 supported). Doubt on
the zero-shot outputs (754 errors): first-token entropy AUROC 0.947 (re-reading 19.3 % of fields catches 90 % of
errors), probe on hidden states 0.840 (H3 supported), combination 0.922 (H2 not supported).

Scenario suite, test split (24 scenarios, one run per system, Apertus 1.5 8B bf16 served by `mlx_lm.server`; counts):

| System                                           | Pass /24 | Obligations /22 | Missing info /4 | Deadlines /20 | Actions /14 | Forbidden / executed |
| ------------------------------------------------ | -------- | --------------- | --------------- | ------------- | ----------- | -------------------- |
| Rules engine only, no model                      | 13       | 17              | 0               | 13            | 10          | 0 / 0                |
| Apertus coordinator, generic tools               | 3        | 6               | 3               | 1             | 2           | 0 / 0                |
| **Apertus coordinator, process tools**           | **12**   | **15**          | **2**           | **12**        | **7**       | **0 / 0**            |
| Same + distilled adapter                         | 10       | 16              | 4               | 11            | 6           | 0 / 0                |
| Process tools, DeepSeek Harness runtime          | 9        | 15              | 3               | 10            | 7           | 0 / 0                |
| Hybrid (post-hoc): rules, then Apertus (process) | 14       | 17              | 2               | 13            | 10          | 0 / 0                |

- Process vs generic tools (H6, supported): deadlines 12 vs 1, obligations 15 vs 6; pass 12 vs 3 (McNemar 9–0,
  p = 0.004). Apertus alone stays below the rules engine; the hybrid's one extra pass over rules is not significant
  (McNemar 1–0, p = 1). Distillation (H7) is not supported (10 vs 12); the harness runtime (H8) is not adopted.
- Run-to-run noise: two identical dev runs at temperature 0 differ on 5 of 43 verdicts. Metrics are recall-oriented,
  which favours the hybrid, and cards and scenarios were written together, so rules-only is not an independent baseline.
  Dev results (43 scenarios): technical report, Table 3.
- No run executed an effect. On dev, the hybrid prepared a duplicated payment in two scenarios (a double-payment guard
  was added since) and, in its re-run, an action carrying the IBAN of an injected phishing e-mail (`tax-be-03`).
- Exploratory: d1-3B routes the conversation's first request to the coordinator or one of four experts, 78.1 % correct
  vs 64.7 % for EmbeddingGemma 2 on 201 requests. Expert adapters are kept only where they beat the base on dev
  (Poursuites, Logement) and are opt-in (`ORDNER_USE_ADAPTERS=1`): `mlx_lm.server` 0.32 reloads the model on each
  adapter change (16 → 35 GB measured).

### Knowledge bases per expert (exploratory, added after the PREREG freeze)

Each expert searches its own base (`data/knowledge/<expert>/`, `ordner.tools.expert_kb`): official passages for topics
fixed before collection (`data/knowledge/topics.json`), federal + VD, ZH, BE, GE, TI, in fr/de/it, filtered at query
time to federal + the dossier's canton. Every passage is a verbatim substring of the saved fetched text, after whitespace normalisation (re-checked: 0
of 712 fail). Official acts are in the repository (not protected by copyright, art. 5 LDA); authority pages are kept
locally (`work/knowledge/`), their URLs listed in each `sources.json`, so a clean clone has the acts only.

Top-3 topic hit on 96 questions (`data/knowledge/questions.json`, 24 per expert, 8 fr / 8 de / 8 it, written blind
before any retrieval run; see the git history of `data/knowledge/`), all with the federal + canton filter:

| Expert                           | Passages (acts + pages) | Sources | Federal / cantonal | Expert base | One global base | BM25 on expert base |
| -------------------------------- | ----------------------- | ------- | ------------------ | ----------- | --------------- | ------------------- |
| Impôts                           | 135 (105 + 30)          | 46      | 79 / 56            | 87.5 %      | 66.7 %          | 79.2 %              |
| Assurance maladie                | 168 (114 + 54)          | 39      | 126 / 42           | 95.8 %      | 95.8 %          | 83.3 %              |
| Poursuites                       | 164 (111 + 53)          | 40      | 107 / 57           | 79.2 %      | 70.8 %          | 79.2 %              |
| Logement et ménage               | 245 (106 + 139)         | 93      | 158 / 87           | 95.8 %      | 91.7 %          | 83.3 %              |
| **All**                          | 712 (436 + 276)         | 218     | 470 / 242          | **89.6 %**  | 81.2 %          | 81.2 %              |
| Official acts only (clean clone) | 436 (436 + 0)           | 92      | 323 / 113          | 90.6 %      | 81.2 %          | 75.0 %              |

- Expert base vs one global base without routing: 8 questions won, 0 lost (McNemar exact p = 0.008); vs BM25: 11–3
  (p = 0.057). 29.2 % of the global base's top-3 lists contain another expert's passages (30.2 % with acts only).
- Limits: topics tagged by the collecting agents (Serafe and OFCOM FAQ chunks by URL and keyword rules), questions
  written by an AI agent, 24 questions per expert, one embedding model, topic match rather than answer quality.
- Known gaps (coverage notes): VD's residents' law says 8 days to register, a Lausanne page says 14 (unresolved); VD's
  LAMal law could not be retrieved (premium reduction from vd.ch pages only); some cantonal texts may be outdated (ZH
  residents' law as of 2018, VD's as of 2015 via LexFind); an Italian FOPH sheet gives the previous cycle's dates, kept
  verbatim.
- An earlier test on the procedure cards' sources (2 × 36 questions, `data/retrieval/`) chose EmbeddingGemma 2 over
  BM25 (80.6 / 77.8 % vs 52.8 / 38.9 % top-3); BM25 stays only as the fallback without weights.

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
4. serves the console on <http://localhost:8000>;
5. if the optional conversation layer built, serves the agentic conversation (DeepSeek Harness web UI under Ordner's
   brand fork, [`harness_fork/`](harness_fork/README.md), MIT) on <http://127.0.0.1:8790>: open the URL with
   `?token=…` printed in the log, pick an expert, ask. Without `LLM_BASE_URL` the model is a scripted mock that reads the
   dossier; with `LLM_BASE_URL` (an OpenAI-compatible server for Apertus 1.5 8B) it runs for real.

The conversation layer is built from the published npm package `@deepseek-ai/dsh@0.2.1-alpha.2` (network at build time
only). If that step fails, the image is built without it and step 5 is skipped; the console works the same.

The explanations in the « Relevé fiscal » view are recorded Apertus 1.5 8B outputs (quotes verified word for word).
Without the conversation layer, « Demander à Ordner » shows hand-written transcripts labelled « Fixture ».

### Replay vs live

|                       | `make run` (replay, Docker)                                       | Live (Apple Silicon Mac, 36 GB, local weights)                                                  |
| --------------------- | ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| Documents             | recorded OCR, Apertus, d1-3B outputs and hidden-state features    | batch pipeline: LightOnOCR-3 → Apertus (+ LoRA) → probe, d1-3B, checks                          |
| Procedures            | rules engine on the dossier                                       | same, then the Apertus coordinator on the same dossier                                          |
| « Demander à Ordner » | conversation with a scripted mock model; else fixture transcripts | Apertus coordinator through `LLM_BASE_URL` (e.g. `mlx_lm.server`); its tools use cached outputs |
| Knowledge search      | BM25 over the card corpus (no weights in the image); the experts' bases need EmbeddingGemma 2 | EmbeddingGemma 2 (live tools or `ORDNER_EMBED=1`): the expert's own base, else the card corpus |

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

# Knowledge search: per-expert bases (data/knowledge/results.json; acts only: results_repo_only.json), then the card corpus
$PY -m ordner.eval.knowledge_experts && ORDNER_KB_REPO_ONLY=1 $PY -m ordner.eval.knowledge_experts
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
   1. RULES ENGINE (no model)                    2. APERTUS 1.5 8B (same dossier, ≤ 12 steps)
   18 procedure cards, 227 verbatim quotes       ROUTER d1-3B picks the expert (78.1 % of 201 requests)
   from 73 official sources: applicability,      EXPERT = Apertus + domain tools + its own knowledge base
   deadlines, completeness, prepared steps,        (federal + dossier canton, EmbeddingGemma 2) + LoRA only
   phishing and double-payment guards              if it beat the base on dev; coordinator = general expert
               └──────────────────┬─────────────────┘
                                  ▼
COCKPIT      what concerns me · what is missing · next step · why (quoted sources) ─► the person validates and acts
```

### Models

| Model                                    | Role                                                                                                                                    | When loaded                                          | Licence                                    |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------ |
| **Apertus 1.5 8B** (text backbone), bf16 | extracts document fields (LoRA); hidden states feed the doubt probe; coordinator; explanations                                          | live mode                                            | Apache-2.0                                 |
| LightOnOCR-3-1B                          | photo or scan → text                                                                                                                    | on demand                                            | Apache-2.0                                 |
| d1-3B                                    | judge: P(the extracted value is right), one doubt signal; routes the conversation's first request to an expert (bf16)                   | on demand (fp32, 14.1 GB: not together with Apertus) | LFM Open License 1.0, **not OSI-approved** |
| EmbeddingGemma 2                         | knowledge search over each expert's official sources (BM25 only as fallback); routing fallback                                          | on demand                                            | Apache-2.0                                 |
| GLM-5.3                                  | **development time only**: distillation teacher, via OpenRouter, on fictional scenarios. Not part of the product; no personal data sent | never at runtime                                     | licence not verified here                  |

Apertus (inference, LoRA and QLoRA training) and d1-3B ran on a Mac Studio M4 Max 36 GB, one large model at a time.
OCR batches ran on it and on the second Mac (a laptop, M4 Max 36 GB), which also ran the evaluation clients and the UI.

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

| Module                                                           | Role                                                                                                                                                              |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `case/`                                                          | Local dossier (`ORDNER_HOME`): facts with provenance and status, cases, actions (double-payment guard), deadlines, append-only events                             |
| `procedures/`                                                    | 18 procedure cards (16 qualified, 2 draft), 227 verbatim quotes from 73 official sources, checked by code                                                         |
| `rules/`                                                         | Applicability, deadlines (holidays, debt-collection holidays, reception-by, cantonal tables), reminders, `.ics`, completeness, consolidation, phishing guard      |
| `tools/`                                                         | The 16 tools above (JSON schema, argument checks, replay or live mode); `expert_kb`: one knowledge base per expert, used by `knowledge.search`                    |
| `agent/`                                                         | Apertus coordinator: bounded loop, subject pinned, person-only operations hidden, prepared actions only, injection filter                                         |
| `harness/`                                                       | DeepSeek Harness integration (MCP server, Apertus tool-call proxy, fail-closed tool allowlist), web presets (coordinator + four experts), d1-3B routing; optional |
| `distill/`                                                       | Scenario variants, teacher runner, strict filter, training data in Apertus's tool-call syntax, QLoRA training                                                     |
| `connectors/`                                                    | Watched inbox, PDF share, eCH-0196, QR-bill, camt.053, OFSP premiums, e-mail drafts (`.eml`, never sent)                                                          |
| `app/`                                                           | Stdlib HTTP server + vanilla JS cockpit, no build step, no CDN (CSP `default-src 'self'`)                                                                         |
| `gen/`, `models/`, `pipeline/`, `finetune/`, `eval/`, `explain/` | Proof 1: synthetic statements with barcode oracle, local model wrappers, batches, LoRA, replay, grounded explanations                                             |
| `eval/scenarios/`                                                | 76 scenarios (67 scored: 43 dev, 24 test), runner, metrics; agents `rules_only`, `coordinator`, `hybrid`, `harness`                                               |

More: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/harness_integration.md`](docs/harness_integration.md),
pre-registration [`PREREG.md`](PREREG.md) (frozen in commit `f52d2c3`, deviations in its Addendum 4).

## Safety by design

- Prepares, never executes: actions start `prepared`; only the person validates; payments are made by the person.
- Facts read by a model stay `proposed` until the person confirms them; the coordinator does not see the confirm or
  reject operations.
- Tool outputs are data: instruction-like passages are removed.
- Payment requests from an unseen IBAN or creditor, or urgent text with a link, are flagged « possible hameçonnage »;
  a second pending payment of the same case and amount is not added. Flagged, not refused: on dev, a hybrid run still
  prepared an action carrying a phishing IBAN (technical report, §5).
- Dates in the coordinator's answer that no tool returned are flagged « à vérifier ».

## Limitations

- Scenarios were written by the team in parallel with the procedure cards: the rules engine is not an independent
  baseline. Small n (43 dev, 24 test) and run-to-run noise (5 of 43 verdicts).
- 18 procedures; tax returns for VD, ZH, BE (qualified), GE and TI (draft). Elsewhere the coverage map says
  « non couverte ». Cantonal rules change yearly; each card carries its access date.
- The agentic web conversation (forked harness UI, experts, routing) demonstrates the evaluated loop but is not
  separately evaluated; with Noa's long dossier the 8B model often asks instead of acting. Without that layer, the
  console's live « Demander à Ordner » gives the coordinator all 16 tools, not the evaluated process toolset.
- Knowledge bases: exploratory, scored on retrieval (topic match), not on the experts' answers; topics tagged by the
  collecting agents, questions written by an AI agent; five cantons only, with the gaps listed above.
- d1-3B's licence is not OSI-approved. All documents are synthetic. Not legal or tax advice: Ordner informs and cites,
  the person decides.

Full list: [technical report](technical_report.md), §6.

## Declarations

Code, procedure cards and scenarios were written with an AI coding assistant (Claude Code) and reviewed by the team.
GLM-5.3 was used at development time only, through OpenRouter, as a distillation teacher on fictional synthetic
scenarios; no personal data was sent and the product never calls it. Third-party components and licences: technical
report, « License ».

Code: Apache-2.0 · documentation: CC-BY-4.0 · data: CDLA-Permissive-2.0.
