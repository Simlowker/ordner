# Technical report — Ordner

**Ordner is a local, sovereign assistant for Swiss paperwork: it knows which administrative procedures concern a person, what is missing, what to do and why, and prepares everything; it never sends, files, signs or pays.**

- **Track:** Track 2B — Ordner
- **Event:** Online
- **Team:** `Meotis` — {{members}}
- **Demo:** {{video_url}}
- **Code:** {{repo_url}}, commit `{{commit}}`; pre-registration `PREREG.md` frozen in commit `f52d2c3` before any model was scored on the test split (Addendum 4 lists the deviations known at the freeze)

## 1. Summary

Ordner keeps a person's administrative dossier on their own machine: it reads the papers they receive, works out which of 18 Swiss procedures apply (tax return, health insurance, debt collection, pension, unemployment, moving, …), computes deadlines from official rules, says what is missing and why, and prepares letters, document requests and payments for the person to validate. Apertus 1.5 8B (bf16, MLX) is its only general-purpose language model; with small support models loaded on demand it runs on one 36 GB Apple Silicon Mac, offline. We measure two claims.

**Proof 1: reading documents without silent errors.** eCH-0196 bank tax statements store their XML in PDF417 barcodes: a free, exact answer key. Apertus extracts eight fields from the readable page (LoRA); a probe on its hidden states, the d1-3B judge and deterministic checks flag values to re-check. On 1,200 frozen test pages (two of three layouts unseen in training, four degradation levels), field exact match is 66.9 % for OCR + rules, 92.1 % for zero-shot Apertus, 98.0 % with LoRA (96.9 % on unseen layouts; H1 supported). Re-reading the most doubtful 30.5 % of fields catches 90 % of zero-shot errors (AUROC 0.922, within-field 0.911; H2 not supported; probe alone 0.840, H3 supported).

**Proof 2: tools and architecture make an 8B model useful as a coordinator.** On 43 dev scenarios grounded in quoted official texts, Apertus passes 14.0 % with generic tools and 27.9-30.2 % with process tools (two identical runs), below the rules engine alone (46.5 %). Rules first, then Apertus on the same dossier passes 53.5 %: the rules supply proven deadlines and steps, Apertus asks what rules cannot see (5 of 7 expected questions, against 0). That gain over rules alone (3 scenarios) is within run-to-run noise. No configuration executed an external effect. Test: 58.3 (hybrid, exploratory) vs 54.2 (rules alone).

### Problem and motivation

- **Not taught, and sensitive.** In 2023, 9.5 % of 18-24-year-olds lived in a household with a tax arrear (FSO figure cited in [20]; original table not checked), 40.9 % of the population in an indebted one in 2022 [21]; 77 % of surveyed adults taught themselves about money [22], and Switzerland is absent from PISA's financial-literacy assessment [23]. A tax file holds sensitive data (art. 5 lit. c nLPD [17]); a cloud service is a processor, often abroad (art. 9, 16-17), and the AI tax assistants we found are cloud-based without published evaluation [24].
- **Why read the page, why not let the model decide.** Scanning damages the barcodes, so VaudTax cannot import a scanned statement [25], and many documents have none: the skill is reading the page, the barcode measures it. Code applies deadline rules exactly but cannot read a letter or ask a question; on dev, Apertus alone gets 10-37 % of deadlines right, the rules 50 %.

### Contributions

1. **The document grades itself.** A payload printed on the same document (the eCH-0196 barcode) is the ground truth for evaluating and fine-tuning extraction from its readable part; our literature search found no prior use of this [18]. Labels are exact, unlimited, and need neither annotators nor a closed model.
2. **Doubt read inside an open model.** A probe on Apertus hidden states, a single-pass judge (d1-3B) and deterministic checks fused into one pre-registered field-level doubt score.
3. **Architecture over model size, measured.** Generic vs process tools on the same model and prompt; rules alone vs Apertus alone vs rules then Apertus; a distilled adapter (H7, under evaluation); one scenario suite; a prepare-only design.
4. **Re-runnable locally.** `make run` replays the evaluation in Docker without GPU, weights or network.

**Related work.** Hidden-state probes beat token uncertainty on hallucinated entities (AUC 0.85 vs ≤ 0.76 [6]) at almost no cost [7], and have been fused with entropy [1]; document confidence has been split into channels [3], OCR self-verified by model agreement [5], judges given guarantees [2] and errors bounded by checks [4]; selective prediction is evaluated by risk-coverage [13], and OCR-then-LLM cascades remain strong [14]. To our knowledge this combination is untested for field extraction and on Apertus.

## 2. Architecture

