# Evaluation deviations and disclosures (before the frozen test run)

- **One test label viewed.** The `oracle_page` of one layout-C test document was printed once to check its number
  format (2 decimals). No score was computed on test.
- **Demo pages and the test split.** Before the freeze, the 3 demo pages of the console (C5) were test pages; their
  barcode values were looked up to build the demo fixtures. The current demo (`data/demo/demo.json`, a pipeline export
  made after the freeze) has 4 pages: 3 dev pages of layout A (`s0004-A-p1-d0`, `s0021-A-p1-d2`, `s0098-A-p1-d3`) and
  one test page of layout B (`s0003-B-p1-d2`).
- **Generic number formats added to the regex baseline** (`regex_baseline.py`, `NUM_RE`): thousands separators
  `'`, `’`, space, U+00A0, U+202F, U+2009 or none, and the decimal comma. Added before the frozen test run, after
  layout C was introduced; layout-independent, no label changed. Predictions on all 480 train/dev pages are
  unchanged.
- **Test-split outputs generated before the freeze, and later additions:** see PREREG.md, Addendum 4.
