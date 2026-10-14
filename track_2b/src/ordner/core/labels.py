"""Human labels (fr, de, it) for the keys the person sees: fact keys, document kinds and subject attributes used by the
procedure cards (required facts and documents, applicability), the demo seed and the connectors. Shared by the cockpit
and the coordinator. A `*` segment matches one institution/reference segment (tax.securities.<bank>.total_tax_value).

    PYTHONPATH=src python -m ordner.core.labels     # self-check: every key of the catalogue has a label
"""
LABELS = {
    # --- fact keys (procedure cards) ---
    "business.has_employees": ("emploie du personnel (oui ou non)", "beschäftigt Personal (ja oder nein)", "impiega personale (sì o no)"),
    "business.start_date": ("date de début de l'activité indépendante", "Beginn der selbständigen Tätigkeit", "data d'inizio dell'attività indipendente"),
    "business.trade_name": ("raison de commerce", "Firmenname", "ragione commerciale"),
    "business.turnover.expected_annual": ("chiffre d'affaires annuel prévu", "erwarteter Jahresumsatz", "cifra d'affari annua prevista"),
    "business.turnover.previous_year": ("chiffre d'affaires de l'année précédente", "Umsatz des Vorjahres", "cifra d'affari dell'anno precedente"),
    "debt.claim.contested_amount": ("montant contesté", "bestrittener Betrag", "importo contestato"),
    "debt.payment_order.amount": ("montant du commandement de payer", "Betrag des Zahlungsbefehls", "importo del precetto esecutivo"),
    "debt.payment_order.creditor": ("créancier (commandement de payer)", "Gläubiger (Zahlungsbefehl)", "creditore (precetto esecutivo)"),
    "debt.payment_order.notified_on": ("date de notification du commandement de payer", "Zustellungsdatum des Zahlungsbefehls", "data di notifica del precetto esecutivo"),
    "debt.payment_order.number": ("numéro de la poursuite", "Betreibungsnummer", "numero dell'esecuzione"),
    "debt.payment_order.office": ("office des poursuites", "Betreibungsamt", "ufficio d'esecuzione"),
    "health_insurance.arrears.outstanding": ("arriérés de primes LAMal (oui ou non)", "ausstehende KVG-Prämien (ja oder nein)", "premi LAMal arretrati (sì o no)"),
    "health_insurance.basic.deductible": ("franchise LAMal", "Franchise der Grundversicherung", "franchigia LAMal"),
    "health_insurance.basic.insurer": ("caisse maladie (assurance de base)", "Krankenkasse (Grundversicherung)", "cassa malati (assicurazione di base)"),
    "health_insurance.basic.model": ("modèle d'assurance (standard, médecin de famille…)", "Versicherungsmodell (Standard, Hausarzt …)", "modello assicurativo (standard, medico di famiglia…)"),
    "health_insurance.basic.premium": ("prime LAMal mensuelle", "monatliche KVG-Prämie", "premio LAMal mensile"),
    "health_insurance.premium.next_year": ("prime LAMal de l'an prochain", "KVG-Prämie des nächsten Jahres", "premio LAMal dell'anno prossimo"),
    "household.members": ("personnes du ménage", "Personen im Haushalt", "persone dell'economia domestica"),
    "household.serafe.invoice_amount": ("montant de la facture Serafe", "Betrag der Serafe-Rechnung", "importo della fattura Serafe"),
    "household.serafe.invoice_due_date": ("échéance de la facture Serafe", "Fälligkeit der Serafe-Rechnung", "scadenza della fattura Serafe"),
    "housing.address.new": ("nouvelle adresse", "neue Adresse", "nuovo indirizzo"),
    "housing.address.previous": ("ancienne adresse", "bisherige Adresse", "indirizzo precedente"),
    "housing.commune.new": ("nouvelle commune", "neue Gemeinde", "nuovo comune"),
    "housing.moving.date": ("date du déménagement", "Umzugsdatum", "data del trasloco"),
    "income.avs_subject": ("revenu soumis à l'AVS (oui ou non)", "AHV-pflichtiges Einkommen (ja oder nein)", "reddito soggetto all'AVS (sì o no)"),
    "move.planned.canton_to": ("canton de destination du déménagement", "Zielkanton des Umzugs", "cantone di destinazione del trasloco"),
    "pension.annual_income": ("revenu annuel (prévoyance)", "Jahreseinkommen (Vorsorge)", "reddito annuo (previdenza)"),
    "pension.has_pension_fund": ("affilié·e à une caisse de pension, 2e pilier (oui ou non)", "einer Pensionskasse angeschlossen, 2. Säule (ja oder nein)", "affiliato/a a una cassa pensioni, 2° pilastro (sì o no)"),
    "pension.pillar3a.paid_in_period": ("montant versé au 3e pilier A dans l'année", "im Jahr in die Säule 3a einbezahlter Betrag", "importo versato nel pilastro 3a nell'anno"),
    "person.ahv_number": ("numéro AVS", "AHV-Nummer", "numero AVS"),
    "person.birth_date": ("date de naissance", "Geburtsdatum", "data di nascita"),
    "person.civil_status": ("état civil", "Zivilstand", "stato civile"),
    "person.in_education": ("en formation (oui ou non)", "in Ausbildung (ja oder nein)", "in formazione (sì o no)"),
    "person.marital_status": ("état civil", "Zivilstand", "stato civile"),
    "person.nationality": ("nationalité", "Staatsangehörigkeit", "nazionalità"),
    "social.ahv.contributions_from_employment": ("cotisations AVS versées sur un salaire", "AHV-Beiträge aus Erwerbstätigkeit", "contributi AVS da attività lucrativa"),
    "social.ahv.spouse_contributions": ("cotisations AVS du conjoint", "AHV-Beiträge des Ehegatten", "contributi AVS del coniuge"),
    "social.supplementary_benefits.receives": ("reçoit des prestations complémentaires (oui ou non)", "bezieht Ergänzungsleistungen (ja oder nein)", "riceve prestazioni complementari (sì o no)"),
    "tax.assessment.net_income": ("revenu net imposable (décision de taxation)", "steuerbares Nettoeinkommen (Veranlagungsverfügung)", "reddito netto imponibile (decisione di tassazione)"),
    "tax.assessment.net_wealth": ("fortune nette imposable (décision de taxation)", "steuerbares Nettovermögen (Veranlagungsverfügung)", "sostanza netta imponibile (decisione di tassazione)"),
    "tax.assessment.notified_on": ("date de notification de la décision de taxation", "Zustellungsdatum der Veranlagungsverfügung", "data di notifica della decisione di tassazione"),
    "tax.instalments.amount": ("montant des acomptes d'impôt", "Betrag der Steuerraten", "importo degli acconti d'imposta"),
    "tax.period": ("période fiscale", "Steuerperiode", "periodo fiscale"),
    "tax.securities.total_tax_value": ("valeur fiscale totale des titres", "Gesamtsteuerwert der Wertschriften", "valore fiscale totale dei titoli"),
    "tax.securities.withholding_tax_total": ("total de l'impôt anticipé", "Total der Verrechnungssteuer", "totale dell'imposta preventiva"),
    "wealth.total": ("fortune totale", "Gesamtvermögen", "sostanza totale"),
    "work.employment.end_date": ("date de fin du contrat de travail", "Ende des Arbeitsverhältnisses", "data di fine del rapporto di lavoro"),
    "work.unemployment.first_claimed_day": ("premier jour de chômage demandé", "erster beantragter Arbeitslosentag", "primo giorno di disoccupazione richiesto"),
    "work.unemployment.fund": ("caisse de chômage choisie", "gewählte Arbeitslosenkasse", "cassa disoccupazione scelta"),
    # --- subject attributes (missing keys of rules.applicable) ---
    "subject.tax_at_source": ("imposé·e à la source (oui ou non)", "quellenbesteuert (ja oder nein)", "imposto/a alla fonte (sì o no)"),
    "subject.household": ("type de ménage (privé ou collectif, p. ex. foyer)", "Haushaltsart (privat oder kollektiv, z. B. Heim)", "tipo di economia domestica (privata o collettiva, p. es. istituto)"),
    "subject.roles": ("situation professionnelle (salarié·e, apprenti·e, indépendant·e…)", "berufliche Situation (angestellt, in Lehre, selbständig …)", "situazione professionale (dipendente, apprendista, indipendente…)"),
    "subject.birth_year": ("année de naissance", "Geburtsjahr", "anno di nascita"),
    "subject.birth_date": ("date de naissance", "Geburtsdatum", "data di nascita"),
    "subject.canton": ("canton de domicile", "Wohnkanton", "cantone di domicilio"),
    "subject.kind": ("type de dossier (personne, ménage, entreprise)", "Art des Dossiers (Person, Haushalt, Unternehmen)", "tipo di dossier (persona, economia domestica, impresa)"),
    "card.validity": ("validité de la fiche à revérifier", "Gültigkeit der Verfahrenskarte zu prüfen", "validità della scheda da verificare"),
    # --- document kinds ---
    "ahv_contribution_decision": ("décision de cotisations AVS", "AHV-Beitragsverfügung", "decisione dei contributi AVS"),
    "ahv_self_employed_status_decision": ("décision de statut d'indépendant (AVS)", "Statusverfügung Selbständigerwerbende (AHV)", "decisione sullo statuto di indipendente (AVS)"),
    "employer_certificate_unemployment": ("attestation de l'employeur (chômage)", "Arbeitgeberbescheinigung (ALV)", "attestato del datore di lavoro (disoccupazione)"),
    "health_insurance_certificate": ("certificat d'assurance maladie", "Versicherungsausweis Krankenkasse", "certificato d'assicurazione malattia"),
    "health_insurance_policy": ("police d'assurance maladie", "Versicherungspolice Krankenkasse", "polizza cassa malati"),
    "health_insurance_premium_letter": ("avis de prime LAMal", "Prämienmitteilung KVG", "comunicazione del premio LAMal"),
    "health_insurance_tax_certificate": ("attestation fiscale d'assurance maladie", "Steuerbescheinigung Krankenkasse", "attestazione fiscale cassa malati"),
    "identity_document": ("pièce d'identité", "Ausweis", "documento d'identità"),
    "job_search_proofs": ("preuves de recherches d'emploi", "Nachweis der Arbeitsbemühungen", "prove della ricerca d'impiego"),
    "lease_contract": ("contrat de bail", "Mietvertrag", "contratto di locazione"),
    "payment_order": ("commandement de payer", "Zahlungsbefehl", "precetto esecutivo"),
    "pension_fund_certificate": ("attestation de rachat 2e pilier", "Bescheinigung Einkauf 2. Säule", "attestazione di riscatto 2° pilastro"),
    "pillar3a_certificate": ("attestation 3e pilier A", "Bescheinigung Säule 3a", "attestazione pilastro 3a"),
    "salary_certificate": ("certificat de salaire", "Lohnausweis", "certificato di salario"),
    "securities_list": ("état des titres", "Wertschriftenverzeichnis", "elenco dei titoli"),
    "serafe_invoice": ("facture Serafe (redevance radio-TV)", "Serafe-Rechnung (Radio- und Fernsehabgabe)", "fattura Serafe (canone radio-TV)"),
    "study_certificate": ("attestation d'études", "Studienbescheinigung", "attestato di studio"),
    "sva_ipv_application_form": ("formulaire de demande de réduction de primes (SVA Zurich)", "Antragsformular Prämienverbilligung (SVA Zürich)", "modulo di domanda di riduzione dei premi (SVA Zurigo)"),
    "swiss_tax_statement_eCH0196": ("relevé fiscal bancaire (eCH-0196)", "Steuerausweis der Bank (eCH-0196)", "estratto fiscale bancario (eCH-0196)"),
    "tax_assessment_decision": ("décision de taxation", "Veranlagungsverfügung", "decisione di tassazione"),
    "tax_instalment_bill": ("bordereau d'acomptes", "Ratenrechnung", "fattura degli acconti"),
    "tax_return_invitation": ("formulaire de déclaration (code de contrôle)", "Steuerformular (Kontrollcode)", "modulo di dichiarazione (codice di controllo)"),
    "qr_bill_invoice": ("facture QR", "QR-Rechnung", "fattura QR"),
    "email": ("e-mail", "E-Mail", "e-mail"),
    # --- demo seed and connectors ---
    "person.birth_year": ("année de naissance", "Geburtsjahr", "anno di nascita"),
    "residence.canton": ("canton de domicile", "Wohnkanton", "cantone di domicilio"),
    "residence.commune": ("commune de domicile", "Wohngemeinde", "comune di domicilio"),
    "household.children": ("nombre d'enfants", "Anzahl Kinder", "numero di figli"),
    "work.apprenticeship.end_date": ("fin de l'apprentissage", "Ende der Lehre", "fine dell'apprendistato"),
    "work.employment.start_date": ("début de l'emploi", "Stellenantritt", "inizio dell'impiego"),
    "work.employment.employer": ("employeur", "Arbeitgeber", "datore di lavoro"),
    "work.employment.rate": ("taux d'activité", "Beschäftigungsgrad", "grado d'occupazione"),
    "finance.institutions": ("établissements financiers déclarés", "angegebene Finanzinstitute", "istituti finanziari dichiarati"),
    "pension.pillar3a.has": ("a un 3e pilier A (oui ou non)", "hat eine Säule 3a (ja oder nein)", "ha un pilastro 3a (sì o no)"),
    "pension.lpp.affiliated": ("affilié·e à la LPP (oui ou non)", "BVG-versichert (ja oder nein)", "affiliato/a alla LPP (sì o no)"),
    "pension.lpp.employee_contributions": ("cotisations LPP de l'employé·e", "BVG-Arbeitnehmerbeiträge", "contributi LPP del lavoratore"),
    "move.planned.date": ("date du déménagement prévu", "geplantes Umzugsdatum", "data del trasloco previsto"),
    "move.planned.commune": ("commune de destination", "Zielgemeinde", "comune di destinazione"),
    "health.lamal.insurer": ("caisse maladie (LAMal)", "Krankenkasse (KVG)", "cassa malati (LAMal)"),
    "health.lamal.deductible": ("franchise LAMal", "Franchise KVG", "franchigia LAMal"),
    "health.lamal.monthly_premium": ("prime LAMal mensuelle", "monatliche KVG-Prämie", "premio LAMal mensile"),
    "health.lamal.accident_cover": ("couverture accident (oui ou non)", "Unfalldeckung (ja oder nein)", "copertura infortuni (sì o no)"),
    "income.employment.*.gross": ("salaire brut — {}", "Bruttolohn — {}", "salario lordo — {}"),
    "tax.securities.*.total_tax_value": ("valeur fiscale des titres — {}", "Steuerwert der Wertschriften — {}", "valore fiscale dei titoli — {}"),
    "tax.securities.*.gross_revenue_a": ("rendement brut A (soumis à l'impôt anticipé) — {}", "Bruttoertrag A (mit Verrechnungssteuer) — {}", "reddito lordo A (soggetto all'imposta preventiva) — {}"),
    "tax.securities.*.gross_revenue_b": ("rendement brut B (sans impôt anticipé) — {}", "Bruttoertrag B (ohne Verrechnungssteuer) — {}", "reddito lordo B (non soggetto all'imposta preventiva) — {}"),
    "tax.securities.*.withholding_tax_claim": ("impôt anticipé à récupérer — {}", "rückforderbare Verrechnungssteuer — {}", "imposta preventiva da recuperare — {}"),
    "bill.*.creditor": ("bénéficiaire de la facture {}", "Zahlungsempfänger der Rechnung {}", "beneficiario della fattura {}"),
    "bill.*.iban": ("IBAN de la facture {}", "IBAN der Rechnung {}", "IBAN della fattura {}"),
    "bill.*.amount": ("montant de la facture {}", "Betrag der Rechnung {}", "importo della fattura {}"),
    "bill.*.reference": ("référence de la facture {}", "Referenz der Rechnung {}", "riferimento della fattura {}"),
    "bill.*.message": ("communication de la facture {}", "Mitteilung der Rechnung {}", "comunicazione della fattura {}"),
}
LANGS = ("fr", "de", "it")


