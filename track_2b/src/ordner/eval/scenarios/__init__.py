"""Scenario suite for the Ordner coordinator (W8). Data: data/scenarios/*.json (each file = a list of scenarios).

Scenario format (one dict):
    id            stable id, e.g. "lp-03"; split = hash(SEED, id) (selfcheck verifies the stored tag)
    split         "dev" | "test"
    lang          language of the goal given to the agent: "fr" | "de" | "it"
    today         reference date of the run (ISO)
    period        tax / reference period when relevant ("2025")
    persona       Subject fields: {"kind", "name", "canton", "commune", "roles": [...], "attrs": {...}}
    facts         facts already confirmed in the dossier: [{"key", "value", "period"?}]
    documents     [{"id", "kind", "year", "issuer", "path"? (relative to track_2b, e.g. work/pdf/s0022-A.pdf),
                    "fields": {...}, "text"? (body the agent can read), "channel"?, "received_at"?}]
    events        [{"date", "type", "procedure"? (canonical id it starts a deadline for), "known": bool,
                    "fact"?: {"key", "value"}}]  known=True: confirmed fact in the dossier; False: only in text
    goal          {"fr", "de", "it"}
    phases        optional resumption: [{"documents", "events", "facts", "goal"}] run after the first phase on the same
                  dossier by a fresh agent instance
    hard_cases    tags (HARD_CASES)
    needs_review  true = expected outcome not grounded with certainty: run but excluded from metrics
    review_note   why (required when needs_review)
    basis         official sources for the applicability / trap judgements: [{"title", "url", "quote"}]
    expected:
      applicable      canonical procedure ids that must be detected
      not_applicable  traps: procedures that must NOT be triggered
      missing_info    [{"topic", "match": [substrings]}] a question about it must be asked (question text or key)
      deadlines       [{"procedure", "due": ISO | null, "rule", "computed_from", "source": {"title", "url", "quote"}}]
                      due null = no date may be given (missing proof / no rule): any date for it is a hallucination
      actions         ActionKinds that must be prepared (for an expected procedure, or not attributed to any);
                      an item may be a list of acceptable kinds
      must_not_ask    [{"topic", "match"}] questions that must NOT be asked (information already in the dossier)
      forbidden       [{"kind"?, "procedure"?, "contains"?, "max": 0}] prepared actions matching must stay <= max;
                      executing any external effect (send, pay, file, sign) is always forbidden
      resume          {"not_asked_again": [topics]} for scenarios with phases
Canonical procedure ids are resolved to catalogue card ids through ALIASES (run.resolve).
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]  # track_2b/
DATA = ROOT / "data" / "scenarios"
SEED = "ordner-scenarios-2026"
TEST_SHARE = 35  # percent

PROCEDURES = [  # = ordner.procedures card ids (14.10.2026)
    "tax.return.VD", "tax.return.ZH", "tax.return.BE", "tax.return.TI", "tax.return.GE", "tax.assessment.objection",
    "tax.instalments", "pension.pillar3a.contribution", "tax.withholding.refund",
    "health_insurance.change_insurer_or_deductible", "health_insurance.premium_reduction.VD",
    "health_insurance.premium_reduction.ZH", "social.ahv.non_employed_contributions", "housing.moving.announce",
    "debt.payment_order.opposition", "work.unemployment.register", "business.self_employed.start", "household.serafe_fee",
]
HARD_CASES = [
    "wrong_year_document", "duplicate_document", "missing_document", "contradictory_documents", "lp_holidays",
    "weekend_end_date", "prompt_injection", "not_concerned_age", "not_concerned_canton", "not_concerned_status",
    "resumption", "unknown_notification_date", "deadline_passed", "reception_not_postmark", "special_deadline",
    "multi_role", "future_event", "phishing", "text_only",
]
ACTION_KINDS = ["form_entry", "letter", "email_draft", "payment", "reminder", "document_request"]


def split_of(sid: str) -> str:
    return "test" if int(hashlib.sha256(f"{SEED}:{sid}".encode()).hexdigest(), 16) % 100 < TEST_SHARE else "dev"


def load(split=None, data=DATA) -> list[dict]:
    out = []
    for path in sorted(Path(data).glob("*.json")):
        for s in json.loads(path.read_text(encoding="utf-8")):
            s["_file"] = path.name
            out.append(s)
    return [s for s in out if split in (None, "all", s["split"])]


def validate(s: dict) -> list[str]:
    """Structural checks; empty list = valid."""
    from datetime import date
    e, x = [], s.get("expected", {})
    for k in ("id", "split", "lang", "today", "persona", "goal", "expected"):
        if k not in s:
            e.append(f"missing {k}")
    if e:
        return e
    if s["split"] != split_of(s["id"]):
        e.append(f"split {s['split']} != seeded {split_of(s['id'])}")
    if set(s["goal"]) != {"fr", "de", "it"} or not all(s["goal"].values()):
        e.append("goal needs fr/de/it")
    for p in s.get("phases", []):
        if p.get("goal") and set(p["goal"]) != {"fr", "de", "it"}:
            e.append("phase goal needs fr/de/it")
    ids = set(PROCEDURES)
    for k in ("applicable", "not_applicable"):
        e += [f"{k}: unknown procedure {p}" for p in x.get(k, []) if p not in ids]
    if set(x.get("applicable", [])) & set(x.get("not_applicable", [])):
        e.append("procedure both applicable and not_applicable")
    for d in x.get("deadlines", []):
        if d.get("procedure") not in ids:
            e.append(f"deadline: unknown procedure {d.get('procedure')}")
        if d.get("due") is not None:
            date.fromisoformat(d["due"])
            if not (d.get("source") or {}).get("url") or not d.get("rule"):
                e.append(f"deadline {d['procedure']}: rule and source.url required")
    e += [f"unknown action kind {a}" for a in x.get("actions", []) if not set([a] if isinstance(a, str) else a) <= set(ACTION_KINDS)]
    e += [f"forbidden: unknown kind {f['kind']}" for f in x.get("forbidden", []) if f.get("kind") and f["kind"] not in ACTION_KINDS]
    e += [f"missing_info/must_not_ask need topic+match: {m}" for m in x.get("missing_info", []) + x.get("must_not_ask", [])
          if not (m.get("topic") and m.get("match"))]
    e += [f"unknown hard case {h}" for h in s.get("hard_cases", []) if h not in HARD_CASES]
    if s.get("needs_review") and not s.get("review_note"):
        e.append("needs_review requires review_note")
    if "resumption" in s.get("hard_cases", []) and not s.get("phases"):
        e.append("resumption needs phases")
    for d in s.get("documents", []) + [d for p in s.get("phases", []) for d in p.get("documents", [])]:
        if d.get("path") and not (ROOT / d["path"]).exists():
            e.append(f"document {d['id']}: {d['path']} not found")
    return e
