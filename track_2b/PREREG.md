# Pre-registration

Status: DRAFT. Frozen by the commit that adds the line "FROZEN" below, before any run on the test split.

## Task

Read the summary page of a Swiss electronic tax statement (eCH-0196) from a photo or scan and extract 8 fields:
`totalTaxValue`, `totalGrossRevenueA`, `totalGrossRevenueB`, `totalWithHoldingTaxClaim`, `institution`, `canton`,
`taxPeriod`, `client_last_name`. Ground truth: the XML embedded in the statement's own PDF417 barcodes (decoded from the
clean PDF, cross-checked against the generator).

## Data and splits

- Synthetic statements generated with a fixed seed (7). Split by document: train 70 % / dev 10 % / test 20 %.
- Layout A (OpenSteuerAuszug renderer) in all splits; layouts B and C (our own renderers, B a compact table, C a bank
  letter with side box, bottom box and distractor subtotals) **only in test**, never seen by any system or rule.
- Train/dev pages: one degradation level each (0-3). Test: layouts A and B at all 4 levels, layout C at levels 0 and 2.
- Test labels are not inspected before the frozen run, except automated integrity checks (counts, oracle round-trip).

## Systems compared

1. OCR (LightOnOCR-3-1B) + rules/regex, no LLM.
2. OCR + Apertus 1.5 8B (text backbone), zero-shot, thinking off, greedy.
3. OCR + Apertus 1.5 8B + LoRA fine-tuned on the train split only (if training completes by Thursday 12:00).

Doubt signals per extracted field (same fields, same pages): min token probability, mean token entropy,
d1-3B validation probability, deterministic checks (statement totals consistency where available), linear probe on
Apertus hidden states (position A = value tokens, position B = token before the value), and a combined logistic model.
Doubt signals are studied on the zero-shot Apertus outputs (primary): probe and combination are fit on train+dev
outputs and evaluated on test. Probe = logistic regression on a 256-d PCA (fit on train) of one layer; the layer, the
regularisation and the combination weights are chosen by cross-validation on train+dev only. For the fine-tuned system,
signals without the probe are calibrated on dev (secondary analysis).

## Hypotheses and primary metrics

- **H1** (primary): fine-tuned Apertus has higher field-level exact-match accuracy than zero-shot Apertus on test.
  Test: paired bootstrap over documents (10 000 resamples), 95 % CI of the difference excludes 0.
- **H2**: the combined doubt score has a higher AUROC for "field is wrong" than every single signal on test.
  Test: paired bootstrap 95 % CI of the AUROC difference vs the best single signal excludes 0.
- **H3**: the hidden-state probe (position A) has AUROC > 0.5 on test (bootstrap CI lower bound > 0.5).

Secondary (reported, not tested): accuracy per degradation level and per layout (seen A vs unseen B); triage curve
(share of fields to review to catch 80/90/95 % of errors); per-field accuracy; seen layout (A) vs unseen layouts (B, C); position B vs A; seconds and memory per page
per model on an Apple M4 Max 36 GB.

## Reading rules

- Exact match after normalisation (numbers: Decimal, 2 decimals for CHF amounts; strings: case-folded, whitespace-collapsed).
- A missing or unparseable field counts as wrong.
- Results are reported whatever their direction; a negative result is reported as such.
- Any deviation from this document after freezing is listed in the technical report.

## Addendum (14.10.2026, before any coordinator run on the scenario test split): administrative scenarios

- Suite: `data/scenarios/` (76 scenarios, 67 scored; `needs_review` excluded), split by a fixed hash seed
  (`ordner-scenarios-2026`, 35 % test). Expected outcomes are grounded in official texts quoted verbatim.
- Systems: `rules_only` (catalogue + rules engine on confirmed facts, no LLM) vs `coordinator` (Apertus 1.5 8B text,
  bf16, MLX, thinking off, same tool registry, at most 12 steps per goal). Prompts and tool descriptions may be tuned
  on the dev split only.
- **H4**: the coordinator asks for missing information in more scenarios than `rules_only` (questions metric) without
  increasing wrong triggers. **H5**: the coordinator prepares **zero** forbidden actions (sending, paying, filing) on test.
- Secondary: obligations recall, precision, deadline exact-match, tool-call schema validity, resumption correctness,
  minutes per goal on an Apple M4 Max 36 GB. With 24 test scenarios these are reported descriptively with exact counts.

## Addendum 2 (14.10.2026, before any run): process tools and distillation

- **H6 (process tools)**: the Apertus 8B coordinator with process-level tools (one tool per administrative process,
  composing the deterministic modules and specialist models) beats the same coordinator with the base tools on the
  scenario test split for deadline exact-match and obligations recall, with zero forbidden actions. Same model, same
  prompts except tool descriptions, same step budget.
- **H7 (distillation)**: a LoRA of Apertus 8B trained on teacher trajectories (teacher: Apertus 1.5 70B; optionally
  GLM-5.3, declared) that pass our rule/oracle filters beats the untrained 8B coordinator on the scenario test split.
  Training trajectories are generated only from dev-split scenarios and new synthetic variants; no test-split scenario,
  persona or document is used for training. Teachers see only fictional data.
- Reference points (descriptive): rules_only baseline; 70B coordinator with the same tools if an endpoint is available.

## Addendum 3 (14.10.2026, before any run): agent runtime

- **H8 (runtime)**: DeepSeek Harness (developer preview, MIT) with our tools exposed over MCP, an Apertus tool-call
  translation layer and a fail-closed approval guard, compared with our Python coordinator loop: same model (Apertus
  1.5 8B), same toolset, same step budget, same scenarios (dev for integration, test once). Decision rule: the harness
  is adopted for the product only if it is not worse on deadline exact-match, obligations recall and questions, keeps
  zero forbidden actions, and has no silent failures (a tool call misread as a final answer counts as a failure).
