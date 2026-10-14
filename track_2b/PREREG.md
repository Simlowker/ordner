# Pre-registration

Status: DRAFT. Frozen by the commit that adds the line "FROZEN" below, before any run on the test split.

## Task

Read the summary page of a Swiss electronic tax statement (eCH-0196) from a photo or scan and extract 8 fields:
`totalTaxValue`, `totalGrossRevenueA`, `totalGrossRevenueB`, `totalWithHoldingTaxClaim`, `institution`, `canton`,
`taxPeriod`, `client_last_name`. Ground truth: the XML embedded in the statement's own PDF417 barcodes (decoded from the
clean PDF, cross-checked against the generator).

## Data and splits

- Synthetic statements generated with a fixed seed (7). Split by document: train 70 % / dev 10 % / test 20 %.
- Layout A (OpenSteuerAuszug renderer) in all splits; layout B (our own renderer) **only in test**.
- Train/dev pages: one degradation level each (0-3). Test: every document at all 4 levels, layouts A and B.
- Test labels are not inspected before the frozen run, except automated integrity checks (counts, oracle round-trip).

## Systems compared

1. OCR (LightOnOCR-3-1B) + rules/regex, no LLM.
2. OCR + Apertus 1.5 8B (text backbone), zero-shot, thinking off, greedy.
3. OCR + Apertus 1.5 8B + LoRA fine-tuned on the train split only (if training completes by Thursday 12:00).

Doubt signals per extracted field (same fields, same pages): min token probability, mean token entropy,
d1-3B validation probability, deterministic checks (statement totals consistency where available), linear probe on
Apertus hidden states (position A = value tokens, position B = token before the value), and a combined logistic model.
Probe layer, regularisation and the combination weights are chosen **on dev only**.

## Hypotheses and primary metrics

- **H1** (primary): fine-tuned Apertus has higher field-level exact-match accuracy than zero-shot Apertus on test.
  Test: paired bootstrap over documents (10 000 resamples), 95 % CI of the difference excludes 0.
- **H2**: the combined doubt score has a higher AUROC for "field is wrong" than every single signal on test.
  Test: paired bootstrap 95 % CI of the AUROC difference vs the best single signal excludes 0.
- **H3**: the hidden-state probe (position A) has AUROC > 0.5 on test (bootstrap CI lower bound > 0.5).

Secondary (reported, not tested): accuracy per degradation level and per layout (seen A vs unseen B); triage curve
(share of fields to review to catch 80/90/95 % of errors); per-field accuracy; position B vs A; seconds and memory per page
per model on an Apple M4 Max 36 GB.

## Reading rules

- Exact match after normalisation (numbers: Decimal, 2 decimals for CHF amounts; strings: case-folded, whitespace-collapsed).
- A missing or unparseable field counts as wrong.
- Results are reported whatever their direction; a negative result is reported as such.
- Any deviation from this document after freezing is listed in the technical report.
