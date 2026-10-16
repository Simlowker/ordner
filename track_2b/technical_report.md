# Technical report — Ordner

**Ordner is a local, sovereign assistant for Swiss paperwork: it knows which administrative procedures concern a person, what is missing, what to do and why, and prepares everything; it never sends, files, signs or pays.**

- **Track:** Track 2B — Own Project
- **Event:** Online
- **Team:** `Meotis` — Simeon Flueck (Meotis)
- **Demo:** https://youtu.be/SoaeVMRXFwI (1 min 48)
- **Code:** https://github.com/Simlowker/ordner, commit `93b5578`; `PREREG.md` frozen in commit `f52d2c3` before any model was scored on the test split (deviations: its Addendum 4 and §6)

## 1. Summary

**What Ordner does for a person.** Ordner keeps a person's administrative dossier on their own Mac and reads the papers they receive. From a payment order and its notification date it computes the opposition deadline, debt-collection holidays included, and prepares the opposition letter; for a tax return it lists the documents still missing (e.g. a declared bank without its statement); once the date and kind of a move or health-insurance change are known, it gives the announcement, deductible or change deadlines and prepares the letters. Each deadline and rule comes with its official source, quoted verbatim and checked by code; cards and sources exist in French, German and Italian. Rules come first: a deterministic engine over 18 procedure cards (227 quotes from 73 official sources) decides what applies and when; Apertus 1.5 8B, the only general-purpose language model, then reads free text, asks for what is missing and explains, as one of four domain experts with their own official sources. It runs offline, prepares and never sends, files, signs or pays; unseen IBANs and urgent links are flagged as possible phishing, instructions found in documents are stripped. No evaluated run executed anything; on the frozen test, no configuration prepared a forbidden action.

