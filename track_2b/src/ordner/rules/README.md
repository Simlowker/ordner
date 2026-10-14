# ordner.rules

Deterministic, explainable rules. Stdlib only, no network. Self-check: `PYTHONPATH=src .venv/bin/python -m ordner.rules.selfcheck`.

```python
from ordner.rules import applicable, compute_deadline, reminders, to_ics, DEADLINE_RULE_IDS, SOURCES
applicable(card, subject, facts, on=None, period=None, accept_proposed=False) -> dict
compute_deadline(rule, subject, context) -> dict
reminders(due, policy="default", today=None) -> list[str]
to_ics(deadlines, subject) -> str
completeness(card, subject, facts, documents, period=None) -> dict
consolidate(facts, period) -> dict
```
Objects can be the `schema.py` dataclasses or the same fields as dicts.

## Applicability

Same syntax as `ordner.procedures.catalog` (W2a validates it, this module evaluates it):

| Condition | Meaning |
|---|---|
| `{}` | always true |
| `{"all": [...]}` / `{"any": [...]}` / `{"not": c}` | boolean combinators |
| `{"role": "student"}` | `"student" in subject.roles`; **empty roles = unknown** (`subject.roles` missing) |
| `{"attr": "canton", "eq": "VD"}` | Subject field (`id kind name canton commune`) or key of `subject.attrs` |
| `{"attr": "age_at_year_end", "gte": 21}` | computed: year of `period` (else of `on`) − `birth_year`, exact since the birthday has passed by 31.12 |
| `{"attr": "age", "gte": 18}` | computed: completed years at `on`; uses `attrs.birth_date` (ISO); with `birth_year` only, decided if both possible ages agree, else `subject.birth_date` missing |
| `{"fact": "income.net", "lte": 46800}` | latest **confirmed** Fact with that key for this subject (and `period` if given) |

Leaf operators, exactly one per leaf: `eq ne in gte gt lte lt exists`.

Three-valued evaluation: a leaf without a value is *unknown*. `all` is false if one branch is false, `any` is true if one branch is true; otherwise unknown propagates and the missing keys are returned. `exists` reads the dossier as it is: absent is false. Other rules:
- only facts with `status == "proposed"` → unknown, with the proposed value shown in `why` so that the coordinator asks for confirmation. `accept_proposed=True` lets proposed facts count (preview mode). Rejected and superseded facts are ignored, and so are other subjects' facts.
- `card.jurisdiction` other than `"CH"` adds an implicit `canton == jurisdiction` condition.
- a card outside `valid_from`/`valid_to` at `on` gives `missing_info` (`card.validity`), never a silent yes. A non-qualified card adds a "to verify" line to `why`.

Result: `{"status": "applicable"|"not_applicable"|"missing_info", "missing": [...], "why": [fr lines], "card", "evaluated_on", "accepted_fact_status"}`. Missing keys are `subject.<field>`, a fact key, or `card.validity`.

## Deadline rules (`DeadlineRule.id` → params)

| id | params | context needed |
|---|---|---|
| `fixed_date` | `month`, `day`, `year_offset`=0, `extensions`?, `reception`? | `period` |
| `days_after_notification` | `days` (0 = « sans délai »), `count`=`calendar`\|`business`, `lp_holidays`=false, `extend_non_working`=true, `from_fact`? | `notified_on`, or `facts` with `from_fact` |
| `debt_collection` | `days`=10 (LP art. 74) | `notified_on` |
| `reception_by` | `month`, `day`, `year_offset`?, `send_by`={`month`,`day`}?, `margin_working_days`=5 | `period` |
| `cantonal_table` | `table`: {canton: fixed_date params incl. `extensions`, `sources`} | `period`, canton |
| `year_end` | `year_offset`? (31.12) | `period` |
| `chosen_date` | `from_fact`? | `chosen_date`, or `facts` with `from_fact` |

