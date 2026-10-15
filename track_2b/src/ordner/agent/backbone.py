"""Rules first, inside an expert's conversation: before Apertus answers, the deterministic engine (ordner.rules +
catalogue) runs on the dossier's confirmed facts for the expert's procedures. Applicable procedures get their case,
their computed deadline and their external steps prepared for validation; missing inputs become questions. Store
writes are idempotent (same case, same action), so it can run at every conversation start.

Same logic as the frozen rules-only baseline (eval.scenarios.agents.rules_only), restricted to an expert's scope."""
from dataclasses import asdict

from ordner import rules
from ordner.core.schema import Action, Deadline, new_id
from ordner.procedures import catalog


def apply(store, sid, today, prefixes=("*",), period=None, notified=None):
    """-> {"applicable", "deadlines", "actions", "questions"}. `notified`: {card_id: date} of known notifications."""
    out = {"applicable": [], "deadlines": [], "actions": [], "questions": []}
    subject, facts = store.get_subject(sid), store.facts(sid, status="confirmed")
    for card in catalog.load_cards():
        if "*" not in prefixes and not card.id.startswith(tuple(prefixes)):
            continue
        r = rules.applicable(card, subject, facts, on=today)
        if r["status"] == "missing_info":
            out["questions"] += [{"missing": k, "question": f"{card.id}: {k} ?"} for k in r["missing"]]
            continue
        if r["status"] != "applicable":
            continue
        case = store.open_case(sid, card.id, period=period)
        out["applicable"].append(card.id)
        if card.deadline:
            ctx = {"period": period, "canton": subject.canton, "today": today, "facts": facts}
            if (notified or {}).get(card.id):
                ctx["notified_on"] = notified[card.id]
            d = rules.compute_deadline(card.deadline, subject, ctx)
            if d.get("due"):
                if not any(x.due == d["due"] for x in store.deadlines(case.id)):
                    store.add_deadline(Deadline(new_id("dl"), case.id, d["due"], card.deadline.id, d.get("computed_from", {})))
                out["deadlines"].append({"procedure": card.id, "due": d["due"]})
            else:
                out["questions"] += [{"missing": k, "question": f"{card.id}: {k} ?"} for k in d.get("missing", [])]
        for step in card.steps:
            if step.get("action"):
                a = store.add_action(Action(new_id("act"), case.id, step["action"], {"card": card.id, "step": step["id"]},
                                            requires_validation=step["action"] != "reminder"))
                out["actions"].append({"procedure": card.id, **asdict(a)})
    return out
