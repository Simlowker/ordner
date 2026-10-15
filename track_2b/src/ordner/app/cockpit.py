"""Cockpit API on top of the parallel workstreams (ordner.case, .procedures, .rules, .agent).

Every module is imported lazily: a missing one becomes an explicit « module pas encore disponible » state
(`Unavailable`, served as HTTP 503), never a crash. Nothing here sends, files or pays anything.

    PYTHONPATH=src python -m ordner.app.cockpit     # self-check (pure functions, no module needed)
"""
import importlib
import os
import sys
import threading
from dataclasses import asdict, is_dataclass
from datetime import date
from email.message import EmailMessage
from typing import get_args

from ordner.core.labels import labels
from ordner.core.schema import Action, CaseState, Deadline, ProcedureCard, Subject, new_id

STATES = list(get_args(CaseState))
DONE = {"result_verified", "closed"}
DOMAINS = ("tax", "health_insurance", "pension", "social", "housing", "debt", "work", "business", "identity")
CANTONS = ("AG", "AI", "AR", "BE", "BL", "BS", "FR", "GE", "GL", "GR", "JU", "LU", "NE",
           "NW", "OW", "SG", "SH", "SO", "SZ", "TG", "TI", "UR", "VD", "VS", "ZG", "ZH")
URGENT_DAYS = 30
RED = 0.5
STATEMENT = "swiss_tax_statement_eCH0196"
MODULES = {"case": "ordner.case.store", "seed": "ordner.case.demo_seed", "procedures": "ordner.procedures.catalog",
           "rules": "ordner.rules", "agent": "ordner.agent.coordinator", "llm": "ordner.agent.llm",
           "drafts": "ordner.connectors.email_drafts"}
SIMULATED = os.environ.get("ORDNER_TODAY") or None   # demo date, e.g. 2026-02-20
if SIMULATED:
    date.fromisoformat(SIMULATED)  # fail at startup on a malformed date


def today_():
    return date.fromisoformat(SIMULATED) if SIMULATED else date.today()
_lock = threading.Lock()


class Unavailable(Exception):
    """A workstream module is not there (yet)."""


class NotFound(Exception):
    pass


def opt(key):
    name = MODULES[key]
    if name not in sys.modules:
        importlib.invalidate_caches()  # modules land while the server runs
    try:
        return importlib.import_module(name)
    except Exception as e:  # a module mid-write must not take the console down
        if not isinstance(e, ModuleNotFoundError):
            sys.stderr.write(f"cockpit: {name}: {e!r}\n")
        return None


def need(key):
    m = opt(key)
    if m is None:
        raise Unavailable(MODULES[key])
    return m


def plain(x):
    return asdict(x) if is_dataclass(x) else x


def modules():
    probe = {"case": "Store", "seed": "seed", "procedures": "load_cards", "rules": "applicable", "agent": "run",
             "llm": "OpenAICompat", "drafts": "render"}
    return {k: hasattr(opt(k), attr) for k, attr in probe.items()}


def llm_client():
    """The model client handed to coordinator.run (LLM_BASE_URL, LLM_NAME, LLM_API_KEY), or (None, reason)."""
    if not os.environ.get("LLM_BASE_URL"):
        return None, "no_endpoint"
    if opt("agent") is None or not hasattr(opt("agent"), "run"):
        return None, "no_agent"
    client = getattr(opt("llm"), "OpenAICompat", None)
    if client is None:
        return None, "no_client"
    return client(os.environ["LLM_BASE_URL"], os.environ.get("LLM_NAME") or "default",
                  os.environ.get("LLM_API_KEY") or None), None


_store = None


def store():
    """One Store for the process (W1's Store is thread-safe); seeds the demo persona into an empty dossier."""
    global _store
    with _lock:
        if _store is None:
            _store = need("case").Store()
        if not _store.subjects() and (seed := getattr(opt("seed"), "seed", None)):
            sid = seed(_store)
            try:
                review_dossier(sid, s=_store)
            except Unavailable:  # no rules or catalogue yet: the dossier stays without cases
                pass
    return _store


def _get(fn, key):
    try:
        x = fn(key)
    except (KeyError, LookupError):
        x = None
    if x is None:
        raise NotFound(key)
    return x


