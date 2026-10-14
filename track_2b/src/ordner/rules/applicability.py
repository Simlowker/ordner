"""Applicability of a ProcedureCard: three-valued evaluation of the declarative condition language (see README.md,
same syntax as ordner.procedures.catalog). Unknown is never silently turned into true or false."""
import operator
from datetime import date

OPS = {"eq": operator.eq, "ne": operator.ne, "gte": operator.ge, "gt": operator.gt, "lte": operator.le,
       "lt": operator.lt, "in": lambda v, target: v in target}
SYMBOL = {"eq": "=", "ne": "≠", "in": "∈", "gte": "≥", "gt": ">", "lte": "≤", "lt": "<"}
SUBJECT_FIELDS = ("id", "kind", "name", "canton", "commune")
AGE_ATTRS = ("age", "age_at_year_end")


def _g(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def _as_date(d) -> date:
    return date.fromisoformat(d) if isinstance(d, str) else d


class _Eval:
    def __init__(self, subject, facts, on: date, period, accept_proposed):
        self.subject, self.on, self.why = subject, on, []
        self.accept = ("confirmed", "proposed") if accept_proposed else ("confirmed",)
        sid = _g(subject, "id")
        self.facts = [f for f in facts if _g(f, "subject_id") in (sid, None)  # never reuse another subject's facts
                      and (period is None or _g(f, "period") in (str(period), None))]

    def node(self, c) -> tuple[bool | None, set]:
        if not c:
            return True, set()
        if "all" in c or "any" in c:
            is_all = "all" in c
            results = [self.node(sub) for sub in c["all" if is_all else "any"]]
            vals = [v for v, _ in results]
            decisive = False if is_all else True
            if decisive in vals:
                return decisive, set()
            if None in vals:
                return None, set().union(*(m for v, m in results if v is None))
            return (not decisive), set()
        if "not" in c:
            v, missing = self.node(c["not"])
            return (None if v is None else not v), missing
        if "role" in c:
            roles = _g(self.subject, "roles") or []
            if not roles:
                self.why.append(f"rôles du sujet inconnus (liste vide) → information manquante pour « {c['role']} »")
                return None, {"subject.roles"}
            ok = c["role"] in roles
            self.why.append(f"rôle « {c['role']} » {'présent' if ok else 'absent'} ({', '.join(roles)}) → {_fr(ok)}")
            return ok, set()
        op = next(k for k in c if k not in ("attr", "fact"))
        return self.attr(c["attr"], op, c[op]) if "attr" in c else self.fact(c["fact"], op, c[op])

    def attr(self, name, op, target):
        if name in AGE_ATTRS:
            return self.age(name, op, target)
        v = _g(self.subject, name) if name in SUBJECT_FIELDS else (_g(self.subject, "attrs") or {}).get(name)
        return self.leaf(f"subject.{name}", v, op, target, f"{name}")

    def age(self, name, op, target):
        attrs = _g(self.subject, "attrs") or {}
        bd = attrs.get("birth_date")
        by = int(bd[:4]) if bd else attrs.get("birth_year")
        if by is None:
            self.why.append(f"{name} : année de naissance inconnue → information manquante")
            return None, {"subject.birth_year"}
        y = self.on.year
        if name == "age_at_year_end":  # exact from the year alone: the birthday has passed by 31.12
            return self.leaf("subject.birth_year", y - by, op, target, f"âge au 31.12.{y} ({y} − {by})")
        if bd:
            b = date.fromisoformat(bd)
            exact = y - b.year - ((self.on.month, self.on.day) < (b.month, b.day))
            return self.leaf("subject.birth_date", exact, op, target, f"âge au {self.on:%d.%m.%Y}")
        candidates = {y - by - 1, y - by} if (self.on.month, self.on.day) != (12, 31) else {y - by}
        results = {OPS[op](a, target) if op != "exists" else target for a in candidates}
        label = f"âge au {self.on:%d.%m.%Y} ({' ou '.join(map(str, sorted(candidates)))}, date de naissance inconnue)"
        if len(results) == 1:
            ok = results.pop()
            self.why.append(f"{label} {SYMBOL.get(op, op)} {target} → {_fr(ok)}")
            return ok, set()
        self.why.append(f"{label} : la date exacte décide → information manquante")
        return None, {"subject.birth_date"}

    def fact(self, key, op, target):
        same = sorted((f for f in self.facts if _g(f, "key") == key), key=lambda f: _g(f, "created_at") or "")
        usable = [f for f in same if _g(f, "status") in self.accept]
        proposed = [f for f in same if _g(f, "status") == "proposed"]
        if not usable and proposed:
            self.why.append(f"fait « {key} » seulement proposé (valeur {_g(proposed[-1], 'value')!r}), "
                            "à confirmer → information manquante")
            return None, {key}
        f = usable[-1] if usable else None
        tag = " (proposé)" if f is not None and _g(f, "status") == "proposed" else ""
        return self.leaf(key, None if f is None else _g(f, "value"), op, target, f"fait « {key} »{tag}")

    def leaf(self, missing_key, v, op, target, label):
        if op == "exists":
            ok = (v is not None) == target
            self.why.append(f"{label} {'présent' if v is not None else 'absent'} (attendu {'présent' if target else 'absent'}) → {_fr(ok)}")
            return ok, set()
        if v is None:
            self.why.append(f"{label} inconnu → information manquante")
            return None, {missing_key}
        try:
            ok = bool(OPS[op](v, target))
        except TypeError:
            self.why.append(f"{label} = {v!r} non comparable à {target!r} → information manquante")
            return None, {missing_key}
        self.why.append(f"{label} = {v!r} (attendu {SYMBOL[op]} {target!r}) → {_fr(ok)}")
        return ok, set()


def _fr(ok: bool) -> str:
    return "vrai" if ok else "faux"


def applicable(card, subject, facts, on=None, period=None, accept_proposed=False) -> dict:
    """{"status": "applicable"|"not_applicable"|"missing_info", "missing": [...], "why": [...]}.
    `on`: reference date (ISO or date, default today) for ages and card validity. `accept_proposed`: preview mode where
    proposed (unconfirmed) facts count; by default only confirmed facts decide."""
    on = _as_date(on) if on else date.today()
    ev = _Eval(subject, facts, on, period, accept_proposed)
    cond = _g(card, "applicability") or {}
    jurisdiction = _g(card, "jurisdiction") or "CH"
    if jurisdiction != "CH":
        cond = {"all": [{"attr": "canton", "eq": jurisdiction}, cond]}
    value, missing = ev.node(cond)
    why = ev.why
    valid_from, valid_to = _g(card, "valid_from"), _g(card, "valid_to")
    if (valid_from and on.isoformat() < valid_from) or (valid_to and on.isoformat() > valid_to):
        why.append(f"fiche valable {valid_from or '…'} → {valid_to or '…'}, hors période au {on:%d.%m.%Y} : règle à revérifier")
        value, missing = (None, missing | {"card.validity"}) if value is not False else (value, missing)
    if _g(card, "qualification", "draft") != "qualified":
        why.append(f"fiche « {_g(card, 'id')} » non qualifiée ({_g(card, 'qualification', 'draft')}) : résultat à vérifier")
    status = {True: "applicable", False: "not_applicable", None: "missing_info"}[value]
    why.append(f"conclusion : {status.replace('_', ' ')}" + (f" (manque : {', '.join(sorted(missing))})" if missing else ""))
    return {"status": status, "missing": sorted(missing) if value is None else [], "why": why,
            "card": _g(card, "id"), "evaluated_on": on.isoformat(), "accepted_fact_status": list(ev.accept)}