Modifiers usable with any rule:
- **`from_fact`**: the start date (or, for `chosen_date`, the date itself) is the value of the latest **confirmed** fact with this key, read from `context["facts"]`. If the fact is absent or only proposed, the result is `missing_info` on that key.
- **`cantonal`**: `{canton: params override}`, merged over the base params for `context.canton` or `subject.canton`. Its `sources` come before the base ones. A `"rule"` text key is kept as `computed_from.cantonal_rule`, with a warning: the text is not interpreted. If the card has `cantonal` and the canton is unknown, the result is `missing_info` (`subject.canton`), because a canton may be stricter than the base. A canton absent from the map gets the base rule, with a warning.
- **`kinds`**: `{event kind: params override}`, at the top level or inside a cantonal entry. It is selected by `context["kind"]`; when the kind is missing, the result is `missing_info` (`kind`). A kind that is not listed gets the base params. Cantonal and top-level `kinds` are merged kind by kind. In top-level `kinds`, `"canton_of": "destination"` (intercantonal arrival) selects the cantonal rule, and the holidays, of the canton of arrival: `context["to_canton"]`, else the confirmed fact `move.planned.canton_to`, else `missing_info`. `"origin"` (the default) uses `context.canton` or `subject.canton`. Example: FR `{"days": 14, "kinds": {"internal": {"days": 30}, "departure": {"days": 0}}}`.
- **`variants`** + `applies_to`: the base rule covers the `applies_to` cases, and each variant `{"case", "id"?, ...params}` is its own rule.
  - With `context["variant"]`, the matching option is computed (`computed_from.variant`).
  - Without it, the result is `{"status": "variants", "missing": ["variant"], "variants": [{"cases", ...result}]}`.
  - An unknown case gives `missing_info`.

Every params dict may carry `"sources": [i, ...]`, which are indexes into `card.sources`; they are returned as `computed_from.card_sources`.
`extensions`: `[{"until": "MM-DD", "fee_chf", "how", "request_by": "MM-DD"?, "sources"}]`. The dates are resolved in the year of the due date and returned as ISO.

Context keys:
- `period`: "2025";
- `notified_on`: ISO date of the proven notification;
- `facts`: list of Facts, for `from_fact`;
- `kind`, `variant`, `chosen_date`: see the modifiers above;
- `canton`: overrides `subject.canton`;
- `extension`: index of the extension that was granted or chosen;
- `margin_working_days`;
- `label`: event title.

Result: `{"status": "computed", "due", "computed_from": {"rule", "version", "inputs", "card_sources", "legal_basis", "steps", "warnings", "label"?, "send_by"?}, "send_by"?, "extensions"?}`. When an input is missing, the result is `{"status": "missing_info", "rule", "missing": [...], "why": [...]}`. A malformed params dict or an unknown rule id raises `ValueError` (card bug, not user info).

Computation:
- **Days after notification**: the deadline runs from the next day (CPC 142 al. 1, PA 20 al. 1). When the end falls on a Saturday, a Sunday or a public holiday, it moves to the next working day (CPC 142 al. 3, PA 20 al. 3).
- **Debt collection (LP)**: the same computation through LP 31. In addition, if the end falls within the féries (LP 56 ch. 2), it is extended to the **third working day** after the féries end; Saturdays, Sundays and holidays are not counted (LP 63). The féries are Easter −7…+7 (Palm Sunday to Quasimodo Sunday), 15–31 July and 18 Dec – 1 Jan. They do not suspend the deadline. There is no special case for poursuite pour effets de change.
- **Fixed and reception dates**: they are **not** moved off weekends; a warning says so, so the date shown is the earliest. Reception dates add `send_by`. This is the source's date when the card gives one (OFSP: 15.11 for 30.11). Otherwise it is N working days earlier, an Ordner heuristic that is stated as such. In both cases it moves back to a working day.

## Holidays (sources in `SOURCES`)

