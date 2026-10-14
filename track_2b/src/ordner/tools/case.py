"""case.load, case.record (local dossier, ordner.case W1) and receipt.verify (is an action's effect proven?)."""
from typing import get_args

from ordner.core.schema import CaseState, Deadline, Fact, ToolSpec, new_id

from .base import ToolError, store

OPS = ["propose_fact", "confirm_fact", "reject_fact", "open_case", "set_state", "add_deadline"]
USER_ONLY_OPS = {"confirm_fact", "reject_fact"}
# Event types that prove an action's effect, besides the person/connector moving the action to "verified".
PROOF_EVENTS = {"receipt_recorded", "proof_recorded", "decision_received", "payment_confirmed", "action_verified"}
MAX_EVENTS = 20


def _need(p, *keys):
    missing = [k for k in keys if p.get(k) in (None, "")]
    if missing:
        raise ToolError(f"{p['op']} needs: {', '.join(missing)}")


def _is_proof(e):
    return e.type in PROOF_EVENTS or (e.type == "action_updated" and e.payload.get("to") == "verified")


def action_events(st, action_id, ctx, case_id=None):
    return [e for e in st.events(subject_id=ctx.get("subject_id"), case_id=case_id)
            if (e.payload or {}).get("action_id") == action_id]


def load(args, ctx):
    st, warnings = store(ctx), []
    if args.get("case_id"):
        case = st.get_case(args["case_id"])
        if case.subject_id != args["subject_id"]:
            raise ToolError(f"case {case.id} belongs to another dossier")
        events = st.events(case_id=case.id)
        if len(events) > MAX_EVENTS:
            warnings.append(f"only the last {MAX_EVENTS} of {len(events)} events are shown")
        return {"case": case, "events": events[-MAX_EVENTS:]}, warnings, {"source": "ordner.case"}
    return st.snapshot(args["subject_id"], last_events=MAX_EVENTS), warnings, {"source": "ordner.case"}


def record(args, ctx):
    op, p, sid = args["op"], args, args["subject_id"]
    actor = "user" if ctx.get("actor") == "user" else "model"
    if op in USER_ONLY_OPS and actor != "user":
        raise ToolError(f"{op} is reserved to the person: ask them to confirm or correct the value")
    st = store(ctx)
    if "case_id" in p and st.get_case(p["case_id"]).subject_id != sid:
        raise ToolError(f"case {p['case_id']} belongs to another dossier")
    if op == "propose_fact":
        _need(p, "key", "value")
        out = st.propose_fact(Fact(id=new_id("fact"), subject_id=sid, key=p["key"], value=p["value"],
                                   period=p.get("period"), unit=p.get("unit"), source_doc=p.get("source_doc"),
                                   doubt=p.get("doubt"), actor=actor))
    elif op in USER_ONLY_OPS:
        _need(p, "fact_id")
        out = getattr(st, op)(p["fact_id"], actor="user")
    elif op == "open_case":
        _need(p, "card_id")
        out = st.open_case(sid, p["card_id"], p.get("period"), actor=actor)
    elif op == "set_state":
        _need(p, "case_id", "state")
        proven = (any(map(_is_proof, action_events(st, a.id, ctx, p["case_id"])))
                  for a in st.get_case(p["case_id"]).actions)
        if p["state"] == "result_verified" and actor != "user" and not any(proven):
            raise ToolError("no recorded proof for any action of this case (see receipt.verify): the result is not "
                            "verified; ask the person")
        out = st.set_state(p["case_id"], p["state"], p.get("reason", ""), actor=actor)
    else:  # add_deadline
        _need(p, "case_id", "due", "rule_id")
        out = st.add_deadline(Deadline(id=new_id("dl"), case_id=p["case_id"], due=p["due"], rule_id=p["rule_id"],
                                       computed_from=p.get("computed_from") or {}, reminders=p.get("reminders") or []),
                              actor=actor)
    return {"op": op, "recorded": out}, [], {"source": "ordner.case", "actor": actor}


def verify(args, ctx):
    st, aid = store(ctx), args["action_id"]
    evs = action_events(st, aid, ctx, args.get("case_id"))
    if not evs:
        raise ToolError(f"no action {aid} in this dossier")
    found = [e for e in evs if _is_proof(e)]
    updates = [e.payload.get("to") for e in evs if e.type == "action_updated"]
    data = {"action_id": aid, "status": "established" if found else "unknown",
            "action_status": updates[-1] if updates else "prepared",
            "proof": [{"event_id": e.id, "type": e.type, "ts": e.ts, "actor": e.actor} for e in found]}
    warnings = []
    if not found:
        warnings.append("no recorded proof: the result is unknown. Do not repeat the operation; look for its receipt "
                        "or native status first")
        if data["action_status"] == "done_by_user":
            warnings.append("the person marked it done, but no receipt is recorded")
    return data, warnings, {"source": "ordner.case events"}


TOOLS = [
    (ToolSpec(
        "case.load",
        "Load the dossier: subject, documents, facts (proposed/confirmed), cases with states, actions, deadlines. "
        "With case_id: that case and its recent events.",
        {"type": "object", "properties": {"subject_id": {"type": "string"}, "case_id": {"type": "string"}},
         "required": ["subject_id"]},
        {"type": "object", "description": "snapshot of the subject, or {case, events}"},
    ), load),
    (ToolSpec(
        "case.record",
        "Write to the local dossier. op and its fields: propose_fact (key, value, period, unit, source_doc, doubt); "
        "open_case (card_id, period); set_state (case_id, state, reason); add_deadline (case_id, due, rule_id, "
        "reminders). Facts stay proposed until the person confirms them.",
        {"type": "object", "properties": {
            "subject_id": {"type": "string"},
            "op": {"type": "string", "enum": OPS},
            "key": {"type": "string", "description": "dotted fact key, e.g. tax.securities.<bank>.total_tax_value"},
            "value": {"description": "number, text or boolean"},
            "period": {"type": "string", "description": "e.g. 2025"},
            "unit": {"type": "string", "description": "e.g. CHF"},
            "source_doc": {"type": "string", "description": "dossier document id the value comes from"},
            "doubt": {"type": "number", "description": "estimated probability the value is wrong, 0-1"},
            "fact_id": {"type": "string"},
            "card_id": {"type": "string", "description": "procedure card id"},
            "case_id": {"type": "string"},
            "state": {"type": "string", "enum": list(get_args(CaseState))},
            "reason": {"type": "string"},
            "due": {"type": "string", "description": "YYYY-MM-DD"},
            "rule_id": {"type": "string", "description": "deadline rule that computed due"},
            "computed_from": {"type": "object", "description": "deadline.computed_from from rules.evaluate"},
            "reminders": {"type": "array", "items": {"type": "string"}}},
         "required": ["subject_id", "op"]},
        {"type": "object", "properties": {"op": {"type": "string"}, "recorded": {"type": "object"}}},
    ), record),
    (ToolSpec(
        "receipt.verify",
        "Check whether an action's effect is proven by a recorded receipt, decision or confirmation: established "
        "or unknown. Never assume success; call before any follow-up or closing.",
        {"type": "object", "properties": {"action_id": {"type": "string"}, "case_id": {"type": "string"}},
         "required": ["action_id"]},
        {"type": "object", "properties": {
            "status": {"type": "string", "enum": ["established", "unknown"]},
            "action_status": {"type": ["string", "null"]}, "proof": {"type": "array"}}},
    ), verify),
]