def _visible(s, subject_id, today):
    """Documents received by `today` and the facts they did not produce later (matters only with ORDNER_TODAY)."""
    docs, facts = s.documents(subject_id), s.facts(subject_id)
    late = {d.id for d in docs if (d.received_at or "")[:10] > today.isoformat()}
    return [d for d in docs if d.id not in late], [f for f in facts if f.source_doc not in late]


def card_info(card_id):
    cat = opt("procedures")
    if cat:
        try:
            return plain(cat.get(card_id))
        except Exception:  # unknown card id
            pass
    return {"id": card_id, "name": {}, "domain": None, "nature": None, "jurisdiction": None,
            "qualification": "unknown", "steps": [], "sources": [], "required_facts": [], "unknown_card": True}


def brief(card):
    return {k: card.get(k) for k in ("id", "name", "domain", "nature", "jurisdiction", "qualification")}


def _due(d):
    try:
        return date.fromisoformat(str(d.get("due"))[:10])
    except ValueError:
        return None


def nearest_due(case):
    dues = [x for x in map(_due, case.get("deadlines") or []) if x]
    return min(dues) if dues else None


def urgent(cases, today, days=URGENT_DAYS):
    out = []
    for c in cases:
        if c["state"] in DONE:
            continue
        for d in c.get("deadlines") or []:
            due = _due(d)
            if due and (due - today).days <= days:
                out.append({"case_id": c["id"], "card": c.get("card"), "due": due.isoformat(), "days": (due - today).days,
                            "rule_id": d.get("rule_id"), "reminders": d.get("reminders") or []})
    return sorted(out, key=lambda u: u["due"])


def red_documents(docs):
    out = []
    for d in docs:
        red = sorted(f for f, p in (d.get("doubt") or {}).items() if p is not None and p >= RED)
        if red:
            out.append({"id": d["id"], "kind": d.get("kind"), "year": d.get("year"), "issuer": d.get("issuer"), "fields": red})
    return out


def _case_step(c):
    due = nearest_due(c)
    base = {"case_id": c["id"], "card": c.get("card"), "state": c["state"], "due": due.isoformat() if due else None}
    action = next((a for a in c.get("actions") or [] if a.get("status") == "prepared" and a.get("requires_validation", True)), None)
    if action:
        return {**base, "kind": "validate", "action_id": action["id"], "action_kind": action.get("kind"),
                "summary": (action.get("payload") or {}).get("summary")}
    if c.get("missing"):
        return {**base, "kind": "provide", "items": c["missing"]}
    if c["state"] == "to_qualify":
        return {**base, "kind": "qualify"}
    return None


def split_missing(open_cases, coverage):
    """(to qualify, missing): procedures whose applicability is still unknown (questions to answer first, then the
    pieces they would need) apart from procedures that apply and genuinely miss documents or information."""
    app = {i["id"]: i for i in (coverage or {}).get("items") or []} if (coverage or {}).get("rules") else None
    qualify, missing = [], []
    for c in open_cases:
        items = c.get("missing") or []
        if app is None:  # no rules engine: subject attributes are the questions
            questions = [i for i in items if i.startswith("subject.")]
        else:
            a = app.get(c["card_id"], {})
            questions = a.get("missing") or [] if a.get("applicability") == "missing_info" else []
        rest = [i for i in items if i not in questions]
        entry = {"case_id": c["id"], "card": c.get("card"), "items": rest}
        if questions:
            qualify.append({**entry, "questions": questions})
        elif rest:
            missing.append(entry)
    return qualify, missing


def payment_alerts(docs, facts):
    """Payment requests (QR-bill, e-mail) that ordner.rules.payment_check finds suspicious: unseen IBAN or creditor,
    urgency with a link."""
    check = getattr(opt("rules"), "payment_check", None)
    out = []
    for d in docs if check else ():
        fields = d.fields or {}
        if d.kind in ("qr_bill_invoice", "email") or fields.get("iban"):
            r = check(fields, docs, facts, d.id)
            if r["suspicious"]:
                out.append({"id": d.id, "kind": d.kind, "year": d.year, "issuer": d.issuer, "warning": r["warning"],
                            "reasons": r["reasons"], "iban": r["iban"]})
    return out


