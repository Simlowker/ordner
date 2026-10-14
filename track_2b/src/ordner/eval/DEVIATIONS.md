# Evaluation deviations and disclosures (before the frozen test run)

- **One test label viewed.** The `oracle_page` of one layout-C test document was printed once to check its number
  format (2 decimals). No score was computed on test.
- **Demo pages come from the test split.** The 3 demo pages of the console (C5) are test pages; their barcode values
  were looked up to build the demo fixtures.
- **Generic number formats added to the regex baseline** (`regex_baseline.py`, `NUM_RE`): thousands separators
  `'`, `’`, space, U+00A0, U+202F, U+2009 or none, and the decimal comma. Added before the frozen test run, after
  layout C was introduced; layout-independent, no label changed. Predictions on all 480 train/dev pages are
  unchanged.
- **Test-split outputs generated before the freeze, and later additions:** see PREREG.md, Addendum 4.
