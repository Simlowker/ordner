"""Dossier checks on what was actually received: completeness of a card's pieces, and per-institution tax totals."""
import re
from datetime import date
from decimal import Decimal

from .applicability import _g, latest_fact

STATEMENT = "swiss_tax_statement_eCH0196"   # one per declared financial institution
# ponytail: kinds tied to the tax year, by kind; other kinds (lease, identity, premium letter) are accepted whatever their
# year. Move to card-level year offsets if a card needs e.g. "year = period + 1".
YEAR_BOUND = {STATEMENT, "salary_certificate", "pillar3a_certificate", "pension_fund_certificate", "securities_list",
              "health_insurance_tax_certificate", "tax_assessment_decision", "tax_instalment_bill", "tax_return_invitation"}
# issued once the tax year is over (certificates, statements, invitation, assessment): not expected before 1 January of
# period + 1. Instalment bills come before or during the year, so they stay required.
AFTER_YEAR = YEAR_BOUND - {"tax_instalment_bill"}
# a required document is waived when a confirmed fact says the person has nothing of that kind
WAIVERS = {"pillar3a_certificate": ("pension.pillar3a.has", False), "pension_fund_certificate": ("pension.lpp.affiliated", False)}
MEASURES = ("total_tax_value", "gross_revenue_a", "gross_revenue_b", "withholding_tax_claim")


def norm(name) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name or "").casefold()).strip("_")


def declared_institutions(facts, subject_id, period=None):
    """(names, None) from confirmed `finance.institutions` (list) or `finance.institutions.<x>` facts; (None, reason) if unknown."""
    keys = sorted({_g(f, "key") for f in facts if _g(f, "key") == "finance.institutions"
                   or str(_g(f, "key")).startswith("finance.institutions.")})
    names, proposed_only = [], []
    for key in keys:
        f, proposed = latest_fact(facts, subject_id, key, period=period)
        if f is None:
            if proposed is not None:
                proposed_only.append(key)
            continue
        values = _g(f, "value") if isinstance(_g(f, "value"), list) else [_g(f, "value")]
        names += [v.get("name") if isinstance(v, dict) else v for v in values]
    if proposed_only and not names:
        return None, f"établissements seulement proposés ({', '.join(proposed_only)}) : à confirmer"
    if not keys:
        return None, "établissements financiers non déclarés (finance.institutions) : nombre de relevés attendu inconnu"
    return [n for n in dict.fromkeys(names) if n], None


def completeness(card, subject, facts, documents, period=None, today=None) -> dict:
    """{"status": "complete"|"incomplete"|"missing_info", "missing_documents", "missing_facts", "wrong_year", "duplicates",
    "not_yet_due", "why"}. With `today` inside the period's year, AFTER_YEAR documents are `not_yet_due`, not missing."""
    sid, year = _g(subject, "id"), int(str(period)[:4]) if period else None
    docs = [d for d in documents if _g(d, "subject_id") in (sid, None)]
    why, missing_docs, missing_facts, wrong_year, unknown, not_yet = [], [], [], [], [], []
    running = bool(today and year) and date.fromisoformat(str(today)[:10]) < date(year + 1, 1, 1)

    def ok_year(d):
        return year is None or _g(d, "kind") not in YEAR_BOUND or _g(d, "year") in (year, None)

    for kind in _g(card, "required_documents") or []:
        if kind in WAIVERS:
            key, value = WAIVERS[kind]
            f, _ = latest_fact(facts, sid, key)
            if f is not None and _g(f, "value") == value:
                why.append(f"{kind} : non requis, fait « {key} » = {value!r} (confirmé)")
                continue
        of_kind = [d for d in docs if _g(d, "kind") == kind]
        good = [d for d in of_kind if ok_year(d)]
        if running and not good and kind in AFTER_YEAR:
            not_yet.append({"kind": kind, "year": year})
            why.append(f"{kind} {year} : pas encore attendu (émis après la fin de l'année {year})")
            continue
        wrong_year += [{"document": _g(d, "id"), "kind": kind, "year": _g(d, "year"), "expected": year}
                       for d in of_kind if not ok_year(d)]
        if kind == STATEMENT:
            names, reason = declared_institutions(facts, sid, period)
            if names is None:
                why.append(f"{kind} : {reason}")
                unknown.append("finance.institutions")
                continue
            got = {norm(_g(d, "issuer") or (_g(d, "fields") or {}).get("institution")): d for d in good}
            for name in names:
                if norm(name) in got:
                    why.append(f"{kind} {year or ''} de {name} : reçu ({_g(got[norm(name)], 'id')})".replace("  ", " "))
                else:
                    missing_docs.append({"issuer": name, "kind": kind, "year": year})
                    why.append(f"{kind} {year or ''} de {name} : manquant".replace("  ", " "))
            for k, d in got.items():
                if k not in {norm(n) for n in names}:
                    why.append(f"relevé de {_g(d, 'issuer')} reçu mais établissement non déclaré : à ajouter à finance.institutions ?")
            continue
        if good:
            why.append(f"{kind} : reçu ({', '.join(_g(d, 'id') for d in good)})")
        else:
            missing_docs.append({"issuer": None, "kind": kind, "year": year if kind in YEAR_BOUND else None})
            why.append(f"{kind} : manquant" + (f" pour {year}" if year and kind in YEAR_BOUND else ""))
    for w in wrong_year:
        why.append(f"{w['kind']} {w['document']} est de {w['year']}, attendu {w['expected']} : mauvaise année")

    for key in _g(card, "required_facts") or []:
        if key == "tax.period" and period:  # the case's own period answers it
            why.append(f"fait « tax.period » : période du dossier {period}")
            continue
        f, proposed = latest_fact(facts, sid, key, period=period)
        if f is None:
            prefixed = [x for x in facts if str(_g(x, "key")).startswith(key + ".") and _g(x, "status") == "confirmed"
                        and _g(x, "subject_id") in (sid, None)]
            if prefixed:
                continue
            missing_facts.append(key)
            why.append(f"fait « {key} » " + ("seulement proposé : à confirmer" if proposed is not None else "absent"))
    missing_facts += [k for k in unknown if k not in missing_facts]

    duplicates, seen_sha, seen_triplet = [], {}, {}
    for d in docs:
        sha, triplet = _g(d, "sha256"), (_g(d, "kind"), norm(_g(d, "issuer")), _g(d, "year"))
        if sha in seen_sha:
            duplicates.append({"documents": [seen_sha[sha], _g(d, "id")], "reason": "même fichier (sha256)"})
        elif triplet[0] and triplet[1] and triplet in seen_triplet:
            duplicates.append({"documents": [seen_triplet[triplet], _g(d, "id")], "reason": "même type, émetteur et année"})
        seen_sha.setdefault(sha, _g(d, "id"))
        seen_triplet.setdefault(triplet, _g(d, "id"))
    why += [f"doublon probable : {' et '.join(x['documents'])} ({x['reason']})" for x in duplicates]

    status = "incomplete" if missing_docs or [k for k in missing_facts if k not in unknown] else (
        "missing_info" if unknown else "complete")
    return {"status": status, "missing_documents": missing_docs, "missing_facts": missing_facts, "wrong_year": wrong_year,
            "duplicates": duplicates, "not_yet_due": not_yet, "why": why, "card": _g(card, "id"), "period": str(period) if period else None}


