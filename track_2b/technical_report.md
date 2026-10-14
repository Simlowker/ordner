# Technical report — Ordner

**Ordner reads Swiss bank tax statements on a laptop, grades itself against each statement's own barcode, and tells the user which values to check.**

- **Track:** Track 2B — Ordner
- **Event:** Online
- **Team:** `{{team_name}}` — {{members}}
- **Demo:** {{video_url}}
- **Code:** {{repo_url}}, commit `{{commit}}`; pre-registration `PREREG.md` frozen in commit `{{prereg_commit}}`

## 1. Summary

Young adults in Switzerland face their first tax return without having been taught how, and the documents involved contain sensitive personal data. Ordner reads the summary page of a bank tax statement (eCH-0196) from a photo or scan, extracts the eight values a taxpayer needs, flags the values it may have misread, and runs on one laptop. Apertus 1.5 8B is the core: fine-tuned with LoRA, it writes the fields as JSON, and a linear probe on its hidden states estimates for each field whether the value is wrong. LightOnOCR-3 (OCR), d1-3B (single-pass judge) and deterministic checks support it. Labels cost nothing: every eCH-0196 statement stores its full XML in Macro-PDF417 barcodes, which we decode as ground truth. On 960 frozen test pages (120 synthetic statements, two layouts of which one is unseen in training, four degradation levels), field-level exact match is {{acc_regex_test}} for OCR + rules, {{acc_base_test}} for zero-shot Apertus and {{acc_lora_test}} after fine-tuning (H1: {{h1_verdict}}). Re-reading the most doubtful {{triage90_combined}} of fields catches 90 % of zero-shot errors (combined AUROC {{auroc_combined}}, H2: {{h2_verdict}}; probe alone {{auroc_probeA}}, H3: {{h3_verdict}}). No external service is called at runtime.

### Problem and motivation

- **Not taught.** In 2023, 9.5 % of 18-24-year-olds lived in a household with at least one tax arrear (FSO figure cited in a St. Gallen parliamentary interpellation of 3.3.2026 [20]; we have not checked the original FSO table). In 2022, 40.9 % of the population lived in an indebted household and 5.5 % in one with tax arrears (FSO SILC 2022, reported by SRF [21]). In a representative survey (n = 1,506), 77 % said they taught themselves about money [22], and Switzerland does not take part in PISA's financial-literacy assessment [23].
- **Why local.** A tax file contains sensitive personal data under art. 5 lit. c of the Data Protection Act (nLPD/FADP): religious affiliation (church tax), health (medical expenses), social-assistance measures [17]. A cloud service makes the provider a processor (art. 9) and often implies disclosure abroad (art. 16-17). Every AI tax assistant we found is cloud-based: PostFinance TaxOptimizer, PaperTax (LLM processing in the United States, according to its website), and the Budgetberatung chatbot (OpenAI; it asks users not to enter bank or health data) [24]. None publishes an evaluation.
- **Why read the page when a barcode exists.** VaudTax cannot import a scanned statement because scanning damages the barcodes [25], and pillar 3a certificates, health-insurance letters and many foreign brokers' statements have no machine-readable part. The useful skill is reading the human-readable page; a clean barcode only serves to measure it.

### Contributions

1. **The document grades itself.** To our knowledge, no prior work uses a payload printed on the same document (here the eCH-0196 barcode) as ground truth for both evaluating and fine-tuning extraction from the human-readable part; our literature search (arXiv 2025-2026) found none [18]. Labels are exact, unlimited, and need neither human annotation nor a closed model.
2. **Doubt read inside an open model, combined with an external judge.** A probe on Apertus hidden states, a calibrated single-pass judge (d1-3B) and deterministic checks are fused into one field-level doubt score for human triage, with pre-registered hypotheses. Phillips et al. [1] fuse a probe with token entropy and Jin et al. [3] decompose document confidence into channels; to our knowledge this three-way combination has not been evaluated for document field extraction, nor on Apertus.
3. **Re-runnable locally.** `make run` replays the full evaluation in Docker without GPU, weights or network; we report cost per page on a named laptop.

**Related work.** Selective prediction is evaluated by risk-coverage since Geifman & El-Yaniv [13]. Hidden-state probes detect hallucinated entities better than token uncertainty (AUC 0.85 vs at most 0.76 on Llama-3.1-8B [6]) and approximate semantic entropy at almost no cost [7]; entropy alone fails in model-dependent ways [1]. Small judges with calibrated abstention can guarantee agreement levels [2]; for financial documents, Jin et al. [3] report auto-acceptance rates at a target error, and HALO [4] bounds generative errors with deterministic checks. OCR-then-LLM cascades remain strong baselines: most vision-language models underperform their own LLM given OCR text on long documents [14]. Among public Hack Apertus Track 2B repositories (searched 14.10.2026; private ones are not visible) we found none on tax statements and none reading hidden states.

## 2. Architecture

```
page image (photo / scan)                                    Figure 1. Pipeline (stages run as resumable batches)
  └─► LightOnOCR-3-1B ......... OCR → Markdown text                                   [support]
        └─► Apertus 1.5 8B + LoRA .. 8 fields as JSON (greedy, thinking off)          [core]
              ├─ token log-probs and entropies of each value
              ├─ hidden states (one teacher-forced pass) ─► linear probe: P(field wrong)
              ├─ d1-3B ............. "Is <value> the <field> shown in this document?" → P(yes)   [support]
              └─ deterministic checks (35 % rule, A + B totals, value present in the OCR text, ...)
                    └─► combined doubt (logistic regression) ─► triage: only doubtful fields go to a person
                          └─► console: fields coloured by doubt, triage slider, explanation, deduction checklist
```