def _lookup(key):
    if key in LABELS:
        return LABELS[key], None
    parts = key.split(".")
    for i in range(1, len(parts)):
        pattern = ".".join(parts[:i] + ["*"] + parts[i + 1:])
        if pattern in LABELS:
            return LABELS[pattern], parts[i].replace("_", " ").title()
    return None, None


def label(key: str, lang: str = "fr") -> str:
    """Human label of a fact key, document kind or "kind:issuer" item; the key itself when unknown."""
    key = str(key)
    kind, _, issuer = key.partition(":")
    names, segment = _lookup(kind)
    if names is None:
        return key
    text = names[LANGS.index(lang) if lang in LANGS else 0].format(segment)
    return f"{text} — {issuer}" if issuer else text


def labels(keys) -> dict:
    """{key: {"fr", "de", "it"}} for the keys that have a label (the UI shows unknown keys raw)."""
    return {k: {lg: label(k, lg) for lg in LANGS} for k in dict.fromkeys(map(str, keys)) if _lookup(k.partition(":")[0])[0]}


def catalogue_keys(cards) -> set:
    """Every key a card can put in front of the person: required facts and documents, applicability facts/attrs."""
    keys = set()

    def walk(c):
        if isinstance(c, dict):
            if "fact" in c:
                keys.add(c["fact"])
            if "attr" in c and c["attr"] not in ("age", "age_at_year_end"):  # ages surface as subject.birth_*
                keys.add(f"subject.{c['attr']}")
            if "role" in c:
                keys.add("subject.roles")
            for v in c.values():
                walk(v)
        elif isinstance(c, list):
            for v in c:
                walk(v)
    for card in cards:
        walk(card.applicability)
        keys.update(card.required_facts, card.required_documents)
    return keys


if __name__ == "__main__":
    from ordner.procedures.catalog import load_cards

    assert label("tax.assessment.net_income") == "revenu net imposable (décision de taxation)"
    assert label("tax.securities.morvessa.total_tax_value", "de") == "Steuerwert der Wertschriften — Morvessa"
    assert label("swiss_tax_statement_eCH0196:Talbruck SA") == "relevé fiscal bancaire (eCH-0196) — Talbruck SA"
    assert label("unknown.key") == "unknown.key" and labels(["unknown.key", "tax.period"]) == {
        "tax.period": {"fr": "période fiscale", "de": "Steuerperiode", "it": "periodo fiscale"}}
    missing = sorted(k for k in catalogue_keys(load_cards()) if _lookup(k)[0] is None)
    assert not missing, f"keys without a label (add them to LABELS): {missing}"
    print(f"labels ok: {len(LABELS)} labels, every catalogue key covered")