```
documents ─► READ: barcode first (eCH-0196, QR-bill: exact); otherwise OCR + Apertus + doubt (below)
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

_Figure 1. Ordner. Steps 1 then 2 are the "hybrid" of §5._

**Deterministic core.** The dossier (`ordner.case`, SQLite, append-only event log) keeps facts with provenance; model-read facts stay `proposed` until the person confirms them; deadlines are superseded, never overwritten. 18 procedure cards (16 qualified, 2 draft) cite 227 official sources whose quotes code verifies verbatim. The rules engine computes applicability, deadlines (notification dates, debt-collection holidays, reception-by dates, cantonal tables), completeness per declared bank, consolidation and a phishing guard. Since the dev run of §5 the dossier also guards against double payments: a concrete payment cancels the rules' generic payment step of the same case, and a second pending payment of the same case and amount is not added. Actions enter as `prepared`, only the person validates them, and no tool has a side effect.

**Coordinator and tools.** A Python loop (`ordner.agent.coordinator`) parses Apertus's native tool calls exactly, pins the subject, hides person-only operations, strips instruction-like text from tool outputs and flags dates no tool returned. The registry holds **16 tools**: 11 generic and 5 process tools, one per procedure family (document intake, tax return, LAMal deductible, payment order, moving), each composing deterministic modules and specialist models; the loop adds `ask_user` and `prepare_action`. The _generic_ toolset shows the 11; the _process_ toolset the 5 plus knowledge search, rules evaluation and case load/record (9). The **hybrid** runs the rules engine, then the coordinator (process toolset) on the same dossier, and merges the outputs. **DeepSeek Harness** [26] is integrated as an optional runtime (MCP server over our dispatch, proxy reusing our parser); with a scripted model it sends identical inputs on all 244 dev model calls.

**Reading pipeline (Proof 1).** LightOnOCR-3 turns the page into text; Apertus + LoRA writes the eight fields as JSON (greedy, thinking off); per field, token statistics, a linear probe on Apertus hidden states, d1-3B's P(yes) for "is this the value shown?" and deterministic checks are combined by logistic regression into one doubt score, and only doubtful fields go to the person.

| Component | Role in Ordner | Licence | Runtime |
| --- | --- | --- | --- |
| **Apertus 1.5 8B** (text backbone `andreasmartin/apertus-v1.5-8b-text`) | Field extraction (LoRA), hidden states for the probe, coordinator (distilled adapter under test), explanations | Apache-2.0 | MLX, bf16 |
| LightOnOCR-3-1B | Page image → text | Apache-2.0 | MPS, bf16, on demand |
| LiquidAI d1-3B | Judge: P(yes) per extracted field in one forward pass; closed questions in `decision.score` (not evaluated) | **LFM Open License 1.0, not OSI-approved** (no commercial licence above USD 10 M revenue) | MPS, fp32 (bf16 creates ties), on demand |
| EmbeddingGemma 2 | Knowledge search over sources and card quotes; explanation passages | Apache-2.0 | bf16 (fp16 gives NaN), on demand; BM25 fallback |
| zxing-cpp | Barcode decoding: oracle, barcode-first reading of eCH-0196 and QR-bills | Apache-2.0 | CPU |
| DeepSeek Harness 0.2.1-alpha.2 | Optional agent runtime, not default, not in the Docker image | MIT | Node ≥ 22.19 |
| GLM-5.3 | **Development only:** distillation teacher on fictional scenarios | not verified here | remote (OpenRouter) |

**Checks** (layout label never used): non-negative amounts; withholding claim = 35 % of revenue A; value present in the OCR text; A + B and footnote totals; canton code; tax year = period end.

**Explanations.** EmbeddingGemma 2 retrieves up to six passages in the user's language from 151 passages of nine official documents (`data/corpus/SOURCES.md`; the knowledge search indexes them with the 227 card quotes, 378 in all); Apertus writes at most 170 words quoting them as «…» [id]; code checks each quote verbatim and removes the others. 20 deterministic deduction rules (2026 [19]) list deductions with sources. Ordner informs; it never advises. In the console, `expert.run` returns Apertus's fields with rule checks and token log-probabilities; the probe and d1-3B run in the evaluated batch pipeline.

### Target architecture (mandatory)

Ordner is deployable **b) air-gapped** (primary) and **a) on-premise** (e.g. a debt-counselling workstation); **c)** is not targeted: the dossier stays on the person's machine.

- **Runtime external services: none** (local weights, no API key, CSP `default-src 'self'`, no telemetry). **Build time:** weights, packages, pinned base image, corpus PDFs, OpenSteuerAuszug. **Development time only:** GLM-5.3 via the OpenRouter API (a foreign service) as distillation teacher on fictional scenarios; no personal data or real document was sent; the product never calls it.
- **One 36 GB Apple Silicon Mac** runs everything offline, models loaded on demand (Apertus bf16 and d1-3B fp32, 14.1 GB, do not fit together); the `make run` image holds no model and no remote client. Apertus and d1-3B ran on a Mac Studio M4 Max 36 GB; OCR batches were split with a second M4 Max 36 GB machine, which also ran the scenario clients.

## 3. Use of Apertus

- **Model:** `swiss-ai/Apertus-v1.5-8B`, text backbone exported as `andreasmartin/apertus-v1.5-8b-text` (Apache-2.0), revision `c0e7eeb`
- **How it is used:** inference (field extraction, coordination over tools, explanations), fine-tuning (LoRA for extraction, QLoRA distillation for coordination), evaluation (white-box doubt probe)
- **Where it runs:** local weights; MLX / mlx-lm, bf16, on a Mac Studio M4 Max (36 GB); for scenario runs, `mlx_lm.server` on the Mac Studio, evaluation client on a second machine

**Extraction and hidden states.** The prompt asks for one JSON object with the eight fields, trilingual label hints and the OCR text (`src/ordner/models/apertus.py`); thinking off, greedy; a missing or unparseable value is wrong. MLX and transformers (bf16, CPU) agree on a validation page (hidden-state cosine ≥ 0.9996). One teacher-forced pass reads the residual stream after layers 4, 8, …, 32; per field we keep position A (mean over the value's tokens) and B (the token before it). Norms grow about a thousandfold with depth and the BOS token reaches |x| ≈ 1.2 × 10⁵, consistent with [8]; we keep float32, standardise, fit a 256-d PCA on training items, and choose layer and regularisation of the logistic probe by statement-grouped cross-validation on train + dev.

**LoRA for extraction.** mlx-lm, rank 16, scale 2, all 32 blocks, learning rate 10⁻⁴, batch 2, 2 epochs over 420 pages, loss on the answer, seed 7, targets = oracle values as displayed. Dev loss 0.343 → 0.003; final adapter, fused, no checkpoint selection (about 2 h, peak 22.6 GB).

**Coordinator.** Thinking off, temperature 0, at most 12 model calls per goal, one toolset-neutral prompt. A malformed tool call is answered as an error, never taken as the answer (silent failures are counted).

**Distillation.** GLM-5.3 ran the same loop and scoring on 400 seeded variants of dev scenarios (names, language, canton, dates, missing or wrong-year documents; expected outcomes recomputed by the rules engine): 58.5 % passed with process tools, 26.3 % with generic tools. A strict filter (every check passes, clean end, no tool-use error) kept 113 trajectories, rendered in Apertus's tool-call syntax. bf16 LoRA ran out of memory at 8k-token turns on 36 GB, so we train QLoRA (LoRA on the last 16 layers of a 4-bit copy of the base) and evaluate the adapter on the bf16 base.

## 4. Data

**Tax statements (Proof 1).** 600 fictional statements (seed 7; German 255, French 199, Italian 146), totals cross-checked by recomputation and OpenSteuerAuszug's verifier (MIT [16]), XML per eCH-0196 v2.2 [15]. _Layout A_ is OpenSteuerAuszug's renderer; _B_ (compact table) and _C_ (bank letter, side panel, distractor subtotals, other number formats) are ours, test only. Degradations 1-3 simulate phone photos. **Oracle:** zxing-cpp decodes the barcode segments of the clean PDF; decoded fields match the generator for all 600 statements, and the displayed totals occur in the text layer of all 840 documents. Gold is the value as displayed.

| Split | Statements | Pages | Composition                                                                       |
| ----- | ---------- | ----- | --------------------------------------------------------------------------------- |
| Train | 420        | 420   | layout A, one random degradation level per page                                   |
| Dev   | 60         | 60    | layout A, one random degradation level per page                                   |
| Test  | 120        | 1,200 | layouts A and B × levels 0-3, layout C × levels 0 and 2 (9,600 fields per system) |

**Scenarios (Proof 2).** 76 scenarios (`data/scenarios/`): a fictional persona, dossier, events and goal, sometimes in phases (resumption), with expected procedures, traps, questions, deadlines with the quoted official text that fixes them, actions and forbidden actions. 9 marked `needs_review` are excluded; 67 are split by a fixed hash seed into 43 dev and 24 test. Dev: 39 obligations, 12 traps, 30 deadlines, 7 missing-information items, 31 actions, 3 resumption scenarios. **Retrieval:** 2 × 36 everyday questions (fr/de/it), the second set held out.

**Licence and privacy.** All data is fictional (no personal data), generated with MIT-licensed tools and released under CDLA-Permissive-2.0. `data/` (< 100 MB) holds replay inputs, demo, scenarios, questions, deduction rules and the 56 redistributable corpus passages; cantonal guides are rebuilt locally.

## 5. Evaluation

### Proof 1: extraction and doubt

**Protocol (PREREG.md).** Field exact match on test after normalisation; 95 % CIs by paired cluster bootstrap over the 120 test statements. **H1:** LoRA beats zero-shot. **H2:** the combined doubt score has a higher AUROC for "field is wrong" than every single signal. **H3:** probe A has AUROC > 0.5. Baselines: OCR + regex (patterns from layout-A train/dev), zero-shot Apertus; for doubt, the field prior, token statistics, d1-3B, checks. Doubt is studied on zero-shot outputs, fit on train + dev. Triage = share of fields re-read, most doubtful first, to catch 80 / 90 / 95 % of errors.

**Dev reference (not a test result).** On the 60 dev pages (layout A only), OCR + regex reaches 0.992 field exact match and zero-shot Apertus 0.938: on the layout the regex was written for, rules are hard to beat, so the question is the unseen layouts. The probe's cross-validated AUROC on train + dev is 0.996; error rates differ by field, so part of it may be field identity, hence the within-field AUROC and field-prior row in Table 2.

**Table 1. Baseline vs Ours, extraction (test, 1,200 pages, 9,600 fields per system; 95 % CI).**

| Setup    | System                          | Field accuracy                                                    | Page fully correct | Seen layout (A)       | Unseen layouts (B, C) |
| -------- | ------------------------------- | ----------------------------------------------------------------- | ------------------ | --------------------- | --------------------- |
| Baseline | OCR + rules/regex (no LLM)      | 66.9 [65.8, 68.0] | 37.9  | 99.0 | 45.5  |
| Baseline | OCR + Apertus 1.5 8B, zero-shot | 92.1 [91.4, 92.8]    | 54.5   | 94.2  | 90.8   |
| **Ours** | OCR + Apertus 1.5 8B + LoRA     | 98.0 [97.7, 98.3]    | 88.3   | 99.7  | 96.9   |

**H1 (supported).** LoRA minus zero-shot: +5.9 [+5.2, +6.6] over 9600 paired fields.

**Table 2. Doubt signals on zero-shot Apertus (test, 754 wrong of 9'600 fields): AUROC for "field is wrong", within-field AUROC, share of fields to re-read to catch 90 % of errors (80 % and 95 %: `data/results/table.md`).**

| Setup | Signal | AUROC [95 % CI] | Within field | 90 % |
| --- | --- | --- | --- | --- |
| Baseline | Field prior P(wrong \| field) | 0.621 [0.602, 0.638] | 0.5 by construction | 70.6 |
| Baseline | Min token probability | 0.917 [0.905, 0.928] | 0.872 | 27.4 |
| Baseline | Mean token entropy | 0.924 [0.913, 0.934] | 0.887 | 27.8 |
| Baseline | d1-3B validation | 0.897 [0.877, 0.915] | 0.815 | 35.6 |
| Baseline | Deterministic checks | 0.815 [0.791, 0.838] | 0.814 | 73.0 |
| Ours (part) | Probe, position A (layer 12) | 0.840 [0.814, 0.863] | 0.858 | 57.1 |
| Ours (part) | Probe, position B (layer 20) | 0.889 [0.871, 0.906] | 0.904 | 37.9 |
| **Ours** | **Combined: probe A + d1 + checks + token statistics** | 0.922 [0.904, 0.938] | 0.911 | 30.5 |

**H2 (not supported).** Combined minus best single signal (first-token entropy): -0.024 [-0.048, -0.001]. **H3 (supported).** Probe A: AUROC 0.840, lower bound 0.814; position B minus A: +0.049 [+0.020, +0.079]. For the LoRA system, the pre-registered doubt calibration on dev is not estimable: it makes 2 errors on the 480 dev fields (`combined_lora` in `results.json`), and 190 on test.

![Figure 2](docs/triage_curves.png)
_Figure 2. Triage curves on zero-shot outputs: share of errors caught vs share of fields re-read, per doubt signal._

Breakdowns by layout, degradation level, language and field: `data/results/table.md` and `results.json`.

**Explanations (light, not pre-registered).** On 30 dev pages, {{explain_verbatim_rate}} of the {{explain_quotes_total}} quotes written by Apertus were verbatim in a retrieved passage (others are removed before display); explanations mention {{explain_fields_mentioned}} of the amounts, match the requested language in {{explain_language_match}} of cases and take {{explain_seconds}} s each.

### Proof 2: coordinator architecture

**Protocol (PREREG addenda 1-4).** Each scenario runs on a fresh temporary dossier, one agent instance per phase, and passes when all its checks pass (obligations, traps, questions, deadlines, actions, forbidden actions, resumption). Specialist models are replayed, knowledge search uses EmbeddingGemma 2, Apertus bf16 is served by `mlx_lm.server`. **H4:** the coordinator asks for missing information more often than rules alone, without more wrong triggers; **H5:** zero forbidden actions; **H6:** process tools beat generic tools on deadlines and obligations; **H7:** the distilled adapter beats the untrained coordinator; **H8:** the harness is adopted only if not worse than our loop. The hybrid, defined after the dev results, is exploratory. **Caveat:** obligations and deadlines count when they appear in tool results, and process tools return code-computed deadlines, so H6 measures whether the model calls the right tool with the right arguments; a deadline counts as right when the expected date is among those produced.

**Table 3. Scenario suite, dev split (43 scored scenarios; Apertus 1.5 8B bf16; count and %).**

| Setup       | System                                               | Pass /43                | Obligations /39         | Missing info /7 | Deadlines exact /30    | Actions /31            |
| ----------- | ---------------------------------------------------- | ----------------------- | ----------------------- | --------------- | ---------------------- | ---------------------- |
| Baseline    | Rules engine only, no model                          | 20 (46.5 %)             | 30 (76.9 %)             | 0 (0 %)         | 15 (50.0 %)            | 24 (77.4 %)            |
| Baseline    | Apertus coordinator, generic tools                   | 6 (14.0 %)              | 13 (33.3 %)             | 3 (42.9 %)      | 3 (10.0 %)             | 3 (9.7 %)              |
| Ours (part) | Apertus coordinator, process tools, run 1 / run 2    | 12 / 13 (27.9 / 30.2 %) | 23 / 22 (59.0 / 56.4 %) | 5 / 3           | 9 / 10 (30.0 / 33.3 %) | 9 / 10 (29.0 / 32.3 %) |
| Runtime     | Same, DeepSeek Harness instead of our loop           | 10 (23.3 %)             | 23 (59.0 %)             | 5 (71.4 %)      | 11 (36.7 %)            | 9 (29.0 %)             |
| **Ours**    | **Hybrid: rules engine, then coordinator (process)** | **23 (53.5 %)**         | **31 (79.5 %)**         | **5 (71.4 %)**  | **16 (53.3 %)**        | **25 (80.6 %)**        |

The rules engine and the hybrid trigger no trap (12 traps); no configuration executed an effect. In 2 scenarios (a bill received by e-mail and by post) the hybrid ended with two prepared payments, the rules' generic payment step and the coordinator's concrete one (2 forbidden actions). The dossier guard of §2 was added afterwards; the hybrid re-run gives pass 53.5 with 1 forbidden actions. Two identical process runs at temperature 0 disagree on **5 of 43 verdicts**: dev gaps below about 12 points of pass rate are not evidence.

**Reading.** Process tools lift Apertus (obligations 33 → 56-59 %, deadlines 10 → 30-33 %), as they lift the teacher (26.3 → 58.5 % on the variants), yet Apertus alone stays below the rules wherever rules can prove. The hybrid matches the rules on what they prove and adds Apertus's questions (5 of 7, against 0); its pass-rate gain over rules alone (+3 scenarios) is within noise. We retain it because it keeps the rules' guarantees and adds what only the model can do. DeepSeek Harness is at parity within the run-to-run spread (pass 23.3 % vs 27.9 / 30.2 %, deadlines 36.7 % vs 30.0 / 33.3 %) but adds about 6 s per run (smoke test), a 2.4 GB alpha toolchain and no capability: optional, not default.

**Table 4. Baseline vs Ours, scenario suite, test split (24 scored scenarios, one run per system).**

| Setup       | System                                     | Pass                  | Obligations          | Missing info          | Deadlines exact     | Actions              | Forbidden / executed                     |
| ----------- | ------------------------------------------ | --------------------- | -------------------- | --------------------- | ------------------- | -------------------- | ---------------------------------------- |
| Baseline    | Rules engine only, no model                | 54.2      | 77.3      | 0.0      | 65.0      | 71.4      | 0 / 0       |
| Baseline    | Apertus coordinator, generic tools         | 12.5       | 27.3       | 75.0       | 5.0       | 14.3       | 0 / 0         |
| Ours (part) | Apertus coordinator, process tools         | 50.0    | 68.2    | 50.0    | 60.0    | 50.0    | 0 / 0   |
| Ours (part) | Same + distilled QLoRA adapter (bf16 base) | 41.7    | 72.7    | 100.0    | 55.0    | 42.9    | 0 / 0   |
| Runtime     | Process tools, DeepSeek Harness            | 37.5    | 68.2    | 75.0    | 50.0    | 50.0    | 0 / 0   |
| **Ours**    | **Hybrid (exploratory)**                   | **58.3** | **77.3** | **50.0** | **65.0** | **71.4** | **0 / 0** |

**H4 (supported), H5 (supported), H6 (supported), H7 (not supported), H8 (not supported: the harness was worse on deadline exact-match (50 % vs 60 %), so it is not the product runtime).** H5 counts forbidden actions *prepared*; only executed effects are impossible by construction (no tool can send, pay, file or sign). The distilled adapter has no held-out dev score: its training variants derive from dev scenarios.

**Knowledge search.** The right card's source is in the top 3 for 80.6 % / 77.8 % of development / held-out questions with EmbeddingGemma 2, 52.8 % / 38.9 % with BM25 and 61.1 % / 50.0 % with RRF fusion (`data/retrieval/`). The gain is cross-lingual: BM25 reaches 94.1 % on same-language development questions (embedding 100 %) but 5 % on held-out cross-lingual ones (embedding 70 %, fusion 15 %). We rank with the embedding alone; BM25 is the fallback without weights.

**Cost (Apple M4 Max 36 GB).** End to end, a page costs 24.5 s on average (p95 85.3 s): OCR 14.9 s, LoRA extraction 6.4 s, hidden-state pass 1.9 s (avoidable by capturing states during generation), d1-3B 0.8 s; peak memory 3.1 GB for OCR and 14.1 GB for d1-3B in fp32. The `make run` replay takes 1 s on CPU.

## 6. Limitations

- **Synthetic documents.** Our layouts test generalisation beyond one layout, not to real statements; gold is the displayed value; we target pages whose barcode is missing or damaged, a distribution we have not measured.
- **Doubt study.** The probe is trained on zero-shot errors (the LoRA system would need a refit); one seed per LoRA.
- **Circular scenario suite.** The team wrote the scenarios in parallel with the procedure cards and revised the cards four minutes after committing the scenarios (`8ee7b32`, `a840bac`), and the rules engine reads the procedure label the scenario author attached to known events: it is not an independent baseline, and its scores likely overstate what it would do on scenarios written by others.
- **Small n, lenient metrics, noise.** 43 dev and 24 test scenarios, 7 dev missing-information items; 5 of 43 verdicts change between identical runs; one run per system on test, exact counts without significance tests. Metrics are recall-oriented: extra procedures and dates are not penalised outside the 12 traps, which favours the hybrid, a union of two outputs defined after the dev results.
- **Pre-registration deviations (Addendum 4).** The batch chain generated all test-split model outputs of Proof 1 (systems 1-3, d1-3B) before the freeze, as it processed every split in one pass; no test score was computed and no output inspected, and greedy decoding would reproduce them. The deterministic rules-only baseline had been scored on all scenario splits by `make run` since commit `de0de46`, before the freeze. One test label was printed to check a number format; one console demo page comes from the test split (`src/ordner/eval/DEVIATIONS.md`). The H7 teacher is GLM-5.3, not the pre-registered Apertus 70B.
- **Distillation.** 113 trajectories, from variants of dev scenarios only; the QLoRA adapter is trained on a 4-bit base and evaluated on the bf16 base (train/serve mismatch).
- **Harness parity** is measured with our proxy's normalisations (bare tool names, our stop rules), not for the harness as shipped. **Hardware:** model runs on one 36 GB Mac Studio (OCR partly on a second M4 Max), models loaded one at a time.
- **Coverage and console.** 18 procedures; tax returns for VD, ZH, BE (qualified), GE and TI (draft); cantonal rules must be re-verified yearly. The console runs the deterministic review, then « Demander à Ordner » calls the coordinator on the same dossier, but with all 16 registry tools in replay mode, not the evaluated process toolset; this path is not scored as such.
- **Licences, pipeline, users.** d1-3B's licence is not OSI-approved, its "revenue" clause ambiguous for a public administration. Apertus reads OCR text, not the image. No human study yet.

## 7. Reproducibility

**Replay (judges).** `make run` builds a `python:3.12-slim` image pinned by digest (numpy 2.4.6, scikit-learn 1.9.1, matplotlib 3.10.9) and, without GPU, weights or network, refits probe and combination from the recorded outputs and recomputes every Proof 1 statistic, runs the scenario suite with the rules engine, seeds and reviews the fictional demo dossier, and serves the console on `http://localhost:8000`.