| Component                                                              | Role in Ordner                                                                           | Licence                                                                                                        | Runtime, precision                                                                      | Evaluated                                     |
| ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | --------------------------------------------- |
| **Apertus 1.5 8B**, text backbone `andreasmartin/apertus-v1.5-8b-text` | Field extraction (LoRA fine-tuned); hidden states read by the doubt probe; explanations  | Apache-2.0 (gated, automatic approval)                                                                         | MLX, bf16                                                                               | yes (core)                                    |
| LightOnOCR-3-1B                                                        | Page image → text                                                                        | Apache-2.0                                                                                                     | transformers, MPS, bf16, longest edge 1,280 px                                          | through downstream systems                    |
| LiquidAI d1-3B                                                         | Judge: one forward pass, no generated token, P(yes) per extracted field; document router | **LFM Open License 1.0, not OSI-approved** (no commercial licence for entities with ≥ USD 10 M annual revenue) | transformers, MPS, fp32 (bf16 quantises answer logits in steps of 0.125, creating ties) | judge: yes; router: no (single document type) |
| EmbeddingGemma 2                                                       | Retrieval of official guide passages to ground explanations                              | Apache-2.0                                                                                                     | sentence-transformers, bf16 (fp16 silently returns NaN)                                 | no (demo)                                     |
| Deterministic checks                                                   | Per-field consistency: True / False / not applicable                                     | ours                                                                                                           | Python                                                                                  | yes                                           |
| zxing-cpp                                                              | Barcode decoding for the oracle only, never a model input                                | Apache-2.0                                                                                                     | CPU                                                                                     | —                                             |

**Deterministic checks** never use the layout label: amounts are non-negative; the withholding claim equals 35 % of revenue A within display rounding; each amount appears in the OCR text (twice when a totals row is printed); the total tax value matches the "of which A … and B …" footnote and A + B the printed total revenue; institution and client name appear in the text; the canton is a valid code printed on the page; the tax year matches the period end.

**Data flow.** Stages run one model at a time on two Apple M4 Max machines with 36 GB of memory (OCR and d1-3B on a laptop, Apertus and LoRA on a Mac Studio) and write JSONL files, so each stage can be resumed or replayed. Apertus alone produces the extracted values; d1-3B, the checks and the probe score them but never change them.

**Explanation and deductions (demo, not evaluated).** The console explains in French, German or Italian where each value goes in the tax return, with cited passages and a badge when a quote is found verbatim in its source. In this submission, explanations are prepared offline for the demo pages ({{explanation_provenance}}); the EmbeddingGemma 2 wrapper is implemented and smoke-tested (bf16, 96 ms per page) but retrieval is not part of the evaluated pipeline. <!-- UPDATE before export if retrieval + Apertus explanations are wired in. --> A checklist applies 20 deterministic deduction rules (federal direct tax and pillar 3a, tax year 2026, amounts from ESTV circular 2-215-D-2025 [19]); each rule cites its source and verification status, and rules not read in a primary source are flagged. The wording informs; it never advises.

### Target architecture (mandatory)

Ordner is deployable as **b) air-gapped** (primary) and **a) on-premise**.

- **Runtime external services: none.** All four models load from local weights; no API key; the console serves only local files (Content-Security-Policy `default-src 'self'`, no CDN, no telemetry). The video shows the pipeline running with Wi-Fi off.
- **Build time only (online, once):** model weights from Hugging Face, Python packages, the Docker base image (pinned by digest), and, for data generation, OpenSteuerAuszug and its PDF417 encoder fork from GitHub.
- **b) Air-gapped:** once built, an Apple Silicon Mac with 36 GB runs the whole pipeline offline; the `make run` image contains no model and no client for any remote service.
- **a) On-premise:** the same software on a workstation of a budget or debt counselling service, under its own administration; no document leaves the premises. Transformers wrappers exist for all four models, but our batch runs used MLX (Apertus) and MPS.
- **c) Sovereign Swiss cloud** would need no code change for the replay, but is not targeted: keeping tax data on the user's machine is the point.

## 3. Use of Apertus

- **Model:** `swiss-ai/Apertus-v1.5-8B`, text backbone exported as `andreasmartin/apertus-v1.5-8b-text` (Apache-2.0)
- **How it is used:** inference (extraction, explanation), fine-tuning (LoRA), evaluation (white-box doubt probe)
- **Where it runs:** local weights; MLX 0.32.3 / mlx-lm 0.32.0 on an Apple M4 Max (36 GB), bf16

**Prompt and decoding.** A system message ("You extract data from Swiss tax statements (eCH-0196 Steuerauszug). You answer with one JSON object and nothing else.") precedes a user message with the eight fields and trilingual label hints, output rules (fixed keys, plain decimals, two-letter canton, `null` if absent) and the page's OCR text (`src/ordner/models/apertus.py`). The chat template is rendered with thinking disabled; decoding is greedy (≤ 256 new tokens) with log-softmax in float32. A tolerant parser maps the answer to the eight fields; missing or unparseable values count as wrong.

**Numerical check.** Batch runs use MLX because the transformers stack swapped heavily on the 36 GB laptop. On a validation page, MLX and the reference transformers implementation (bf16, CPU) gave an identical greedy answer, and hidden states at the probed positions had cosine similarity ≥ 0.9996. In our smoke test, transformers on MPS deviated on some prompt tokens (cosine down to 0.74 at layers 16 and 24), hence validation against CPU.

