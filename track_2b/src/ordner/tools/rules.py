"""rules.evaluate, dossier.check and schedule.plan: wrappers over ordner.rules (W3), cards from ordner.procedures (W2),
dossier from ordner.case (W1). Every date is evaluated at ctx["today"] (the scenario date), not the machine clock."""
from datetime import date

from ordner.core.schema import ToolSpec

from .base import ToolError, need, store, today


def _card(card_id):
    try:
        return need("ordner.procedures.catalog", "W2 procedure catalogue").get(card_id)
    except KeyError:
        raise ToolError(f"unknown procedure card '{card_id}'") from None


def evaluate(args, ctx):
    R = need("ordner.rules", "W3 rules engine")
    card, on = _card(args["card_id"]), today(ctx).isoformat()
    st = store(ctx)
    subject = st.get_subject(args["subject_id"])
    facts = st.facts(args["subject_id"])
    preview = bool(args.get("include_proposed"))
    res = R.applicable(card, subject, facts, on=on, period=args.get("period"), accept_proposed=preview)
    warnings = []
    proposed = sorted({f.key for f in facts if f.status == "proposed"})
    if preview and proposed:
        warnings.append(f"preview only: relies on unconfirmed facts ({', '.join(proposed[:10])})")
    if card.qualification != "qualified":
        warnings.append(f"procedure card is '{card.qualification}': to verify before acting on it")
    deadline = None
    if card.deadline and res.get("status") == "applicable":
        context = {"period": args.get("period"), "today": on, "facts": facts, **(args.get("context") or {})}
        deadline = R.compute_deadline(card.deadline, subject, context)
    data = {"card_id": card.id, **res, "deadline": deadline, "qualification": card.qualification,
            "sources": list({s.url: {"title": s.title, "url": s.url, "verified": s.verified} for s in card.sources}.values())}
    prov = {"source": "ordner.rules", "engine_version": getattr(R, "VERSION", None), "card": card.id,
            "valid_from": card.valid_from, "valid_to": card.valid_to, "facts_status": res.get("accepted_fact_status"),
            "on": on}
    return data, warnings, prov


def check(args, ctx):
    R = need("ordner.rules", "W3 rules engine")
    st, sid, period = store(ctx), args["subject_id"], args["period"]
    facts, card = st.facts(sid), _card(args["card_id"]) if args.get("card_id") else None
    data, warnings = {"completeness": None, "consolidation": None}, []
    if card is not None:
        c = data["completeness"] = R.completeness(card, st.get_subject(sid), facts, st.documents(sid), period)
        missing = [f"{d['kind']} {d['issuer'] or ''}".strip() for d in c["missing_documents"]] + c["missing_facts"]
        if missing:
            warnings.append(f"{card.id} {period}: missing {', '.join(missing)}")
        if c["wrong_year"] or c["duplicates"]:
            warnings.append(f"{len(c['wrong_year'])} document(s) of the wrong year, {len(c['duplicates'])} duplicate(s)")
    if card is None or card.domain == "tax":
        t = data["consolidation"] = R.consolidate(facts, period)
        if t["status"] != "final":
            warnings.append(f"consolidated totals are {t['status']}: not final")
    return data, warnings, {"source": "ordner.rules.completeness/consolidate", "card": card.id if card else None}


def plan(args, ctx):
    R = need("ordner.rules", "W3 rules engine")
    try:
        due = date.fromisoformat(args["due"])
    except ValueError as e:
        raise ToolError(f"due must be YYYY-MM-DD ({e})") from None
    day, policy = today(ctx), args.get("policy", "default")
    rem = R.reminders(due.isoformat(), policy, today=day.isoformat())  # past reminders dropped
    data = {"due": due.isoformat(), "days_left": (due - day).days, "overdue": due < day, "reminders": rem,
            "next_resume": rem[0] if rem else max(due, day).isoformat()}
    warnings = ["deadline passed: look for an extension or late procedure before acting"] if due < day else []
    return data, warnings, {"source": "ordner.rules.reminders", "policy": policy, "today": day.isoformat()}


TOOLS = [
    (ToolSpec(
        "rules.evaluate",
        "Decide with the encoded rules whether a procedure applies to the subject: applicable, not_applicable or "
        "missing_info (with the missing facts), plus its deadline when applicable and the official sources.",
        {"type": "object", "properties": {
            "card_id": {"type": "string", "description": "procedure card id, e.g. tax.return.VD"},
            "subject_id": {"type": "string"},
            "period": {"type": "string", "description": "e.g. 2025"},
            "context": {"type": "object", "description": "deadline inputs, e.g. {notification_date: YYYY-MM-DD}"},
            "include_proposed": {"type": "boolean", "description": "preview counting unconfirmed facts; default "
                                 "false = confirmed facts only"}},
         "required": ["card_id", "subject_id"]},
        {"type": "object", "properties": {
            "status": {"type": "string", "enum": ["applicable", "not_applicable", "missing_info"]},
            "missing": {"type": "array"}, "why": {"type": "array"}, "deadline": {"type": ["object", "null"]},
            "qualification": {"type": "string"}, "sources": {"type": "array"}}},
    ), evaluate),
    (ToolSpec(
        "dossier.check",
        "Check what the dossier actually holds for a period (read only). With card_id: missing documents (e.g. "
        "one tax statement per declared bank), wrong-year documents, duplicates, missing facts. Tax: consolidated "
        "statement totals per measure, provisional while any input is unconfirmed or missing.",
        {"type": "object", "properties": {
            "subject_id": {"type": "string"},
            "period": {"type": "string", "description": "e.g. 2025"},
            "card_id": {"type": "string", "description": "procedure card whose required documents are checked"}},
         "required": ["subject_id", "period"]},
        {"type": "object", "properties": {
            "completeness": {"type": ["object", "null"], "description": "{status complete|incomplete|missing_info, "
                             "missing_documents, missing_facts, wrong_year, duplicates, why}"},
            "consolidation": {"type": ["object", "null"], "description": "{status final|provisional|incomplete, "
                              "totals: {measure: {total, status, by_institution}}, institutions_missing, why}"}}},
    ), check),
    (ToolSpec(
        "schedule.plan",
        "Plan reminders for a due date and the next date to resume the case. Computes only; record the deadline "
        "with case.record add_deadline.",
        {"type": "object", "properties": {
            "due": {"type": "string", "description": "YYYY-MM-DD"},
            "policy": {"type": "string", "description": "reminder policy, default 'default'"}},
         "required": ["due"]},
        {"type": "object", "properties": {
            "days_left": {"type": "integer"}, "overdue": {"type": "boolean"},
            "reminders": {"type": "array", "items": {"type": "string"}, "description": "upcoming only"},
            "next_resume": {"type": "string"}}},
    ), plan),
]