def _measure_key(key: str):
    """(measure, institution key) for tax.statement.<m>.<inst> (eCH-0196 connector) or tax.securities.<inst>.<m> (seed)."""
    p = key.split(".")
    if len(p) == 4 and p[:2] == ["tax", "statement"] and p[2] in MEASURES:
        return p[2], p[3]
    if len(p) == 4 and p[:2] == ["tax", "securities"] and p[3] in MEASURES:
        return p[3], p[2]
    return None


def consolidate(facts, period) -> dict:
    """Sum the per-institution statement totals of one subject for `period`. Any proposed input makes a total provisional."""
    subjects = {_g(f, "subject_id") for f in facts} - {None}
    if len(subjects) > 1:
        raise ValueError(f"consolidate: facts of several subjects {sorted(subjects)}; never mix dossiers")
    sid = subjects.pop() if subjects else None
    usable = [f for f in facts if _g(f, "status") in ("confirmed", "proposed") and _g(f, "period") in (str(period), None)]
    declared, reason = declared_institutions(facts, sid, period)
    by_norm = {norm(n): n for n in declared or []}

    def institution(key):  # seed slug "morvessa" ↔ declared "Morvessa Banque SA" ↔ connector slug "morvessa_banque_sa"
        return by_norm.get(key) or next((n for k, n in by_norm.items() if k.startswith(key + "_")), key)

    picked = {}
    for f in usable:
        mk = _measure_key(str(_g(f, "key")))
        if mk is None or _g(f, "value") is None:
            continue
        slot = (mk[0], institution(mk[1]))
        rank = (_g(f, "status") == "confirmed", _g(f, "created_at") or "")
        if slot not in picked or rank > picked[slot][0]:
            picked[slot] = (rank, f)
    included = sorted({inst for _, inst in picked})
    why, totals = [], {}
    for m in MEASURES:
        rows = {inst: f for (mm, inst), (_, f) in picked.items() if mm == m}
        lacking = [i for i in included if i not in rows]
        provisional = [i for i, f in rows.items() if _g(f, "status") == "proposed"]
        total = sum((Decimal(str(_g(f, "value"))) for f in rows.values()), Decimal(0))
        totals[m] = {"total": float(total) if rows else None,
                     "status": "missing" if not rows else "provisional" if provisional or lacking else "confirmed",
                     "by_institution": {i: {"value": _g(f, "value"), "status": _g(f, "status"), "fact": _g(f, "id")}
                                        for i, f in sorted(rows.items())},
                     "institutions_lacking": lacking}
        if rows:
            why.append(f"{m} = {float(total)} sur {len(rows)} établissement(s)"
                       + (f", provisoire (proposé : {', '.join(provisional)})" if provisional else "")
                       + (f", sans valeur pour {', '.join(lacking)}" if lacking else ""))
    missing = [n for n in declared or [] if n not in included] if declared is not None else None
    if missing:
        why.append(f"établissements déclarés sans relevé consolidé : {', '.join(missing)}")
    if reason:
        why.append(reason)
    any_provisional = any(t["status"] in ("provisional",) for t in totals.values())
    status = "incomplete" if missing or declared is None else "provisional" if any_provisional else "final"
    return {"period": str(period), "status": status, "totals": totals, "institutions_included": included,
            "institutions_missing": missing, "why": why}
