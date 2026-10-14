"""demenagement.annoncer: a move -> departure/arrival (or internal) announcements with the cantonal deadlines (card
housing.moving.announce: kinds arrival/departure/internal, destination/origin canton rules), tax canton at 31.12 (tax
return card of that canton when the catalogue has one), LAMal premium region, Serafe; prepared announcement."""
from datetime import date

from ordner.core.schema import ToolSpec

from ..base import ToolError
from . import (CANTONS, card, deadline, fmt, given, iso, label, lang, prepare, question, remember, result, sources,
               subject_ctx, t, value)

CARD = "housing.moving.announce"


def _same(a, b):
    return bool(a and b) and a.strip().casefold() == b.strip().casefold()


def annoncer(args, ctx):
    from ordner import rules as R

    st, subject, day = subject_ctx(args, ctx)
    sid, lg, c, attrs = subject.id, lang(subject), card(CARD), subject.attrs or {}
    facts = st.facts(sid)
    move = iso(args.get("move_date"), "move_date")
    from_arg = bool(move)
    move = move or iso(value(facts, "housing.moving.date", "move.planned.date"), "housing.moving.date")
    moved = bool(attrs.get("previous_commune") or attrs.get("previous_canton"))  # subject already at the new address
    to_canton = (args.get("to_canton") or value(facts, "move.planned.canton_to") or (subject.canton if moved else None))
    to_commune = (args.get("to_commune") or value(facts, "move.planned.commune", "housing.commune.new")
                  or (subject.commune if moved else None))
    from_commune = args.get("from_commune") or (attrs.get("previous_commune") if moved else subject.commune)
    from_canton = args.get("from_canton") or attrs.get("previous_canton") or subject.canton
    for k, v in (("to_canton", to_canton), ("from_canton", from_canton)):
        if v and v not in CANTONS:
            raise ToolError(f"{k} must be a two-letter canton code, got {v!r}")
    warnings, questions, missing, prepared, deadlines, tasks, applicable = [], [], [], [], [], [], [CARD]

    if args.get("to_canton"):
        remember(st, sid, "move.planned.canton_to", to_canton)
    if args.get("to_commune"):
        remember(st, sid, "move.planned.commune", to_commune)
    if from_arg:
        remember(st, sid, "housing.moving.date", move)
    if not move:
        missing.append("housing.moving.date")
        questions.append(question("housing.moving.date", t(lg, "À quelle date déménagez-vous (ou avez-vous déménagé) ?",
                                                          "An welchem Datum ziehen Sie um (oder sind Sie umgezogen)?",
                                                          "In che data trasloca (o ha traslocato)?")))
    if not (to_canton or to_commune):
        missing.append("move.planned.canton_to")
        questions.append(question("move.planned.canton_to", t(lg, "Dans quelle commune et quel canton allez-vous habiter ?",
                                                             "In welche Gemeinde und welchen Kanton ziehen Sie?",
                                                             "In quale comune e cantone andrà ad abitare?")))
    dest_known = bool(to_canton or to_commune)
    if to_commune and not to_canton:
        warnings.append(t(lg, f"canton de {to_commune} supposé {from_canton} (même canton) : à confirmer",
                          f"Kanton von {to_commune} als {from_canton} angenommen: bitte bestätigen",
                          f"cantone di {to_commune} supposto {from_canton}: da confermare"))
    to_canton = to_canton or from_canton
    internal = _same(from_commune, to_commune) and to_canton == from_canton
    facts_ = facts + ([given(sid, "housing.moving.date", move)] if move else [])
    if move:
        legs = ([("internal", from_canton, t(lg, f"annoncer le changement d'adresse à {to_commune}",
                                            f"Adressänderung in {to_commune} melden", f"annunciare il cambio d'indirizzo a "
                                            f"{to_commune}"))] if internal else
                [("departure", from_canton, t(lg, f"annoncer le départ à {from_commune or 'l’ancienne commune'}",
                                              f"Wegzug in {from_commune or 'der bisherigen Gemeinde'} melden",
                                              f"annunciare la partenza a {from_commune or 'il comune attuale'}")),
                 ("arrival", to_canton, t(lg, f"annoncer l'arrivée à {to_commune or 'la nouvelle commune'}",
                                          f"Zuzug in {to_commune or 'der neuen Gemeinde'} melden",
                                          f"annunciare l'arrivo a {to_commune or 'il nuovo comune'}"))][:2 if dest_known else 1])
        for kind, canton, what in legs:
            res = R.compute_deadline(c.deadline, subject, {"kind": kind, "canton": canton, "to_canton": to_canton,
                                                           "facts": facts_, "today": day.isoformat()})
            if d := deadline(c, res, what, kind=kind, canton=canton):
                deadlines.append(d)
                if d["due"] < day.isoformat():
                    warnings.append(t(lg, f"{what} : délai du {fmt(d['due'])} dépassé, faites-le sans attendre",
                                      f"{what}: Frist {fmt(d['due'])} verpasst, sofort erledigen",
                                      f"{what}: termine del {fmt(d['due'])} superato, lo faccia subito"))
            else:
                missing += res.get("missing", [])

    # taxes: the canton of domicile on 31 December taxes the whole year
    tax_note = t(lg, "règle du domicile au 31 décembre (LHID art. 68) : source à vérifier dans Ordner",
                 "Wohnsitz am 31. Dezember (StHG Art. 68): Quelle in Ordner zu prüfen",
                 "domicilio al 31 dicembre (LAID art. 68): fonte da verificare in Ordner")
    if move and dest_known and from_canton != to_canton:
        y = date.fromisoformat(move).year
        for period, canton in ((y - 1, from_canton), (y, to_canton)):
            tc = card(f"tax.return.{canton}")
            task = {"task": t(lg, f"impôts {period} : canton de {canton} (domicile au 31.12.{period})",
                              f"Steuern {period}: Kanton {canton} (Wohnsitz am 31.12.{period})",
                              f"imposte {period}: cantone {canton} (domicilio al 31.12.{period})"),
                    "to_verify": tax_note}
            if tc is None:
                task["note"] = t(lg, f"pas de fiche Ordner pour la déclaration {canton} : délai à vérifier auprès du canton",
                                 f"keine Ordner-Karte für {canton}: Frist beim Kanton prüfen",
                                 f"nessuna scheda Ordner per {canton}: termine da verificare")
                tasks.append(task)
                continue
            res = R.compute_deadline(tc.deadline, subject, {"period": str(period), "canton": canton,
                                                            "today": day.isoformat()}) if tc.deadline else None
            d = deadline(tc, res, t(lg, f"déclaration d'impôt {period} ({canton})", f"Steuererklärung {period} ({canton})",
                                    f"dichiarazione d'imposta {period} ({canton})"))
            if d and d["due"] < day.isoformat():
                continue  # earlier return, presumably filed; not part of this move
            task["card_id"] = tc.id
            tasks.append(task)
            if d:
                deadlines.append(d)
                applicable.append(tc.id)
    s_ = card("household.serafe_fee")
    tasks.append({"task": t(lg, "Serafe : rien à faire, la redevance suit le registre des habitants (annonce communale)",
                            "Serafe: nichts zu tun, die Abgabe folgt dem Einwohnerregister",
                            "Serafe: nulla da fare, il canone segue il registro degli abitanti"),
                  "sources": sources(s_, [3]) if s_ else []})
    tasks.append({"task": t(lg, "LAMal : annoncer la nouvelle adresse à la caisse maladie ; la prime dépend du canton et "
                                "de la région de domicile (primes OFSP par région)",
                            "KVG: neue Adresse der Krankenkasse melden; die Prämie hängt von Kanton und Region ab",
                            "LAMal: comunicare il nuovo indirizzo alla cassa malati; il premio dipende da cantone e "
                            "regione"),
                  "source": "OFSP/BAG, Primes de l'assurance-maladie (opendata.swiss)",
                  "changes_premium": from_canton != to_canton or None})

    docs_needed = [label(k, lg) for k in c.required_documents]
    if move and dest_known and not missing:
        arrival = next((d for d in deadlines if d.get("kind") in ("arrival", "internal")), None)
        prepared.append(prepare(st, sid, CARD, str(date.fromisoformat(move).year), "form_entry", {
            "step": "announce_arrival", "commune": to_commune, "canton": to_canton, "move_date": move,
            "due": arrival and arrival["due"], "bring": docs_needed,
            "how": t(lg, "au contrôle des habitants (guichet ou guichet virtuel / eDéménagement si la commune le propose)",
                     "bei der Einwohnerkontrolle (Schalter oder eUmzug, falls angeboten)",
                     "al controllo abitanti (sportello o eTrasloco se disponibile)")}))
    if deadlines:
        parts = "; ".join(f"{d['what']} {t(lg, 'au plus tard le', 'bis', 'entro il')} {fmt(d['due'])}" for d in deadlines)
        summary = t(lg, f"Déménagement le {fmt(move)} : {parts}.", f"Umzug am {fmt(move)}: {parts}.",
                    f"Trasloco il {fmt(move)}: {parts}.")
    else:
        summary = t(lg, "Déménagement : il me faut la date (et la destination) pour calculer les délais d'annonce.",
                    "Umzug: Ich brauche das Datum (und das Ziel) für die Meldefristen.",
                    "Trasloco: mi servono la data (e la destinazione) per calcolare i termini.")
    return (result(summary, status="applicable", card_id=CARD, applicable=applicable, deadlines=deadlines,
                   missing=missing, questions=questions, prepared=prepared, tasks=tasks, bring=docs_needed,
                   move={"date": move, "from": [from_commune, from_canton], "to": [to_commune, to_canton],
                         "kind": "internal" if internal else "intercommunal"}),
            warnings, {"card": CARD, "source": "ordner.rules"})


TOOLS = [(ToolSpec(
    "demenagement.annoncer",
    "Move (déménagement, Umzug, trasloco), planned or done: departure and arrival announcements with the cantonal "
    "deadlines, which canton taxes the year (domicile on 31.12) and its tax return deadline, LAMal address/premium, "
    "Serafe; prepares the arrival announcement.",
    {"type": "object", "properties": {
        "subject_id": {"type": "string"},
        "move_date": {"type": "string", "description": "YYYY-MM-DD of the move"},
        "to_canton": {"type": "string", "enum": CANTONS, "description": "canton of the new home"},
        "to_commune": {"type": "string"},
        "from_commune": {"type": "string", "description": "only if not the dossier's commune"},
        "from_canton": {"type": "string", "enum": CANTONS, "description": "only if not the dossier's canton"}},
     "required": ["subject_id"]},
    {"type": "object", "description": "summary, deadlines (departure, arrival, tax return), tasks, questions, "
                                      "prepared_actions"},
), annoncer)]