**Does it work reliably?** _Reading:_ eCH-0196 bank statements carry their data in PDF417 barcodes, a free exact answer key; on 1,200 frozen test pages (two of three layouts unseen in training), field exact match is 66.9 % for OCR + rules, 92.1 % for zero-shot Apertus, 98.0 % with LoRA (96.9 % on unseen layouts; H1). Of the doubt signals, first-token entropy is best (AUROC 0.947: re-reading 19.3 % of fields catches 90 % of errors), above our hidden-state probe (0.840; H3) and combination (0.922; H2 not supported); up to 75 of 754 errors stay unflagged. _Procedures:_ on 24 frozen test scenarios the rules engine alone passes 13 (54.2 %), with 11 of 14 tax deadlines exact but 1 of 2 payment-order, 0 of 2 LAMal and 0 of 1 moving deadlines, whose decisive fact sits in free text; rules first, then Apertus passes 14 (original prompt) or 13 (current prompt); process tools lift Apertus alone from 3 to 12 passes over generic tools (H6, p = 0.004); distillation from GLM-5.3 did not help (H7). For context, Claude Opus 5.5 in the same harness passes 19 (79.2 %) with all 20 deadlines: the gap lies in reading such facts, preparing actions and asking blocking questions, the method we now train (tool-use training raised Apertus's obligations recall from 36.4 to 81.8 %, without a significant pass gain). _Sources:_ each expert's own base puts a right-topic official passage in the top 3 for 89.6 % of 96 blind questions vs 81.2 % for one global base (p = 0.008); d1-3B picks the right expert for 78.1 % of 201 requests.

**Scope.** 18 procedures (11 federal; tax returns for VD, ZH, BE, and GE, TI as drafts; premium reduction for VD, ZH), 5 cantons, 3 languages: other cantons get the federal procedures only. All dossiers and documents are fictional; the team wrote the scenarios together with the cards; no user study (§6).

**Motivation.** A tax file is sensitive data (art. 5 lit. c nLPD [17]), yet the AI tax assistants we found are cloud services without published evaluation [18], and scanning damages the barcodes, so VaudTax cannot import a scanned statement [19]: the skill is reading the page.

**Contributions.** (1) A document that grades itself (barcode labels); (2) a pre-registered doubt study inside an open model; (3) a measured rules-first architecture for an 8B model, with run-to-run noise and a frontier reference; (4) a deterministic process teacher; (5) one verified knowledge base per expert; (6) replay without GPU, weights or network.

**Related work.** Hidden-state probes detect hallucinated entities [6, 7] and have been fused with entropy [1]; document confidence has been split into channels [3], OCR self-verified by model agreement [5], judges given guarantees [2] and errors bounded by checks [4]; selective prediction is evaluated by risk-coverage [13], and OCR-then-LLM cascades remain strong [14].

## 2. Architecture

**Deterministic core.** Model-read facts stay `proposed` until the person confirms them; code verifies every card quote verbatim (16 cards qualified, 2 draft). The rules engine computes applicability, deadlines (debt-collection holidays, reception-by dates, cantonal tables), completeness, a phishing flag (unseen IBAN or creditor, urgent link) and a double-payment guard (since §5's dev run). Actions enter as `prepared`; no tool has side effects.

**Coordinator.** A Python loop parses Apertus's native tool calls, pins the subject, hides person-only operations, strips instruction-like text from tool outputs, flags dates no tool returned and attaches the phishing warning to payments; its prompt's rule 4 (explicit since §5) says to prepare the next step of every applicable procedure once nothing blocking is missing. Toolsets: _generic_ (11 tools) or _process_ (one tool per procedure family: document intake, tax return, LAMal deductible, payment order, moving; plus knowledge search, rules evaluation, case load/record: 9). The **hybrid** runs the rules engine, then the coordinator (process) on the same dossier. **Experts:** d1-3B routes the first request (EmbeddingGemma 2 as fallback, the coordinator when unsure); `knowledge.search` and 3 passages injected after the question use the expert's own base.

```
documents ─► READ: barcode first (eCH-0196, QR-bill); else OCR + Apertus + doubt signals
               │ facts enter as "proposed"; only the person confirms them
               ▼
DOSSIER      local SQLite: documents · facts (incl. canton) · cases · deadlines · actions
               │
   1. RULES ENGINE (no model)                 2. APERTUS 1.5 8B (same dossier, ≤ 12 steps)
   18 procedure cards, 227 verbatim quotes    ROUTER d1-3B picks the expert (78.1 % of 201)
   from 73 official sources: applicability,   EXPERT = Apertus + domain tools + own knowledge
   deadlines, completeness, phishing and        base (federal + dossier canton) + LoRA if it
   double-payment guards                        won on dev; coordinator = general expert
               └─────────────────┬──────────────────┘
                                 ▼
COCKPIT      what concerns me · what is missing · next step · why (quoted) ─► the person acts
```

_Figure 1. Ordner. Rules, then the coordinator: the "hybrid" of §5. Router, experts, knowledge bases: exploratory (§5)._

**Reading (Proof 1).** LightOnOCR-3 turns the page into text; Apertus writes eight fields as JSON. Doubt signals per field: token statistics, linear probes on hidden states, d1-3B's P(yes) for "is this the value shown?", deterministic checks (non-negative amounts, withholding claim = 35 % of revenue A, value present in the OCR text, totals, canton, tax year) and their logistic combination. **Explanations** quote official passages retrieved by EmbeddingGemma 2; code removes every quote not found verbatim.

| Component                                                            | Role                                                                                   | Licence                                                                                | Runtime             |
| ------------------------ | -------------------------------------------------- | -------------------------- | ---------------- |
| **Apertus 1.5 8B** [9]                                               | extraction, probe, coordinator, experts, explanations                                  | Apache-2.0                                                                             | MLX, bf16           |
| LightOnOCR-3-1B [11]                                                 | page image → text                                                                      | Apache-2.0                                                                             | MPS, bf16           |
| LiquidAI d1-3B [10]                                                  | doubt judge (fp32: bf16 creates ties); expert routing (bf16)                           | **LFM Open License 1.0, not OSI-approved** (commercial use capped at USD 10 M revenue) | MPS                 |
| EmbeddingGemma 2 [11]                                                | knowledge search (per-expert bases), explanations, routing fallback                                       | Apache-2.0                                                                             | bf16; BM25 fallback |
| zxing-cpp                                                            | barcode decoding (oracle)                                                              | Apache-2.0                                                                             | CPU                 |
| DeepSeek Harness 0.2.1-alpha.2 [20], fork `harness_fork/` | optional runtime replacing our loop (H8), conversation UI; in Docker if its build step succeeds | MIT                                                                                    | Node ≥ 22.19        |
| GLM-5.3, DeepSeek V4.1 Flash | **development only:** teachers on fictional dev variants (§3) | not verified | OpenRouter |
| Claude Opus 5.5 | **development only:** frontier reference (§5), never training data | proprietary | OpenRouter; Claude Code |

### Target architecture (mandatory)

**b) Air-gapped** (primary) and **a) on-premise** (e.g. a debt-counselling office); **c)** is not targeted. **Run time:** no external service (local weights, no API key, CSP `default-src 'self'`, harness telemetry off). **Build time:** weights, Python and npm packages, pinned base images, corpus PDFs. **Development only:** the teachers and the frontier reference run (OpenRouter, Claude Code: foreign services), on fictional scenarios. Tested on two Macs on a LAN (Apertus on a Mac Studio M4 Max 36 GB, clients and UI on the other), Apertus and d1-3B loaded one at a time; no end-to-end run with the network cut.

