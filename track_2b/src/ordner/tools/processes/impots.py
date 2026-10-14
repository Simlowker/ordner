"""impots.preparer_declaration: tax return of one period -> applicability for the canton card, completeness (one statement
per declared institution, wrong year, duplicates with contradicting values), consolidated statement totals
(provisional/final), deadline with source and extension options, prepared document requests (email_drafts
bank_document_request) and form entry, cantonal entry guide lines from verified sources, questions for the person."""
import re

from ordner.core.schema import Fact, ToolSpec, new_id

from . import card, deadline, fmt, given, label, lang, prepare, question, result, subject_ctx, t, value

STATEMENT = "swiss_tax_statement_eCH0196"
FIELDS = {"totalTaxValue": "total_tax_value", "totalGrossRevenueA": "gross_revenue_a",
          "totalGrossRevenueB": "gross_revenue_b", "totalWithHoldingTaxClaim": "withholding_tax_claim"}
EMPLOYED = {"salaried", "apprentice"}
GUIDE_QUERY = {"fr": "état des titres relevé fiscal valeur fiscale rendements impôt anticipé",
               "de": "Wertschriftenverzeichnis Steuerauszug Steuerwert Ertrag Verrechnungssteuer",
               "it": "elenco dei titoli estratto fiscale valore fiscale reddito imposta preventiva"}
WHERE = {"total_tax_value": ("fortune : titres et avoirs (valeur fiscale au 31.12)", "Vermögen: Wertschriften und Guthaben "
                             "(Steuerwert 31.12.)", "sostanza: titoli e averi (valore fiscale al 31.12)"),
         "gross_revenue_a": ("rendements soumis à l'impôt anticipé (A)", "Erträge mit Verrechnungssteuer (A)",
                             "redditi soggetti all'imposta preventiva (A)"),
         "gross_revenue_b": ("rendements sans impôt anticipé (B)", "Erträge ohne Verrechnungssteuer (B)",
                             "redditi senza imposta preventiva (B)"),
         "withholding_tax_claim": ("impôt anticipé à récupérer", "Verrechnungssteueranspruch", "imposta preventiva da "
                                   "recuperare")}


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "_", str(s or "").casefold()).strip("_")


def _num(x):
    try:
        return float(str(x).replace("'", "").replace(" ", ""))
    except (TypeError, ValueError):
        return None


def _statement_facts(sid, docs, facts, period):
    """Proposed in-memory facts from the statements' recorded fields, for institutions without any total fact yet."""
    from ordner.rules.dossier import _measure_key
    known = {mk[1] for f in facts if (mk := _measure_key(str(f.key)))}
    out = []
    for d in docs:
        if d.kind != STATEMENT or str(d.year) != period:
            continue
        inst = _slug(d.issuer or (d.fields or {}).get("institution"))
        if any(inst.startswith(k) or k.startswith(inst) for k in known):
            continue
        for field, measure in FIELDS.items():
            v = _num((d.fields or {}).get(field))
            if v is not None:
                out.append(Fact(new_id("fact"), sid, f"tax.statement.{measure}.{inst}", v, period=period, unit="CHF",
                                source_doc=d.id, actor="connector"))
        known.add(inst)
    return out


def _guide(lg, canton, card_id):
    """Where the totals go, from verified cantonal passages only (corpus + card quotes); never an invented line number."""
    from ..knowledge import search
    try:
        hits = search({"query": GUIDE_QUERY[lg], "canton": canton, "lang": lg, "k": 8, "card_id": card_id},
                      {})[0]["passages"]
    except Exception:
        hits = []
    hits = [h for h in hits if h["jurisdiction"] == canton][:2]
    return [{"source": h["passage_id"], "title": h["title"][:90], "url": h["url"], "excerpt": h["text"][:220]}
            for h in hits]


