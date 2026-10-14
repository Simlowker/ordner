"""Deadline rules (registry by id), Swiss holidays, LP debt-collection holidays, reminders and RFC 5545 export.
Every computed date carries computed_from = rule, version, inputs, card source indexes, legal basis, steps, warnings.
A missing input gives {"status": "missing_info", ...}; nothing is guessed. Stdlib only, no network."""
from datetime import date, datetime, timedelta, timezone

from .applicability import _as_date, _g, latest_fact

VERSION = "2026-10-14"
DAY = timedelta(days=1)

# Legal basis, keyed by id (quotes checked word for word with tools/fedlex.py on 14.10.2026, unless verified=False).
SOURCES = {
    "cst_110_3": {"title": "Cst. art. 110 al. 3 (fête nationale)", "url": "https://www.fedlex.admin.ch/eli/cc/1999/404/fr#art_110",
                  "quote": "Le 1er août est le jour de la fête nationale.", "verified": True},
    "cpc_142": {"title": "CPC art. 142 al. 1 et 3 (computation)", "url": "https://www.fedlex.admin.ch/eli/cc/2010/262/fr#art_142",
                "quote": "Si le dernier jour est un samedi, un dimanche ou un jour férié reconnu par le droit fédéral ou le "
                         "droit cantonal du siège du tribunal, le délai expire le premier jour ouvrable qui suit.", "verified": True},
    "pa_20": {"title": "PA art. 20 al. 1 et 3 (computation, procédure administrative fédérale)",
              "url": "https://www.fedlex.admin.ch/eli/cc/1969/737_757_755/fr#art_20",
              "quote": "Lorsque le délai échoit un samedi, un dimanche ou un jour férié selon le droit fédéral ou cantonal, "
                       "son terme est reporté au premier jour ouvrable qui suit.", "verified": True},
    "lp_31": {"title": "LP art. 31 (renvoi au CPC)", "url": "https://www.fedlex.admin.ch/eli/cc/11/529_488_529/fr#art_31",
              "quote": "les règles du code de procédure civile du 19 décembre 2008 (CPC) s’appliquent à la computation et à "
                       "l’observation des délais.", "verified": True},
    "lp_56": {"title": "LP art. 56 ch. 2 (féries)", "url": "https://www.fedlex.admin.ch/eli/cc/11/529_488_529/fr#art_56",
              "quote": "pendant les féries, à savoir sept jours avant et sept jours après les fêtes de Pâques et de Noël, "
                       "ainsi que du 15 juillet au 31 juillet", "verified": True},
    "lp_63": {"title": "LP art. 63 (prolongation au troisième jour utile)",
              "url": "https://www.fedlex.admin.ch/eli/cc/11/529_488_529/fr#art_63",
              "quote": "le délai est prolongé jusqu’au troisième jour utile. Pour le calcul du délai de trois jours, le samedi, "
                       "le dimanche et les jours légalement fériés ne sont pas comptés.", "verified": True},
    "lp_74": {"title": "LP art. 74 al. 1 (opposition, 10 jours)", "url": "https://www.fedlex.admin.ch/eli/cc/11/529_488_529/fr#art_74",
              "quote": "à l’office dans les dix jours à compter de la notification du commandement de payer.", "verified": True},
    "ofj_holidays": {"title": "OFJ, Jours fériés légaux ou considérés comme tels en Suisse (liste par canton)",
                     "url": "https://www.bj.admin.ch/dam/bj/de/data/publiservice/service/zivilprozessrecht/kant-feiertage.pdf",
                     "quote": None, "verified": False},  # PDF returned HTTP 502 on 14.10.2026: cantonal lists to re-check
}

FIXED = {"new_year": (1, 1, "Nouvel An"), "berchtold": (1, 2, "2 janvier"), "epiphany": (1, 6, "Épiphanie"),
         "st_joseph": (3, 19, "Saint-Joseph"), "labour": (5, 1, "1er mai"), "peter_paul": (6, 29, "Saints Pierre et Paul"),
         "national": (8, 1, "Fête nationale"), "assumption": (8, 15, "Assomption"), "all_saints": (11, 1, "Toussaint"),
         "immaculate": (12, 8, "Immaculée Conception"), "christmas": (12, 25, "Noël"), "st_stephen": (12, 26, "Saint-Étienne"),
         "restoration": (12, 31, "Restauration de la République")}
