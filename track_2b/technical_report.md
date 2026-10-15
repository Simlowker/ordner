# Technical report — Ordner

**Ordner is a local, sovereign assistant for Swiss paperwork: it knows which administrative procedures concern a person, what is missing, what to do and why, and prepares everything; it never sends, files, signs or pays.**

- **Track:** Track 2B — Own Project
- **Event:** Online
- **Team:** `Meotis` — {{members}}
- **Demo:** {{video_url}}
- **Code:** {{repo_url}}, commit `{{commit}}`; `PREREG.md` frozen in commit `f52d2c3` before any model was scored on the test split (deviations: its Addendum 4 and §6)

## 1. Summary

Ordner keeps a person's administrative dossier on their own hardware: it reads their papers, works out which of 18 Swiss procedures apply (tax return, health insurance, debt collection, pension, moving, …), computes deadlines from official rules, says what is missing and why, and prepares letters, document requests and payments for the person to validate. Apertus 1.5 8B is its only general-purpose language model. Tested configuration: Apertus served on a Mac Studio M4 Max 36 GB, clients and UI on a second Mac over the local network; nothing leaves the LAN at run time.

**Proof 1: reading documents and flagging most errors.** eCH-0196 bank tax statements carry their data in PDF417 barcodes: a free, exact answer key. On 1,200 frozen test pages (two of three layouts unseen in training), field exact match is 66.9 % for OCR + rules, 92.1 % for zero-shot Apertus and 98.0 % with LoRA (96.9 % on unseen layouts; H1 supported). A probe on Apertus hidden states detects errors (AUROC 0.840; H3 supported), but a free signal, first-token entropy, is best (0.947; re-reading 19.3 % of fields catches 90 % of zero-shot errors); our pre-registered combination is significantly worse (0.922, 30.5 %; H2 not supported). Up to 75 of 754 errors stay unflagged at that budget.

**Proof 2: process tools make Apertus 8B a usable component, not a replacement for rules.** On 24 frozen test scenarios, one tool per procedure instead of generic tools lifts Apertus from 3 to 12 passed scenarios (12.5 → 50.0 %; exact deadlines 1 → 12 of 20; McNemar p = 0.004; H6 supported), still below the rules engine alone (13, 54.2 %). Rules first, then Apertus, defined after the dev results, passes 14 (58.3 %; vs rules p = 1, not significant) and asks 2 of 4 questions the rules cannot. Distillation did not help (H7 not supported). No run executed an effect; on dev, one hybrid run prepared an action carrying a phishing e-mail's IBAN.

**Motivation.** A tax file is sensitive data (art. 5 lit. c nLPD [17]), yet the AI tax assistants we found are cloud services without published evaluation [18], and scanning damages the barcodes, so VaudTax cannot import a scanned statement [19]: the skill is reading the page.

**Contributions.** (1) **The document grades itself:** its barcode labels extraction from the readable page exactly, with no annotator or closed model (untested on real statements). (2) **A pre-registered doubt study inside an open model**, whose fusion hypothesis failed. (3) **A measured coordinator architecture for an 8B model** on one prepare-only suite, with exact counts and run-to-run noise. (4) **Replay** in Docker without GPU, weights or network.

**Related work.** Hidden-state probes detect hallucinated entities [6, 7] and have been fused with entropy [1]; document confidence has been split into channels [3], OCR self-verified by model agreement [5], judges given guarantees [2] and errors bounded by checks [4]; selective prediction is evaluated by risk-coverage [13], and OCR-then-LLM cascades remain strong [14].

## 2. Architecture

```
documents ─► READ: barcode first (eCH-0196, QR-bill); else OCR + Apertus + doubt signals
               │ facts enter as "proposed"; only the person confirms them
               ▼
DOSSIER      local SQLite, append-only events: documents · facts · cases · deadlines · actions
               │
   1. RULES ENGINE (no model)                 2. APERTUS COORDINATOR (same dossier, ≤ 12 steps)
   18 procedure cards, 227 official sources   free text, missing information, questions;
   quoted verbatim: applicability, deadlines, process toolset (9) + ask_user + prepare_action
   completeness, phishing and double-payment guards
               └─────────────────┬──────────────────┘
                                 ▼
COCKPIT      what concerns me · what is missing · next step · why (quoted) ─► the person acts
```