**Hidden states.** After generation, one teacher-forced pass over prompt and answer reads the residual stream after decoder layers 4, 8, …, 32. Per field we keep position A (mean over the value's tokens) and position B (the token just before the value). Apertus's residual norm grows about a thousandfold with depth (mean answer-token norm ≈ 6 after the embeddings, ≈ 6,000 at layer 31), and the BOS token reaches |x| ≈ 1.2 × 10⁵ from layer 3 on, consistent with the exploding activations reported by Claritas on Apertus v1 [8]. We therefore keep float32 wherever float16 would overflow, standardise each dimension before a 256-component PCA fitted on training items only, and choose the layer and regularisation of the logistic-regression probe by cross-validation grouped by statement on train + dev.

**LoRA fine-tuning.** mlx-lm LoRA: rank 16, scale 2 (α = 32), dropout 0, all 32 blocks; Adam, learning rate 10⁻⁴, batch 2, 420 iterations (2 epochs over 420 training pages), 2,048 tokens max, gradient checkpointing, loss on the answer only, seed 7. Inputs are the OCR text of degraded training pages inside the exact extraction prompt; targets are the oracle values as displayed on the page, in the zero-shot answers' JSON layout. For every example we assert that the training sequence tokenises to exactly the extraction prompt followed by the target (mlx-lm's chat dataset would otherwise render the template with thinking enabled). Dev provides the validation loss; the final adapter is used, fused into the weights. Training took {{lora_train_minutes}} min (peak {{lora_peak_gb}} GB).

## 4. Data

**Generator.** Fictional statements are drawn with a fixed seed (7): a fictional bank and client, 1-4 accounts (CHF, EUR, USD), 0-6 securities (Swiss dividends with 35 % withholding tax), a loan in 25 % of cases, language set by canton. Totals are computed by us and cross-checked by an independent recomputation and by OpenSteuerAuszug's verifier (MIT [16]); the XML follows eCH-0196 v2.2 [15]. 600 statements: German 255, French 199, Italian 146 (2 redrawn because the barcode encoder rejected their payload size).

**Layouts and degradations.** _Layout A_ is OpenSteuerAuszug's renderer: a 5-8 page PDF whose last pages carry the Macro-PDF417 barcodes; models only see page 1 (the summary), rendered at 200 dpi greyscale. _Layout B_ is our own one-page renderer (reportlab) with different typography, labels and number format, used in test only. _Degradation_ levels 1-3 simulate phone photos (perspective, rotation, shading, contrast, blur, noise, JPEG quality 85 down to 25), seeded per page; level 0 is the clean render.

**Oracle.** zxing-cpp reads the barcode segments of the clean PDF; segments are ordered, concatenated, zlib-decompressed and parsed. The decoded fields match the generator's values for all 600 statements (0 mismatches), and in all 720 documents (600 layout A, 120 layout B) the four displayed totals occur in the PDF text layer. **Gold is the value as displayed:** layout A prints three totals rounded to whole CHF (the withholding claim with 2 decimals); layout B prints 2 decimals.

**Splits** (by statement, PREREG):

| Split | Statements | Pages | Composition                                                              |
| ----- | ---------- | ----- | ------------------------------------------------------------------------ |
| Train | 420        | 420   | layout A, one random degradation level per page                          |
| Dev   | 60         | 60    | layout A, one random degradation level per page                          |
| Test  | 120        | 960   | layouts A and B × 4 levels for every statement (7,680 fields per system) |

**Licence and privacy.** All documents are fictional and contain no personal data; they are generated with MIT-licensed tools, and the official `taxstatement` jar is neither used nor redistributed. Generated data is released under CC0 ({{hf_dataset_url}}). `data/` (< 100 MB) holds `items.jsonl` (one row per page × field × system: prediction, gold, doubt features), `probe/{A,B}.npz` (PCA-256 projections, float16), the demo pages and the deduction rules; full activations are not in the repository.

## 5. Evaluation

**Protocol (PREREG.md).** Field-level exact match on test after normalisation (amounts as Decimal with 2 decimals; strings case-folded, whitespace collapsed). 95 % CIs: paired cluster bootstrap over the 120 test statements (10,000 resamples, seed 0) shared by all statistics; models are fit once, so CIs reflect test-sampling variability only. **H1:** fine-tuning raises accuracy (CI of the paired difference excludes 0). **H2:** the combined doubt score has a higher AUROC for "field is wrong" than every single signal. **H3:** the position-A probe has AUROC > 0.5 (CI lower bound > 0.5). **Baselines:** OCR + rules/regex without LLM, whose label patterns were written from layout-A train/dev pages (it knows only layout A); OCR + zero-shot Apertus; for doubt, minimum token probability, mean token entropy, d1-3B validation and the deterministic checks.

**Doubt study.** Doubt is studied on zero-shot outputs (primary), because LoRA outputs on training pages are overfit and contain few errors. Probe and combination are fit on train + dev and scored on test; the combination is a logistic regression over token statistics, d1 P(yes), check results and the out-of-fold probe score. For the fine-tuned system, a combination without the probe is calibrated on dev (secondary). Triage = share of fields a person re-reads, most doubtful first, to catch 80 / 90 / 95 % of wrong fields; a missing signal counts as maximal doubt.

**Table 1. Baseline vs Ours, extraction (test, 960 pages, 7,680 fields per system; 95 % CI).**

| Setup    | System                          | Field accuracy                                                    | Page fully correct | Layout A (seen)       | Layout B (unseen)     |
| -------- | ------------------------------- | ----------------------------------------------------------------- | ------------------ | --------------------- | --------------------- |
| Baseline | OCR + rules/regex (no LLM)      | {{acc_regex_test}} [{{acc_regex_test_lo}}, {{acc_regex_test_hi}}] | {{page_ok_regex}}  | {{acc_regex_layoutA}} | {{acc_regex_layoutB}} |
| Baseline | OCR + Apertus 1.5 8B, zero-shot | {{acc_base_test}} [{{acc_base_test_lo}}, {{acc_base_test_hi}}]    | {{page_ok_base}}   | {{acc_base_layoutA}}  | {{acc_base_layoutB}}  |
| **Ours** | OCR + Apertus 1.5 8B + LoRA     | {{acc_lora_test}} [{{acc_lora_test_lo}}, {{acc_lora_test_hi}}]    | {{page_ok_lora}}   | {{acc_lora_layoutA}}  | {{acc_lora_layoutB}}  |