def next_step(cases, docs, today):
    """One step: an urgent case first, then red pieces to re-read, then the nearest case with something to do;
    obligations before rights and options (the person decides whether to pursue those)."""
    obligation_first = lambda c: ((c.get("card") or {}).get("nature") not in ("obligation", None), nearest_due(c) or date.max)
    open_cases = sorted((c for c in cases if c["state"] not in DONE), key=obligation_first)
    steps = [(c, s) for c in open_cases if (s := _case_step(c))]
    urgent_steps = [st for c, st in steps if (due := nearest_due(c)) and (due - today).days <= URGENT_DAYS]
    if urgent_steps:
        return urgent_steps[0]
    if red := red_documents(docs):
        return {"kind": "review", "document": red[0]}
    return steps[0][1] if steps else None


def classify(cards, subject, facts, applicable=None):
    """Coverage of one subject: which procedures were examined, which are covered, which stay to verify."""
    canton = subject.canton
    items = []
    for card in cards:
        if card.jurisdiction not in ("CH", canton):
            continue
        try:
            app = applicable(card, subject, facts) if applicable else {"status": "unknown"}
        except Exception as e:  # a broken rule must stay visible, not kill the home page
            sys.stderr.write(f"cockpit: applicable({card.id}): {e!r}\n")
            app = {"status": "error"}
        status = app.get("status", "unknown")
        verdict = ("not_applicable" if status == "not_applicable" and card.qualification == "qualified"
                   else "covered" if status == "applicable" and card.qualification == "qualified" else "to_verify")
        items.append({**brief(plain(card)), "applicability": status, "missing": app.get("missing") or [],
                      "why": app.get("why") or [], "verdict": verdict})
    seen = {i["domain"] for i in items}
    counts = {v: sum(i["verdict"] == v for i in items) for v in ("covered", "to_verify", "not_applicable")}
    return {"available": True, "canton": canton, "rules": applicable is not None, "items": items, "counts": counts,
            "domains_without_card": [d for d in DOMAINS if d not in seen]}


def grid(cards):
    rank = {"qualified": 2, "draft": 1, "unknown": 1}
    cells, domains = {}, list(DOMAINS)
    for c in map(plain, cards):
        if c["domain"] not in domains:
            domains.append(c["domain"])
        cell = cells.setdefault(c["domain"], {}).setdefault(c["jurisdiction"], {"rank": 0, "cards": []})
        cell["rank"] = max(cell["rank"], rank.get(c.get("qualification"), 1))
        cell["cards"].append({"id": c["id"], "name": c.get("name") or {}, "qualification": c.get("qualification")})
    for row in cells.values():
        for cell in row.values():
            cell["status"] = "qualified" if cell.pop("rank") == 2 else "draft"
    return {"domains": domains, "jurisdictions": ["CH", *CANTONS], "cells": cells,
            "counts": {s: sum(c["status"] == s for r in cells.values() for c in r.values()) for s in ("qualified", "draft")}}


# --- endpoints -------------------------------------------------------------------------------------------------

def subjects():
    return {"subjects": [plain(x) for x in store().subjects()]}


def _with_cards(cases):
    out = []
    for c in map(plain, cases):
        out.append({**c, "card": brief(card_info(c["card_id"]))})
    return out


def coverage_for(subject, facts, today):
    cat = opt("procedures")
    if cat is None:
        return {"available": False, "module": MODULES["procedures"]}
    fn = getattr(opt("rules"), "applicable", None)
    return classify(cat.load_cards(), subject, facts, fn and (lambda c, s, f: fn(c, s, f, on=today)))


def wealth(facts, today):
    """Consolidated per-institution tax-statement totals for last year (ordner.rules.consolidate)."""
    fn = getattr(opt("rules"), "consolidate", None)
    if fn is None:
        return {"available": False, "module": "ordner.rules.consolidate"}
    try:
        return {"available": True, **fn(facts, str(today.year - 1))}
    except ValueError as e:  # e.g. facts of several subjects
        sys.stderr.write(f"cockpit: consolidate: {e!r}\n")
        return {"available": False, "module": "ordner.rules.consolidate"}