**Live (Apple Silicon, outside Docker).** Python 3.11 with torch 2.14.1, transformers 5.19.0, accelerate 1.15.0, sentence-transformers 6.1.0, mlx 0.32.3, mlx-lm 0.32.0, zxing-cpp 3.1.1, pypdfium2 5.14.0, reportlab 5.0.1, scikit-learn 1.9.1, OpenSteuerAuszug `eeb3b3d` (with the `vroonhof/pdf417-py` fork, `44ce800`). Model revisions (`docs/model_revisions.txt`): Apertus `c0e7eeb`, LightOnOCR-3-1B `23d5440`, EmbeddingGemma 2 `914f7f8`, d1-3B `051bcc4`. Every command (generation, OCR, extraction, d1, LoRA, probe, scenario runs for each system, distillation, retrieval) is listed in `track_2b/README.md`.

**Seeds and checks.** Seeds: generator 7, degradations keyed by page, LoRA 7, PCA 0, bootstrap 0, scenario split by a fixed hash seed, distillation variants 7. Self-checks (`ordner.gen`, `ordner.eval`, `ordner.case`, `ordner.tools`, `ordner.eval.scenarios`, `ordner.harness`) assert generator determinism, the oracle round trip, metric definitions, dossier rules and quote verification. A page whose extraction fails counts as wrong for all fields (0 pages). Random dossier identifiers make scenario runs non-reproducible at the token level. Deviations after the freeze (`f52d2c3`): PREREG.md Addendum 4 (test outputs generated before the freeze but not scored; GLM-5.3 as the only teacher; QLoRA evaluated on bf16; exploratory hybrid; EmbeddingGemma in scenario runs; noise; hardware). After the freeze: the exploratory hybrid + distilled test run was not made (owner's decision, distilled coordinator below base on dev); the domain experts and d1-3B expert routing are exploratory additions; demo documents no longer carry hand-written doubt values.

## 8. Next steps

- The hybrid with the process toolset as the console's default path; the distilled adapter only if H7 holds on test.
- QR-bills (the QR payload is the oracle) and health-insurance letters checked against FOPH premium data, with the same doubt layer; a conformal threshold turning triage into a guarantee [3, 12].
- Scenarios written outside the team (counselling services) to break the circularity; consented, anonymised real statements labelled by their barcodes; a user study.

## License

Creative Commons Attribution 4.0 (CC-BY-4.0). All HackApertus projects are open-sourced.

**Third-party components.** Models: Apertus 1.5 8B (Apache-2.0), LightOnOCR-3-1B (Apache-2.0), EmbeddingGemma 2 (Apache-2.0), d1-3B (LFM Open License 1.0, not OSI). Development only, not shipped: GLM-5.3 through the OpenRouter API (distillation teacher on fictional data; licence and weight availability not verified here). Optional runtime, not in the image: DeepSeek Harness 0.2.1-alpha.2, commit `d743267` (MIT; built with Node.js and pnpm). Data generation: OpenSteuerAuszug (MIT), pdf417gen fork (MIT), python-barcode (MIT), reportlab (BSD), pypdfium2 (BSD-3-Clause / Apache-2.0), zxing-cpp (Apache-2.0), swiss-qr-bill / `qrbill` (MIT). Learning and inference: mlx and mlx-lm, including `mlx_lm.server` (MIT), transformers and sentence-transformers (Apache-2.0), torch (BSD-style), scikit-learn (BSD-3-Clause), numpy (BSD-3-Clause), matplotlib (PSF-based), Pillow (MIT-CMU). Docker base image `python:3.12-slim`. Corpus: eCH-0196 (free use with attribution), ESTV circular 2-215 (federal publication), cantonal guides of Bern, Ticino and Graubünden (not redistributed; `data/corpus/SOURCES.md`).

**Declarations.** Code, procedure cards and scenarios were written with an AI coding assistant (Claude Code; the commits say so) and reviewed and run by the authors; card quotes are verified verbatim by code, and eCH-0196 labels come from the barcodes, not from a model. Apart from GLM-5.3 (development-time teacher on fictional scenarios), no external model generated training data or labels. The console server, Makefile/Docker layout and `LLM_*` convention come from our own LPD Navigator prototype (Apache-2.0), written on 12.10.2026 within the hackathon window. Third-party code is used only as installed libraries, except DeepSeek Harness, built locally (git-ignored).

## References

[1] E. Phillips, F. K. Gustafsson, S. Wu, A. Thakur, D. A. Clifton. _Entropy Alone is Insufficient for Safe Selective Prediction in LLMs._ arXiv:2603.21172, 2026.
[2] J. Jung, F. Brahman, Y. Choi. _Trust or Escalate: LLM Judges with Provable Guarantees for Human Agreement._ arXiv:2407.18370, 2024.
[3] Y. Jin, Y. Wang, Y. Han et al. _Perception, Layout, and Validation: Calibrated Confidence for Reliable Straight-Through Processing of Financial Documents._ arXiv:2609.20110, 2026.
[4] B. Raduta, H. Velicu, A. Preda, S. Chiricescu. _Zero Hallucination, by Construction: Hallucination-Aware Layered Oversight (HALO)._ arXiv:2607.17883, 2026.
[5] Y. Zhang, T. Liang, X. Huang et al. _Consensus Entropy: Harnessing Multi-VLM Agreement for Self-Verifying and Self-Improving OCR._ arXiv:2504.11101, 2025.
[6] O. Obeso et al. _Real-Time Detection of Hallucinated Entities in Long-Form Generation._ arXiv:2509.03531, 2025.
[7] J. Kossen et al. _Semantic Entropy Probes: Robust and Cheap Hallucination Detection in LLMs._ arXiv:2406.15927, 2024.
[8] Apertus Claritas. _Active interpretability with hallucination probes: exploding activations in Apertus 8B._ apertus-claritas.org (accessed 13.10.2026).
[9] Swiss AI Initiative. _Apertus: Democratizing Open and Compliant LLMs for Global Language Environments._ arXiv:2509.14233, 2025.
[10] A. Amini, A. Banaszak, H. Benoit et al. _LFM2 Technical Report._ arXiv:2511.23404, 2025. Liquid AI, _d1-3B_ model card, huggingface.co/LiquidAI/d1-3B, 2026.
[11] LightOn, _LightOnOCR-3_ model card, huggingface.co/lightonai/LightOnOCR-3-1B, 2026. Google, _EmbeddingGemma 2_ model card, huggingface.co/google/embeddinggemma-2, 2026.
[12] Y. Dou, S. Lian, S. Li. _Conformal Cascade: Distribution-Free Accuracy Guarantees for Multi-Tier LLM Inference._ arXiv:2607.25018, 2026.
[13] Y. Geifman, R. El-Yaniv. _Selective Classification for Deep Neural Networks._ NeurIPS, 2017.
[14] Y. Ma et al. _MMLongBench-Doc: Benchmarking Long-context Document Understanding with Visualizations._ arXiv:2407.01523, 2024.
[15] eCH. _eCH-0196 E-Steuerauszug V2.2.0_, incl. Beilage 2 (barcode generation), 2022; _eCH-0270 V1.0.0 Barcode generation_, 2024. ech.ch.
[16] F. Vroonhof et al. _OpenSteuerAuszug_, github.com/vroonhof/opensteuerauszug (MIT), commit eeb3b3d.
[17] Federal Act on Data Protection (FADP / nLPD), SR 235.1, art. 5 lit. c, 9, 16-17, 22. fedlex.admin.ch.
[18] Literature search on document AI verified by oracles (arXiv 2025-2026), 14.10.2026, project notes `papers_systemes_composes.md` §4.4.
[19] ESTV. _Circular 2-215-D-2025: Ausgleich der Folgen der kalten Progression, Steuerjahr 2026_, 11.09.2025.
[20] Kantonsrat St. Gallen, interpellation 51.26.22, 3.3.2026 (citing FSO, 2023).
[21] SRF, "Rund 40 Prozent der Bevölkerung hatten 2022 Schulden", 29.10.2024 (citing FSO SILC 2022).
[22] Raiffeisen Schweiz, survey on financial knowledge (n = 1,506, fieldwork July 2025), 25.11.2025.
[23] OECD. _PISA 2022 Results (Volume IV): How Financially Smart Are Students?_, 2024.
[24] PostFinance TaxOptimizer product page; papertax.ch; budgetberatung.ch/budget-chatbot (accessed 14.10.2026).
[25] BCV. _Procédure fiscale : e-relevé fiscal_ (flyer).
[26] DeepSeek. _DeepSeek Harness_, github.com/deepseek-ai/deepseek-harness (MIT, developer preview), commit d743267 (0.2.1-alpha.2).

## Placeholders (fill, then delete this section before PDF export)

145 placeholders in the text above: 83 come from `data/results/results.json` (written by `make run` / `python -m ordner.eval.run`), 5 from `data/explain_eval.json` (written by `python -m ordner.explain.eval_explain`), 44 from the scenario result files `data/results/scenarios_<agent>.json` (written by `python -m ordner.eval.scenarios.run`; their names carry no split, so copy each file after its run and check that `split` is `test`, or `dev` for the re-run), and 13 are filled by hand. Formats: `%` = multiply by 100, one decimal, no % sign inside table cells that already say %; "percentage points" = multiply by 100, signed, one decimal. The `_unseen` values are derived from the layout-B and layout-C breakdowns (weighted by `n`); `results.json` gives no CI for them.

| Placeholder | File | JSON path | Format |
| --- | --- | --- | --- |
| `{{acc_base_layoutA}}` | `data/results/results.json` | `breakdown["apertus-base"].layout["A"].acc` | % |
| `{{acc_base_test}}` | `data/results/results.json` | `accuracy["apertus-base"].acc` | % |
| `{{acc_base_test_hi}}` | `data/results/results.json` | `accuracy["apertus-base"].ci[1]` | % |
| `{{acc_base_test_lo}}` | `data/results/results.json` | `accuracy["apertus-base"].ci[0]` | % |
| `{{acc_base_unseen}}` | `data/results/results.json` | `derived: (breakdown["apertus-base"].layout["B"].acc × breakdown["apertus-base"].layout["B"].n + breakdown["apertus-base"].layout["C"].acc × breakdown["apertus-base"].layout["C"].n) / (breakdown["apertus-base"].layout["B"].n + breakdown["apertus-base"].layout["C"].n)` | % (no CI) |
| `{{acc_lora_layoutA}}` | `data/results/results.json` | `breakdown["apertus-lora"].layout["A"].acc` | % |
| `{{acc_lora_test}}` | `data/results/results.json` | `accuracy["apertus-lora"].acc` | % |
| `{{acc_lora_test_hi}}` | `data/results/results.json` | `accuracy["apertus-lora"].ci[1]` | % |
| `{{acc_lora_test_lo}}` | `data/results/results.json` | `accuracy["apertus-lora"].ci[0]` | % |
| `{{acc_lora_unseen}}` | `data/results/results.json` | `derived: (breakdown["apertus-lora"].layout["B"].acc × breakdown["apertus-lora"].layout["B"].n + breakdown["apertus-lora"].layout["C"].acc × breakdown["apertus-lora"].layout["C"].n) / (breakdown["apertus-lora"].layout["B"].n + breakdown["apertus-lora"].layout["C"].n)` | % (no CI) |
| `{{acc_regex_layoutA}}` | `data/results/results.json` | `breakdown["regex"].layout["A"].acc` | % |
| `{{acc_regex_test}}` | `data/results/results.json` | `accuracy["regex"].acc` | % |
| `{{acc_regex_test_hi}}` | `data/results/results.json` | `accuracy["regex"].ci[1]` | % |
| `{{acc_regex_test_lo}}` | `data/results/results.json` | `accuracy["regex"].ci[0]` | % |
| `{{acc_regex_unseen}}` | `data/results/results.json` | `derived: (breakdown["regex"].layout["B"].acc × breakdown["regex"].layout["B"].n + breakdown["regex"].layout["C"].acc × breakdown["regex"].layout["C"].n) / (breakdown["regex"].layout["B"].n + breakdown["regex"].layout["C"].n)` | % (no CI) |
| `{{auroc_combined}}` | `data/results/results.json` | `doubt["apertus-base"]["combined"].auroc` | 3 decimals |
| `{{auroc_combined_hi}}` | `data/results/results.json` | `doubt["apertus-base"]["combined"].ci[1]` | 3 decimals |
| `{{auroc_combined_lo}}` | `data/results/results.json` | `doubt["apertus-base"]["combined"].ci[0]` | 3 decimals |
| `{{auroc_d1}}` | `data/results/results.json` | `doubt["apertus-base"]["d1 validation"].auroc` | 3 decimals |
| `{{auroc_d1_hi}}` | `data/results/results.json` | `doubt["apertus-base"]["d1 validation"].ci[1]` | 3 decimals |
| `{{auroc_d1_lo}}` | `data/results/results.json` | `doubt["apertus-base"]["d1 validation"].ci[0]` | 3 decimals |
| `{{auroc_entropy}}` | `data/results/results.json` | `doubt["apertus-base"]["mean entropy"].auroc` | 3 decimals |
| `{{auroc_entropy_hi}}` | `data/results/results.json` | `doubt["apertus-base"]["mean entropy"].ci[1]` | 3 decimals |
| `{{auroc_entropy_lo}}` | `data/results/results.json` | `doubt["apertus-base"]["mean entropy"].ci[0]` | 3 decimals |
| `{{auroc_fieldprior}}` | `data/results/results.json` | `doubt["apertus-base"]["field prior"].auroc` | 3 decimals |
| `{{auroc_fieldprior_hi}}` | `data/results/results.json` | `doubt["apertus-base"]["field prior"].ci[1]` | 3 decimals |
| `{{auroc_fieldprior_lo}}` | `data/results/results.json` | `doubt["apertus-base"]["field prior"].ci[0]` | 3 decimals |
| `{{auroc_minprob}}` | `data/results/results.json` | `doubt["apertus-base"]["min token prob"].auroc` | 3 decimals |
| `{{auroc_minprob_hi}}` | `data/results/results.json` | `doubt["apertus-base"]["min token prob"].ci[1]` | 3 decimals |
| `{{auroc_minprob_lo}}` | `data/results/results.json` | `doubt["apertus-base"]["min token prob"].ci[0]` | 3 decimals |
| `{{auroc_probeA}}` | `data/results/results.json` | `doubt["apertus-base"]["probe A"].auroc` | 3 decimals |
| `{{auroc_probeA_hi}}` | `data/results/results.json` | `doubt["apertus-base"]["probe A"].ci[1]` | 3 decimals |
| `{{auroc_probeA_lo}}` | `data/results/results.json` | `doubt["apertus-base"]["probe A"].ci[0]` | 3 decimals |
| `{{auroc_probeB}}` | `data/results/results.json` | `doubt["apertus-base"]["probe B"].auroc` | 3 decimals |
| `{{auroc_probeB_hi}}` | `data/results/results.json` | `doubt["apertus-base"]["probe B"].ci[1]` | 3 decimals |
| `{{auroc_probeB_lo}}` | `data/results/results.json` | `doubt["apertus-base"]["probe B"].ci[0]` | 3 decimals |
| `{{auroc_rules}}` | `data/results/results.json` | `doubt["apertus-base"]["rules"].auroc` | 3 decimals |
| `{{auroc_rules_hi}}` | `data/results/results.json` | `doubt["apertus-base"]["rules"].ci[1]` | 3 decimals |
| `{{auroc_rules_lo}}` | `data/results/results.json` | `doubt["apertus-base"]["rules"].ci[0]` | 3 decimals |
| `{{cost_d1_mean}}` | `data/results/results.json` | `costs.stages["d1 (apertus-base)"].mean` | seconds, 1 decimal |
| `{{cost_hidden_mean}}` | `data/results/results.json` | `costs.stages["apertus-base hidden-state pass"].mean` | seconds, 1 decimal |
| `{{cost_lora_mean}}` | `data/results/results.json` | `costs.stages["apertus-lora"].mean` | seconds, 1 decimal |
| `{{cost_ocr_mean}}` | `data/results/results.json` | `costs.stages["ocr"].mean` | seconds, 1 decimal |
| `{{cost_total_lora_mean}}` | `data/results/results.json` | `costs.stages["total apertus-lora"].mean` | seconds, 1 decimal |
| `{{cost_total_lora_p95}}` | `data/results/results.json` | `costs.stages["total apertus-lora"].p95` | seconds, 1 decimal |
| `{{dev_hybrid2_forbidden}}` | `data/agent_runs/dev/dev_hybrid_process_v2.json` | `metrics.forbidden_actions` | integer |
| `{{dev_hybrid2_pass}}` | `data/agent_runs/dev/dev_hybrid_process_v2.json` | `metrics.pass_rate` | % |
| `{{explain_fields_mentioned}}` | `data/explain_eval.json` | `amounts_mentioned_share` | % |
| `{{explain_language_match}}` | `data/explain_eval.json` | `language_match_rate` | % |
| `{{explain_quotes_total}}` | `data/explain_eval.json` | `quotes_total` | integer |
| `{{explain_seconds}}` | `data/explain_eval.json` | `mean_seconds` | seconds, 1 decimal |
| `{{explain_verbatim_rate}}` | `data/explain_eval.json` | `citation_verbatim_rate` | % |
| `{{h1_ci_hi}}` | `data/results/results.json` | `h1.ci[1]` | percentage points, signed |
| `{{h1_ci_lo}}` | `data/results/results.json` | `h1.ci[0]` | percentage points, signed |
| `{{h1_diff}}` | `data/results/results.json` | `h1.diff` | percentage points, signed |
| `{{h1_n_paired}}` | `data/results/results.json` | `h1.n_items_paired` | integer |
| `{{h1_verdict}}` | `data/results/results.json` | `h1.supported` | true → "supported", false → "not supported" |
| `{{h2_best_single}}` | `data/results/results.json` | `h2.best_single` | text |
| `{{h2_ci_hi}}` | `data/results/results.json` | `h2.ci[1]` | 3 decimals, signed |
| `{{h2_ci_lo}}` | `data/results/results.json` | `h2.ci[0]` | 3 decimals, signed |
| `{{h2_diff}}` | `data/results/results.json` | `h2.diff` | 3 decimals, signed |
| `{{h2_verdict}}` | `data/results/results.json` | `h2.supported` | true → "supported", false → "not supported" |
| `{{h3_verdict}}` | `data/results/results.json` | `h3.supported` | true → "supported", false → "not supported" |
| `{{n_items_base}}` | `data/results/results.json` | `doubt["apertus-base"]["_n"].items` | integer, thousands separator |
| `{{n_wrong_base}}` | `data/results/results.json` | `doubt["apertus-base"]["_n"].wrong` | integer |
| `{{n_wrong_lora}}` | `data/results/results.json` | `doubt["apertus-lora"]["_n"].wrong` | integer |
| `{{page_ok_base}}` | `data/results/results.json` | `accuracy["apertus-base"].page_all_ok` | % |
| `{{page_ok_lora}}` | `data/results/results.json` | `accuracy["apertus-lora"].page_all_ok` | % |
| `{{page_ok_regex}}` | `data/results/results.json` | `accuracy["regex"].page_all_ok` | % |
| `{{posb_minus_a_diff}}` | `data/results/results.json` | `position_b_vs_a.diff` | 3 decimals, signed |
| `{{posb_minus_a_hi}}` | `data/results/results.json` | `position_b_vs_a.ci[1]` | 3 decimals, signed |
| `{{posb_minus_a_lo}}` | `data/results/results.json` | `position_b_vs_a.ci[0]` | 3 decimals, signed |
| `{{probe_a_layer}}` | `data/results/results.json` | `probe.A.layer` | integer |
| `{{probe_b_layer}}` | `data/results/results.json` | `probe.B.layer` | integer |
| `{{runtime_seconds}}` | `data/results/results.json` | `runtime_seconds` | seconds, integer |
| `{{t_base_act}}` | `data/agent_runs/test/coordinator_base.json` | `metrics.action_recall` | % |
| `{{t_base_dl}}` | `data/agent_runs/test/coordinator_base.json` | `metrics.deadline_exact` | % |
| `{{t_base_eff}}` | `data/agent_runs/test/coordinator_base.json` | `metrics.executed_effects` | integer |
| `{{t_base_forb}}` | `data/agent_runs/test/coordinator_base.json` | `metrics.forbidden_actions` | integer |
| `{{t_base_miss}}` | `data/agent_runs/test/coordinator_base.json` | `metrics.missing_info_recall` | % |
| `{{t_base_obl}}` | `data/agent_runs/test/coordinator_base.json` | `metrics.obligations_recall` | % |
| `{{t_base_pass}}` | `data/agent_runs/test/coordinator_base.json` | `metrics.pass_rate` | % |
| `{{t_distill_act}}` | `data/agent_runs/test/coordinator_process_distill.json` | `metrics.action_recall` | % |
| `{{t_distill_dl}}` | `data/agent_runs/test/coordinator_process_distill.json` | `metrics.deadline_exact` | % |
| `{{t_distill_eff}}` | `data/agent_runs/test/coordinator_process_distill.json` | `metrics.executed_effects` | integer |
| `{{t_distill_forb}}` | `data/agent_runs/test/coordinator_process_distill.json` | `metrics.forbidden_actions` | integer |
| `{{t_distill_miss}}` | `data/agent_runs/test/coordinator_process_distill.json` | `metrics.missing_info_recall` | % |
| `{{t_distill_obl}}` | `data/agent_runs/test/coordinator_process_distill.json` | `metrics.obligations_recall` | % |
| `{{t_distill_pass}}` | `data/agent_runs/test/coordinator_process_distill.json` | `metrics.pass_rate` | % |
| `{{t_harness_act}}` | `data/agent_runs/test/harness_process.json` | `metrics.action_recall` | % |
| `{{t_harness_dl}}` | `data/agent_runs/test/harness_process.json` | `metrics.deadline_exact` | % |
| `{{t_harness_eff}}` | `data/agent_runs/test/harness_process.json` | `metrics.executed_effects` | integer |
| `{{t_harness_forb}}` | `data/agent_runs/test/harness_process.json` | `metrics.forbidden_actions` | integer |
| `{{t_harness_miss}}` | `data/agent_runs/test/harness_process.json` | `metrics.missing_info_recall` | % |
| `{{t_harness_obl}}` | `data/agent_runs/test/harness_process.json` | `metrics.obligations_recall` | % |
| `{{t_harness_pass}}` | `data/agent_runs/test/harness_process.json` | `metrics.pass_rate` | % |
| `{{t_hybrid_act}}` | `data/agent_runs/test/hybrid_process.json` | `metrics.action_recall` | % |
| `{{t_hybrid_dl}}` | `data/agent_runs/test/hybrid_process.json` | `metrics.deadline_exact` | % |
| `{{t_hybrid_eff}}` | `data/agent_runs/test/hybrid_process.json` | `metrics.executed_effects` | integer |
| `{{t_hybrid_forb}}` | `data/agent_runs/test/hybrid_process.json` | `metrics.forbidden_actions` | integer |
| `{{t_hybrid_miss}}` | `data/agent_runs/test/hybrid_process.json` | `metrics.missing_info_recall` | % |
| `{{t_hybrid_obl}}` | `data/agent_runs/test/hybrid_process.json` | `metrics.obligations_recall` | % |
| `{{t_hybrid_pass}}` | `data/agent_runs/test/hybrid_process.json` | `metrics.pass_rate` | % |
| `{{t_process_act}}` | `data/agent_runs/test/coordinator_process.json` | `metrics.action_recall` | % |
| `{{t_process_dl}}` | `data/agent_runs/test/coordinator_process.json` | `metrics.deadline_exact` | % |
| `{{t_process_eff}}` | `data/agent_runs/test/coordinator_process.json` | `metrics.executed_effects` | integer |
| `{{t_process_forb}}` | `data/agent_runs/test/coordinator_process.json` | `metrics.forbidden_actions` | integer |
| `{{t_process_miss}}` | `data/agent_runs/test/coordinator_process.json` | `metrics.missing_info_recall` | % |
| `{{t_process_obl}}` | `data/agent_runs/test/coordinator_process.json` | `metrics.obligations_recall` | % |
| `{{t_process_pass}}` | `data/agent_runs/test/coordinator_process.json` | `metrics.pass_rate` | % |
| `{{t_rules_act}}` | `data/agent_runs/test/rules_only.json` | `metrics.action_recall` | % |
| `{{t_rules_dl}}` | `data/agent_runs/test/rules_only.json` | `metrics.deadline_exact` | % |
| `{{t_rules_eff}}` | `data/agent_runs/test/rules_only.json` | `metrics.executed_effects` | integer |
| `{{t_rules_forb}}` | `data/agent_runs/test/rules_only.json` | `metrics.forbidden_actions` | integer |
| `{{t_rules_miss}}` | `data/agent_runs/test/rules_only.json` | `metrics.missing_info_recall` | % |
| `{{t_rules_obl}}` | `data/agent_runs/test/rules_only.json` | `metrics.obligations_recall` | % |
| `{{t_rules_pass}}` | `data/agent_runs/test/rules_only.json` | `metrics.pass_rate` | % |
| `{{triage90_combined}}` | `data/results/results.json` | `doubt["apertus-base"]["combined"].triage["0.9"]` | % |
| `{{triage90_d1}}` | `data/results/results.json` | `doubt["apertus-base"]["d1 validation"].triage["0.9"]` | % |
| `{{triage90_entropy}}` | `data/results/results.json` | `doubt["apertus-base"]["mean entropy"].triage["0.9"]` | % |
| `{{triage90_fieldprior}}` | `data/results/results.json` | `doubt["apertus-base"]["field prior"].triage["0.9"]` | % |
| `{{triage90_minprob}}` | `data/results/results.json` | `doubt["apertus-base"]["min token prob"].triage["0.9"]` | % |
| `{{triage90_probeA}}` | `data/results/results.json` | `doubt["apertus-base"]["probe A"].triage["0.9"]` | % |
| `{{triage90_probeB}}` | `data/results/results.json` | `doubt["apertus-base"]["probe B"].triage["0.9"]` | % |
| `{{triage90_rules}}` | `data/results/results.json` | `doubt["apertus-base"]["rules"].triage["0.9"]` | % |
| `{{wf_combined}}` | `data/results/results.json` | `doubt["apertus-base"]["combined"].within_field.auroc` | 3 decimals |
| `{{wf_d1}}` | `data/results/results.json` | `doubt["apertus-base"]["d1 validation"].within_field.auroc` | 3 decimals |
| `{{wf_entropy}}` | `data/results/results.json` | `doubt["apertus-base"]["mean entropy"].within_field.auroc` | 3 decimals |
| `{{wf_minprob}}` | `data/results/results.json` | `doubt["apertus-base"]["min token prob"].within_field.auroc` | 3 decimals |
| `{{wf_probeA}}` | `data/results/results.json` | `doubt["apertus-base"]["probe A"].within_field.auroc` | 3 decimals |
| `{{wf_probeB}}` | `data/results/results.json` | `doubt["apertus-base"]["probe B"].within_field.auroc` | 3 decimals |
| `{{wf_rules}}` | `data/results/results.json` | `doubt["apertus-base"]["rules"].within_field.auroc` | 3 decimals |

**Filled by hand:**

| Placeholder | Source |
| --- | --- |
| `{{commit}}` | commit hash of the submission |
| `{{h4_verdict}}` | H4 decision rule of PREREG.md applied to Table 4 ("supported" / "not supported") |
| `{{h5_verdict}}` | H5 decision rule of PREREG.md applied to Table 4 ("supported" / "not supported") |
| `{{h6_verdict}}` | H6 decision rule of PREREG.md applied to Table 4 ("supported" / "not supported") |
| `{{h7_verdict}}` | H7 decision rule of PREREG.md applied to Table 4 ("supported" / "not supported", or "not run") |
| `{{h8_verdict}}` | H8 decision rule of PREREG.md applied to Table 4 ("supported" / "not supported", or "not run") |
| `{{hf_dataset_url}}` | Hugging Face dataset URL (or remove the parenthesis) |
| `{{lora_peak_gb}}` | peak memory printed by finetune/train.py |
| `{{members}}` | member names |
| `{{n_error_pages}}` | number of rows with an "error" key in work/extract.apertus-*.jsonl (0 if none) |
| `{{prereg_deviations}}` | deviations from PREREG.md found after the freeze, or "none" |
| `{{repo_url}}` | public repository URL |
| `{{video_url}}` | demo video URL |

Also copy `data/results/triage_curves.png` to `docs/` after the frozen run (Figure 2).