**H1 ({{h1_verdict}}).** LoRA minus zero-shot: {{h1_diff}} [{{h1_ci_lo}}, {{h1_ci_hi}}] over {{h1_n_paired}} paired fields.

**Table 2. Doubt signals on zero-shot Apertus (test, {{n_wrong_base}} wrong of {{n_items_base}} fields): AUROC for "field is wrong" and share of fields to re-read to catch 80 / 90 / 95 % of errors.**

| Setup             | Signal                                                 | AUROC [95 % CI]                                                                  | 80 %                       | 90 %                       | 95 %                       |
| ----------------- | ------------------------------------------------------ | -------------------------------------------------------------------------------- | -------------------------- | -------------------------- | -------------------------- |
| Baseline          | Min token probability                                  | {{auroc_minprob}} [{{auroc_minprob_lo}}, {{auroc_minprob_hi}}]                   | {{triage80_minprob}}       | {{triage90_minprob}}       | {{triage95_minprob}}       |
| Baseline          | Mean token entropy                                     | {{auroc_entropy}} [{{auroc_entropy_lo}}, {{auroc_entropy_hi}}]                   | {{triage80_entropy}}       | {{triage90_entropy}}       | {{triage95_entropy}}       |
| Baseline          | d1-3B validation                                       | {{auroc_d1}} [{{auroc_d1_lo}}, {{auroc_d1_hi}}]                                  | {{triage80_d1}}            | {{triage90_d1}}            | {{triage95_d1}}            |
| Baseline          | Deterministic checks                                   | {{auroc_rules}} [{{auroc_rules_lo}}, {{auroc_rules_hi}}]                         | {{triage80_rules}}         | {{triage90_rules}}         | {{triage95_rules}}         |
| Ours (part)       | Probe, position A (layer {{probe_a_layer}})            | {{auroc_probeA}} [{{auroc_probeA_lo}}, {{auroc_probeA_hi}}]                      | {{triage80_probeA}}        | {{triage90_probeA}}        | {{triage95_probeA}}        |
| Ours (part)       | Probe, position B (layer {{probe_b_layer}})            | {{auroc_probeB}} [{{auroc_probeB_lo}}, {{auroc_probeB_hi}}]                      | {{triage80_probeB}}        | {{triage90_probeB}}        | {{triage95_probeB}}        |
| **Ours**          | **Combined: probe A + d1 + checks + token statistics** | {{auroc_combined}} [{{auroc_combined_lo}}, {{auroc_combined_hi}}]                | {{triage80_combined}}      | {{triage90_combined}}      | {{triage95_combined}}      |
| Ours, LoRA system | Combined without probe (fit on dev)                    | {{auroc_lora_combined}} [{{auroc_lora_combined_lo}}, {{auroc_lora_combined_hi}}] | {{triage80_lora_combined}} | {{triage90_lora_combined}} | {{triage95_lora_combined}} |

**H2 ({{h2_verdict}}).** Combined minus best single signal ({{h2_best_single}}): {{h2_diff}} [{{h2_ci_lo}}, {{h2_ci_hi}}]; "single" also covers mean token probability, first-token entropy and probe B (`data/results/table.md`). **H3 ({{h3_verdict}}).** Probe A: AUROC {{auroc_probeA}}, lower bound {{auroc_probeA_lo}}. Position B minus A: {{posb_minus_a_diff}} [{{posb_minus_a_lo}}, {{posb_minus_a_hi}}]. The fine-tuned system makes {{n_wrong_lora}} errors on test, so its triage figures have wide intervals.

![Figure 2](docs/triage_curves.png)
_Figure 2. Triage curves on zero-shot outputs: share of errors caught vs share of fields re-read, per doubt signal._

**Table 3. Breakdowns of field accuracy (test).**

| Group                       | Fields | Rules/regex           | Apertus zero-shot    | Apertus + LoRA       |
| --------------------------- | ------ | --------------------- | -------------------- | -------------------- |
| Degradation 0 (clean)       | 1,920  | {{acc_regex_d0}}      | {{acc_base_d0}}      | {{acc_lora_d0}}      |
| Degradation 1               | 1,920  | {{acc_regex_d1}}      | {{acc_base_d1}}      | {{acc_lora_d1}}      |
| Degradation 2               | 1,920  | {{acc_regex_d2}}      | {{acc_base_d2}}      | {{acc_lora_d2}}      |
| Degradation 3 (hard)        | 1,920  | {{acc_regex_d3}}      | {{acc_base_d3}}      | {{acc_lora_d3}}      |
| Layout A (seen in training) | 3,840  | {{acc_regex_layoutA}} | {{acc_base_layoutA}} | {{acc_lora_layoutA}} |
| Layout B (never seen)       | 3,840  | {{acc_regex_layoutB}} | {{acc_base_layoutB}} | {{acc_lora_layoutB}} |
| German                      | 3,328  | {{acc_regex_de}}      | {{acc_base_de}}      | {{acc_lora_de}}      |
| French                      | 3,008  | {{acc_regex_fr}}      | {{acc_base_fr}}      | {{acc_lora_fr}}      |
| Italian                     | 1,344  | {{acc_regex_it}}      | {{acc_base_it}}      | {{acc_lora_it}}      |

The rules baseline encodes layout A only; its layout-B column measures how much a hand-written extractor depends on one layout. Per-field accuracy and layout × degradation cells with CIs are in `data/results/` (Figure 3).

![Figure 3](docs/accuracy_by_degradation.png)
_Figure 3. Field accuracy by degradation level, per layout and system (95 % CI)._

**Table 4. Cost per page, Apple M4 Max 36 GB** (seconds over the pipeline runs; peak memory from our one-page smoke test).