| Holiday | Source | Status |
|---|---|---|
| 1 August | Cst. 110 al. 3 | verified quote; the only federal holiday |
| Saturday | CPC 142 al. 3 / PA 20 al. 3 text | verified |
| Cantonal lists VD, ZH, BE, GE, TI | OFJ list "Jours fériés légaux ou considérés comme tels en Suisse" | **not verified**: the PDF returned HTTP 502 on 14.10.2026 |

The cantonal list depends on the canton (`context.canton` or `subject.canton`). Easter is computed with the anonymous Gregorian algorithm. Jeûne fédéral Monday falls after the 3rd Sunday of September, Jeûne genevois on the Thursday after the 1st Sunday. When the canton is unknown or not listed, only Saturday, Sunday and 1 August count, and a warning flags the date as the earliest possible (safe) one.

## Reminders and calendar

- Policies: `default` T-30/T-7/T-1, `short` T-3/T-1 (10-day deadlines), `reception` T-30/T-14/T-7/T-1, or a list of day offsets.
- `to_ics` returns an RFC 5545 VCALENDAR, CRLF, folded at 75 octets:
  - one all-day VEVENT per Deadline, with UID `<deadline id>@ordner.local`;
  - one VALARM DISPLAY per reminder, with an absolute UTC trigger at 08:00Z. When `Deadline.reminders` is empty, the default policy applies.
  - The DESCRIPTION gives the rule, the steps, the warnings and the bases. The caller writes the file locally; nothing is sent.

## Dossier checks

`completeness(card, subject, facts, documents, period)` compares `card.required_documents` with the documents received.
- **Year**: for the tax-year kinds (`YEAR_BOUND`: statements, salary, 3a and LPP certificates, assessment, instalments, invitation…), the document must be of the `period` year. A document of another year is listed in `wrong_year` and does not count. Other kinds are accepted whatever their year.
- **Statements**: `swiss_tax_statement_eCH0196` expands to one statement per declared institution. Institutions come from confirmed `finance.institutions` (list of `{"name"}` or strings), or from one fact per `finance.institutions.<x>`. Matching uses the normalized issuer name. An institution list that is undeclared or only proposed gives `missing_info`. A statement from an undeclared issuer is reported in `why`.
- **Waivers** (`WAIVERS`): `pillar3a_certificate` is not required when `pension.pillar3a.has` = false (confirmed); `pension_fund_certificate` likewise when `pension.lpp.affiliated` = false.
- **Required facts**: `card.required_facts` must have a confirmed fact (or a confirmed fact under `key.`). A fact that is only proposed is listed as missing.
- **Duplicates**: same sha256, or same kind, issuer and year.
- **Result**: `{"status": "complete"|"incomplete"|"missing_info", "missing_documents": [{"issuer", "kind", "year"}], "missing_facts", "wrong_year", "duplicates", "why"}`. If something is surely missing the status is `incomplete`; if only unknowns remain it is `missing_info`.

`consolidate(facts, period)` sums per measure (`total_tax_value`, `gross_revenue_a`, `gross_revenue_b`, `withholding_tax_claim`) the per-institution facts.
- **Accepted keys**: `tax.statement.<measure>.<institution>` (eCH-0196 connector) and `tax.securities.<institution>.<measure>` (seed). Position-level keys are ignored.
- **Institution matching**: an institution key is mapped to the declared name, by exact or prefix slug (`morvessa` → « Morvessa Banque SA »). Two sources for the same institution and measure are counted once: a confirmed fact beats a proposed one, then the latest wins.
- **Per measure**: `total` (exact Decimal sum), `status` = `confirmed` | `provisional` (a proposed input, or an included institution without a value) | `missing`, `by_institution`, `institutions_lacking`.
- **Top level**: `status` = `incomplete` (declared institution without a statement, or institutions unknown) | `provisional` | `final`, plus `institutions_included`, `institutions_missing` and `why`. Facts of several subjects raise `ValueError`.
