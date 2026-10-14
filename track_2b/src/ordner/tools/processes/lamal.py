"""lamal.revoir_franchise: change of insurer, deductible or model for next year -> deadlines per variant (30.11 reception,
31.12 for a higher deductible) with send-by date, OFSP premium comparison and break-even (connectors.ofsp_premiums,
offline data in work/ofsp), arrears block, prepared letter. Card health_insurance.change_insurer_or_deductible."""
import re
from functools import lru_cache

from ordner.core.schema import ToolSpec

from ..base import ToolError
from . import card, deadline, fmt, given, lang, prepare, question, remember, result, sources, subject_ctx, t, value

CARD = "health_insurance.change_insurer_or_deductible"
CHANGES = ["change_insurer", "lower_deductible", "higher_deductible", "leave_restricted_model"]
DEDUCTIBLES = [300, 500, 1000, 1500, 2000, 2500]
DOWNLOAD = "PYTHONPATH=src .venv/bin/python -m ordner.connectors.ofsp_premiums download"


def _num(x):
    m = re.search(r"\d[\d']*(?:\.\d+)?", str(x if x is not None else ""))
    return float(m.group().replace("'", "")) if m else None


@lru_cache(maxsize=4)
def _rows(canton):
    from ordner.connectors import ofsp_premiums as O
    return tuple(O.load(canton=canton))


def _age_class(subject, year):
    by = (subject.attrs or {}).get("birth_year")
    if not by:
        return "adult", True
    age = year - int(by)
    return ("child" if age <= 18 else "young_adult" if age <= 25 else "adult"), False


def compare(subject, year, deductible, monthly, accident, expected_costs, region=None):
    """OFSP comparison for the subject's profile, or ({}, [warnings]) when the data is not loaded."""
    from ordner.connectors import ofsp_premiums as O
    if not (O.WORK / "Prämien_CH.csv").exists():
        return None, [f"données OFSP non chargées : lancer `{DOWNLOAD}` (une fois, hors ligne ensuite)"]
    rows, warnings = [r for r in _rows(subject.canton) if r["year"] == year], []
    if not rows:
        return None, [f"pas de primes OFSP {year} pour {subject.canton} dans work/ofsp (données d'une autre année)"]
    regions = sorted({r["region"] for r in rows})
    if region is None:
        region = regions[0]
        if len(regions) > 1:
            warnings.append(f"région de primes supposée {region} (le canton en a {regions}) : dépend de la commune, à "
                            "vérifier sur la page OFSP de la commune")
    age, unknown_age = _age_class(subject, year)
    if unknown_age:
        warnings.append("année de naissance inconnue : tarif adulte supposé")
    costs = float(expected_costs or 0)
    offers = O.compare(list(rows), subject.canton, region, age, bool(accident), deductible=deductible, expected_costs=costs)
    if not offers:
        return None, warnings + ["aucune offre OFSP pour ce profil"]
    best = offers[0]
    same = O.compare(list(rows), subject.canton, region, age, bool(accident), expected_costs=costs)
    table = O.deductible_table([o for o in same if o["insurer"] == best["insurer"] and o["tariff"] == best["tariff"]],
                               costs, age)
    out = {"year": year, "region": region, "age_class": age, "accident": bool(accident), "expected_costs": costs,
           "cheapest": [{k: o[k] for k in ("insurer", "tariff_name", "model", "deductible", "monthly", "total")}
                        for o in offers[:3]],
           "best_deductible": table["best"], "break_even": table["break_even"], "source": O.SOURCE,
           "insurer_note": "assureur = numéro OFSP (noms absents des données)"}
    if monthly:
        out["saving_per_year_vs_current"] = round(12 * (monthly - best["monthly"]), 2)
    return out, warnings