| Stage         | Model, runtime                          | Mean s / page        | p95               | Peak memory               |
| ------------- | --------------------------------------- | -------------------- | ----------------- | ------------------------- |
| OCR           | LightOnOCR-3-1B, MPS bf16               | {{cost_ocr_mean}}    | {{cost_ocr_p95}}  | 3.1 GB                    |
| Extraction    | Apertus zero-shot, MLX bf16             | {{cost_base_mean}}   | {{cost_base_p95}} | {{mem_apertus_mlx_gb}} GB |
| Extraction    | Apertus + LoRA (fused), MLX bf16        | {{cost_lora_mean}}   | {{cost_lora_p95}} | same                      |
| Hidden states | Apertus, teacher-forced pass, 8 layers  | {{cost_hidden_mean}} | —                 | same                      |
| Judge         | d1-3B, MPS fp32, all fields in one pass | {{cost_d1_mean}}     | {{cost_d1_p95}}   | 14.1 GB                   |
| Rules/regex   | Python, CPU                             | {{cost_regex_mean}}  | —                 | —                         |

OCR dominates. The probe itself adds a 256-d projection and a dot product per field; its cost is the extra forward pass, which capturing states during generation would remove. The `make run` replay takes {{runtime_seconds}} s on CPU.

## 6. Limitations

- **Synthetic documents.** All pages are generated: one real-world renderer family (OpenSteuerAuszug) and one layout of our own. Layout B tests generalisation beyond a single layout, not to real bank statements; amounts, names and positions follow our own distributions.
- **Rounding as displayed.** Layout A prints totals rounded to whole CHF and gold is the displayed value: we measure reading, not recovery of the exact XML value.
- **The barcode makes the task moot when readable.** Where a clean barcode exists, a decoder suffices. Our position is to calibrate on barcode documents and deploy where the barcode is missing or damaged (scans, photos, pillar 3a and health-insurance documents); that target distribution differs from the evaluation and is not measured.
- **Doubt study.** The probe is trained on zero-shot errors; in the deployed LoRA configuration it must be refitted on the fine-tuned model's errors, which free barcode labels allow but we did not do in time. Bootstrap CIs ignore refitting variance; LoRA used one seed.
- **Pipeline choices.** Apertus reads OCR text, not the image (its native vision runs only in unmerged MLX forks). Router accuracy is not evaluated: the corpus has a single document type.
- **Licence.** d1-3B's LFM Open License 1.0 is not OSI-approved, and "revenue" is ambiguous for a public administration. An Apache-2.0 alternative (Cloudflare clef-flash) exists but was not evaluated.
- **No human study.** We have not tested whether triage and explanations help young adults or counsellors.
- **Demo.** Some demo pages come from the test split; they are shown for display only and nothing was tuned on them.

## 7. Reproducibility

**Replay (judges).** `make run` builds a `python:3.12-slim` image pinned by digest (numpy 2.4.6, scikit-learn 1.9.1, matplotlib 3.10.9). It reads `data/items.jsonl` and `data/probe/*.npz`, refits the probe and the combined model on train + dev, recomputes every test statistic with the bootstrap, writes `data/results/` (`results.json`, `table.md`, figures) and serves the console on `http://localhost:8000`. No GPU, no weights, no network. `make eval` runs the replay only.

**Live pipeline (Apple Silicon, outside Docker, which cannot use the Mac GPU).** Python 3.11 in `.venv` with torch 2.14.1, transformers 5.19.0, accelerate 1.15.0, sentence-transformers 6.1.0, mlx 0.32.3, mlx-lm 0.32.0, zxing-cpp 3.1.1, pypdfium2 5.14.0, reportlab 5.0.1, scikit-learn 1.9.1, and OpenSteuerAuszug at commit `eeb3b3d` (which pulls the `vroonhof/pdf417-py` fork, commit `44ce800`). d1-3B is pinned to revision `051bcc46` because it ships remote code; the other checkpoints are referenced by Hub ID ({{model_revisions}}).

```bash
make live    # generate 600 statements (seed 7) + OCR + Apertus zero-shot with hidden states, into work/
PY=.venv/bin/python; export PYTHONPATH=src
$PY -m ordner.pipeline.d1_batch --tag apertus-base
PY=$PY src/ordner/finetune/train.sh          # LoRA; model path in src/ordner/finetune/lora_config.yaml
$PY -m ordner.pipeline.extract_batch --tag apertus-lora --adapter work/adapters/lora-v1
$PY -m ordner.pipeline.d1_batch --tag apertus-lora
$PY -m ordner.eval.regex_baseline --work work
$PY -m ordner.eval.build_items --work work --data data && $PY -m ordner.eval.probe --work work --data data
make run
```

**Seeds and checks.** Generator 7, degradations keyed by page identifier, LoRA 7, PCA 0, bootstrap 0, deterministic grouped folds. Self-checks (`ordner.gen.selfcheck`, `ordner.eval.selfcheck`, `ordner.eval.metrics`, `ordner.eval.rules`) assert generator determinism, the oracle round trip and the metric definitions. `PREREG.md` was frozen before the first test run; deviations: {{prereg_deviations}}.

## 8. Next steps

- QR-bills (SIX v2.3; the QR payload is the oracle) and health-insurance premium letters checked against FOPH open premium data.
- A conformal threshold turning triage into a guarantee ("at most x % undetected errors") [3, 12].
- Probe refitted on the fine-tuned model's errors; hidden states captured during generation.
- Real layouts: consented, anonymised statements from counselling services, labelled for free by their barcodes.
- Apertus's native vision once merged upstream, compared with the OCR cascade.
- A user study with young adults and counsellors.

## License

Creative Commons Attribution 4.0 (CC-BY-4.0). All HackApertus projects are open-sourced.