_Figure 1. Ordner. Steps 1 then 2 form the "hybrid" of §5._

**Deterministic core.** Model-read facts stay `proposed` until the person confirms them. 18 procedure cards (16 qualified, 2 draft) cite 227 official sources whose quotes code verifies verbatim. The rules engine computes applicability, deadlines (debt-collection holidays, reception-by dates, cantonal tables), completeness, a phishing flag (unseen IBAN or creditor, urgent link) and, since the dev run of §5, a double-payment guard. Actions enter as `prepared`; no tool has a side effect.

**Coordinator.** A Python loop parses Apertus's native tool calls, pins the subject, hides person-only operations, strips instruction-like text from tool outputs, flags dates no tool returned and attaches the phishing warning to payments it prepares. The _generic_ toolset has 11 tools; the _process_ toolset has one tool per procedure family (document intake, tax return, LAMal deductible, payment order, moving) plus knowledge search, rules evaluation and case load/record (9). The **hybrid** runs the rules engine, then the coordinator (process) on the same dossier. DeepSeek Harness [20] optionally replaces our loop and serves the console's conversation.

**Reading (Proof 1).** LightOnOCR-3 turns the page into text; Apertus writes eight fields as JSON. Doubt signals per field: token statistics, linear probes on hidden states, d1-3B's P(yes) for "is this the value shown?", deterministic checks (non-negative amounts, withholding claim = 35 % of revenue A, value present in the OCR text, totals, canton, tax year) and their pre-registered logistic combination. **Explanations** quote official passages retrieved by EmbeddingGemma 2; code removes every quote not found verbatim.

| Component                                                            | Role                                                                                   | Licence                                                                                | Runtime             |
| -------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ------------------- |
| **Apertus 1.5 8B** [9]                                               | extraction, probe, coordinator, experts, explanations                                  | Apache-2.0                                                                             | MLX, bf16           |
| LightOnOCR-3-1B [11]                                                 | page image → text                                                                      | Apache-2.0                                                                             | MPS, bf16           |
| LiquidAI d1-3B [10]                                                  | doubt judge (fp32: bf16 creates ties); expert routing (bf16)                           | **LFM Open License 1.0, not OSI-approved** (commercial use capped at USD 10 M revenue) | MPS                 |
| EmbeddingGemma 2 [11]                                                | knowledge search, explanations, routing fallback                                       | Apache-2.0                                                                             | bf16; BM25 fallback |
| zxing-cpp                                                            | barcode decoding (oracle)                                                              | Apache-2.0                                                                             | CPU                 |
| DeepSeek Harness 0.2.1-alpha.2 (npm) and our UI fork `harness_fork/` | optional runtime (H8), conversation UI; in the Docker image if its build step succeeds | MIT                                                                                    | Node ≥ 22.19        |
| GLM-5.3                                                              | **development only:** distillation teacher, fictional scenarios                        | not verified                                                                           | OpenRouter API      |

### Target architecture (mandatory)

**b) Air-gapped** (primary) and **a) on-premise** (e.g. a debt-counselling office); **c)** is not targeted. **Run time:** no external service (local weights, no API key, CSP `default-src 'self'`, harness telemetry off). **Build time:** weights, Python and npm packages, pinned base images, corpus PDFs. **Development only:** GLM-5.3 through OpenRouter (a foreign service) on fictional scenarios. Tested on two Macs on a LAN (§1), Apertus and d1-3B loaded one at a time; no end-to-end run with the network cut.

## 3. Use of Apertus

- **Model:** `swiss-ai/Apertus-v1.5-8B`, text backbone exported as `andreasmartin/apertus-v1.5-8b-text` (Apache-2.0), revision `c0e7eeb`
- **How it is used:** inference (extraction, tool coordination, explanations); fine-tuning (LoRA for extraction; QLoRA for a distilled coordinator and four domain experts); white-box evaluation (doubt probe)
- **Where it runs:** local weights, MLX / mlx-lm, bf16, Mac Studio M4 Max 36 GB