EASTER_BASED = {"good_friday": (-2, "Vendredi saint"), "easter_monday": (1, "Lundi de Pâques"), "ascension": (39, "Ascension"),
                "whit_monday": (50, "Lundi de Pentecôte"), "corpus_christi": (60, "Fête-Dieu")}
# ponytail: five cantons from the OFJ list as known on 14.10.2026 (unverified, see SOURCES["ofj_holidays"]); add a canton
# by adding a line. Without a canton only the federal 1 August counts: the result is the earliest possible (safe) date.
CANTONAL = {
    "VD": ["new_year", "berchtold", "good_friday", "easter_monday", "ascension", "whit_monday", "jeune_federal_monday", "christmas"],
    "ZH": ["new_year", "berchtold", "good_friday", "easter_monday", "labour", "ascension", "whit_monday", "christmas", "st_stephen"],
    "BE": ["new_year", "berchtold", "good_friday", "easter_monday", "ascension", "whit_monday", "christmas", "st_stephen"],
    "GE": ["new_year", "good_friday", "easter_monday", "ascension", "whit_monday", "jeune_genevois", "christmas", "restoration"],
    "TI": ["new_year", "epiphany", "st_joseph", "easter_monday", "labour", "ascension", "whit_monday", "corpus_christi",
           "peter_paul", "assumption", "all_saints", "immaculate", "christmas", "st_stephen"],
}