def _letter(lg, change, insurer, current, new, model, year, period, subject):
    from ordner.connectors import email_drafts
    if change == "change_insurer":
        v = {"end_date": f"31.12.{period}", "sender_name": subject.name, "recipient_name": insurer, "place": subject.commune}
        r = email_drafts.render("lamal_termination", {k: x for k, x in v.items() if x})
        return "lamal_termination", r["subject"], r["body"], r["missing"]
    what = {"higher_deductible": t(lg, f"passer à la franchise de CHF {new}", f"auf die Franchise von CHF {new} wechseln",
                                   f"passare alla franchigia di CHF {new}"),
            "lower_deductible": t(lg, f"passer à la franchise de CHF {new}", f"auf die Franchise von CHF {new} wechseln",
                                  f"passare alla franchigia di CHF {new}"),
            "leave_restricted_model": t(lg, f"quitter le modèle {model or 'actuel'} pour le modèle standard (libre choix "
                                            "du médecin)", f"vom Modell {model or ''} ins Standardmodell (freie Arztwahl) "
                                        "wechseln", f"lasciare il modello {model or ''} per il modello standard")}[change]
    subj = t(lg, f"Assurance obligatoire des soins : modification au 1er janvier {year}",
             f"Grundversicherung: Änderung per 1. Januar {year}", f"Assicurazione di base: modifica al 1° gennaio {year}")
    body = t(lg, f"Madame, Monsieur,\n\nPar la présente, je souhaite {what} dès le 1er janvier {year}"
                 f"{f' (franchise actuelle : CHF {current})' if current and 'deductible' in change else ''}.\n\n"
                 "Je vous remercie de me confirmer cette modification par écrit.\n\nMeilleures salutations\n\n"
                 f"{subject.name}\n",
             f"Sehr geehrte Damen und Herren\n\nIch möchte per 1. Januar {year} {what}.\n\nBitte bestätigen Sie mir "
             f"diese Änderung schriftlich.\n\nFreundliche Grüsse\n\n{subject.name}\n",
             f"Gentili signore e signori,\n\ndesidero {what} dal 1° gennaio {year}.\n\nVi prego di confermarmi la "
             f"modifica per iscritto.\n\nCordiali saluti\n\n{subject.name}\n")
    return "lamal_change", subj, body, ([] if new or change == "leave_restricted_model" else ["new_deductible"])


