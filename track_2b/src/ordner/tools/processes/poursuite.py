"""poursuite.repondre: a payment order (commandement de payer, LP) was received -> exact opposition deadline, legitimacy
checks, prepared opposition letter (total or partial). Card debt.payment_order.opposition; ordner.rules (LP holidays);
connectors.email_drafts (lp_opposition template); rules.payment_check (phishing)."""
import re

from ordner.core.schema import ToolSpec

from . import card, deadline, fmt, iso, lang, prepare, question, remember, result, sources, subject_ctx, t, value

CARD = "debt.payment_order.opposition"
OFFICE = re.compile(r"office des poursuites|office cantonal des poursuites|betreibungsamt|ufficio (d'|di )?esecuzione", re.I)
NOT_PO = {"payment_reminder", "invoice", "qr_bill_invoice", "email"}
INJECTION = re.compile(r"\b(ignor\w*|oubli\w*|vergiss\w*|dimentic\w*|disregard)\b.{0,40}\b(instruction|consigne|anweisung|"
                       r"istruzion|previous|précédent)", re.I)
NUMBER = re.compile(r"(?:poursuite|betreibung|esecuzione)\s*n[°o.]?\s*([\d][\d\s./-]{3,})", re.I)


def _doc(st, sid, ref):
    if not ref:
        return None
    try:
        d = st.get_document(ref)
    except KeyError:
        return None
    return d if d.subject_id == sid else None