def overview(subject_id, today=None):
    today = today or today_()
    s = store()
    subject = _get(s.get_subject, subject_id)
    docs_raw, facts = _visible(s, subject_id, today)
    docs = [plain(d) for d in docs_raw]
    cases = _with_cards(s.cases(subject_id=subject_id))
    open_cases = [c for c in cases if c["state"] not in DONE]
    coverage = coverage_for(subject, facts, today)
    qualify, missing = split_missing(open_cases, coverage)
    alerts = payment_alerts(docs_raw, facts)
    keys = ([k for c in cases for k in c.get("missing") or []] + [k for i in coverage.get("items") or [] for k in i["missing"]]
            + [a["kind"] for a in alerts if a["kind"]])
    return {"today": today.isoformat(), "simulated": bool(SIMULATED), "subject": plain(subject), "documents": docs,
            "cases": cases, "urgent": urgent(cases, today), "review": red_documents(docs), "payment_alerts": alerts,
            "next_step": next_step(cases, docs, today), "wealth": wealth(facts, today),
            "to_qualify": qualify, "missing": missing, "labels": labels(keys), "coverage": coverage}


def case_detail(case_id, today=None):
    today = today or today_()
    s = store()
    case = plain(_get(s.get_case, case_id))
    card = card_info(case["card_id"])
    for d in case.get("deadlines") or []:
        d["days"] = (_due(d) - today).days if _due(d) else None
    docs_raw, facts_raw = _visible(s, case["subject_id"], today)
    check = getattr(opt("rules"), "completeness", None)
    completeness = (check(card, s.get_subject(case["subject_id"]), facts_raw, docs_raw, case.get("period"), today=today)
                    if check and not card.get("unknown_card") else None)
    docs = {d["id"]: {k: d.get(k) for k in ("kind", "year", "issuer", "read_path")} for d in map(plain, docs_raw)}
    keys, kinds, dom = card.get("required_facts") or [], set(card.get("required_documents") or []), card.get("domain")

    def linked(f):  # ponytail: key/domain/document heuristic, an explicit case<->fact link in W1 if this misleads
        k = f["key"]
        return (any(k == r or k.startswith(r + ".") for r in keys) or (dom and k.startswith(dom + "."))
                or docs.get(f.get("source_doc"), {}).get("kind") in kinds)
    facts = [f for f in map(plain, facts_raw) if not case.get("period") or f.get("period") in (None, case["period"])]
    shown = {f["key"] for f in facts if linked(f)}  # a linked key brings its whole history (e.g. the person's correction)
    facts = [f for f in facts if f["key"] in shown]
    events = sorted((plain(e) for e in s.events(case_id=case_id)), key=lambda e: e.get("ts") or "")
    known = getattr(opt("rules"), "SOURCES", {})
    basis = {k for d in case.get("deadlines") or [] for k in (d.get("computed_from") or {}).get("legal_basis") or []}
    return {"today": today.isoformat(), "case": case, "card": card, "facts": facts, "documents": docs,
            "events": events, "states": STATES, "rule_sources": {k: known[k] for k in basis if k in known},
            "completeness": completeness, "labels": labels([*(case.get("missing") or []), *(f["key"] for f in facts)])}


def _schedule(card, subject, docs, today, rules):
    """(period, computed deadline | None). The year the documents point to (latest year among the kinds the card
    needs) when its deadline is ahead, or when the card is an obligation (a passed deadline is shown, never skipped);
    otherwise the first period whose deadline is still ahead; otherwise last year."""
    def compute(y):
        try:
            return rules.compute_deadline(card.deadline, subject, {"period": str(y), "label": card.name.get("fr", card.id)})
        except ValueError as e:  # rule id unknown to this rules version
            return {"status": "error", "error": str(e)}
    years = [d.year for d in docs if d.kind in (card.required_documents or []) and d.year]
    if not card.deadline:
        return str(max(years) if years else today.year - 1), None
    if years:
        dl = compute(max(years))
        if dl.get("status") != "computed" or dl["due"] >= today.isoformat() or card.nature == "obligation":
            return str(max(years)), dl if dl.get("status") == "computed" else None
    for y in range(today.year - 1, today.year + 2):
        dl = compute(y)
        if dl.get("status") != "computed":
            return str(today.year - 1), None  # needs an input the dossier does not have (e.g. a notification date)
        if dl["due"] >= today.isoformat():
            return str(y), dl
    return str(today.year - 1), None