def revoir(args, ctx):
    from ordner import rules as R

    st, subject, day = subject_ctx(args, ctx)
    sid, lg, c = subject.id, lang(subject), card(CARD)
    year = args.get("year") or day.year + 1
    if not 2000 < year < 2100:
        raise ToolError("year must be the premium year, e.g. 2027")
    period = str(year - 1)
    facts, docs = st.facts(sid), st.documents(sid)
    attrs = subject.attrs or {}
    letters = sorted((d for d in docs if d.kind == "health_insurance_premium_letter"), key=lambda d: (d.year or 0, d.received_at))
    letter = next((d for d in reversed(letters) if d.year == year), letters[-1] if letters else None)
    lf = (letter.fields or {}) if letter else {}
    insurer = (value(facts, "health_insurance.basic.insurer", "health.lamal.insurer") or lf.get("insurer")
               or (letter.issuer if letter else None))
    current = value(facts, "health_insurance.basic.deductible", "health.lamal.deductible") or attrs.get("lamal_deductible") \
        or lf.get("deductible")
    model = value(facts, "health_insurance.basic.model") or attrs.get("lamal_model") or lf.get("model")
    monthly = lf.get("monthly_premium") or value(facts, "health.lamal.monthly_premium", "health_insurance.premium.next_year")
    accident = lf.get("accident_cover") if lf.get("accident_cover") is not None else value(facts, "health.lamal.accident_cover")
    current = int(_num(current)) if _num(current) is not None else None
    monthly = _num(monthly)
    new = args.get("new_deductible")
    if new is not None and new not in DEDUCTIBLES:
        raise ToolError(f"new_deductible must be one of {DEDUCTIBLES} (adults)")
    change = args.get("change")
    if not change and new and current:
        change = "higher_deductible" if new > current else "lower_deductible" if new < current else None
    warnings, questions, missing, prepared = [], [], [], []

    shim = [given(sid, "health_insurance.basic.insurer", insurer)] if insurer else []
    app = R.applicable(c, subject, facts + shim, on=day.isoformat(), period=period)
    if app["status"] != "applicable":
        missing += app["missing"]
        if "health_insurance.basic.insurer" in app["missing"]:
            questions.append(question("health_insurance.basic.insurer", t(
                lg, "Auprès de quelle caisse maladie êtes-vous assuré·e pour l'assurance de base ?",
                "Bei welcher Krankenkasse sind Sie grundversichert?", "Presso quale cassa malati è assicurato/a per "
                "l'assicurazione di base?")))
        if app["status"] == "not_applicable":
            return (result(t(lg, "Ce changement LAMal ne s'applique pas à ce dossier.", "Dieser KVG-Wechsel betrifft "
                             "dieses Dossier nicht.", "Questo cambio LAMal non riguarda il dossier."),
                           status="not_applicable", card_id=CARD, why=app["why"][:3]), warnings, {"card": CARD})
    if insurer and letter is not None and not value(facts, "health_insurance.basic.insurer", "health.lamal.insurer"):
        remember(st, sid, "health_insurance.basic.insurer", insurer, source_doc=letter.id)

    arrears = (value(facts, "health_insurance.arrears.outstanding") is True or attrs.get("lamal_arrears") is True
               or any(d.kind == "payment_reminder" and (not insurer or not d.issuer or d.issuer == insurer) for d in docs))
    if arrears:
        warnings.append(t(lg, "arriérés de primes avec rappel : tant qu'ils ne sont pas entièrement payés, le changement de "
                              f"caisse est bloqué (rappels jusqu'au 30.11.{period}) ; payez-les à temps, ou le changement "
                              "n'aura pas lieu", "Prämienausstände mit Mahnung: Kassenwechsel blockiert, bis alles bezahlt ist",
                          "premi arretrati con richiamo: il cambio di cassa è bloccato finché non sono pagati"))

    base_ctx = {"period": period, "today": day.isoformat()}
    deadlines, options = [], []
    if change:
        res = R.compute_deadline(c.deadline, subject, {**base_ctx, "variant": change})
        deadlines.append(deadline(c, res, t(lg, "réception par la caisse (pas le cachet postal)", "Eingang bei der Kasse "
                                            "(nicht Poststempel)", "ricezione presso la cassa (non il timbro postale)"),
                                  variant=change))
    else:
        res = R.compute_deadline(c.deadline, subject, base_ctx)
        for v in res.get("variants", []):
            if d := deadline(c, v, "/".join(v["cases"]), variant=v["cases"]):
                options.append(d)
        missing.append("health_insurance.change")
        questions.append(question("health_insurance.change", t(
            lg, f"Que voulez-vous changer pour {year} : de caisse, franchise plus haute, franchise plus basse, ou quitter "
                "un modèle médecin de famille/télémédecine ?",
            f"Was möchten Sie für {year} ändern: Kasse, höhere oder tiefere Franchise, oder ein Hausarzt-/Telmed-Modell "
            "verlassen?", f"Cosa vuole cambiare per il {year}: cassa, franchigia più alta o più bassa, o lasciare un "
            "modello medico di famiglia/telemedicina?")))
    dl = deadlines[0] if deadlines else None
    if dl and dl["due"] < day.isoformat():
        warnings.append(t(lg, f"délai du {fmt(dl['due'])} dépassé : le changement n'est plus possible pour {year}",
                          f"Frist {fmt(dl['due'])} abgelaufen: Wechsel für {year} nicht mehr möglich",
                          f"termine del {fmt(dl['due'])} scaduto: cambio non più possibile per il {year}"))
    elif dl and dl.get("send_by") and dl["send_by"] < day.isoformat():
        warnings.append(t(lg, f"envoi conseillé avant le {fmt(dl['send_by'])} dépassé : la lettre doit PARVENIR à la "
                              f"caisse le {fmt(dl['due'])} au plus tard (poster ce jour-là ne suffit pas) ; recommandé "
                              "urgent ou dépôt au guichet", f"Empfohlener Versand bis {fmt(dl['send_by'])} verpasst: der "
                          f"Brief muss am {fmt(dl['due'])} EINTREFFEN", f"invio consigliato entro il {fmt(dl['send_by'])} "
                          f"superato: la lettera deve ARRIVARE entro il {fmt(dl['due'])}"))

    comparison, w = compare(subject, year, new or current, monthly, accident,
                            args.get("expected_costs"), (subject.attrs or {}).get("premium_region"))
    warnings += w
    if change and app["status"] == "applicable" and not (dl and dl["due"] < day.isoformat()):
        template, subj, body, gaps = _letter(lg, change, insurer, current, new, model, year, period, subject)
        prepared.append(prepare(st, sid, CARD, period, "letter", {
            "template": template, "recipient": insurer, "subject": subj, "body": body, "missing": gaps,
            "change": change, "due": dl and dl["due"], "send_by": dl and dl.get("send_by"),
            "how": t(lg, "lettre signée, en recommandé ou « Courrier A Plus »", "unterschriebener Brief, eingeschrieben "
                     "oder A-Post Plus", "lettera firmata, raccomandata o « Posta A Plus »")}))
        if change == "change_insurer":
            warnings.append(t(lg, "affiliez-vous d'abord à la nouvelle caisse (demande d'admission) : l'ancienne "
                                  "affiliation ne prend fin que quand la nouvelle caisse l'a confirmée",
                              "zuerst bei der neuen Kasse anmelden: die alte Versicherung endet erst nach deren Bestätigung",
                              "prima affiliarsi alla nuova cassa: la vecchia termina solo dopo la sua conferma"))
    if dl:
        summary = t(lg, f"LAMal {year} ({change}) : votre lettre doit parvenir à {insurer or 'la caisse'} au plus tard le "
                        f"{fmt(dl['due'])}" + (f" (à poster avant le {fmt(dl['send_by'])})" if dl.get("send_by") else "")
                    + (". Lettre préparée, à signer et envoyer vous-même." if prepared else "."),
                    f"KVG {year} ({change}): Ihr Brief muss bis {fmt(dl['due'])} bei {insurer or 'der Kasse'} eintreffen"
                    + (f" (Versand bis {fmt(dl['send_by'])})" if dl.get("send_by") else "")
                    + (". Brief vorbereitet, selbst unterschreiben und senden." if prepared else "."),
                    f"LAMal {year} ({change}): la lettera deve arrivare a {insurer or 'la cassa'} entro il {fmt(dl['due'])}"
                    + (f" (spedire entro il {fmt(dl['send_by'])})" if dl.get("send_by") else "")
                    + (". Lettera preparata, da firmare e inviare lei stesso." if prepared else "."))
    else:
        summary = t(lg, f"LAMal {year} : changement de caisse ou franchise plus basse = réception au 30.11.{period} ; "
                        f"franchise plus haute = au 31.12.{period}. Précisez le changement voulu.",
                    f"KVG {year}: Kassenwechsel oder tiefere Franchise bis 30.11.{period}, höhere Franchise bis "
                    f"31.12.{period} (Eingang). Welche Änderung?",
                    f"LAMal {year}: cambio di cassa o franchigia più bassa entro il 30.11.{period}, più alta entro il "
                    f"31.12.{period}. Quale cambio?")
    if comparison and comparison.get("best_deductible"):
        summary += t(lg, f" Selon l'OFSP, franchise la moins chère pour {comparison['expected_costs']:.0f} CHF de frais : "
                         f"{comparison['best_deductible']['deductible']}.",
                     f" Laut BAG günstigste Franchise bei {comparison['expected_costs']:.0f} CHF Kosten: "
                     f"{comparison['best_deductible']['deductible']}.",
                     f" Secondo l'UFSP, franchigia più conveniente con {comparison['expected_costs']:.0f} CHF di costi: "
                     f"{comparison['best_deductible']['deductible']}.")
    current_ = {"insurer": insurer, "deductible": current, "model": model, "monthly_premium": monthly}
    return (result(summary, status="applicable" if app["status"] == "applicable" else app["status"], card_id=CARD,
                   applicable=[CARD] if app["status"] == "applicable" else [], deadlines=deadlines, missing=missing,
                   questions=questions, prepared=prepared, current=current_, deadline_options=options,
                   comparison=comparison, arrears=arrears,
                   sources=sources(c, [0, 5, 2] if arrears else [0, 5])),
            warnings, {"card": CARD, "source": "ordner.rules + connectors.ofsp_premiums"})


TOOLS = [(ToolSpec(
    "lamal.revoir_franchise",
    "Health insurance (LAMal/KVG) for next year: change insurer, raise or lower the deductible (franchise), or leave a "
    "family-doctor/telmed model. Gives the reception deadline (30.11, or 31.12 for a higher deductible) and send-by date, "
    "the OFSP premium comparison and break-even, and prepares the letter.",
    {"type": "object", "properties": {
        "subject_id": {"type": "string"},
        "change": {"type": "string", "enum": CHANGES},
        "new_deductible": {"type": "integer", "description": "wanted deductible in CHF (300, 500, 1000, 1500, 2000, 2500)"},
        "expected_costs": {"type": "number", "description": "expected yearly medical costs in CHF, if the person said"},
        "year": {"type": "integer", "description": "premium year concerned, default next year"}},
     "required": ["subject_id"]},
    {"type": "object", "description": "summary, deadlines (or deadline_options), comparison, questions, prepared_actions"},
), revoir)]