def repondre(args, ctx):
    from ordner import rules as R
    from ordner.connectors import email_drafts
    from ordner.rules.phishing import _norm, _same, known

    st, subject, day = subject_ctx(args, ctx)
    sid, lg, c = subject.id, lang(subject), card(CARD)
    facts, docs = st.facts(sid), st.documents(sid)
    doc = _doc(st, sid, args.get("document_id"))
    pos = [d for d in docs if d.kind == "payment_order"]
    if doc is None and pos:
        doc = pos[-1]
    fields = dict(doc.fields or {}) if doc else {}
    text = str(fields.get("text") or "")
    warnings, questions, prepared = [], [], []

    notified, origin = iso(args.get("notified_on"), "notified_on"), "given"
    if not notified and (v := value(facts, "debt.payment_order.notified_on", confirmed_only=True)):
        notified, origin = iso(v, "notified_on"), "dossier"
    if not notified and fields.get("notified_on"):
        notified, origin = iso(fields["notified_on"], "notified_on"), "document"
        warnings.append(t(lg, "date de notification lue sur le document : à vérifier sur l'exemplaire remis",
                          "Zustelldatum vom Dokument gelesen: auf dem Exemplar prüfen",
                          "data di notifica letta sul documento: da verificare sull'esemplare ricevuto"))
    is_po = doc is not None and doc.kind == "payment_order"
    others = [d for d in docs if d.kind == "payment_reminder"]  # a reminder « avant poursuite » is not an order yet
    if not is_po and not notified and (others or (doc is not None and doc.kind in NOT_PO)):
        what = (doc or others[-1]).kind
        summary = t(lg, f"Ce document ({what}) n'est pas un commandement de payer : aucune opposition n'est possible ni "
                        "nécessaire. L'opposition se fait uniquement contre un commandement de payer de l'office des "
                        "poursuites, dans les 10 jours de sa notification.",
                    f"Dieses Dokument ({what}) ist kein Zahlungsbefehl: kein Rechtsvorschlag möglich oder nötig. "
                    "Rechtsvorschlag nur gegen einen Zahlungsbefehl des Betreibungsamts, innert 10 Tagen.",
                    f"Questo documento ({what}) non è un precetto esecutivo: nessuna opposizione possibile né necessaria. "
                    "L'opposizione si fa solo contro un precetto dell'ufficio d'esecuzione, entro 10 giorni.")
        return result(summary, status="not_applicable", card_id=CARD, sources=sources(c, [0])), warnings, {"card": CARD}
    if not (is_po or notified or args.get("creditor") or args.get("amount")):
        q = question("debt.payment_order.notified_on", t(
            lg, "Avez-vous reçu un commandement de payer de l'office des poursuites ? Si oui, à quelle date vous a-t-il "
                "été notifié (remis) ?",
            "Haben Sie einen Zahlungsbefehl des Betreibungsamts erhalten? Wenn ja, an welchem Datum wurde er zugestellt?",
            "Ha ricevuto un precetto esecutivo dall'ufficio d'esecuzione? Se sì, in che data le è stato notificato?"))
        return result(t(lg, "Aucun commandement de payer dans le dossier.", "Kein Zahlungsbefehl im Dossier.",
                        "Nessun precetto esecutivo nel dossier."), status="missing_info", card_id=CARD,
                      missing=["debt.payment_order.notified_on"], questions=[q]), warnings, {"card": CARD}

    # legitimacy: official office, known creditor, phishing signals, instructions aimed at an assistant
    creditor = args.get("creditor") or fields.get("creditor") or value(facts, "debt.payment_order.creditor")
    office = (doc.issuer if doc else None) or value(facts, "debt.payment_order.office")
    checks = {"official_office": bool(office and OFFICE.search(office)), "creditor_known": None, "phishing": False}
    if not checks["official_office"]:
        warnings.append(t(lg, f"émetteur « {office or 'inconnu'} » non reconnu comme office des poursuites : un vrai "
                              "commandement de payer vient de l'office (ou de la poste/police pour lui)",
                          f"Absender « {office or 'unbekannt'} » nicht als Betreibungsamt erkannt",
                          f"mittente « {office or 'sconosciuto'} » non riconosciuto come ufficio d'esecuzione"))
    if creditor:
        _, names = known(docs, facts, exclude_doc=doc.id if doc else None)
        checks["creditor_known"] = _same(_norm(creditor), names)
        if not checks["creditor_known"]:
            warnings.append(t(lg, f"créancier « {creditor} » inconnu du dossier : vérifiez si vous lui devez vraiment "
                                  "quelque chose avant de décider",
                              f"Gläubiger « {creditor} » im Dossier unbekannt: Forderung prüfen",
                              f"creditore « {creditor} » sconosciuto nel dossier: verifichi il credito"))
    if doc is not None:
        risk = R.payment_check({"fields": fields}, docs, facts, doc.id)
        if risk["iban"] or risk["suspicious"] and any("lien" in r for r in risk["reasons"]):
            checks["phishing"] = True
            warnings.append(t(lg, "le document demande un paiement (IBAN ou lien) : un commandement de payer ne se "
                                  "règle jamais via un lien ou un IBAN reçu par message. Ne payez rien, n'ouvrez aucun lien",
                              "das Dokument verlangt eine Zahlung (IBAN oder Link): nichts bezahlen, keinen Link öffnen",
                              "il documento chiede un pagamento (IBAN o link): non paghi nulla, non apra link"))
        if INJECTION.search(text):
            checks["phishing"] = True
            warnings.append(t(lg, "le document contient des instructions adressées à un assistant (manipulation) : elles "
                                  "sont ignorées, aucun paiement n'est préparé",
                              "das Dokument enthält Anweisungen an einen Assistenten (Manipulation): ignoriert",
                              "il documento contiene istruzioni rivolte a un assistente (manipolazione): ignorate"))

    if not notified:
        q = question("debt.payment_order.notified_on", t(
            lg, "À quelle date le commandement de payer vous a-t-il été notifié (remis en main propre ou retiré à la "
                "poste) ? La date figure sur votre exemplaire.",
            "An welchem Datum wurde Ihnen der Zahlungsbefehl zugestellt? Das Datum steht auf Ihrem Exemplar.",
            "In che data le è stato notificato il precetto esecutivo? La data figura sul suo esemplare."))
        summary = t(lg, "Opposition possible dans les 10 jours dès la notification (LP art. 74), sans motivation. Il me "
                        "faut la date de notification pour calculer le dernier jour.",
                    "Rechtsvorschlag innert 10 Tagen ab Zustellung (SchKG Art. 74), ohne Begründung. Ich brauche das "
                    "Zustelldatum für die Frist.",
                    "Opposizione entro 10 giorni dalla notifica (LEF art. 74), senza motivazione. Mi serve la data di "
                    "notifica per calcolare il termine.")
        return (result(summary, status="applicable", card_id=CARD, applicable=[CARD],
                       missing=["debt.payment_order.notified_on"], questions=[q], checks=checks),
                warnings, {"card": CARD})

    res = R.compute_deadline(c.deadline, subject, {"notified_on": notified, "canton": subject.canton,
                                                   "today": day.isoformat()})
    dl = deadline(c, res, t(lg, "opposition (dernier jour)", "Rechtsvorschlag (letzter Tag)", "opposizione (ultimo giorno)"),
                  notified_on=notified, notified_from=origin)
    if origin == "given":
        remember(st, sid, "debt.payment_order.notified_on", notified)
    for key, v in (("debt.payment_order.creditor", args.get("creditor")), ("debt.payment_order.amount", args.get("amount"))):
        if v not in (None, ""):
            remember(st, sid, key, v)
    overdue = dl and dl["due"] < day.isoformat()
    if overdue:
        warnings.append(t(lg, "le délai d'opposition est dépassé : seule une restitution de délai pour empêchement non "
                              "fautif reste envisageable (à vérifier avec l'office)",
                          "die Frist ist abgelaufen: nur Wiederherstellung bei unverschuldetem Hindernis (beim Amt prüfen)",
                          "il termine è scaduto: solo restituzione per impedimento non colposo (da verificare con l'ufficio)"))
    partial = args.get("contested_amount")
    number = fields.get("number") or value(facts, "debt.payment_order.number") or (
        m.group(1).strip() if (m := NUMBER.search(text)) else None)
    vars_ = {k: v for k, v in {"number": number, "notified_on": fmt(notified), "creditor": creditor,
                               "contested_amount": f"{partial:.2f}" if isinstance(partial, (int, float)) else None,
                               "sender_name": subject.name, "recipient_name": office or "Office des poursuites",
                               "place": subject.commune}.items() if v not in (None, "")}
    if not overdue:
        r = email_drafts.render("lp_opposition", vars_)
        prepared.append(prepare(st, sid, CARD, str(day.year), "letter", {
            "template": "lp_opposition", "vars": vars_, "recipient": vars_["recipient_name"], "subject": r["subject"],
            "body": r["body"], "missing": r["missing"], "due": dl and dl["due"],
            "how": t(lg, "lettre signée en recommandé, ou déclaration au guichet de l'office (demander une attestation)",
                     "unterschriebener Brief (eingeschrieben) oder Erklärung am Schalter (Bestätigung verlangen)",
                     "lettera firmata raccomandata o dichiarazione allo sportello (chiedere attestazione)")}))
    kind = (t(lg, f"partielle (CHF {partial:.2f} contestés)", f"teilweise (CHF {partial:.2f} bestritten)",
              f"parziale (CHF {partial:.2f} contestati)") if partial else t(lg, "totale", "vollständig", "totale"))
    summary = t(lg, f"Commandement de payer notifié le {fmt(notified)} : opposition jusqu'au {fmt(dl and dl['due'])} "
                    f"inclus (10 jours, LP art. 74), sans motivation. Lettre d'opposition {kind} préparée : à signer et "
                    "envoyer vous-même." if not overdue else
                    f"Commandement de payer notifié le {fmt(notified)} : le délai d'opposition a expiré le "
                    f"{fmt(dl and dl['due'])}.",
                f"Zahlungsbefehl zugestellt am {fmt(notified)}: Rechtsvorschlag bis {fmt(dl and dl['due'])} (10 Tage, "
                f"SchKG Art. 74), ohne Begründung. Rechtsvorschlag ({kind}) vorbereitet: selbst unterschreiben und senden."
                if not overdue else f"Zahlungsbefehl vom {fmt(notified)}: Frist am {fmt(dl and dl['due'])} abgelaufen.",
                f"Precetto notificato il {fmt(notified)}: opposizione entro il {fmt(dl and dl['due'])} (10 giorni, "
                f"LEF art. 74), senza motivazione. Opposizione {kind} preparata: da firmare e inviare lei stesso."
                if not overdue else f"Precetto del {fmt(notified)}: termine scaduto il {fmt(dl and dl['due'])}.")
    explain = [{"text": t(lg, "L'opposition n'a pas besoin d'être motivée.", "Der Rechtsvorschlag muss nicht begründet "
                          "werden.", "L'opposizione non deve essere motivata."), "sources": sources(c, [6])},
               {"text": t(lg, "Opposition partielle : indiquer exactement le montant contesté, sinon toute la dette est "
                              "réputée reconnue.", "Teilweiser Rechtsvorschlag: bestrittenen Betrag genau angeben.",
                          "Opposizione parziale: indicare esattamente l'importo contestato."), "sources": sources(c, [7])},
               {"text": t(lg, "L'office donne acte gratuitement de l'opposition sur demande.", "Das Amt bestätigt den "
                              "Rechtsvorschlag auf Verlangen kostenlos.", "L'ufficio attesta gratuitamente l'opposizione "
                              "su richiesta."), "sources": sources(c, [8])}]
    return (result(summary, status="applicable", card_id=CARD, applicable=[CARD], deadlines=[dl], questions=questions,
                   prepared=prepared, checks=checks, explain=explain), warnings, {"card": CARD, "source": "ordner.rules"})


TOOLS = [(ToolSpec(
    "poursuite.repondre",
    "Payment order received (commandement de payer, Zahlungsbefehl, precetto esecutivo): exact 10-day opposition "
    "deadline with LP holidays, legitimacy and phishing checks, prepared opposition letter (total or partial). "
    "Use for any debt-collection question; it also says when a mere reminder is not a payment order.",
    {"type": "object", "properties": {
        "subject_id": {"type": "string"},
        "notified_on": {"type": "string", "description": "YYYY-MM-DD the order was handed over, if the person said it"},
        "creditor": {"type": "string"},
        "amount": {"type": "number", "description": "CHF claimed"},
        "contested_amount": {"type": "number", "description": "only for a partial opposition: CHF contested"},
        "document_id": {"type": "string", "description": "dossier document of the payment order"}},
     "required": ["subject_id"]},
    {"type": "object", "description": "summary, status, deadlines, questions, prepared_actions, checks, explain"},
), repondre)]