def easter(y: int) -> date:
    """Gregorian Easter Sunday (anonymous Gregorian algorithm, Meeus/Jones/Butcher)."""
    a, (b, c) = y % 19, divmod(y, 100)
    d, e = divmod(b, 4)
    g = (b - (b + 8) // 25 + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(y, month, day + 1)


def _sunday_after(d: date) -> date:
    return d + timedelta(days=(6 - d.weekday()) % 7)


def holidays(year: int, canton: str | None = None) -> dict[date, str]:
    """Federal 1 August (Cst. 110 al. 3) plus the canton's official holidays, {date: French name}."""
    out = {date(year, 8, 1): "Fête nationale"}
    for name in CANTONAL.get(canton or "", []):
        if name in FIXED:
            m, d, label = FIXED[name]
            out[date(year, m, d)] = label
        elif name in EASTER_BASED:
            off, label = EASTER_BASED[name]
            out[easter(year) + timedelta(days=off)] = label
        elif name == "jeune_federal_monday":  # Monday after the third Sunday of September
            out[_sunday_after(date(year, 9, 1)) + timedelta(days=15)] = "Lundi du Jeûne fédéral"
        elif name == "jeune_genevois":  # Thursday after the first Sunday of September
            out[_sunday_after(date(year, 9, 1)) + timedelta(days=4)] = "Jeûne genevois"
    return out


def non_working(d: date, canton: str | None) -> str | None:
    if d.weekday() >= 5:
        return ("samedi", "dimanche")[d.weekday() - 5]
    return holidays(d.year, canton).get(d)


def lp_ferie(d: date) -> tuple[date, date] | None:
    """LP art. 56 ch. 2 féries containing d: Easter −7…+7 (Rameaux to Quasimodo), 15–31 July, 18 Dec – 1 Jan."""
    e = easter(d.year)
    for start, end in ((e - 7 * DAY, e + 7 * DAY), (date(d.year, 7, 15), date(d.year, 7, 31)),
                       (date(d.year, 12, 18), date(d.year + 1, 1, 1)), (date(d.year - 1, 12, 18), date(d.year, 1, 1))):
        if start <= d <= end:
            return start, end
    return None


def _next_working(d: date, canton, steps: list) -> date:
    while reason := non_working(d, canton):
        steps.append(f"{d:%d.%m.%Y} est un jour non ouvrable ({reason}) → report au lendemain")
        d += DAY
    return d


def _nth_working_after(d: date, n: int, canton) -> date:
    while n:
        d += DAY
        n -= not non_working(d, canton)
    return d


def _year(context: dict, offset: int = 0) -> int | None:
    period = context.get("period")
    return int(str(period)[:4]) + offset if period else None


def _missing(rule_id: str, keys: list[str], why: str) -> dict:
    return {"status": "missing_info", "rule": rule_id, "missing": keys, "why": [why]}


def _canton(subject, context):
    return context.get("canton") or _g(subject, "canton")


def _holiday_basis(canton, res: dict):
    if canton in CANTONAL:
        res["basis"].append("ofj_holidays")
    else:
        res["warnings"].append(f"canton {canton or 'inconnu'} : seuls le samedi, le dimanche et le 1er août sont pris en "
                               "compte ; la date est la plus précoce possible (prudente), un jour férié cantonal pourrait la repousser")


# ---- rules: each returns a missing_info dict or {"due": date, "inputs", "steps", "warnings", "basis", extras...} --------

def _days_after(rule_id, params, subject, context):
    lp = rule_id == "debt_collection" or bool(params.get("lp_holidays"))
    if params.get("from_fact"):
        n, why = _fact_date(params["from_fact"], subject, context)
        if n is None:
            return _missing(rule_id, [params["from_fact"]], why)
        start = {"from_fact": params["from_fact"], "start_on": n.isoformat()}
    elif context.get("notified_on"):
        n = _as_date(context["notified_on"])
        start = {"notified_on": n.isoformat()}
    else:
        return _missing(rule_id, ["notified_on"], "date de notification (prouvée) inconnue : aucun délai n'est calculé")
    days = params.get("days", 10 if lp else None)
    if not isinstance(days, int) or days < 0:
        raise ValueError(f"{rule_id}: params.days must be an int >= 0, got {days!r}")
    business = params.get("count", "calendar") == "business"
    canton = _canton(subject, context)
    res = {"inputs": {**start, "days": days, "count": "business" if business else "calendar", "canton": canton, "lp_holidays": lp},
           "steps": [], "warnings": [], "basis": ["lp_31", "cpc_142"] + (["lp_74"] if days == 10 else []) if lp else ["pa_20", "cpc_142"]}
    _holiday_basis(canton, res)
    if days == 0:
        res["steps"].append(f"sans délai : au plus tard le jour de l'événement, {n:%d.%m.%Y}")
        res["warnings"].append("« sans délai » lu comme « aussitôt que possible, au plus tard le jour même » (interprétation Ordner)")
        return {**res, "due": n}
    end = _nth_working_after(n, days, canton) if business else n + timedelta(days=days)
    origin = f"fait « {params['from_fact']} »" if params.get("from_fact") else "notification"
    res["steps"].append(f"{origin} le {n:%d.%m.%Y}, le délai court dès le lendemain ; {days} jours "
                        f"{'ouvrables ' if business else ''}→ {end:%d.%m.%Y}")
    if lp and lp_ferie(n):
        res["warnings"].append("notification pendant les féries : ses effets pourraient être reportés après les féries "
                               "(jurisprudence à vérifier) ; la date donnée est la plus précoce")
    while True:
        if lp and (ferie := lp_ferie(end)):
            new_end = _nth_working_after(ferie[1], 3, canton)
            res["basis"] += ["lp_56", "lp_63"]
            res["steps"].append(f"{end:%d.%m.%Y} tombe dans les féries ({ferie[0]:%d.%m} – {ferie[1]:%d.%m.%Y}) → troisième "
                                f"jour utile après les féries (samedi, dimanche et fériés non comptés) : {new_end:%d.%m.%Y}")
            end = new_end
        elif params.get("extend_non_working", True) and non_working(end, canton):
            end = _next_working(end, canton, res["steps"])
            continue
        break
    return {**res, "due": end}


def _fixed(rule_id, params, subject, context):
    offset = params.get("year_offset", 0)
    year = _year(context, offset)
    if year is None:
        return _missing(rule_id, ["period"], "période inconnue : l'année de l'échéance ne peut pas être fixée")
    due = date(year, params["month"], params["day"])
    res = {"inputs": {"period": str(context["period"]), "month": params["month"], "day": params["day"], "year_offset": offset},
           "steps": [f"{due:%d.%m.%Y} : {due:%d.%m} de l'année de la période {context['period']} + {offset}"],
           "warnings": [], "basis": []}
    canton = _canton(subject, context)
    if reason := non_working(due, canton):
        res["warnings"].append(f"{due:%d.%m.%Y} tombe un jour non ouvrable ({reason}) ; un report éventuel dépend de la loi "
                               "de procédure applicable et n'est pas appliqué (date prudente)")
    extensions = []
    for ext in params.get("extensions") or []:
        e = dict(ext)
        for k in ("until", "request_by"):
            if e.get(k):
                m, d = map(int, str(e[k])[-5:].split("-"))
                e[k] = date(due.year, m, d).isoformat()
        extensions.append(e)
    if extensions:
        res["extensions"] = extensions
    chosen = context.get("extension")
    if chosen is not None:
        if not (isinstance(chosen, int) and 0 <= chosen < len(extensions) and extensions[chosen].get("until")):
            return _missing(rule_id, ["extension"], f"prolongation {chosen!r} inconnue pour cette règle")
        ext = extensions[chosen]
        res["inputs"]["extension"] = chosen
        res["steps"].append(f"prolongation retenue : {ext.get('how', '?')} jusqu'au {ext['until']} (frais {ext.get('fee_chf', '?')} CHF)")
        due = _as_date(ext["until"])
    if rule_id == "reception_by" or params.get("reception"):
        res["send_by"] = _send_by(due, params, context, canton, res["steps"])
        res["warnings"].append("date de RÉCEPTION : le cachet postal ne compte pas ; pas de report au jour ouvrable suivant")
    return {**res, "due": due}


def _cantonal_table(rule_id, params, subject, context):
    canton = _canton(subject, context)
    if not canton:
        return _missing(rule_id, ["subject.canton"], "canton inconnu : la table cantonale ne peut pas être lue")
    if canton not in params.get("table", {}):
        return _missing(rule_id, [f"table.{canton}"], f"canton {canton} absent de la table de la fiche : à qualifier")
    res = _fixed(rule_id, {**params["table"][canton]}, subject, context)
    if "due" in res:
        res["inputs"]["canton"] = canton
    return res


def _fact_date(key, subject, context):
    """(date, None) from the latest confirmed fact `key` in context["facts"], or (None, French reason)."""
    f, proposed = latest_fact(context.get("facts") or [], _g(subject, "id"), key)
    if f is None:
        return None, (f"fait « {key} » seulement proposé (valeur {_g(proposed, 'value')!r}) : à confirmer avant tout calcul"
                      if proposed is not None else f"fait « {key} » absent du dossier : aucun délai n'est calculé")
    try:
        return _as_date(_g(f, "value")), None
    except (TypeError, ValueError):
        return None, f"fait « {key} » = {_g(f, 'value')!r} n'est pas une date ISO"


def _chosen(rule_id, params, subject, context):
    if context.get("chosen_date"):
        d, origin = _as_date(context["chosen_date"]), {"chosen_date": context["chosen_date"]}
    elif params.get("from_fact"):
        d, why = _fact_date(params["from_fact"], subject, context)
        if d is None:
            return _missing(rule_id, [params["from_fact"]], why)
        origin = {"from_fact": params["from_fact"], "chosen_date": d.isoformat()}
    else:
        return _missing(rule_id, ["chosen_date"], "date choisie par la personne inconnue (ex. premier jour d'indemnité demandé)")
    return {"due": d, "inputs": origin, "steps": [f"au plus tard le jour choisi par la personne : {d:%d.%m.%Y}"],
            "warnings": [], "basis": []}


def _merge(params: dict, override: dict) -> dict:
    out = {**params, **override, "sources": list(dict.fromkeys((override.get("sources") or []) + (params.get("sources") or [])))}
    if "kinds" in params and "kinds" in override:  # per-kind merge: a cantonal "internal" keeps the card's "departure"
        out["kinds"] = {k: {**params["kinds"].get(k, {}), **override["kinds"].get(k, {})}
                        for k in {**params["kinds"], **override["kinds"]}}
    return out


DESTINATION_FACT = "move.planned.canton_to"


def _specialize(rule_id, params, subject, context):
    """Apply params["cantonal"][canton] then params["kinds"][kind]. A kind with "canton_of": "destination" (intercantonal
    arrival) reads the canton of arrival, "origin" the subject's. Returns (params, applied, context) or a missing dict."""
    applied = {"warnings": []}
    kind = context.get("kind")
    if params.get("kinds") and not kind:
        return _missing(rule_id, ["kind"], f"type d'événement nécessaire (règles propres : {', '.join(params['kinds'])})")
    canton_of = (params.get("kinds") or {}).get(kind, {}).get("canton_of", "origin")
    cantonal = params.pop("cantonal", None)
    if cantonal:
        if canton_of == "destination":
            canton, key = context.get("to_canton"), DESTINATION_FACT
            if not canton:
                f, _ = latest_fact(context.get("facts") or [], _g(subject, "id"), DESTINATION_FACT)
                canton = _g(f, "value") if f is not None else None
        else:
            canton, key = _canton(subject, context), "subject.canton"
        if not canton:
            return _missing(rule_id, [key], f"canton {'d’arrivée' if canton_of == 'destination' else ''} inconnu : la fiche "
                            "prévoit des règles cantonales".replace("  ", " "))
        context = {**context, "canton": canton}  # holidays follow the canton whose rule applies
        entry = dict(cantonal.get(canton) or {})
        if entry:
            if entry.get("rule"):
                applied["cantonal_rule"] = entry.pop("rule")
                applied["warnings"].append(f"règle cantonale {canton} décrite en texte (cantonal_rule) : à lire, le calcul "
                                           "ne reprend que ses paramètres chiffrés")
            params = _merge(params, entry)
            applied["cantonal"] = canton
        else:
            applied["warnings"].append(f"canton {canton} sans règle propre dans la fiche : règle de base appliquée, à qualifier")
        if canton_of == "destination":
            applied["canton_of"] = "destination"
    kinds = params.pop("kinds", None)
    if kinds and kind in kinds:
        params = _merge(params, {k: v for k, v in kinds[kind].items() if k != "canton_of"})
        applied["kind"] = kind
    return params, applied, context


def _variants(rule_id, params, subject, context):
    base = {k: v for k, v in params.items() if k not in ("variants", "applies_to")}
    options = [(params.get("applies_to") or ["default"], rule_id, base)]
    options += [([v["case"]], v.get("id", rule_id), {k: x for k, x in v.items() if k not in ("case", "id")})
                for v in params["variants"]]
    known = [c for cases, _, _ in options for c in cases]
    chosen = context.get("variant")
    if chosen is None:
        results = [{"cases": cases, **compute_deadline({"id": rid, "params": p}, subject, context)} for cases, rid, p in options]
        return {"status": "variants", "rule": rule_id, "missing": ["variant"], "variants": results,
                "why": [f"plusieurs échéances selon l'option : préciser la variante parmi {', '.join(known)}"]}
    for cases, rid, p in options:
        if chosen in cases:
            r = compute_deadline({"id": rid, "params": p}, subject, context)
            if r["status"] == "computed":
                r["variant"] = r["computed_from"]["variant"] = chosen
            return r
    return _missing(rule_id, ["variant"], f"variante {chosen!r} inconnue ; variantes : {', '.join(known)}")


RULES = {
    "fixed_date": _fixed,
    "days_after_notification": _days_after,
    "debt_collection": _days_after,
    "reception_by": _fixed,
    "cantonal_table": _cantonal_table,
    "year_end": lambda rid, p, s, c: _fixed(rid, {"month": 12, "day": 31, **p}, s, c),
    "chosen_date": _chosen,
}


def compute_deadline(rule, subject, context: dict) -> dict:
    """{"status": "computed", "due": "YYYY-MM-DD", "computed_from": {...}, ...} or {"status": "missing_info", "missing": [...]}."""
    rule_id, params = _g(rule, "id"), dict(_g(rule, "params") or {})
    context = context or {}
    if rule_id not in RULES:
        raise ValueError(f"unknown deadline rule {rule_id!r}; known: {DEADLINE_RULE_IDS}")
    if params.get("variants"):
        return _variants(rule_id, params, subject, context)
    spec = _specialize(rule_id, params, subject, context)
    if isinstance(spec, dict):
        return spec
    params, applied, context = spec
    res = RULES[rule_id](rule_id, params, subject, context)
    if res.get("status") == "missing_info":
        return res
    table_entry = params.get("table", {}).get(res["inputs"].get("canton"), {}) if rule_id == "cantonal_table" else {}
    if table_entry.get("rule"):
        applied["cantonal_rule"] = table_entry["rule"]
    computed_from = {"rule": rule_id, "version": VERSION, "inputs": res["inputs"],
                     "card_sources": table_entry.get("sources", params.get("sources", [])),
                     "legal_basis": list(dict.fromkeys(res["basis"])), "steps": res["steps"],
                     "warnings": applied.pop("warnings") + res["warnings"], **applied}
    if context.get("label"):
        computed_from["label"] = context["label"]
    if "send_by" in res:
        computed_from["send_by"] = res["send_by"]
    out = {"status": "computed", "due": res["due"].isoformat(), "computed_from": computed_from}
    out.update({k: res[k] for k in ("send_by", "extensions") if k in res})
    return out


def _send_by(due: date, params, context, canton, steps) -> str:
    """Suggested posting date: explicit send_by from the card's source, else N working days before (Ordner heuristic)."""
    if params.get("send_by"):
        s = date(due.year, params["send_by"]["month"], params["send_by"]["day"])
        how = "date conseillée par la source de la fiche"
    else:
        n = int(context.get("margin_working_days", params.get("margin_working_days", 5)))
        s, k = due, n
        while k:
            s -= DAY
            k -= not non_working(s, canton)
        how = f"marge de {n} jours ouvrables, heuristique Ordner et non règle légale"
    while reason := non_working(s, canton):
        steps.append(f"{s:%d.%m.%Y} non ouvrable ({reason}) → envoi avancé")
        s -= DAY
    steps.append(f"envoi conseillé au plus tard le {s:%d.%m.%Y} ({how})")
    return s.isoformat()


DEADLINE_RULE_IDS = list(RULES)

# ---- reminders and calendar export --------------------------------------------------------------------------------------

POLICIES = {"default": (30, 7, 1), "short": (3, 1), "reception": (30, 14, 7, 1)}


def reminders(due: str, policy="default", today=None) -> list[str]:
    """Reminder dates before `due` (policy name or list of day offsets); with `today`, past reminders are dropped."""
    offsets = POLICIES[policy] if isinstance(policy, str) else policy
    d = _as_date(due)
    out = sorted({d - timedelta(days=n) for n in offsets if n > 0})
    if today:
        out = [r for r in out if r >= _as_date(today)]
    return [r.isoformat() for r in out]


def _esc(text: str) -> str:
    return str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545 §3.1: lines of at most 75 octets, continuation lines start with one space, UTF-8 never split."""
    parts, cur = [], ""
    for ch in line:
        if len((cur + ch).encode()) > (74 if parts else 75):
            parts.append(cur)
            cur = ch
        else:
            cur += ch
    return "\r\n ".join(parts + [cur])


def to_ics(deadlines, subject) -> str:
    """RFC 5545 VCALENDAR: one all-day VEVENT per deadline, one VALARM per reminder (09:00 CET = 08:00Z). Local text only."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Meotis//Ordner//FR", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             f"X-WR-CALNAME:{_esc('Ordner – ' + str(_g(subject, 'name') or _g(subject, 'id')))}"]
    for dl in deadlines:
        due, cf = _as_date(_g(dl, "due")), _g(dl, "computed_from") or {}
        summary = cf.get("label") or f"Échéance {_g(dl, 'rule_id')} ({_g(dl, 'case_id')})"
        desc = "\n".join([f"Règle : {cf.get('rule', _g(dl, 'rule_id'))} (version {cf.get('version', '?')})",
                          *cf.get("steps", []), *(f"Attention : {w}" for w in cf.get("warnings", [])),
                          *(["Bases : " + ", ".join(SOURCES[k]["title"] for k in cf["legal_basis"] if k in SOURCES)]
                            if cf.get("legal_basis") else []),
                          "Ordner prépare ; la personne agit (rien n'est envoyé automatiquement)."])
        lines += ["BEGIN:VEVENT", f"UID:{_g(dl, 'id')}@ordner.local", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{due:%Y%m%d}", f"DTEND;VALUE=DATE:{due + DAY:%Y%m%d}",
                  f"SUMMARY:{_esc(summary)}", f"DESCRIPTION:{_esc(desc)}", "TRANSP:TRANSPARENT"]
        for r in _g(dl, "reminders") or reminders(due.isoformat()):
            lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_esc('Rappel : ' + summary)}",
                      f"TRIGGER;VALUE=DATE-TIME:{_as_date(r):%Y%m%d}T080000Z", "END:VALARM"]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "".join(_fold(line) + "\r\n" for line in lines)
