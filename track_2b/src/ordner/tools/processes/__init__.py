"""Process tools (H6, PREREG Addendum 2): one tool per administrative process. Each encodes the procedure and calls the
deterministic modules (ordner.rules, ordner.procedures, connectors) and the specialist models (replay caches in replay
mode) itself, so the coordinating model only routes, fills arguments, asks the person and explains.

Every tool returns the registry envelope; `data` is compact: summary (subject language), status, card_id, applicable,
deadlines [{card_id, what, due, send_by?, rule, sources (card quote ids "card#i" / legal basis ids), url}], missing,
questions [{missing, question}], prepared_actions (action ids). Writes: proposed facts and prepared actions only
(actor "ordner"; a case is opened only to hold a prepared action). Nothing is sent, filed or paid.

Toolsets for the H6 comparison (same model, same prompt): `base` = the generic tools, `process` = these tools plus the
generic entry points still needed for procedures without a process tool, `both` = everything.
"""
from datetime import date

from ordner.core.schema import Action, Fact, new_id

from ..base import ToolError

LANGS = ("fr", "de", "it")
CANTON_LANG = {"VD": "fr", "GE": "fr", "NE": "fr", "JU": "fr", "FR": "fr", "VS": "fr", "TI": "it"}
CANTONS = "AG AI AR BE BL BS FR GE GL GR JU LU NE NW OW SG SH SO SZ TG TI UR VD VS ZG ZH".split()


def lang(subject) -> str:
    return (subject.attrs or {}).get("lang") or CANTON_LANG.get(subject.canton or "", "de")


def t(lg, fr, de, it) -> str:
    return {"fr": fr, "de": de, "it": it}.get(lg, fr)


def label(key, lg="fr") -> str:
    try:
        from ordner.core.labels import label as _label
        return _label(key, lg)
    except Exception:  # labels module missing or mid-edit: the raw key is still meaningful
        return key


def fmt(iso) -> str:
    return date.fromisoformat(iso).strftime("%d.%m.%Y") if iso else "?"


def card(card_id):
    from ordner.procedures import catalog
    try:
        return catalog.get(card_id)
    except KeyError:
        return None


def value(facts, *keys, confirmed_only=False):
    """Latest value among `keys` (confirmed first, then proposed unless confirmed_only), else None."""
    for statuses in (("confirmed",),) if confirmed_only else (("confirmed",), ("proposed",)):
        found = sorted((f for f in facts if f.key in keys and f.status in statuses), key=lambda f: f.created_at)
        if found:
            return found[-1].value
    return None


def given(sid, key, val, period=None) -> Fact:
    """In-memory fact for the rules engine: a value given by the person in this conversation (also proposed to the
    dossier with remember()). Never stored as confirmed."""
    return Fact(new_id("fact"), sid, key, val, period=period, status="confirmed", actor="user")


def remember(st, sid, key, val, period=None, source_doc=None, doubt=None):
    """Propose a fact (actor ordner) unless the same key/value is already proposed or confirmed. Returns its id."""
    for f in st.facts(sid, key_prefix=key):
        if f.key == key and f.value == val and f.status in ("proposed", "confirmed"):
            return f.id
    return st.propose_fact(Fact(new_id("fact"), sid, key, val, period=period, source_doc=source_doc, doubt=doubt,
                                actor="ordner")).id


def prepare(st, sid, card_id, period, kind, payload) -> str:
    """Prepared action (never executed) on the case of card_id/period, opened if needed. Returns the action id."""
    case = st.open_case(sid, card_id, period, actor="ordner")
    a = st.add_action(Action(new_id("act"), case.id, kind, {**payload, "card": card_id, "prepared_by": "ordner.process"},
                             requires_validation=True), actor="ordner")
    return a.id


def sources(c, idxs, verified_only=True) -> list[str]:
    return [f"{c.id}#{i}" for i in idxs or [] if i < len(c.sources) and (c.sources[i].verified or not verified_only)]


def deadline(c, res, what, **extra) -> dict | None:
    """Compact deadline entry from ordner.rules.compute_deadline output, None when not computed."""
    if not res or res.get("status") != "computed":
        return None
    from ordner.rules import SOURCES
    cf = res["computed_from"]
    ids = sources(c, cf.get("card_sources"))[:4] + [k for k in cf.get("legal_basis", [])
                                                     if SOURCES.get(k, {}).get("verified")][:3]
    url = next((c.sources[i].url for i in cf.get("card_sources") or [] if i < len(c.sources) and c.sources[i].verified),
               None)
    out = {"card_id": c.id, "what": what, "due": res["due"], "rule": cf["rule"], "sources": ids, "url": url, **extra}
    if res.get("send_by"):
        out["send_by"] = res["send_by"]
    if res.get("extensions"):
        out["extensions"] = [{k: e.get(k) for k in ("until", "fee_chf", "request_by") if e.get(k) is not None}
                             | {"how": (e.get("how") or "")[:90]} for e in res["extensions"]]
    if cf.get("warnings"):
        out["notes"] = [w[:140] for w in cf["warnings"][:2]]
    return out


def question(missing, text) -> dict:
    return {"missing": missing, "question": text}


def result(summary, *, status, card_id=None, applicable=(), deadlines=(), missing=(), questions=(), prepared=(),
           **extra) -> dict:
    # questions right after the summary: what the model must relay first, and safe from the coordinator's clipping
    return {"summary": summary, "status": status, "card_id": card_id, "questions": list(questions),
            "missing": list(missing), "applicable": list(dict.fromkeys(applicable)),
            "deadlines": [d for d in deadlines if d], "prepared_actions": list(dict.fromkeys(prepared)), **extra}


def subject_ctx(args, ctx):
    from ..base import store, today
    st = store(ctx)
    try:
        subject = st.get_subject(args["subject_id"])
    except KeyError:
        raise ToolError(f"unknown subject {args['subject_id']}") from None
    return st, subject, today(ctx)


def iso(value_, name) -> str | None:
    if value_ in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value_)[:10]).isoformat()
    except ValueError:
        raise ToolError(f"{name} must be YYYY-MM-DD, got {value_!r}") from None


from . import demenagement, impots, lamal, piece, poursuite  # noqa: E402  (they import the helpers above)

TOOLS = piece.TOOLS + impots.TOOLS + lamal.TOOLS + poursuite.TOOLS + demenagement.TOOLS
NAMES = {spec.name for spec, _ in TOOLS}
# generic entry points kept next to the process tools: dossier read/write, procedures without a process tool, sources
PROCESS_KEEP = {"case.load", "case.record", "rules.evaluate", "knowledge.search"}
TOOLSETS = ("base", "process", "both")


def in_toolset(name: str, toolset: str = "both") -> bool:
    if toolset not in TOOLSETS:
        raise ValueError(f"toolset must be one of {TOOLSETS}")
    if toolset == "both":
        return True
    if toolset == "base":
        return name not in NAMES
    return name in NAMES or name in PROCESS_KEEP
