"""Procedure catalogue: ProcedureCard JSON files in procedures/cards/<card id>.json, loader and validator.

Card file = the ProcedureCard fields as JSON (schema.py); `deadline` is {"id", "params"} or null, `sources` a list of
{"title", "url", "quote", "verified", "accessed"}. Unknown keys are errors (typos would otherwise be silently lost).

Traceability: any "sources": [i, ...] key in a step or anywhere in deadline.params = indexes into card.sources, so
every rule points at the verbatim quote that supports it (validated recursively).

Applicability condition language (this module checks the syntax; ordner.rules evaluates it, see rules/README.md):
    {}                                       always applicable
    {"all": [c, ...]}  {"any": [c, ...]}  {"not": c}
    {"role": "salaried"}                     "salaried" in subject.roles
    {"attr": "canton", "eq": "VD"}           Subject field (kind, canton, commune) or key of subject.attrs;
                                             computed attrs: "age" (at evaluation date), "age_at_year_end"
    {"fact": "tax.assessment.notified_on", "exists": true}   latest confirmed Fact with this key
Leaf operators (exactly one per attr/fact leaf): eq, ne, in (list), gte, gt, lte, lt, exists (bool).
Example: {"all": [{"attr": "canton", "eq": "VD"}, {"role": "salaried"}]}

Deadline rule ids: ordner.rules.DEADLINE_RULE_IDS when importable, else DEADLINE_RULES (params: rules/README.md):
    fixed_date, reception_by  {"month", "day", "year_offset"?}  int month/day required (relative to the period year)
    days_after_notification   {"days"}                          counted from the proven notification date
    cantonal_table            {"table": {"VD": {fixed_date params, "sources"}, ...}}
    year_end                  {}                                31.12 of the period
Informational params: "extensions": [{"until": "MM-DD", "fee_chf" (null if unknown), "how", "request_by"?, "sources"}],
"cantonal": {"VD": {"rule": str, "sources": [i]}} (verified canton specifics of a federal card).

Qualification: "qualified" only if every source is verified (quote found word for word in the fetched page);
anything else is "draft" or "unknown" and must say why in `notes`.
"""
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import get_args

from ordner.core.schema import ActionKind, DeadlineRule, Nature, ProcedureCard, Qualification, Source

CARDS_DIR = Path(__file__).parent / "cards"

DEADLINE_RULES = ["fixed_date", "days_after_notification", "reception_by", "cantonal_table", "year_end"]
DOMAINS = ["tax", "health_insurance", "pension", "social", "housing", "debt", "work", "business", "identity"]
CANTONS = ("AG AI AR BE BL BS FR GE GL GR JU LU NE NW OW SG SH SO SZ TG TI UR VD VS ZG ZH").split()
LANGS = ("fr", "de", "it")
OPS = {"eq", "ne", "in", "gte", "gt", "lte", "lt", "exists"}
FIELDS = set(ProcedureCard.__dataclass_fields__)
SOURCE_FIELDS = set(Source.__dataclass_fields__)
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def deadline_rule_ids() -> list[str]:
    try:
        from ordner.rules import DEADLINE_RULE_IDS
        return list(DEADLINE_RULE_IDS)
    except ImportError:
        return DEADLINE_RULES


def from_dict(d: dict) -> ProcedureCard:
    d = dict(d)
    d["sources"] = [Source(**s) for s in d.get("sources", [])]
    if d.get("deadline"):
        d["deadline"] = DeadlineRule(**d["deadline"])
    return ProcedureCard(**d)


@lru_cache(maxsize=1)
def _all() -> dict[str, ProcedureCard]:
    cards = {}
    for path in sorted(CARDS_DIR.glob("*.json")):
        card = from_dict(json.loads(path.read_text(encoding="utf-8")))
        if card.id != path.stem:
            raise ValueError(f"{path.name}: id {card.id!r} must match the file name")
        cards[card.id] = card
    return cards