**Third-party components.** Models: Apertus 1.5 8B (Apache-2.0), LightOnOCR-3-1B (Apache-2.0), EmbeddingGemma 2 (Apache-2.0), d1-3B (LFM Open License 1.0, not OSI). Data generation: OpenSteuerAuszug (MIT), pdf417gen fork (MIT), python-barcode (MIT), reportlab (BSD), pypdfium2 (BSD-3-Clause / Apache-2.0), zxing-cpp (Apache-2.0), swiss-qr-bill / `qrbill` (MIT; installed for the QR-bill extension, not used in the evaluated pipeline). Learning and inference: mlx and mlx-lm (MIT), transformers and sentence-transformers (Apache-2.0), torch (BSD-style), scikit-learn (BSD-3-Clause), numpy (BSD-3-Clause), matplotlib (PSF-based), Pillow (MIT-CMU). Docker base image `python:3.12-slim`.

**Declarations.** Code was written with an AI coding assistant (Claude Code); the authors reviewed and ran all of it, and the assistant produced no data or labels. No closed model generated training data or labels. The console server, the Makefile/Docker layout and the `LLM_*` variable convention are adapted from our own LPD Navigator prototype (Apache-2.0), written on 12.10.2026 within the hackathon window (1-16.10.2026). Third-party code is used only as installed libraries.

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

## Placeholders (fill, then delete this section before PDF export)

130 placeholders in the text above: 116 come from `data/results/results.json` (written by `make run` / `python -m ordner.eval.run`) and 14 are filled by hand. Formats: `%` = multiply by 100, one decimal, no % sign inside table cells that already say %; "percentage points" = multiply by 100, signed, one decimal.