**Extraction and probe.** Greedy, thinking off; a missing or unparseable value is wrong. A teacher-forced pass reads the residual stream after layers 4, 8, …, 32 (float32: norms grow about a thousandfold with depth [8]); per field we keep position A (mean over the value's tokens) and B (the token before it), standardise and project on a 256-d PCA; the probe's layer and regularisation are chosen by statement-grouped cross-validation on train + dev. **LoRA:** mlx-lm, rank 16, scale 2, all 32 blocks, learning rate 10⁻⁴, batch 2, 2 epochs, seed 7. **Coordinator:** thinking off, temperature 0, at most 12 model calls per goal, one toolset-neutral prompt; a malformed tool call is an error, never the answer. **Distillation:** GLM-5.3 ran the same loop on 400 seeded variants of dev scenarios (outcomes recomputed by the rules engine): 234 passed with process tools (58.5 %), 105 with generic tools (26.3 %); a strict filter kept 113 trajectories. bf16 LoRA ran out of memory at 8k-token turns, so we trained QLoRA (last 16 layers of a 4-bit copy) and serve it on the bf16 base.

## 4. Data

**Tax statements (Proof 1).** 600 fictional statements (seed 7; German 255, French 199, Italian 146), totals checked by recomputation and OpenSteuerAuszug's verifier (MIT [16]), XML per eCH-0196 v2.2 [15]. Layout A is OpenSteuerAuszug's renderer; B (compact table) and C (bank letter, distractor subtotals) are ours, test only. Degradations 1-3 simulate phone photos. The decoded barcodes match the generator for all 600 statements; gold is the value as displayed. Train 420 and dev 60 pages (layout A); test 120 statements, 1,200 pages (A and B × 4 levels, C × 2).

**Scenarios (Proof 2).** 76 scenarios (`data/scenarios/`): a fictional persona, dossier, events and goal, sometimes in phases, with expected procedures, traps (including a prompt-injection e-mail), questions, deadlines with the official text that fixes them, actions and forbidden actions. The team wrote them with an AI coding assistant; nobody outside the team reviewed them. 67 (9 `needs_review` excluded) are split by a fixed hash seed into 43 dev and 24 test. **Retrieval:** 2 × 36 questions (fr/de/it), half held out. All data is fictional, CDLA-Permissive-2.0, 39 MB.

## 5. Evaluation

### Proof 1: extraction and doubt

**Protocol (PREREG.md).** Field exact match after normalisation; 95 % CIs by paired cluster bootstrap over the 120 test statements. **H1:** LoRA beats zero-shot. **H2:** the combined doubt score has a higher AUROC for "field is wrong" than every single signal. **H3:** probe A has AUROC > 0.5. Doubt is fit on zero-shot outputs of train + dev (221 errors in 3,840 layout-A fields). On dev (layout A, for which the regex was written), OCR + regex reaches 0.992, zero-shot Apertus 0.938.

**Table 1. Baseline vs Ours, extraction (test, 1,200 pages, 9,600 fields per system; field accuracy %, 95 % CI).**

| Setup    | System                          | Field accuracy    | Page fully correct | Seen layout (A) | Unseen layouts (B, C) |
| -------- | ------------------------------- | ----------------- | ------------------ | --------------- | --------------------- |
| Baseline | OCR + rules/regex (no LLM)      | 66.9 [65.8, 68.0] | 37.9               | 99.0            | 45.5                  |
| Baseline | OCR + Apertus 1.5 8B, zero-shot | 92.1 [91.4, 92.8] | 54.5               | 94.2            | 90.8                  |
| **Ours** | OCR + Apertus 1.5 8B + LoRA     | 98.0 [97.7, 98.3] | 88.3               | 99.7            | 96.9                  |

**H1 (supported).** LoRA minus zero-shot: +5.9 points [+5.2, +6.6] over 9,600 paired fields. Layout C (bank letter) stays at 90.8 % with LoRA (B: 100.0 %).

**Table 2. Baseline vs Ours, doubt signals on zero-shot Apertus (test, 754 wrong of 9,600 fields): AUROC for "field is wrong", within-field AUROC, % of fields re-read to catch 90 % of errors. Best in bold.**

| Setup    | Signal                                             | AUROC [95 % CI]          | Within field | Re-read for 90 % |
| -------- | -------------------------------------------------- | ------------------------ | ------------ | ---------------- |
| Baseline | Field prior P(wrong \| field)                      | 0.621 [0.602, 0.638]     | 0.5          | 70.6             |
| Baseline | Min token probability                              | 0.917 [0.905, 0.928]     | 0.872        | 27.4             |
| Baseline | Mean token entropy                                 | 0.924 [0.913, 0.934]     | 0.887        | 27.8             |
| Baseline | **First-token entropy**                            | **0.947 [0.932, 0.960]** | **0.916**    | **19.3**         |
| Baseline | d1-3B validation                                   | 0.897 [0.877, 0.915]     | 0.815        | 35.6             |
| Baseline | Deterministic checks                               | 0.815 [0.791, 0.838]     | 0.814        | 73.0             |
| Ours     | Probe, position A (layer 12)                       | 0.840 [0.814, 0.863]     | 0.858        | 57.1             |
| Ours     | Probe, position B (layer 20)                       | 0.889 [0.871, 0.906]     | 0.904        | 37.9             |
| Ours     | Combined (pre-registered): rows above except probe B, plus mean token probability | 0.922 [0.904, 0.938]     | 0.911        | 30.5             |

**H2 (not supported, reversed).** Combined minus first-token entropy: −0.024 [−0.048, −0.001]; fit on 221 layout-A errors (cross-validated AUROC 0.996), the combination does worse on test than one of its own free inputs, likely over-fitting. **H3 (supported).** Probe A: 0.840, lower bound 0.814; position B is better (+0.049 [+0.020, +0.079]); both stay below the token statistics, and the within-field test AUROC (0.858) shows the drop from cross-validation (0.996, best of 32 grid cells) is not just field identity. **Silent errors.** At the 90 % budget, up to 75 of 754 errors stay unflagged; on demo page `s0003-B` (test) zero-shot Apertus reads `totalTaxValue` 9.03 instead of 23,805.62 with combined doubt 0.002. For LoRA, the pre-registered dev calibration is not estimable (2 errors in 480 dev fields; 190 on test); one LoRA output (`s0586-A`: 1,962,279,958,001,002 instead of 21,274) passes every check because its digits occur in the OCR text, and alone sets the mean CHF error in `data/results/table.md` (breakdowns there).

**Explanations (not evaluated at scale).** The planned evaluation on 30 dev pages did not complete (server error); the 4 demo explanations, generated by Apertus, kept 6 verbatim quotes and removed 3, and contain the errors listed in §6.

### Proof 2: coordinator architecture

**Protocol (PREREG addenda 1-4).** Each scenario runs on a fresh dossier and passes when all its checks pass; specialist models are replayed; Apertus bf16 is served by `mlx_lm.server`. **H4:** more missing-information questions than rules alone, without more wrong triggers; **H5:** no forbidden action prepared on test; **H6:** process beat generic tools on deadlines and obligations; **H7:** the distilled adapter beats the untrained coordinator; **H8:** the harness is adopted only if not worse than our loop. **Caveats:** cards and scenarios were written together and the rules engine reads the procedure label the author attached to events, so rules-only is not an independent baseline; metrics are recall-oriented, which favours a union such as the hybrid; process tools return code-computed deadlines, so H6 tests whether the model calls the right tool with the right arguments.

**Table 3. Scenario suite, dev split (43 scenarios; counts).**

| System                                       | Pass /43                | Obligations /39 | Missing info /7 | Deadlines /30 | Forbidden prepared |
| -------------------------------------------- | ----------------------- | --------------- | --------------- | ------------- | ------------------ |
| Rules engine only, no model                  | 20 (46.5 %)             | 30              | 0               | 15            | 0                  |
| Apertus, generic tools                       | 6 (14.0 %)              | 13              | 3               | 3             | 0                  |
| Apertus, process tools, run 1 / run 2        | 12 / 13 (27.9 / 30.2 %) | 23 / 22         | 5 / 3           | 9 / 10        | 0                  |
| Same, DeepSeek Harness runtime               | 10 (23.3 %)             | 23              | 5               | 11            | 0                  |
| Same as process, distilled adapter           | 7 (16.3 %)              | 19              | 6               | 9             | 0                  |
| Hybrid (post-hoc), run 1 / re-run with guard | 23 / 23 (53.5 %)        | 31 / 31         | 5 / 4           | 16 / 16       | 2 / 1              |

Two identical process runs disagree on 5 of 43 verdicts, so dev gaps below about 12 points are not evidence (hybrid vs rules: McNemar 4–1, p = 0.375). The hybrid's forbidden actions: in run 1, two pending payments for one bill received twice (the guard was added afterwards); in the re-run, one action in `tax-be-03` contained the IBAN of an injected phishing e-mail, and the final answer told the person to pay it. Nothing was executed.

**Table 4. Baseline vs Ours, scenario suite, test split (24 scenarios, one run per system; counts).**

| Setup    | System                                | Pass /24        | Obligations /22 | Missing info /4 | Deadlines /20 | Actions /14 | Forbidden / executed |
| -------- | ------------------------------------- | --------------- | --------------- | --------------- | ------------- | ----------- | -------------------- |
| Baseline | Rules engine only, no model           | 13 (54.2 %)     | 17              | 0               | 13            | 10          | 0 / 0                |
| Baseline | Apertus, generic tools                | 3 (12.5 %)      | 6               | 3               | 1             | 2           | 0 / 0                |
| **Ours** | **Apertus, process tools**            | **12 (50.0 %)** | **15**          | **2**           | **12**        | **7**       | **0 / 0**            |
| Ours     | Same + distilled adapter              | 10 (41.7 %)     | 16              | 4               | 11            | 6           | 0 / 0                |
| Runtime  | Process tools, DeepSeek Harness       | 9 (37.5 %)      | 15              | 3               | 10            | 7           | 0 / 0                |
| Post-hoc | Hybrid: rules, then Apertus (process) | 14 (58.3 %)     | 17              | 2               | 13            | 10          | 0 / 0                |

**H4 (supported),** weakly: 3/4 (generic) and 2/4 (process) missing items asked against 0/4, no wrong trigger; but only 4 items, in free text the rules do not read, the rules phrase questions as "card: key ?", which the matcher never recognises, and extra questions are not penalised. **H5 (supported)** on test. **H6 (supported):** deadlines 12 vs 1 of 20, obligations 15 vs 6 of 22, pass 12 vs 3 (McNemar 9–0, exact p = 0.004). **H7 (not supported).** PREREG fixed no metric; we use the pass rate: 10 vs 12 (McNemar 2–4, p = 0.69), with more questions (4 vs 2) and obligations (16 vs 15), fewer deadlines (11 vs 12) and actions (6 vs 7); on dev, from which its training variants derive, 7/43 (16.3 %) vs 12-13. Likely causes: only 113 trajectories, holding the teacher's decisions without its reasoning; QLoRA trained on 4-bit, served on bf16. **H8: not adopted under the pre-registered rule** (deadlines 10 vs 12, other criteria not worse); the gap is within the dev run-to-run noise (dev deadlines: 11 vs 9-10 of 30). **Hybrid (post-hoc):** 14 vs 13 against rules alone (McNemar 1–0, p = 1, not significant), same obligations, deadlines and actions plus 2/4 questions; process tools alone vs rules: 12 vs 13 (3–4, p = 1).

**Exploratory, not pre-registered: domain experts and routing.** Four experts (Impôts, Assurance maladie, Poursuites, Logement) are Apertus 8B with domain tools and prompt plus a QLoRA adapter (150 iterations) on their domain's GLM-5.3 trajectories (252 in all). A rule fixed before the test runs keeps an adapter only if it beats the base on dev pass rate: kept for Poursuites (5/7 vs 0/7) and Logement (3/9 vs 2/9), not for Assurance maladie (2/7 vs 2/7) and Impôts (3/14 vs 3/14; base re-run 5/14). Dev is in-distribution, test has 0-14 scenarios per expert, and adapters lower dev tool-call validity (e.g. Impôts 0.935 → 0.515, Assurance maladie 0.964 → 0.588). These runs (05:16–07:11) also scored 19 test scenarios before the official test runs (07:12–09:54); no commit lies between, and no Table 4 system uses an expert. d1-3B routes the first request: 78.1 % correct vs 64.7 % for EmbeddingGemma 2 on 201 requests (dev and test; de 80.6 / 70.1, fr 77.6 / 59.7, it 76.1 / 64.2 %; threshold not pre-registered). Adapters are opt-in: `mlx_lm.server` 0.32 reloads the model on each adapter change (16 → 35 GB measured).

**Knowledge search.** Top-3 hit (dev / held-out): EmbeddingGemma 2 80.6 / 77.8 %, BM25 52.8 / 38.9 %, RRF fusion 61.1 / 50.0 %; the gap is cross-lingual (held-out, n = 20: 70 % vs 5 % for BM25), so BM25 is only the fallback without weights.

**Cost.** Mean per page (1,260 dev and test pages): OCR 14.9 s (all 1,680 pages), LoRA extraction 6.4 s, hidden-state pass 1.9 s, d1-3B 0.7 s; total 24.5 s, p95 85.3 s. OCR ran in three batches on two machines (means 11.0, 12.8, 18.6 s), the slowest setting the tail (p95 87.6 s); the rest on the Mac Studio. Smoke-test peaks: 3.1 GB (OCR), 14.1 GB (d1-3B fp32).

## 6. Limitations

- **Synthetic documents.** Our layouts test generalisation beyond one layout, not to real statements; the pages we target (barcode missing or damaged) are unmeasured.
- **Checks share the OCR's errors** and have no plausibility bound (`s0586-A`); the probe is trained on zero-shot errors only; one seed per LoRA; the scenario suite is small and internal (§5).
- **Prompt injection.** Flagged payments carry a warning but are not refused (dev `tax-be-03`); a refusal guard is future work.
- **Explanations and language.** Only quotes are verified. The demo shows a Graubünden statement explained in French as "canton de Berne", `totalTaxValue` described as withholding tax, the internal label "DOUBTFUL" shown to the person and a wrong value (9.03) repeated. 23 of 24 final answers of the process coordinator on test start in English although personas write fr/de/it (heuristic count); language is not scored, and the fix after the test runs (`a12b85a`) is not evaluated.
- **Distillation and experts.** Trained on variants of dev scenarios only, on a 4-bit base, served on bf16. GLM-5.3's terms for training on its outputs were not verified; the adapters are not shipped.
- **Deployment.** The console's conversation (expert presets, routing) is not the evaluated configuration. 18 procedures; tax returns for VD, ZH, BE (qualified), GE, TI (draft). d1-3B's licence is not OSI-approved. Apertus reads OCR text, not the image. No user study.
- **Pre-registration deviations.** At the freeze (Addendum 4): all Proof 1 test outputs had been generated, not scored or inspected, in a batch over all splits; the rules baseline had been scored on all scenario splits since `de0de46`; GLM-5.3 replaced Apertus 70B as teacher; QLoRA on bf16; hybrid exploratory; EmbeddingGemma in scenario runs. Before (`src/ordner/eval/DEVIATIONS.md`): one test label printed; demo pages from the test split (now one, `s0003-B`). After: `2edae96` (47 minutes after the freeze) stopped counting guard-cancelled actions as prepared (action status is not in the run files, so its effect on test cannot be checked); H7's metric chosen at analysis; expert A/B on test scenarios (§5); the hybrid + distilled test run cut (owner's decision).