def load_cards(jurisdiction=None) -> list[ProcedureCard]:
    """All cards; with a canton code, that canton's cards plus the federal ("CH") ones that apply everywhere."""
    cards = _all().values()
    if jurisdiction:
        cards = [c for c in cards if c.jurisdiction in (jurisdiction, "CH")]
    return list(cards)


def get(card_id) -> ProcedureCard:
    return _all()[card_id]


def _langs(value, where) -> list[str]:
    if not isinstance(value, dict):
        return [f"{where}: must be a {{fr, de, it}} dict"]
    return [f"{where}: missing or empty '{lang}'" for lang in LANGS if not str(value.get(lang) or "").strip()]


def _condition(c, where) -> list[str]:
    if not isinstance(c, dict):
        return [f"{where}: condition must be a dict"]
    if not c:
        return []
    if "all" in c or "any" in c:
        key = "all" if "all" in c else "any"
        if len(c) != 1 or not isinstance(c[key], list):
            return [f"{where}: '{key}' takes a list and nothing else"]
        return [e for i, sub in enumerate(c[key]) for e in _condition(sub, f"{where}.{key}[{i}]")]
    if "not" in c:
        return [f"{where}: 'not' takes one condition"] if len(c) != 1 else _condition(c["not"], f"{where}.not")
    if "role" in c:
        return [] if len(c) == 1 and isinstance(c["role"], str) else [f"{where}: role leaf is {{'role': str}}"]
    subject = [k for k in ("attr", "fact") if k in c]
    ops = set(c) - {"attr", "fact"}
    if len(subject) != 1 or not isinstance(c[subject[0]], str):
        return [f"{where}: leaf needs exactly one of all/any/not/role/attr/fact, got {sorted(c)}"]
    if len(ops) != 1 or not ops <= OPS:
        return [f"{where}: {subject[0]} leaf needs exactly one operator of {sorted(OPS)}, got {sorted(ops)}"]
    op = ops.pop()
    if op == "in" and not isinstance(c[op], list):
        return [f"{where}: 'in' takes a list"]
    if op == "exists" and not isinstance(c[op], bool):
        return [f"{where}: 'exists' takes true/false"]
    return []


def _source_refs(obj, n, where) -> list[str]:
    """Every "sources" key found anywhere in obj must list indexes into card.sources."""
    if isinstance(obj, list):
        return [e for i, v in enumerate(obj) for e in _source_refs(v, n, f"{where}[{i}]")]
    if not isinstance(obj, dict):
        return []
    errors = [e for k, v in obj.items() if k != "sources" for e in _source_refs(v, n, f"{where}.{k}")]
    refs = obj.get("sources", [])
    if not isinstance(refs, list) or not all(isinstance(i, int) and 0 <= i < n for i in refs):
        errors.append(f"{where}: 'sources' must list indexes into card.sources (0..{n - 1})")
    return errors