def preparer(args, ctx):
    from ordner import rules as R
    from ordner.connectors import email_drafts

    st, subject, day = subject_ctx(args, ctx)
    sid, lg = subject.id, lang(subject)
    period = str(args.get("period") or day.year - 1)
    canton = (args.get("canton") or subject.canton or "").upper()
    c = card(f"tax.return.{canton}")
    if c is None:
        q = [] if canton else [question("subject.canton", t(lg, "Dans quel canton habitiez-vous au 31 décembre ?",
                                                             "In welchem Kanton wohnten Sie am 31. Dezember?",
                                                             "In quale cantone abitava il 31 dicembre?"))]
        return (result(t(lg, f"Pas de fiche Ordner pour la déclaration du canton {canton or '?'} : à vérifier auprès "
                             "du canton.", f"Keine Ordner-Karte für die Steuererklärung {canton or '?'}.",
                         f"Nessuna scheda Ordner per la dichiarazione del cantone {canton or '?'}."),
                       status="missing_info", missing=["subject.canton"] if not canton else [], questions=q),
                [f"tax.return.{canton} not in the catalogue"], {})
    facts, docs = st.facts(sid), st.documents(sid)
    warnings, questions, prepared, missing = [], [], [], []
    shim = [given(sid, "tax.period", period, period)]
    if value(facts, "finance.institutions") is None and (accounts := value(facts, "tax.bank_accounts")):
        shim.append(given(sid, "finance.institutions", accounts if isinstance(accounts, list) else [accounts], period))
    facts_ = facts + shim
    app = R.applicable(c, subject, facts_, on=day.isoformat(), period=period)
    if app["status"] == "not_applicable":
        return (result(t(lg, f"Déclaration {period} ({canton}) : non applicable à ce dossier.", f"Steuererklärung {period} "
                         f"({canton}): betrifft dieses Dossier nicht.", f"Dichiarazione {period} ({canton}): non "
                         "applicabile."), status="not_applicable", card_id=c.id, why=app["why"][:4]),
                warnings, {"card": c.id})
    if app["status"] == "missing_info":
        missing += app["missing"]
        questions += [question(k, t(lg, f"Pouvez-vous préciser : {label(k, 'fr')} ?", f"Bitte angeben: {label(k, 'de')}?",
                                    f"Può precisare: {label(k, 'it')}?")) for k in app["missing"]]

    # completeness: what is missing, of the wrong year, duplicated
    comp = R.completeness(c, subject, facts_, docs, period)
    roles = set(subject.roles or [])
    employed = bool(roles & EMPLOYED) or value(facts, "work.employment.employer") is not None
    by_id = {d.id: d for d in docs}
    statements, salary, other = [], [], []
    for m in comp["missing_documents"]:
        if m["kind"] == STATEMENT:
            statements.append(m["issuer"])
        elif m["kind"] == "salary_certificate":
            if employed:
                salary.append(m)
        elif m["kind"] != "tax_return_invitation":
            other.append(m["kind"])
    if any(m["kind"] == "tax_return_invitation" for m in comp["missing_documents"]):
        warnings.append(t(lg, "formulaire de déclaration (code d'accès) pas encore dans le dossier : envoyé par "
                              "l'administration fiscale", "Steuerformular (Zugangscode) noch nicht im Dossier: kommt von "
                              "der Steuerverwaltung", "modulo di dichiarazione non ancora nel dossier: inviato "
                              "dall'amministrazione fiscale"))
    for w in comp["wrong_year"]:
        d = by_id.get(w["document"])
        warnings.append(t(lg, f"{label(w['kind'], 'fr')} de {d.issuer if d else '?'} : année {w['year']} au lieu de "
                              f"{period}, ne compte pas", f"{label(w['kind'], 'de')} von {d.issuer if d else '?'}: Jahr "
                          f"{w['year']} statt {period}", f"{label(w['kind'], 'it')} di {d.issuer if d else '?'}: anno "
                          f"{w['year']} invece di {period}"))
    contradictions = []
    for dup in comp["duplicates"]:
        a, b = (by_id.get(x) for x in dup["documents"])
        if not (a and b):
            continue
        diff = {f: [(a.fields or {}).get(f), (b.fields or {}).get(f)] for f in FIELDS
                if _num((a.fields or {}).get(f)) is not None and _num((b.fields or {}).get(f)) is not None
                and _num((a.fields or {}).get(f)) != _num((b.fields or {}).get(f))}
        exact = next((x for x in (a, b) if x.read_path == "barcode" or str(x.path).lower().endswith(".pdf")), None)
        contradictions.append({"documents": dup["documents"], "issuer": a.issuer, "differs": diff,
                               "exact": exact.id if exact else None})
        if diff:
            f, (va, vb) = next(iter(diff.items()))
            questions.append(question(f"tax.statement.{FIELDS[f]}", t(
                lg, f"Les deux relevés {a.issuer} {period} donnent une valeur fiscale différente ({f}) : {va} et {vb}. "
                    "Lequel est juste ? (le PDF avec code-barres fait foi)",
                f"Die zwei Steuerauszüge {a.issuer} {period} widersprechen sich beim Steuerwert ({f}): {va} und {vb}. "
                "Welcher stimmt? (PDF mit Barcode ist massgebend)",
                f"I due estratti {a.issuer} {period} danno un valore fiscale diverso ({f}): {va} e {vb}. Quale è giusto?")))
        else:
            warnings.append(t(lg, f"doublon : {' et '.join(dup['documents'])} ({dup['reason']}), compté une fois",
                              f"Doppel: {' und '.join(dup['documents'])}, einmal gezählt",
                              f"doppione: {' e '.join(dup['documents'])}, contato una volta"))

    # questions, most blocking first: statements, salary, institutions unknown, contradictions (above), the rest
    if statements:
        questions.insert(0, question(STATEMENT, t(
            lg, f"Il manque le relevé fiscal {period} de : {', '.join(statements)}. Pouvez-vous le demander à la banque "
                "(demande préparée) ou l'ajouter ?",
            f"Es fehlt der Steuerauszug {period} von: {', '.join(statements)}. Bitte bei der Bank anfordern (Anfrage "
            "vorbereitet) oder hinzufügen.",
            f"Manca l'estratto fiscale {period} di: {', '.join(statements)}. Può richiederlo alla banca (richiesta "
            "preparata) o aggiungerlo?")))
    if salary:
        questions.insert(1 if statements else 0, question("salary_certificate", t(
            lg, f"Il manque votre certificat de salaire {period}. Pouvez-vous l'ajouter (votre employeur le fournit) ?",
            f"Ihr Lohnausweis {period} fehlt. Können Sie ihn hinzufügen (vom Arbeitgeber)?",
            f"Manca il certificato di salario {period}. Può aggiungerlo (lo fornisce il datore di lavoro)?")))
    if "finance.institutions" in comp["missing_facts"]:
        questions.append(question("finance.institutions", t(
            lg, f"Auprès de quelles banques ou plateformes aviez-vous des comptes ou des titres au 31.12.{period} ?",
            f"Bei welchen Banken hatten Sie am 31.12.{period} Konten oder Wertschriften?",
            f"Presso quali banche aveva conti o titoli al 31.12.{period}?")))
    if {"pillar3a_certificate", "pension_fund_certificate"} & set(other):
        questions.append(question("pension.pillar3a.has", t(
            lg, f"Avez-vous versé au 3e pilier A ou racheté du 2e pilier en {period} ? Si oui, il faut l'attestation.",
            f"Haben Sie {period} in die Säule 3a einbezahlt oder sich in die 2. Säule eingekauft? Dann braucht es die "
            "Bescheinigung.", f"Ha versato nel pilastro 3a o riscattato il 2° pilastro nel {period}? Serve l'attestazione.")))
    if "person.civil_status" in comp["missing_facts"]:
        questions.append(question("person.civil_status", t(lg, f"Quel était votre état civil au 31.12.{period} ?",
                                                           f"Wie war Ihr Zivilstand am 31.12.{period}?",
                                                           f"Qual era il suo stato civile al 31.12.{period}?")))
    missing += [f"{STATEMENT}:{s}" for s in statements] + [m["kind"] for m in salary] + other + [
        k for k in comp["missing_facts"] if k not in ("tax.period",)]

    # consolidated totals (statements' recorded values count as proposed inputs)
    cons = R.consolidate(facts_ + _statement_facts(sid, docs, facts, period), period)
    totals = {m: {"total": v["total"], "status": v["status"]} for m, v in cons["totals"].items() if v["total"] is not None}

    res = R.compute_deadline(c.deadline, subject, {"period": period, "canton": canton, "today": day.isoformat(),
                                                   "facts": facts_}) if c.deadline else None
    dl = deadline(c, res, t(lg, f"dépôt de la déclaration {period}", f"Einreichung Steuererklärung {period}",
                            f"invio della dichiarazione {period}"))
    if dl and dl["due"] < day.isoformat():
        open_ext = [e for e in dl.get("extensions", []) if e.get("until") and e["until"] >= day.isoformat()]
        warnings.append(t(lg, f"délai ordinaire du {fmt(dl['due'])} passé" + (
            f" : prolongation possible jusqu'au {fmt(open_ext[0]['until'])} ({open_ext[0]['how']})" if open_ext else
            " : demandez une prolongation ou déposez au plus vite"), f"ordentliche Frist {fmt(dl['due'])} vorbei",
            f"termine ordinario del {fmt(dl['due'])} scaduto"))

    applicable = app["status"] == "applicable"
    status_word = t(lg, *{"final": ("définitif", "definitiv", "definitivo"), "provisional": ("provisoire", "provisorisch",
                                                                                      "provvisorio"),
                          "incomplete": ("incomplet", "unvollständig", "incompleto")}[cons["status"]])
    guide = _guide(lg, canton, c.id)
    entry = [{"measure": m, "value": v["total"], "status": v["status"], "where": t(lg, *WHERE[m]),
              "line": None if guide else t(lg, "ligne à vérifier dans le guide cantonal", "Ziffer in der kantonalen "
                                             "Wegleitung prüfen", "rigo da verificare nelle istruzioni cantonali"),
              "sources": [g["source"] for g in guide]} for m, v in totals.items()]
    if app["status"] != "not_applicable":  # missing_info: still likely; the person validates every prepared action
        for issuer in statements:
            stmt = next((d for d in docs if d.kind == STATEMENT and d.issuer == issuer), None)
            v = {"year": period, "client_number": (stmt.fields or {}).get("client_number") if stmt else None,
                 "sender_name": subject.name, "recipient_name": issuer}
            r = email_drafts.render("bank_document_request", {k: x for k, x in v.items() if x})
            prepared.append(prepare(st, sid, c.id, period, "document_request", {
                "template": "bank_document_request", "recipient": issuer, "subject": r["subject"], "body": r["body"],
                "missing": r["missing"], "document": f"{STATEMENT}:{issuer}:{period}"}))
        for m in salary:
            employer = value(facts, "work.employment.employer") or t(lg, "votre employeur", "Ihr Arbeitgeber",
                                                                      "il datore di lavoro")
            prepared.append(prepare(st, sid, c.id, period, "document_request", {
                "recipient": employer, "document": f"salary_certificate:{period}",
                "subject": t(lg, f"Certificat de salaire {period}", f"Lohnausweis {period}", f"Certificato di salario "
                             f"{period}"),
                "body": t(lg, f"Madame, Monsieur,\n\nPourriez-vous me faire parvenir mon certificat de salaire {period} ? "
                              f"Merci d'avance.\n\n{subject.name}\n", f"Guten Tag\n\nKönnten Sie mir bitte meinen "
                          f"Lohnausweis {period} zustellen? Vielen Dank.\n\n{subject.name}\n", f"Buongiorno,\n\npotreste "
                          f"inviarmi il certificato di salario {period}? Grazie.\n\n{subject.name}\n")}))
        prepared.append(prepare(st, sid, c.id, period, "form_entry", {
            "step": "fill_in", "period": period, "canton": canton, "status": cons["status"], "entries": entry,
            "note": t(lg, "valeurs à reporter dans le logiciel cantonal ; provisoires tant que des pièces manquent ou ne "
                          "sont pas confirmées", "Werte für die kantonale Software; provisorisch solange Belege fehlen",
                      "valori da riportare nel software cantonale; provvisori finché mancano documenti")}))
    tv = totals.get("total_tax_value")
    summary = t(lg, f"Déclaration {period} ({canton}) : à rendre au plus tard le {fmt(dl and dl['due'])}"
                    + (f" (prolongation possible jusqu'au {fmt(dl['extensions'][0]['until'])})"
                       if dl and dl.get("extensions") and dl["extensions"][0].get("until") else "") + ". "
                    + (f"Il manque : {', '.join(statements + [label(m['kind'], 'fr') for m in salary])} ; demande(s) "
                       "préparée(s). " if statements or salary else "Pièces principales reçues. ")
                    + (f"Valeur fiscale des titres : CHF {tv['total']:,.2f} ({status_word})." if tv else ""),
                f"Steuererklärung {period} ({canton}): einzureichen bis {fmt(dl and dl['due'])}. "
                + (f"Es fehlt: {', '.join(statements + [label(m['kind'], 'de') for m in salary])}; Anfrage(n) vorbereitet. "
                   if statements or salary else "Hauptbelege vorhanden. ")
                + (f"Steuerwert Wertschriften: CHF {tv['total']:,.2f} ({status_word})." if tv else ""),
                f"Dichiarazione {period} ({canton}): da inviare entro il {fmt(dl and dl['due'])}. "
                + (f"Manca: {', '.join(statements + [label(m['kind'], 'it') for m in salary])}; richiesta/e preparata/e. "
                   if statements or salary else "Documenti principali ricevuti. ")
                + (f"Valore fiscale dei titoli: CHF {tv['total']:,.2f} ({status_word})." if tv else ""))
    return (result(summary, status=app["status"], card_id=c.id, applicable=[c.id] if applicable else [], deadlines=[dl],
                   missing=missing, questions=questions[:4], prepared=prepared, totals=totals,
                   consolidation=cons["status"], duplicates=contradictions, guide=guide,
                   qualification=c.qualification),
            warnings + ([f"fiche {c.id} : {c.qualification}, à vérifier"] if c.qualification != "qualified" else []),
            {"card": c.id, "source": "ordner.rules completeness/consolidate/compute_deadline"})


TOOLS = [(ToolSpec(
    "impots.preparer_declaration",
    "Tax return (déclaration d'impôt, Steuererklärung, dichiarazione) of a year: whether it applies, missing documents "
    "(one statement per bank, salary certificate), wrong-year and duplicate documents, consolidated totals, deadline "
    "with extension options; prepares the document requests and the form entry. Use for any tax return question.",
    {"type": "object", "properties": {
        "subject_id": {"type": "string"},
        "period": {"type": "string", "description": "tax year, e.g. 2025 (default: last year)"},
        "canton": {"type": "string", "description": "two-letter canton of domicile on 31.12, default the dossier's"}},
     "required": ["subject_id"]},
    {"type": "object", "description": "summary, deadlines, missing, questions, prepared_actions, totals, guide"},
), preparer)]
