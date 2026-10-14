# `ordner.app` — Ordner cockpit and demo console

Stdlib HTTP server + vanilla HTML/CSS/JS (no build step, no CDN: works air-gapped).

```bash
PYTHONPATH=src python -m ordner.app.server   # console only, http://localhost:8000
PYTHONPATH=src python -m ordner.app          # replay (python -m ordner.eval.run) if present, then console
PYTHONPATH=src python -m ordner.app.deductions   # self-check of the deductions rules
```

Env: `PORT` (8000), `HOST` (0.0.0.0), `ORDNER_DATA` (default `track_2b/data`), `ORDNER_HOME` (dossier, default `~/.ordner`),
`LLM_BASE_URL` / `LLM_NAME` / `LLM_API_KEY` (live « Demander à Ordner »; without them the panel replays `data/demo/transcripts.json`),
`ORDNER_TODAY` (simulated date for the demo, e.g. `2026-02-20`: urgencies, review, rules, hides documents received later).

## Cockpit (`cockpit.py`, hash routes `#/home`, `#/inbox`, `#/cases`, `#/case/<id>`, `#/coverage`, `#/releve`)

Reads `ordner.case` (W1), `ordner.procedures.catalog` (W2), `ordner.rules` (W3), `ordner.agent` (W5), all imported lazily:
a missing module gives HTTP 503 `{"error": "unavailable", "module"}` and the view says « module pas encore disponible ».
An empty dossier is seeded with the fictional persona (`ordner.case.demo_seed`) and reviewed once: every card of the
subject's canton + CH that is not `not_applicable` opens a case with its next deadline, reminders and missing pieces
(`POST /api/review`, idempotent; also the « Revoir le dossier » button). Missing pieces come from
`ordner.rules.completeness` (waivers, wrong year, duplicates, one statement per declared bank); each missing bank
statement gets a prepared `document_request` with the `email_drafts` letter, downloadable as `.eml` once validated. Endpoints: see the docstring of `server.py`.
« Valider » only records the person's validation (`Store.update_action(..., "validated")`, event `action_updated`):
nothing is ever sent, filed or paid. Self-check: `PYTHONPATH=src python -m ordner.app.cockpit`.

The console reads three files; all of them are produced elsewhere:

| File                                | Producer                                                           | Versioned         |
| ----------------------------------- | ------------------------------------------------------------------ | ----------------- |
| `data/demo/demo.json` + page images | demo export of the pipeline (currently a hand-written **fixture**) | yes               |
| `data/results/results.json`         | `python -m ordner.eval.run`                                        | no (`.gitignore`) |
| `data/rules/deductions_2026.json`   | hand-written from the AFC/ESTV circular 2-215-D-2025               | yes               |

## `data/demo/demo.json`

```jsonc
{
  "fixture": true, // true -> the console shows a "fixture" banner; drop it for real outputs
  "doubt_levels": { "orange": 0.25, "red": 0.5 }, // colour bands on `doubt`
  "documents": [
    {
      "page_id": "s0012-B-p1-d2", // as in work/pages.jsonl
      "image": "s0012-B-p1-d2.jpg", // file in data/demo/ (JPEG, ~1600 px, < 300 KB)
      "language": "de", // document language (fr|de|it)
      "layout": "A", // "B" is shown as "never seen in training"
      "degradation": 2, // 0..3
      "route": {
        "model": "d1-3B",
        "label": "swiss_tax_statement_eCH0196",
        "p": 0.93,
      }, // optional
      "fields": [
        {
          "field": "client_last_name", // one of the 8 fields of ordner.eval.metrics.FIELDS
          "value": "Muller", // extracted value (string)
          "gold": "Müller", // barcode oracle, null if unknown
          "correct": false, // metrics.field_correct(field, value, gold), null if gold is null
          "model": "Apertus 1.5 8B (LoRA)", // display name of the system that produced `value`
          "doubt": 0.57, // combined doubt score in [0,1] (higher = more likely wrong), null if none
          "signals": {
            // any of them may be null/absent
            "probe": 0.61, // probe P(error)                      -> flagged if >= 0.5
            "d1_p_yes": 0.38, // d1-3B P(value is right)             -> flagged if < 0.5
            "rule": "wht_35", // deterministic check id (wht_35, sum_ab; unknown ids shown raw)
            "rule_ok": true, // result of that check                -> flagged if false
            "lp_min": -1.6, // min log-prob of the value tokens    -> flagged if exp() < 0.5
          },
        },
      ],
      "explanation": {
        "text": { "fr": "...", "de": "...", "it": "..." }, // "\n" = new paragraph, lines starting with "•" = list items
        "citations": [
          {
            "source": "label",
            "url": "https://... or null",
            "quote": "verbatim passage or null",
            "verified": true,
          },
        ], // verified = quote found word for word
      },
    },
  ],
}
```

The flag thresholds on single signals only drive the "why" column; the colour comes from `doubt`.

## `data/results/results.json` (written by `ordner.eval.run`; only what the console reads)

```jsonc
{
  "fixture": true,                        // only in the fixture -> banner
  "curves": {                             // Apertus zero-shot, test split: [[share of fields re-read, share of errors caught], ...]
    "combined": [[0.0, 0.0], [0.01, 0.13], ...],      // slider curve: "combined", else "probe A", else the first one
    "min token prob": [...], "d1 validation": [...], "rules": [...], "probe A": [...]   // drawn in grey
  },
  "doubt": {"apertus-base": {"combined": {"auroc": 0.97}, "_n": {"items": 2304, "wrong": 163}}}   // caption
}
```

The slider is the share of fields re-read (most doubtful first); the console interpolates the share of errors caught
on the curve and starts where 90 % of the errors are caught. Missing file or no curve -> the panel says to run
`make eval`. The fixture (`data/results/results.json`, synthetic) is not versioned and is overwritten by the replay.

## `data/rules/deductions_2026.json`

`tax_year`, `scope`, `disclaimer` (fr/de/it), `sources` (id -> title, url, `official`, `verification`) and `rules`.
Each rule: `id`, `when` (all must hold: `key`, `!key`, `key=value`, `key!=value`, `key>n` on the profile),
`title`/`amount`/`condition`/`legal_basis` (fr/de/it), `sources` (ids), `verification`
(`primary` = read in an official source, `secondary`, `unverified`), optional `unverified_note` (fr/de/it, what is not
verified) and optional `estimate` = clamp(`fixed` + profile[`base`] × Π`factors`, `min`, `max`).
Any rule that is not `primary`, or has an `unverified_note`, is flagged « non vérifié » in the console.
Profile keys: see the `profile` block of the JSON (`POST /api/deductions` validates them).