## 7. Reproducibility

**Replay (judges).** `make run` builds a `python:3.12-slim` image pinned by digest (numpy 2.4.6, scikit-learn 1.9.1, matplotlib 3.10.9) with an optional conversation layer: Node from a pinned `node:22-slim` and npm `@deepseek-ai/dsh@0.2.1-alpha.2` fetched at build time (transitive dependencies not locked), patched by `harness_fork/`, skipped if that step fails. Without GPU, weights or network, the container refits probe and combination from the recorded outputs and recomputes every Proof 1 statistic (1.3 s), runs the rules baseline on all scenarios, seeds the demo dossier and serves the cockpit (port 8000) and the conversation (port 8790; a scripted mock model unless `LLM_BASE_URL` points at Apertus). The model rows of Tables 3-4 are committed run files (`data/agent_runs/`), not re-run or re-scored.

**Live (Apple Silicon).** Python 3.11, torch 2.14.1, transformers 5.19.0, accelerate 1.15.0, sentence-transformers 6.1.0, mlx 0.32.3, mlx-lm 0.32.0, zxing-cpp 3.1.1, pypdfium2 5.14.0, reportlab 5.0.1, OpenSteuerAuszug `eeb3b3d`; model revisions in `docs/model_revisions.txt`; commands in `track_2b/README.md`. Seeds are fixed; self-checks cover the generator, the oracle round trip, metrics, dossier rules and quote verification. Batched serving makes scenario runs non-reproducible at the token level.