def review_dossier(subject_id, today=None, s=None):
    """Periodic review (transversal path 2, no model): compare the subject to the catalogue and open the expected
    cases with their next deadline, reminders and missing pieces. Idempotent (Store dedups cases and deadlines)."""
    today = today or today_()
    s = s or store()
    rules, cat = need("rules"), need("procedures")
    subject = _get(s.get_subject, subject_id)
    docs, facts = _visible(s, subject_id, today)
    opened = []
    for card in cat.load_cards():
        if card.jurisdiction not in ("CH", subject.canton):
            continue
        period, dl = _schedule(card, subject, docs, today, rules)
        app = rules.applicable(card, subject, facts, on=today, period=period)
        if app["status"] == "not_applicable":
            continue
        case = s.open_case(subject_id, card.id, period, actor="rule")
        if dl:
            s.add_deadline(Deadline(new_id("dl"), case.id, dl["due"], card.deadline.id,
                                    {**dl["computed_from"], **{k: dl[k] for k in ("send_by", "extensions") if k in dl}},
                                    rules.reminders(dl["due"], today=today)))
        comp = rules.completeness(card, subject, facts, docs, period, today=today)  # waivers, wrong year, per-bank, not yet issued
        missing = [f"{m['kind']}:{m['issuer']}" if m.get("issuer") else m["kind"] for m in comp["missing_documents"]]
        missing = list(dict.fromkeys(missing + comp["missing_facts"] + list(app.get("missing") or [])))
        s.set_missing(case.id, missing, actor="rule")
        if s.get_case(case.id).state == "to_qualify":
            s.set_state(case.id, "missing_documents" if missing else "ready_to_prepare", actor="rule")
        if s.get_case(case.id).state not in DONE:
            for m in comp["missing_documents"]:
                if m["kind"] == STATEMENT and m.get("issuer"):
                    _request_statement(s, case.id, subject, m["issuer"], period)
        opened.append(case.id)
    return {"cases": opened}


def _request_statement(s, case_id, subject, issuer, period):
    """Prepare (never send) the request of a missing eCH-0196 statement, with the email_drafts letter."""
    for c in s.cases(subject_id=subject.id):  # one request per bank and year, even if several cases need it
        if any(a.payload.get("issuer") == issuer and a.payload.get("vars", {}).get("year") == period
               and a.status != "cancelled" for a in c.actions):
            return
    vars_ = {"year": period, "sender_name": subject.name, "recipient_name": issuer, "place": subject.commune or ""}
    payload = {"template": "bank_document_request", "vars": vars_, "issuer": issuer, "kind": STATEMENT,
               "summary": {"fr": f"Demander le relevé fiscal {period} (eCH-0196) à {issuer}",
                           "de": f"Steuerausweis {period} (eCH-0196) bei {issuer} anfordern",
                           "it": f"Chiedere l'estratto fiscale {period} (eCH-0196) a {issuer}"}}
    if ed := opt("drafts"):
        r = ed.render("bank_document_request", vars_)
        payload.update(subject=r["subject"], body=r["body"], missing_vars=r["missing"])
    s.add_action(Action(new_id("act"), case_id, "document_request", payload), actor="ordner")  # idempotent on payload


def eml(case_id, action_id):
    """The .eml draft of a validated action: same headers as email_drafts.draft, in memory, no PDF. Never sent."""
    case = _get(store().get_case, case_id)
    a = next((x for x in case.actions if x.id == action_id), None)
    if a is None or not a.payload.get("template"):
        raise NotFound(action_id)
    if a.status in ("prepared", "cancelled"):
        raise ValueError("only a validated action has a draft to download")
    r = need("drafts").render(a.payload["template"], a.payload.get("vars", {}))
    msg = EmailMessage()
    if a.payload.get("to"):
        msg["To"] = a.payload["to"]
    msg["Subject"] = r["subject"]
    msg["X-Unsent"] = "1"
    msg["X-Ordner-Action"] = a.id
    msg["X-Ordner-Status"] = "draft, never sent by Ordner"
    msg.set_content(r["body"])
    return bytes(msg), "message/rfc822", f"{a.id}.eml"