| Placeholder                  | JSON path in `data/results/results.json`                      | Format                                      |
| ---------------------------- | ------------------------------------------------------------- | ------------------------------------------- |
| `{{acc_base_d0}}`            | `breakdown["apertus-base"].degradation["0"].acc`              | %                                           |
| `{{acc_base_d1}}`            | `breakdown["apertus-base"].degradation["1"].acc`              | %                                           |
| `{{acc_base_d2}}`            | `breakdown["apertus-base"].degradation["2"].acc`              | %                                           |
| `{{acc_base_d3}}`            | `breakdown["apertus-base"].degradation["3"].acc`              | %                                           |
| `{{acc_base_de}}`            | `breakdown["apertus-base"].language["de"].acc`                | %                                           |
| `{{acc_base_fr}}`            | `breakdown["apertus-base"].language["fr"].acc`                | %                                           |
| `{{acc_base_it}}`            | `breakdown["apertus-base"].language["it"].acc`                | %                                           |
| `{{acc_base_layoutA}}`       | `breakdown["apertus-base"].layout["A"].acc`                   | %                                           |
| `{{acc_base_layoutB}}`       | `breakdown["apertus-base"].layout["B"].acc`                   | %                                           |
| `{{acc_base_test}}`          | `accuracy["apertus-base"].acc`                                | %                                           |
| `{{acc_base_test_hi}}`       | `accuracy["apertus-base"].ci[1]`                              | %                                           |
| `{{acc_base_test_lo}}`       | `accuracy["apertus-base"].ci[0]`                              | %                                           |
| `{{acc_lora_d0}}`            | `breakdown["apertus-lora"].degradation["0"].acc`              | %                                           |
| `{{acc_lora_d1}}`            | `breakdown["apertus-lora"].degradation["1"].acc`              | %                                           |
| `{{acc_lora_d2}}`            | `breakdown["apertus-lora"].degradation["2"].acc`              | %                                           |
| `{{acc_lora_d3}}`            | `breakdown["apertus-lora"].degradation["3"].acc`              | %                                           |
| `{{acc_lora_de}}`            | `breakdown["apertus-lora"].language["de"].acc`                | %                                           |
| `{{acc_lora_fr}}`            | `breakdown["apertus-lora"].language["fr"].acc`                | %                                           |
| `{{acc_lora_it}}`            | `breakdown["apertus-lora"].language["it"].acc`                | %                                           |
| `{{acc_lora_layoutA}}`       | `breakdown["apertus-lora"].layout["A"].acc`                   | %                                           |
| `{{acc_lora_layoutB}}`       | `breakdown["apertus-lora"].layout["B"].acc`                   | %                                           |
| `{{acc_lora_test}}`          | `accuracy["apertus-lora"].acc`                                | %                                           |
| `{{acc_lora_test_hi}}`       | `accuracy["apertus-lora"].ci[1]`                              | %                                           |
| `{{acc_lora_test_lo}}`       | `accuracy["apertus-lora"].ci[0]`                              | %                                           |
| `{{acc_regex_d0}}`           | `breakdown["regex"].degradation["0"].acc`                     | %                                           |
| `{{acc_regex_d1}}`           | `breakdown["regex"].degradation["1"].acc`                     | %                                           |
| `{{acc_regex_d2}}`           | `breakdown["regex"].degradation["2"].acc`                     | %                                           |
| `{{acc_regex_d3}}`           | `breakdown["regex"].degradation["3"].acc`                     | %                                           |
| `{{acc_regex_de}}`           | `breakdown["regex"].language["de"].acc`                       | %                                           |
| `{{acc_regex_fr}}`           | `breakdown["regex"].language["fr"].acc`                       | %                                           |
| `{{acc_regex_it}}`           | `breakdown["regex"].language["it"].acc`                       | %                                           |
| `{{acc_regex_layoutA}}`      | `breakdown["regex"].layout["A"].acc`                          | %                                           |
| `{{acc_regex_layoutB}}`      | `breakdown["regex"].layout["B"].acc`                          | %                                           |
| `{{acc_regex_test}}`         | `accuracy["regex"].acc`                                       | %                                           |
| `{{acc_regex_test_hi}}`      | `accuracy["regex"].ci[1]`                                     | %                                           |
| `{{acc_regex_test_lo}}`      | `accuracy["regex"].ci[0]`                                     | %                                           |
| `{{auroc_combined}}`         | `doubt["apertus-base"]["combined"].auroc`                     | 3 decimals                                  |
| `{{auroc_combined_hi}}`      | `doubt["apertus-base"]["combined"].ci[1]`                     | 3 decimals                                  |
| `{{auroc_combined_lo}}`      | `doubt["apertus-base"]["combined"].ci[0]`                     | 3 decimals                                  |
| `{{auroc_d1}}`               | `doubt["apertus-base"]["d1 validation"].auroc`                | 3 decimals                                  |
| `{{auroc_d1_hi}}`            | `doubt["apertus-base"]["d1 validation"].ci[1]`                | 3 decimals                                  |
| `{{auroc_d1_lo}}`            | `doubt["apertus-base"]["d1 validation"].ci[0]`                | 3 decimals                                  |
| `{{auroc_entropy}}`          | `doubt["apertus-base"]["mean entropy"].auroc`                 | 3 decimals                                  |
| `{{auroc_entropy_hi}}`       | `doubt["apertus-base"]["mean entropy"].ci[1]`                 | 3 decimals                                  |
| `{{auroc_entropy_lo}}`       | `doubt["apertus-base"]["mean entropy"].ci[0]`                 | 3 decimals                                  |
| `{{auroc_lora_combined}}`    | `doubt["apertus-lora"]["combined (no probe)"].auroc`          | 3 decimals                                  |
| `{{auroc_lora_combined_hi}}` | `doubt["apertus-lora"]["combined (no probe)"].ci[1]`          | 3 decimals                                  |
| `{{auroc_lora_combined_lo}}` | `doubt["apertus-lora"]["combined (no probe)"].ci[0]`          | 3 decimals                                  |
| `{{auroc_minprob}}`          | `doubt["apertus-base"]["min token prob"].auroc`               | 3 decimals                                  |
| `{{auroc_minprob_hi}}`       | `doubt["apertus-base"]["min token prob"].ci[1]`               | 3 decimals                                  |
| `{{auroc_minprob_lo}}`       | `doubt["apertus-base"]["min token prob"].ci[0]`               | 3 decimals                                  |
| `{{auroc_probeA}}`           | `doubt["apertus-base"]["probe A"].auroc`                      | 3 decimals                                  |
| `{{auroc_probeA_hi}}`        | `doubt["apertus-base"]["probe A"].ci[1]`                      | 3 decimals                                  |
| `{{auroc_probeA_lo}}`        | `doubt["apertus-base"]["probe A"].ci[0]`                      | 3 decimals                                  |
| `{{auroc_probeB}}`           | `doubt["apertus-base"]["probe B"].auroc`                      | 3 decimals                                  |
| `{{auroc_probeB_hi}}`        | `doubt["apertus-base"]["probe B"].ci[1]`                      | 3 decimals                                  |
| `{{auroc_probeB_lo}}`        | `doubt["apertus-base"]["probe B"].ci[0]`                      | 3 decimals                                  |
| `{{auroc_rules}}`            | `doubt["apertus-base"]["rules"].auroc`                        | 3 decimals                                  |
| `{{auroc_rules_hi}}`         | `doubt["apertus-base"]["rules"].ci[1]`                        | 3 decimals                                  |
| `{{auroc_rules_lo}}`         | `doubt["apertus-base"]["rules"].ci[0]`                        | 3 decimals                                  |
| `{{cost_base_mean}}`         | `costs.stages["apertus-base"].mean`                           | seconds, 1 decimal                          |
| `{{cost_base_p95}}`          | `costs.stages["apertus-base"].p95`                            | seconds, 1 decimal                          |
| `{{cost_d1_mean}}`           | `costs.stages["d1 (apertus-base)"].mean`                      | seconds, 1 decimal                          |
| `{{cost_d1_p95}}`            | `costs.stages["d1 (apertus-base)"].p95`                       | seconds, 1 decimal                          |
| `{{cost_lora_mean}}`         | `costs.stages["apertus-lora"].mean`                           | seconds, 1 decimal                          |
| `{{cost_lora_p95}}`          | `costs.stages["apertus-lora"].p95`                            | seconds, 1 decimal                          |
| `{{cost_ocr_mean}}`          | `costs.stages["ocr"].mean`                                    | seconds, 1 decimal                          |
| `{{cost_ocr_p95}}`           | `costs.stages["ocr"].p95`                                     | seconds, 1 decimal                          |
| `{{cost_regex_mean}}`        | `costs.stages["regex"].mean`                                  | seconds, 1 decimal                          |
| `{{h1_ci_hi}}`               | `h1.ci[1]`                                                    | percentage points, signed                   |
| `{{h1_ci_lo}}`               | `h1.ci[0]`                                                    | percentage points, signed                   |
| `{{h1_diff}}`                | `h1.diff`                                                     | percentage points, signed                   |
| `{{h1_n_paired}}`            | `h1.n_items_paired`                                           | integer                                     |
| `{{h1_verdict}}`             | `h1.supported`                                                | true → "supported", false → "not supported" |
| `{{h2_best_single}}`         | `h2.best_single`                                              | text                                        |
| `{{h2_ci_hi}}`               | `h2.ci[1]`                                                    | 3 decimals, signed                          |
| `{{h2_ci_lo}}`               | `h2.ci[0]`                                                    | 3 decimals, signed                          |
| `{{h2_diff}}`                | `h2.diff`                                                     | 3 decimals, signed                          |
| `{{h2_verdict}}`             | `h2.supported`                                                | true → "supported", false → "not supported" |
| `{{h3_verdict}}`             | `h3.supported`                                                | true → "supported", false → "not supported" |
| `{{n_items_base}}`           | `doubt["apertus-base"]["_n"].items`                           | integer, thousands separator                |
| `{{n_wrong_base}}`           | `doubt["apertus-base"]["_n"].wrong`                           | integer                                     |
| `{{n_wrong_lora}}`           | `doubt["apertus-lora"]["_n"].wrong`                           | integer                                     |
| `{{page_ok_base}}`           | `accuracy["apertus-base"].page_all_ok`                        | %                                           |
| `{{page_ok_lora}}`           | `accuracy["apertus-lora"].page_all_ok`                        | %                                           |
| `{{page_ok_regex}}`          | `accuracy["regex"].page_all_ok`                               | %                                           |
| `{{posb_minus_a_diff}}`      | `position_b_vs_a.diff`                                        | 3 decimals, signed                          |
| `{{posb_minus_a_hi}}`        | `position_b_vs_a.ci[1]`                                       | 3 decimals, signed                          |
| `{{posb_minus_a_lo}}`        | `position_b_vs_a.ci[0]`                                       | 3 decimals, signed                          |
| `{{probe_a_layer}}`          | `probe.A.layer`                                               | integer                                     |
| `{{probe_b_layer}}`          | `probe.B.layer`                                               | integer                                     |
| `{{runtime_seconds}}`        | `runtime_seconds`                                             | seconds, integer                            |
| `{{triage80_combined}}`      | `doubt["apertus-base"]["combined"].triage["0.8"]`             | %                                           |
| `{{triage80_d1}}`            | `doubt["apertus-base"]["d1 validation"].triage["0.8"]`        | %                                           |
| `{{triage80_entropy}}`       | `doubt["apertus-base"]["mean entropy"].triage["0.8"]`         | %                                           |
| `{{triage80_lora_combined}}` | `doubt["apertus-lora"]["combined (no probe)"].triage["0.8"]`  | %                                           |
| `{{triage80_minprob}}`       | `doubt["apertus-base"]["min token prob"].triage["0.8"]`       | %                                           |
| `{{triage80_probeA}}`        | `doubt["apertus-base"]["probe A"].triage["0.8"]`              | %                                           |
| `{{triage80_probeB}}`        | `doubt["apertus-base"]["probe B"].triage["0.8"]`              | %                                           |
| `{{triage80_rules}}`         | `doubt["apertus-base"]["rules"].triage["0.8"]`                | %                                           |
| `{{triage90_combined}}`      | `doubt["apertus-base"]["combined"].triage["0.9"]`             | %                                           |
| `{{triage90_d1}}`            | `doubt["apertus-base"]["d1 validation"].triage["0.9"]`        | %                                           |
| `{{triage90_entropy}}`       | `doubt["apertus-base"]["mean entropy"].triage["0.9"]`         | %                                           |
| `{{triage90_lora_combined}}` | `doubt["apertus-lora"]["combined (no probe)"].triage["0.9"]`  | %                                           |
| `{{triage90_minprob}}`       | `doubt["apertus-base"]["min token prob"].triage["0.9"]`       | %                                           |
| `{{triage90_probeA}}`        | `doubt["apertus-base"]["probe A"].triage["0.9"]`              | %                                           |
| `{{triage90_probeB}}`        | `doubt["apertus-base"]["probe B"].triage["0.9"]`              | %                                           |
| `{{triage90_rules}}`         | `doubt["apertus-base"]["rules"].triage["0.9"]`                | %                                           |
| `{{triage95_combined}}`      | `doubt["apertus-base"]["combined"].triage["0.95"]`            | %                                           |
| `{{triage95_d1}}`            | `doubt["apertus-base"]["d1 validation"].triage["0.95"]`       | %                                           |
| `{{triage95_entropy}}`       | `doubt["apertus-base"]["mean entropy"].triage["0.95"]`        | %                                           |
| `{{triage95_lora_combined}}` | `doubt["apertus-lora"]["combined (no probe)"].triage["0.95"]` | %                                           |
| `{{triage95_minprob}}`       | `doubt["apertus-base"]["min token prob"].triage["0.95"]`      | %                                           |
| `{{triage95_probeA}}`        | `doubt["apertus-base"]["probe A"].triage["0.95"]`             | %                                           |
| `{{triage95_probeB}}`        | `doubt["apertus-base"]["probe B"].triage["0.95"]`             | %                                           |
| `{{triage95_rules}}`         | `doubt["apertus-base"]["rules"].triage["0.95"]`               | %                                           |