def validate(card) -> list[str]:
    """Schema checks on a ProcedureCard or its JSON dict. Empty list = valid."""
    if isinstance(card, dict):
        unknown = set(card) - FIELDS
        missing = {"id", "name", "domain", "nature", "jurisdiction", "applicability"} - set(card)
        if unknown or missing:
            return [m for m in (unknown and f"unknown fields {sorted(unknown)}", missing and f"missing fields {sorted(missing)}") if m]
        bad = [i for i, s in enumerate(card.get("sources") or []) if not isinstance(s, dict) or set(s) - SOURCE_FIELDS]
        if bad:
            return [f"sources{bad}: must be dicts with keys from {sorted(SOURCE_FIELDS)}"]
        try:
            card = from_dict(card)
        except TypeError as e:
            return [str(e)]
    errors = []
    if not isinstance(card.id, str) or not re.fullmatch(r"[a-z0-9_]+(\.[a-z0-9_]+)*(\.[A-Z]{2})?", card.id):
        errors.append(f"id {card.id!r}: dotted lowercase, optional canton suffix (e.g. tax.return.VD)")
    errors += _langs(card.name, "name")
    if card.domain not in DOMAINS:
        errors.append(f"domain {card.domain!r} not in {DOMAINS}")
    if card.nature not in get_args(Nature):
        errors.append(f"nature {card.nature!r} not in {get_args(Nature)}")
    if card.jurisdiction != "CH" and card.jurisdiction not in CANTONS:
        errors.append(f"jurisdiction {card.jurisdiction!r}: 'CH' or a canton code")
    errors += _condition(card.applicability, "applicability")
    for f in ("required_facts", "required_documents", "outputs"):
        v = getattr(card, f)
        if not isinstance(v, list) or not all(isinstance(x, str) and x for x in v):
            errors.append(f"{f}: list of non-empty strings")
    if not card.outputs:
        errors.append("outputs: say what closes the case (receipt, decision, payment)")
    n = len(card.sources)
    if card.deadline is not None:
        if card.deadline.id not in deadline_rule_ids():
            errors.append(f"deadline.id {card.deadline.id!r} not in {deadline_rule_ids()}")
        if not isinstance(card.deadline.params, dict):
            errors.append("deadline.params: dict")
        else:
            p = card.deadline.params
            entries = {"params": p}
            if card.deadline.id == "cantonal_table":
                table = p.get("table")
                if not isinstance(table, dict) or not table:
                    errors.append("deadline.params.table: {canton: fixed_date params}")
                    table = {}
                entries = {f"table.{k}": v if isinstance(v, dict) else {} for k, v in table.items()}
            need = {"fixed_date": ("month", "day"), "reception_by": ("month", "day"), "cantonal_table": ("month", "day"),
                    "days_after_notification": ("days",)}.get(card.deadline.id, ())
            errors += [f"deadline.{w}.{k}: int required" for w, e in entries.items() for k in need if not isinstance(e.get(k), int)]
            errors += _source_refs(p, n, "deadline.params")
    if not card.steps:
        errors.append("steps: at least one step")
    seen = set()
    for i, step in enumerate(card.steps):
        where = f"steps[{i}]"
        if not isinstance(step, dict) or not step.get("id"):
            errors.append(f"{where}: dict with an 'id'")
            continue
        if step["id"] in seen:
            errors.append(f"{where}: duplicate id {step['id']!r}")
        seen.add(step["id"])
        errors += _langs(step.get("label"), f"{where}.label")
        if step.get("who") not in ("user", "ordner"):
            errors.append(f"{where}.who: 'user' or 'ordner'")
        if "action" in step and step["action"] not in get_args(ActionKind):
            errors.append(f"{where}.action {step['action']!r} not in {get_args(ActionKind)}")
        errors += _source_refs(step, n, where)
    if not card.sources:
        errors.append("sources: at least one official source")
    for i, s in enumerate(card.sources):
        if not s.title or not str(s.url).startswith(("https://", "http://")):
            errors.append(f"sources[{i}]: title and http(s) url required")
        if s.verified and not (s.quote or "").strip():
            errors.append(f"sources[{i}]: verified=True needs the verbatim quote")
        if s.accessed is not None and not DATE.match(s.accessed):
            errors.append(f"sources[{i}].accessed: YYYY-MM-DD")
    if card.qualification not in get_args(Qualification):
        errors.append(f"qualification {card.qualification!r} not in {get_args(Qualification)}")
    if card.qualification == "qualified" and not (card.sources and all(s.verified for s in card.sources)):
        errors.append("qualification 'qualified' requires every source verified")
    if card.qualification != "qualified" and not (card.notes or "").strip():
        errors.append("notes: say what is not verified (draft/unknown card)")
    for f in ("valid_from", "valid_to"):
        v = getattr(card, f)
        if v is not None and not DATE.match(str(v)):
            errors.append(f"{f}: YYYY-MM-DD")
    return [e for e in errors if e]