## 8. Next steps

- Refuse flagged payments; answer in the person's language and score it.
- Scenarios written by counselling services; consented real statements labelled by their barcodes; a user study.
- QR-bills (the payload is the oracle) with first-token entropy as the default doubt signal and a conformal threshold [3, 12].

## License

Creative Commons Attribution 4.0 (CC-BY-4.0). All HackApertus projects are open-sourced.

**Third-party components.** Models and agent runtime: table in §2 (DeepSeek Harness commit `d743267`). Libraries: OpenSteuerAuszug, pdf417gen fork, python-barcode, `qrbill`, mlx, mlx-lm (MIT); Pillow (MIT-CMU); transformers, sentence-transformers, zxing-cpp (Apache-2.0); torch (BSD-style); scikit-learn, numpy (BSD-3-Clause); pypdfium2 (BSD-3-Clause / Apache-2.0); reportlab (BSD); matplotlib (PSF-based). Base images `python:3.12-slim`, `node:22-slim`. Corpus: eCH-0196 (free use with attribution), ESTV circular 2-215 (federal publication), cantonal guides of Bern, Ticino and Graubünden (not redistributed).

**Declarations.** Code, procedure cards and scenarios were written with an AI coding assistant (Claude Code; the commits say so) and reviewed and run by the authors. GLM-5.3 is the only external model that generated training data (development time, fictional scenarios). The console server, Makefile/Docker layout and `LLM_*` convention come from our LPD Navigator prototype (Apache-2.0), written on 12.10.2026 within the hackathon window.

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
[17] Federal Act on Data Protection (FADP / nLPD), SR 235.1, art. 5 lit. c. fedlex.admin.ch.
[18] PostFinance TaxOptimizer product page; papertax.ch; budgetberatung.ch/budget-chatbot (accessed 14.10.2026).
[19] BCV. _Procédure fiscale : e-relevé fiscal_ (flyer).
[20] DeepSeek. _DeepSeek Harness_, github.com/deepseek-ai/deepseek-harness (MIT, developer preview), commit d743267 (0.2.1-alpha.2).

