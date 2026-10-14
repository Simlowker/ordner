"""rules.evaluate and schedule.plan: wrappers over ordner.rules (W3), cards from ordner.procedures (W2), dossier from ordner.case (W1)."""
from datetime import date

from ordner.core.schema import ToolSpec

from .base import ToolError, need, store


def evaluate(args, ctx):
    R = need("ordner.rules", "W3 rules engine")
    catalog = need("ordner.procedures.catalog", "W2 procedure catalogue")
    try:
        card = catalog.get(args["card_id"])
    except KeyError:
        raise ToolError(f"unknown procedure card '{args['card_id']}'") from None
    st = store(ctx)
    subject = st.get_subject(args["subject_id"])
    facts = st.facts(args["subject_id"])
    preview = bool(args.get("include_proposed"))
    res = R.applicable(card, subject, facts, period=args.get("period"), accept_proposed=preview)
    warnings = []
    proposed = sorted({f.key for f in facts if f.status == "proposed"})
    if preview and proposed:
        warnings.append(f"preview only: relies on unconfirmed facts ({', '.join(proposed[:10])})")
    if card.qualification != "qualified":
        warnings.append(f"procedure card is '{card.qualification}': to verify before acting on it")
    deadline = None
    if card.deadline and res.get("status") == "applicable":
        deadline = R.compute_deadline(card.deadline, subject, {"period": args.get("period"), **(args.get("context") or {})})
    data = {"card_id": card.id, **res, "deadline": deadline, "qualification": card.qualification,
            "sources": [{"title": s.title, "url": s.url, "verified": s.verified} for s in card.sources]}
    prov = {"source": "ordner.rules", "engine_version": getattr(R, "VERSION", None), "card": card.id,
            "valid_from": card.valid_from, "valid_to": card.valid_to, "facts_status": res.get("accepted_fact_status")}
    return data, warnings, prov


def plan(args, ctx):
    R = need("ordner.rules", "W3 rules engine")
    try:
        due = date.fromisoformat(args["due"])
        today = date.fromisoformat(ctx.get("today") or date.today().isoformat())
    except ValueError as e:
        raise ToolError(f"dates must be YYYY-MM-DD ({e})") from None
    policy = args.get("policy", "default")
    rem = sorted(R.reminders(due.isoformat(), policy))
    upcoming = [r for r in rem if r >= today.isoformat()]
    data = {"due": due.isoformat(), "days_left": (due - today).days, "overdue": due < today, "reminders": rem,
            "next_resume": upcoming[0] if upcoming else max(due, today).isoformat()}
    warnings = ["deadline passed: look for an extension or late procedure before acting"] if due < today else []
    return data, warnings, {"source": "ordner.rules.reminders", "policy": policy, "today": today.isoformat()}


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
        "schedule.plan",
        "Plan reminders for a due date and the next date to resume the case. Computes only; record the deadline "
        "with case.record add_deadline.",
        {"type": "object", "properties": {
            "due": {"type": "string", "description": "YYYY-MM-DD"},
            "policy": {"type": "string", "description": "reminder policy, default 'default'"}},
         "required": ["due"]},
        {"type": "object", "properties": {
            "days_left": {"type": "integer"}, "overdue": {"type": "boolean"},
            "reminders": {"type": "array", "items": {"type": "string"}}, "next_resume": {"type": "string"}}},
    ), plan),
]