def review(subject_id):
    review_dossier(subject_id)
    return overview(subject_id)


def validate_action(case_id, action_id):
    """Records the person's validation. Never sends, files or pays: the person acts herself."""
    s = store()
    case = _get(s.get_case, case_id)
    action = next((a for a in case.actions if a.id == action_id), None)
    if action is None:
        raise NotFound(action_id)
    if action.status != "prepared":
        raise ValueError(f"action is {action.status}, only a prepared action can be validated")
    s.update_action(action_id, "validated")
    return case_detail(case_id)


def coverage_map():
    return grid(need("procedures").load_cards())


def calendar(subject_id):
    to_ics = getattr(need("rules"), "to_ics", None)
    if to_ics is None:
        raise Unavailable("ordner.rules.to_ics")
    s = store()
    subject = _get(s.get_subject, subject_id)
    return to_ics([d for c in s.cases(subject_id=subject_id) for d in c.deadlines], subject)


def ask(subject_id, question):
    llm, reason = llm_client()
    if llm is None:
        raise Unavailable(reason)
    result = need("agent").run(question, subject_id, llm, store(), ctx={"today": today_().isoformat()})
    return {"mode": "live", "model": os.environ.get("LLM_NAME") or None, "result": plain(result)}


if __name__ == "__main__":
    from ordner.core.schema import Action, Case, Deadline

    today = date(2026, 10, 14)
    tax = Case("c1", "s", "tax.return.VD", state="missing_documents", missing=["salary_certificate"],
               deadlines=[Deadline("d1", "c1", "2026-11-01", "fixed_date")])
    lamal = Case("c2", "s", "health.subsidy.VD", state="ready_to_validate",
                 deadlines=[Deadline("d2", "c2", "2027-01-31", "fixed_date")],
                 actions=[Action("a1", "c2", "letter", {}), Action("a2", "c2", "payment", {}, status="validated")])
    done = Case("c3", "s", "x", state="closed", deadlines=[Deadline("d3", "c3", "2026-10-01", "fixed_date")])
    cases = [plain(c) for c in (lamal, tax, done)]
    docs = [{"id": "doc1", "doubt": {"amount": 0.7, "iban": 0.1}}, {"id": "doc2", "doubt": {}}]

    u = urgent(cases, today)
    assert [(x["case_id"], x["days"]) for x in u] == [("c1", 18)], u
    assert red_documents(docs) == [{"id": "doc1", "kind": None, "year": None, "issuer": None, "fields": ["amount"]}]
    assert next_step(cases, docs, today)["kind"] == "provide"                       # urgent case first
    assert next_step(cases, docs, date(2026, 9, 1))["kind"] == "review"             # nothing urgent: red piece
    assert next_step(cases, [], date(2026, 9, 1))["case_id"] == "c1"                # nothing red: nearest case
    assert next_step([cases[0]], [], today) == {"case_id": "c2", "card": None, "state": "ready_to_validate",
                                                "due": "2027-01-31", "kind": "validate", "action_id": "a1",
                                                "action_kind": "letter", "summary": None}
    assert next_step([plain(done)], [], today) is None

    card = lambda i, dom, jur, q: ProcedureCard(i, {"fr": i}, dom, "obligation", jur, {}, qualification=q)
    cards = [card("tax.return.VD", "tax", "VD", "qualified"), card("tax.return.GE", "tax", "GE", "qualified"),
             card("avs.non_active", "social", "CH", "draft"), card("health.subsidy.VD", "health_insurance", "VD", "qualified"),
             card("serafe", "housing", "CH", "qualified")]
    noa = Subject("s", "person", "Noa", canton="VD")
    app = lambda c, s, f: {"status": {"serafe": "not_applicable", "health.subsidy.VD": "missing_info"}.get(c.id, "applicable"),
                           "missing": ["income"] if c.id == "health.subsidy.VD" else []}
    cov = classify(cards, noa, [], app)
    assert {i["id"]: i["verdict"] for i in cov["items"]} == {"tax.return.VD": "covered", "avs.non_active": "to_verify",
                                                            "health.subsidy.VD": "to_verify", "serafe": "not_applicable"}, cov
    assert cov["counts"] == {"covered": 1, "to_verify": 2, "not_applicable": 1}
    assert "pension" in cov["domains_without_card"] and "tax" not in cov["domains_without_card"]
    assert all(i["verdict"] == "to_verify" for i in classify(cards, noa, [], None)["items"])  # no rules: nothing covered

    open_ = [{"id": "c1", "card_id": "tax.return.VD", "card": None, "missing": ["subject.tax_at_source", "salary_certificate"]},
             {"id": "c2", "card_id": "health.subsidy.VD", "card": None, "missing": ["income", "study_certificate"]},
             {"id": "c3", "card_id": "serafe", "card": None, "missing": []}]
    cov2 = {"rules": True, "items": [{"id": "tax.return.VD", "applicability": "missing_info", "missing": ["subject.tax_at_source"]},
                                     {"id": "health.subsidy.VD", "applicability": "applicable", "missing": []}]}
    q, m = split_missing(open_, cov2)
    assert q == [{"case_id": "c1", "card": None, "items": ["salary_certificate"], "questions": ["subject.tax_at_source"]}], q
    assert m == [{"case_id": "c2", "card": None, "items": ["income", "study_certificate"]}], m
    assert split_missing(open_, {"available": False})[0][0]["questions"] == ["subject.tax_at_source"]  # no rules engine
    from ordner.core import labels as L
    assert L.labels(["tax.assessment.net_income"])["tax.assessment.net_income"]["fr"] == "revenu net imposable (décision de taxation)"
    if opt("procedures"):  # every key a card can show has a human label
        assert not [k for k in L.catalogue_keys(opt("procedures").load_cards()) if L._lookup(k)[0] is None]

    g = grid(cards)
    assert g["cells"]["tax"]["VD"]["status"] == "qualified" and g["cells"]["social"]["CH"]["status"] == "draft"
    assert g["counts"] == {"qualified": 4, "draft": 1} and g["jurisdictions"][0] == "CH" and len(g["jurisdictions"]) == 27
    # review on the demo persona (temporary dossier): Talbruck statement missing, one request prepared, idempotent
    if all(opt(k) for k in ("case", "seed", "procedures", "rules")):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            st = opt("case").Store(f"{tmp}/t.db")
            sid = opt("seed").seed(st)
            for _ in range(2):
                review_dossier(sid, today=date(2026, 2, 20), s=st)
            vd = next(c for c in st.cases(sid) if c.card_id == "tax.return.VD")
            assert vd.period == "2025" and vd.deadlines[0].due == "2026-03-15", vd
            assert f"{STATEMENT}:Talbruck Banque Privée SA" in vd.missing and "pillar3a_certificate" not in vd.missing, vd.missing
            reqs = [a for c in st.cases(sid) for a in c.actions if a.payload.get("issuer") == "Talbruck Banque Privée SA"]
            assert len(reqs) == 1 and reqs[0].requires_validation and reqs[0].status == "prepared", reqs
            p3a = next(c for c in st.cases(sid) if c.card_id == "pension.pillar3a.contribution")  # period known, cert not due
            assert p3a.period == "2026" and p3a.missing == ["pension.pillar3a.paid_in_period", "income.avs_subject"], p3a
            _store = st  # case_detail reads the process store
            rate = [(f["value"], f["status"]) for f in case_detail(vd.id, today=date(2026, 2, 20))["facts"]
                    if f["key"] == "work.employment.rate"]
            assert rate == [(0.6, "rejected"), (1.0, "confirmed")], rate  # the misread comes with its correction
            from ordner.core.schema import Document
            st.add_document(Document("doc_phish", sid, "placeholder:phish", "f" * 64, "email", 2026, "Helvia (?)",
                                    received_at="2026-10-13T09:00:00+00:00", fields={  # fixed: the check views 14.10
                "text": "URGENT : payez 89 CHF aujourd'hui sur https://helvia-pay.example, IBAN CH93 0076 2011 6238 5295 7"}))
            alerts = payment_alerts(*_visible(st, sid, date(2026, 10, 14)))
            assert [a["id"] for a in alerts] == ["doc_phish"] and alerts[0]["warning"]["fr"].startswith("possible hameçonnage"), alerts
            st.close()
    print("cockpit self-check ok")