**Filled by hand (not in `results.json`):**

| Placeholder                  | Source                                                                                                                      |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| `{{commit}}`                 | commit hash of the submission                                                                                               |
| `{{cost_hidden_mean}}`       | mean of seconds_hidden in work/extract.apertus-base.jsonl (not aggregated in costs.json)                                    |
| `{{explanation_provenance}}` | how the demo explanations were produced (e.g. "generated by Apertus offline, quotes checked verbatim" or "written by hand") |
| `{{hf_dataset_url}}`         | Hugging Face dataset URL (or remove the parenthesis)                                                                        |
| `{{lora_peak_gb}}`           | peak memory printed by finetune/train.py                                                                                    |
| `{{lora_train_minutes}}`     | wall time of finetune/train.py                                                                                              |
| `{{mem_apertus_mlx_gb}}`     | peak MLX memory during extraction (not measured by the pipeline)                                                            |
| `{{members}}`                | member names                                                                                                                |
| `{{model_revisions}}`        | Hub commit hashes of Apertus, LightOnOCR-3 and EmbeddingGemma 2                                                             |
| `{{prereg_commit}}`          | commit that adds "FROZEN" to PREREG.md                                                                                      |
| `{{prereg_deviations}}`      | deviations from PREREG.md after freezing, or "none"                                                                         |
| `{{repo_url}}`               | public repository URL                                                                                                       |
| `{{team_name}}`              | team name                                                                                                                   |
| `{{video_url}}`              | demo video URL                                                                                                              |

Also copy `data/results/triage_curves.png` and `data/results/accuracy_by_degradation.png` to `docs/` after the frozen run (Figures 2-3).