## Placeholders (fill, then delete this section before PDF export)

If `data/explain_eval.json` is produced, replace the "Explanations" paragraph of §5 by the one below, then run `cd track_2b && PYTHONPATH=src .venv/bin/python -m ordner.eval.fill_report` (it fills the rows below whose file exists and only replaces placeholders still present in the text; `%` = multiply by 100, one decimal, no % sign):

> **Explanations (not pre-registered).** On 30 dev pages, {{explain_verbatim_rate}} % of the {{explain_quotes_total}} quotes written by Apertus were verbatim in a retrieved passage (the others are removed before display); explanations mention {{explain_fields_mentioned}} % of the extracted amounts, match the requested language in {{explain_language_match}} % of cases and take {{explain_seconds}} s each. The text around quotes is not checked (§6).

| Placeholder | File | JSON path | Format |
| --- | --- | --- | --- |
| `{{explain_fields_mentioned}}` | `data/explain_eval.json` | `amounts_mentioned_share` | % |
| `{{explain_language_match}}` | `data/explain_eval.json` | `language_match_rate` | % |
| `{{explain_quotes_total}}` | `data/explain_eval.json` | `quotes_total` | integer |
| `{{explain_seconds}}` | `data/explain_eval.json` | `mean_seconds` | seconds, 1 decimal |
| `{{explain_verbatim_rate}}` | `data/explain_eval.json` | `citation_verbatim_rate` | % |

**Filled by hand:** `{{members}}` (member names), `{{repo_url}}` (public repository URL), `{{video_url}}` (demo video URL), `{{commit}}` (commit hash of the submission).