## 3. Use of Apertus

- **Model:** `swiss-ai/Apertus-v1.5-8B`, text backbone exported as `andreasmartin/apertus-v1.5-8b-text` (Apache-2.0), revision `c0e7eeb`
- **How it is used:** inference (extraction, tool coordination, explanations); fine-tuning (LoRA for extraction; QLoRA for a distilled coordinator, domain experts and shared tool-use adapters); white-box evaluation (doubt probe)
- **Where it runs:** local weights, MLX / mlx-lm, bf16, Mac Studio M4 Max 36 GB

**Extraction and probe.** Greedy, thinking off; a missing or unparseable value is wrong. A teacher-forced pass reads the residual stream after layers 4, 8, …, 32 (float32: norms grow about a thousandfold with depth [8]); per field we keep position A (mean over the value's tokens) and B (the token before it), standardise and project on a 256-d PCA; the probe's layer and regularisation are chosen by statement-grouped cross-validation on train + dev. **LoRA:** mlx-lm, rank 16, scale 2, all 32 blocks, learning rate 10⁻⁴, batch 2, 2 epochs, seed 7. **Coordinator:** thinking off, temperature 0, at most 12 model calls per goal, one toolset-neutral prompt; a malformed tool call is an error, never the answer. **Distillation (H7):** GLM-5.3 ran the same loop on 400 seeded dev variants (outcomes recomputed by the rules engine): 234 passed with process tools, 105 with generic tools; a strict filter kept 113 trajectories. bf16 LoRA ran out of memory at 8k-token turns, so every coordinator adapter is QLoRA (last 16 layers of a 4-bit copy, rank 16), served on the bf16 base.

**Tool-use adapters** (expert mode). On a 24-variant dev pilot DeepSeek V4.1 Flash passed 20 (US$ 0.0044 per variant), GLM-5.3 16 ($0.0224); DeepSeek then played 227 of the 496 dev variants before credits ran out (162 passed, 126 kept by the filter): **tools-v1** trains on their 367 tool-call turns (original prompt). The **process teacher** (`ordner.distill.process`) plays an ideal expert's method deterministically in the same loop, from tool results only, never from expected outcomes: all procedures of the domain in the person's canton, computed deadlines recorded, each step prepared (no payment after injected instructions), one question for missing facts. It passes 328 of 496 dev variants (all kept by the filter), including all 14 `inst-01` variants (every LLM teacher fails the pilot's two), but it is not the stronger teacher overall (15 of 24 pilot variants): it skips what tool results cannot decide (§6). **tools-v2:** 572 turns (process 307, DeepSeek 265), balanced by source scenario, rule-4 prompt.

## 4. Data

**Tax statements (Proof 1).** 600 fictional statements (seed 7; German 255, French 199, Italian 146), totals checked by recomputation and OpenSteuerAuszug's verifier (MIT [16]), XML per eCH-0196 v2.2 [15]. Layout A is OpenSteuerAuszug's renderer; B (compact table) and C (bank letter, distractor subtotals) are ours, test only. Degradations 1-3 simulate phone photos. The decoded barcodes match the generator for all 600 statements; gold is the value as displayed. Train 420 and dev 60 pages (layout A); test 120 statements, 1,200 pages (A and B × 4 levels, C × 2).

**Scenarios (Proof 2).** 76 scenarios (`data/scenarios/`): a fictional persona, dossier, events and goal, sometimes in phases, with expected procedures, traps (including a prompt-injection e-mail), questions, deadlines with the official text that fixes them, actions and forbidden actions. The team wrote them with an AI coding assistant; nobody outside the team reviewed them. 67 (9 `needs_review` excluded) are split by a fixed hash seed into 43 dev and 24 test. All of this is fictional. Training variants (496, seeded) derive from dev scenarios only. After the freeze, dev scenarios `serafe-01/02/03` got a valid IBAN and QR reference: the old ones failed the check digits, so Ordner flagged phishing and refusing was right (all IBANs audited: test is clean).

**Expert knowledge bases** (`data/knowledge/`, Table 5): 26 topics fixed before collection; AI agents fetched federal and VD, ZH, BE, GE, TI sources (fr/de/it) on 15.10; each of the 712 passages is a substring of the saved fetched text (script, 0 failures). Official acts are in the repository (art. 5 LDA); authority pages stay local, URLs in `sources.json`. Data: CDLA-Permissive-2.0, 40 MB.

## 5. Evaluation

### Proof 1: extraction and doubt

**Protocol (PREREG.md).** Field exact match after normalisation; 95 % CIs by paired cluster bootstrap over the 120 test statements. **H1:** LoRA beats zero-shot. **H2:** the combined doubt score has a higher AUROC for "field is wrong" than every single signal. **H3:** probe A has AUROC > 0.5. Doubt is fit on zero-shot outputs of train + dev (221 errors in 3,840 layout-A fields).

**Table 1. Baseline vs Ours, extraction (test, 1,200 pages, 9,600 fields per system; field accuracy %, 95 % CI).**

| Setup    | System                          | Field accuracy    | Page fully correct | Seen layout (A) | Unseen layouts (B, C) |
| -------- | ------------------------------- | ----------------- | ------------------ | --------------- | --------------------- |
| Baseline | OCR + rules/regex (no LLM)      | 66.9 [65.8, 68.0] | 37.9               | 99.0            | 45.5                  |
| Baseline | OCR + Apertus 1.5 8B, zero-shot | 92.1 [91.4, 92.8] | 54.5               | 94.2            | 90.8                  |
| **Ours** | OCR + Apertus 1.5 8B + LoRA     | 98.0 [97.7, 98.3] | 88.3               | 99.7            | 96.9                  |

**H1 (supported).** LoRA minus zero-shot: +5.9 points [+5.2, +6.6] over 9,600 paired fields. Layout C (bank letter) stays at 90.8 % with LoRA (B: 99.97 %, 3,839/3,840).

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
| Ours     | Combined (frozen code): rows above but probe B, + mean token probability | 0.922 [0.904, 0.938]     | 0.911        | 30.5             |

**H2 (not supported, reversed).** Combined minus first-token entropy (fixed in the frozen evaluation code, not named in PREREG.md): −0.024 [−0.048, −0.001]; it is not above PREREG's mean token entropy either (0.924); fit on 221 layout-A errors (cross-validated AUROC 0.996), the combination does worse on test than one of its own free inputs, likely over-fitting. **H3 (supported).** Probe A: 0.840, lower bound 0.814; position B is better (+0.049 [+0.020, +0.079]); both stay below the token statistics, and the within-field test AUROC (0.858) shows the drop from cross-validation (0.996, best of 32 grid cells) is not just field identity. **Silent errors.** At the 90 % budget, up to 75 of 754 errors stay unflagged; on demo page `s0003-B` (test) zero-shot Apertus reads `totalTaxValue` 9.03 instead of 23,805.62 with combined doubt 0.002. For LoRA, the pre-registered dev calibration is not estimable (2 errors in 480 dev fields; 190 on test); one LoRA output (`s0586-A`: 1,962,279,958,001,002 instead of 21,274) passes every check because its digits occur in the OCR text, and alone sets the mean CHF error in `data/results/table.md`.

### Proof 2: coordinator architecture

**Protocol (PREREG addenda 1-4).** Each scenario runs on a fresh dossier and passes when all its checks pass; specialist models are replayed; Apertus bf16 is served by `mlx_lm.server`. **H4:** more missing-information questions than rules alone, without more wrong triggers; **H5:** no forbidden action prepared on test; **H6:** process beat generic tools on deadlines and obligations; **H7:** the distilled adapter beats the untrained coordinator; **H8:** the harness is adopted only if not worse than our loop. **Caveats:** cards and scenarios were written together and the rules engine reads the procedure label the author attached to events, so rules-only is not an independent baseline; metrics are recall-oriented, which favours a union such as the hybrid; process tools return code-computed deadlines, so H6 tests whether the model calls the right tool with the right arguments.

**Dev (43 scenarios, `data/agent_runs/dev/`).** Passed: rules only 20 (46.5 %), process tools 12 and 13 in two identical runs, which disagree on 5 verdicts (dev gaps below about 12 points are noise), hybrid 23 (vs rules: McNemar 4–1, p = 0.375). Only the hybrid prepared forbidden actions (none executed): duplicated payments in `inst-02`, `serafe-02` (before the double-payment guard) and, in its re-run, an action in `tax-be-03` with an injected phishing e-mail's IBAN, which the answer told the person to pay (no warning in the run file).

**Table 3. Baseline vs Ours, scenario suite, test split (24 scenarios, one run per system, original prompt as pre-registered; counts).**

| Setup    | System                                | Pass /24        | Obligations /22 | Missing info /4 | Deadlines /20 | Actions /14 | Forbidden / executed |
| ----------- | ------------------------------------- | ------------- | ------------- | ------------- | ------------- | ----------- | ------------- |
| Baseline | Rules engine only, no model           | 13 (54.2 %)     | 17              | 0               | 13            | 10          | 0 / 0                |
| Baseline | Apertus, generic tools                | 3 (12.5 %)      | 6               | 3               | 1             | 2           | 0 / 0                |
| **Ours** | **Apertus, process tools**            | **12 (50.0 %)** | **15**          | **2**           | **12**        | **7**       | **0 / 0**            |
| Ours     | Same + distilled adapter              | 10 (41.7 %)     | 16              | 4               | 11            | 6           | 0 / 0                |
| Runtime  | Process tools, DeepSeek Harness       | 9 (37.5 %)      | 15              | 3               | 10            | 7           | 0 / 0                |
| Post-hoc | Hybrid: rules, then Apertus (process) | 14 (58.3 %)     | 17              | 2               | 13            | 10          | 0 / 0                |

**H4 (supported),** weakly: 3/4 (generic) and 2/4 (process) missing items asked vs 0/4, no wrong trigger; but only 4 items, the rules' "card: key ?" questions never match and extra questions are not penalised. **H5 (supported)** on test. **H6 (supported)** on its pre-registered metrics: deadlines 12 vs 1 of 20, obligations recall 68.2 vs 27.3 %; scenario pass 12 vs 3 (McNemar on pass 9–0, exact p = 0.004). **H7 (not supported).** PREREG fixed no metric; pass rate: 10 vs 12 (McNemar 2–4, p = 0.69); on dev, where its variants come from, 7/43 vs 12-13. Likely causes: only 113 trajectories, holding the teacher's decisions without its reasoning; QLoRA trained on 4-bit, served on bf16. **H8: not adopted under the pre-registered rule** (deadlines 10 vs 12, other criteria not worse); the gap is within the dev run-to-run noise (dev deadlines: 11 vs 9-10 of 30). **Hybrid (post-hoc):** 14 vs 13 against rules alone (McNemar 1–0, p = 1, not significant).

### Scenario suite with the current prompt (exploratory, after the freeze)

**Protocol.** Rule 4 of the prompt was made explicit after a dev error analysis (every frontier teacher's most frequent failure on the pilot: an action not prepared; Claude Code: 18 → 21 of 24 after the fix); every Table 4 row then ran once on the frozen test, labels untouched. Expert rows pick the expert from the scenario's expected procedures (oracle routing, `expert_for`, the same for every model). Frontier row: six Claude Code agents play turn by turn in the same loop (`ordner.distill.manual`), seeing neither scores nor files. tools-v1 was selected on dev by the rule fixed before testing (pass 8 vs 6 of 43, original prompt).

**Table 4. Same harness, frozen test, rule-4 prompt, one run each (counts); rules engine alone: Table 3.**

| System | Pass /24 | Obligations /22 | Missing info /4 | Deadlines /20 | Actions /14 | Tool calls | Forbidden / executed |
| -------------------------------------------------------------- | ------------ | ------------ | ------- | ------- | ------- | ------ | -------- |
| **Ordner: rules, then Apertus 8B (process tools)** | **13 (54.2 %)** | **17 (77.3 %)** | **0** | **13** | **10** | **87** | **0 / 0** |
| Apertus 8B expert alone, base | 5 (20.8 %) | 8 (36.4 %) | 1 | 5 | 2 | 44 | 0 / 0 |
| Apertus 8B expert alone + tools-v1 adapter | 7 (29.2 %) | 18 (81.8 %) | 0 | 12 | 6 | 235 | 0 / 0 |
| Context only: Claude Opus 5.5 expert (closed) | 19 (79.2 %) | 21 (95.5 %) | 1 | 20 | 13 | 87 | 0 / 0 |

**Reading.** Rules first stays the reliable configuration: with rule 4 the hybrid passes exactly the rules engine's 13 scenarios with the same counts (vs Table 3: `tax-zh-03` lost, questions 2 → 0 of 4). Apertus alone is not yet reliable: tool-use training raised obligations 8 → 18 of 22 (36.4 → 81.8 %), deadlines 5 → 12 and actions 2 → 6, but it asks no question, triggers one trap and passes 7 vs 5 (McNemar 4–2, p = 0.69). The frontier row shows how far a general model goes in the same harness (19; vs the hybrid 6–0, p = 0.031) and where the gap lies: preparing actions (13 vs 6 of 14) and recording deadlines (20 vs 12), not finding procedures (21 vs 18); it also misses 3 of 4 blocking questions. That method is what the process teacher (§3) constructs. **tools-v2** (dev, rule 4): 14 vs 6 of 43 for the base, obligations 35 vs 9 of 39, but no final answer in any scenario (tool-call turns only), so not run on the test (an adapter must also answer in ≥ 90 % of dev scenarios; rule set before). **Rules first inside each expert** (the web UI): 19 of 43 vs hybrid 24 and expert alone 6; same obligations and actions as the hybrid, answers 43/43, blocking questions 1 of 7 vs 7 of 7; below the hybrid, so no test run.

**Exploratory: experts and routing.** Per-expert QLoRA adapters (each domain's share of 252 GLM-5.3 trajectories) are kept only where they beat the base on dev pass rate (rule fixed before testing): Poursuites (5/7 vs 0/7) and Logement (3/9 vs 2/9), not Assurance maladie (2/7 vs 2/7); Impôts invalid. These runs scored 19 test scenarios before the official runs. d1-3B routes the first request right for 78.1 % of 201 requests (EmbeddingGemma 2: 64.7 %).

**Table 5. Per-expert knowledge bases (exploratory): top-3 topic hit, %, on blind questions; acts only = clean clone.**

| Expert | Passages | Acts + pages | Sources | CH / cantons | Expert base | Global base | BM25 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Impôts | 135 | 105 + 30 | 46 | 79 / 56 | 87.5 | 66.7 | 79.2 |
| LAMal | 168 | 114 + 54 | 39 | 126 / 42 | 95.8 | 95.8 | 83.3 |
| Poursuites | 164 | 111 + 53 | 40 | 107 / 57 | 79.2 | 70.8 | 79.2 |
| Logement | 245 | 106 + 139 | 93 | 158 / 87 | 95.8 | 91.7 | 83.3 |
| **All** | 712 | 436 + 276 | 218 | 470 / 242 | **89.6** | 81.2 | 81.2 |
| Acts only | 436 | 436 + 0 | 92 | 323 / 113 | 90.6 | 81.2 | 75.0 |

**Protocol.** Added after the PREREG freeze: topics fixed (15.10, 11:40) and 96 questions written blind before any retrieval run (git history of `data/knowledge/`). Hit: a top-3 passage tagged with the question's topic; all systems keep federal + the question's canton; the global base pools all experts. The expert base wins 8 questions, loses none (McNemar p = 0.008; vs BM25 11–3, p = 0.057); 29.2 % of global top-3 lists hold another expert's passages (30.2 % acts only). **Limits:** topics tagged by the collecting agents (FAQ chunks by URL and keywords), questions by an AI agent, 24 per expert, one embedding model, topic match, not answer quality.

**Cost.** Mean per page (1,260 dev and test pages): OCR 14.9 s (1,680 pages, two machines), LoRA extraction 6.4 s, hidden-state pass 1.9 s, d1-3B 0.7 s; total 24.5 s, p95 85.3 s. Peaks: 3.1 GB (OCR), 14.1 GB (d1-3B fp32).

## 6. Limitations

- **Synthetic documents.** Our layouts test generalisation beyond one layout, not to real statements; the pages we target (barcode missing or damaged) are unmeasured.
- **Checks share the OCR's errors** and have no plausibility bound (`s0586-A`); the probe is trained on zero-shot errors only; one seed per LoRA; the scenario suite is small and internal (§5).
- **Explanations and language.** Not evaluated at scale; only quotes are verified (4 demo explanations: 6 verbatim quotes kept, 3 removed); one calls a Graubünden statement "canton de Berne" and repeats a wrong value. 23 of 24 final answers of the hybrid on test start in English (heuristic; language is not scored); the language-detector fix and the web UI's language reminder (`783249d`) are not evaluated.
- **Distillation and experts.** Dev variants only; the teachers' terms for training on their outputs not verified; adapters not shipped (tools-v1 not in the web presets). The process teacher skips AHV for non-employed persons and withholding-tax refunds (no positive dev case; labelling new situations with the same engine would be circular) and free-text LAMal and moving deadlines.
- **Deployment.** The agentic web conversation (forked harness UI, experts, routing) demonstrates the evaluated loop, not separately evaluated; on Noa's long dossier the 8B model often asks instead of acting. Apertus reads OCR text, not the image.
- **Pre-registration deviations.** At the freeze (Addendum 4): Proof 1 test outputs generated, not scored or inspected; GLM-5.3 replaced Apertus 70B as teacher; QLoRA on bf16; hybrid exploratory; EmbeddingGemma in scenario runs. Not in Addendum 4: `make run` scored the rules baseline on every split from `de0de46`; OCR also ran on the laptop. Before (`src/ordner/eval/DEVIATIONS.md`): one test label printed; demo pages from the test split (now one). After: `2edae96` stopped counting guard-cancelled actions as prepared (effect on test uncheckable); H7's metric chosen at analysis; expert A/B and knowledge bases; hybrid + distilled test run cut (owner's decision); rule 4, Serafe labels and Table 4, nothing tuned on test failures.

## 7. Reproducibility

**Replay (judges).** `make run` builds a `python:3.12-slim` image pinned by digest (numpy 2.4.6, scikit-learn 1.9.1, matplotlib 3.10.9), plus an optional conversation layer (pinned `node:22-slim`, npm `@deepseek-ai/dsh@0.2.1-alpha.2` fetched at build time, transitive dependencies not locked, patched by `harness_fork/`, skipped if it fails). Without GPU, weights or network, it refits probe and combination from the recorded outputs, recomputes every Proof 1 statistic (1.3 s), runs the rules baseline on all scenarios, seeds the demo dossier and serves the cockpit and the conversation (a scripted mock model unless `LLM_BASE_URL` is set). Model results of Tables 3-5 are committed files (`data/agent_runs/`, `data/knowledge/`), not re-run.

**Live (Apple Silicon).** Python 3.11, torch 2.14.1, transformers 5.19.0, accelerate 1.15.0, sentence-transformers 6.1.0, mlx 0.32.3, mlx-lm 0.32.0, zxing-cpp 3.1.1, pypdfium2 5.14.0, reportlab 5.0.1, OpenSteuerAuszug `eeb3b3d`; model revisions in `docs/model_revisions.txt`; commands in the README. Seeds fixed; self-checks cover generator, oracle round trip, metrics, dossier rules, quote verification. Batched serving makes scenario runs non-reproducible token by token.

## 8. Next steps

- All 26 cantons; score answers and language; refuse flagged payments; extend the process teacher (independent labels); counselling-service scenarios, consented real statements, a user study; QR-bills; entropy doubt with a conformal threshold [3, 12].

## License

Creative Commons Attribution 4.0 (CC-BY-4.0). All HackApertus projects are open-sourced.

**Third-party components.** Models and runtime: §2. Libraries: OpenSteuerAuszug, pdf417gen fork, python-barcode, `qrbill`, mlx, mlx-lm (MIT); Pillow (MIT-CMU); transformers, sentence-transformers, zxing-cpp (Apache-2.0); torch (BSD-style); scikit-learn, numpy (BSD-3-Clause); pypdfium2 (BSD-3-Clause / Apache-2.0); reportlab (BSD); matplotlib (PSF-based). Corpus: eCH-0196 (free use with attribution), ESTV circular 2-215 (federal publication), cantonal guides of Bern, Ticino and Graubünden (not redistributed); knowledge-base official acts (art. 5 LDA).

**Declarations.** Code, procedure cards, scenarios and knowledge bases were made with an AI coding assistant (Claude Code; the commits say so), reviewed and run by the authors. Training data came only from GLM-5.3 and DeepSeek V4.1 Flash (fictional dev variants); Claude Opus 5.5 was a reference run only, never training data (`filter.py`). Console server, Makefile/Docker layout and `LLM_*` convention come from our LPD Navigator prototype (Apache-2.0, 12.10.2026, within the hackathon window).

## References

<div style="font-size: 9pt">

[1] E. Phillips et al. _Entropy Alone is Insufficient for Safe Selective Prediction in LLMs._ arXiv:2603.21172, 2026.
[2] J. Jung et al. _Trust or Escalate: LLM Judges with Provable Guarantees for Human Agreement._ arXiv:2407.18370, 2024.
[3] Y. Jin et al. _Perception, Layout, and Validation: Calibrated Confidence for Reliable Straight-Through Processing of Financial Documents._ arXiv:2609.20110, 2026.
[4] B. Raduta et al. _Zero Hallucination, by Construction: Hallucination-Aware Layered Oversight (HALO)._ arXiv:2607.17883, 2026.
[5] Y. Zhang et al. _Consensus Entropy: Harnessing Multi-VLM Agreement for Self-Verifying and Self-Improving OCR._ arXiv:2504.11101, 2025.
[6] O. Obeso et al. _Real-Time Detection of Hallucinated Entities in Long-Form Generation._ arXiv:2509.03531, 2025.
[7] J. Kossen et al. _Semantic Entropy Probes: Robust and Cheap Hallucination Detection in LLMs._ arXiv:2406.15927, 2024.
[8] Apertus Claritas. _Active interpretability with hallucination probes: exploding activations in Apertus 8B._ apertus-claritas.org (accessed 13.10.2026).
[9] Swiss AI Initiative. _Apertus: Democratizing Open and Compliant LLMs for Global Language Environments._ arXiv:2509.14233, 2025.
[10] A. Amini et al. _LFM2 Technical Report._ arXiv:2511.23404, 2025. Liquid AI, _d1-3B_ model card, huggingface.co/LiquidAI/d1-3B, 2026.
[11] LightOn, _LightOnOCR-3_ model card, huggingface.co/lightonai/LightOnOCR-3-1B, 2026. Google, _EmbeddingGemma 2_ model card, huggingface.co/google/embeddinggemma-2, 2026.
[12] Y. Dou et al. _Conformal Cascade: Distribution-Free Accuracy Guarantees for Multi-Tier LLM Inference._ arXiv:2607.25018, 2026.
[13] Y. Geifman, R. El-Yaniv. _Selective Classification for Deep Neural Networks._ NeurIPS, 2017.
[14] Y. Ma et al. _MMLongBench-Doc: Benchmarking Long-context Document Understanding with Visualizations._ arXiv:2407.01523, 2024.
[15] eCH. _eCH-0196 E-Steuerauszug V2.2.0_, incl. Beilage 2 (barcode generation), 2022; _eCH-0270 V1.0.0 Barcode generation_, 2024. ech.ch.
[16] F. Vroonhof et al. _OpenSteuerAuszug_, github.com/vroonhof/opensteuerauszug (MIT), commit eeb3b3d.
[17] Federal Act on Data Protection (FADP / nLPD), SR 235.1, art. 5 lit. c. fedlex.admin.ch.
[18] PostFinance TaxOptimizer product page; papertax.ch; budgetberatung.ch/budget-chatbot (accessed 14.10.2026).
[19] BCV. _Procédure fiscale : e-relevé fiscal_ (flyer).
[20] DeepSeek. _DeepSeek Harness_, github.com/deepseek-ai/deepseek-harness (MIT), commit d743267.

</div>

## Placeholders (fill, then delete this section before PDF export)

If `data/explain_eval.json` is produced, add the paragraph below at the end of §5 "Proof 1" and shorten the "Explanations and language" limitation accordingly, then run `cd track_2b && PYTHONPATH=src .venv/bin/python -m ordner.eval.fill_report` (it fills the rows below whose file exists and only replaces placeholders still present in the text; `%` = multiply by 100, one decimal, no % sign):

> **Explanations (not pre-registered).** On 30 dev pages, {{explain_verbatim_rate}} % of the {{explain_quotes_total}} quotes written by Apertus were verbatim in a retrieved passage (the others are removed before display); explanations mention {{explain_fields_mentioned}} % of the extracted amounts, match the requested language in {{explain_language_match}} % of cases and take {{explain_seconds}} s each. The text around quotes is not checked (§6).

| Placeholder | File | JSON path | Format |
| --- | --- | --- | --- |
| `{{explain_fields_mentioned}}` | `data/explain_eval.json` | `amounts_mentioned_share` | % |
| `{{explain_language_match}}` | `data/explain_eval.json` | `language_match_rate` | % |
| `{{explain_quotes_total}}` | `data/explain_eval.json` | `quotes_total` | integer |
| `{{explain_seconds}}` | `data/explain_eval.json` | `mean_seconds` | seconds, 1 decimal |
| `{{explain_verbatim_rate}}` | `data/explain_eval.json` | `citation_verbatim_rate` | % |

**Filled by hand:** `Simeon Flueck (Meotis)` (member names), `https://github.com/Simlowker/ordner` (public repository URL), `{{video_url}}` (demo video URL), `93b5578` (commit hash of the submission).
