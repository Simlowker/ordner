"""piece.recevoir: document intake. Route (d1-3B in live, barcode/route cache/heuristic in replay) -> barcode fast path
(eCH-0196, QR-bill, camt via connectors.inbox) or AI read (OCR + Apertus extraction via expert.run; replay caches, else
the fields recorded at import) -> doubt -> proposed facts -> the procedure/case it belongs to; duplicates and wrong year."""
import re
from pathlib import Path

from ordner.core.schema import ToolSpec

from ..base import ROOT, ToolError, mode
from . import card, label, lang, question, remember, result, subject_ctx, t

STATEMENT = "swiss_tax_statement_eCH0196"
FIELDS = {"totalTaxValue": "total_tax_value", "totalGrossRevenueA": "gross_revenue_a",
          "totalGrossRevenueB": "gross_revenue_b", "totalWithHoldingTaxClaim": "withholding_tax_claim"}
DOUBT = 0.1  # P(wrong) above which a value is shown as doubtful
# ponytail: keyword router for replay mode when no barcode and no d1 cache; d1-3B (decision.score) does it in live mode
KEYWORDS = [(STATEMENT, r"relev[ée] fiscal|steuerauszug|steuerausweis|estratto fiscale|eCH-0196|valeur fiscale"),
            ("payment_order", r"commandement de payer|zahlungsbefehl|precetto esecutivo"),
            ("health_insurance_premium_letter", r"prime|franchise|prämie|premio|franchigia|LAMal|KVG"),
            ("salary_certificate", r"certificat de salaire|lohnausweis|certificato di salario"),
            ("tax_assessment_decision", r"décision de taxation|veranlagungsverfügung|decisione di tassazione"),
            ("payment_reminder", r"rappel|mahnung|sollecito|richiamo")]
YEAR_KINDS = {STATEMENT, "salary_certificate", "pillar3a_certificate", "pension_fund_certificate"}


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "_", str(s or "").casefold()).strip("_")


def _import(ref, sid, st):
    """A file path inside track_2b -> stored Document via connectors.inbox (barcode fast path); (doc, status, message)."""
    path = next((p for p in (Path(ref).expanduser(), ROOT / ref) if p.is_file()), None)
    if path is None:
        raise ToolError(f"unknown document '{ref}': give a dossier document id or a file path inside track_2b")
    if not path.resolve().is_relative_to(ROOT):
        raise ToolError("only files inside the project (or dossier documents) are read")
    from ordner.connectors import inbox
    parsed = inbox.import_file(path, sid, "share", st)[0]
    if parsed.status == "duplicate":
        same = next((d for d in st.documents(sid) if d.sha256 == parsed.document.sha256), None)
        return same, "duplicate", "même fichier déjà au dossier"
    return st.get_document(parsed.document.id) if parsed.status != "unsupported" else parsed.document, parsed.status, \
        parsed.message


def _ref(doc):
    """What document.resolve understands: a doc_ id (through the store), else the stored file path."""
    return doc.id if doc.id.startswith("doc_") or str(doc.path).startswith("placeholder:") else str(doc.path)


def _route(doc, text, ctx):
    if doc.kind:
        return doc.kind, "dossier"
    if mode(ctx) == "live" and text:
        from ..decision import score
        a = score({"text": text, "questions": [{"id": "k", "type": "doc_type"}]}, ctx)[0]["answers"]["k"]
        if a["answer"] != "unknown":
            return a["answer"], "d1-3B"
    for kind, pat in KEYWORDS:
        if text and re.search(pat, text, re.I):
            return kind, "heuristic: keywords"
    return None, "unknown"


def _ai_read(doc, ctx, warnings):
    """(fields, doubt per field, path) for a statement without barcode: expert.run (replay cache / live Apertus), else
    the values recorded at import."""
    from ..expert import run
    try:
        data, w, prov = run({"process": "tax_statement_extraction", "doc": _ref(doc)}, ctx)
        warnings += w
        doubt = {f: 0.5 for f in data.get("to_verify", [])}
        return data["fields"], doubt, f"ai ({prov.get('source')}: {prov.get('model', '')})".strip()
    except ToolError as e:
        warnings.append(f"lecture IA indisponible ({e}) : valeurs enregistrées à l'import")
        return dict(doc.fields or {}), dict(doc.doubt or {}), "recorded at import"


def recevoir(args, ctx):
    st, subject, day = subject_ctx(args, ctx)
    sid, lg, ref = subject.id, lang(subject), args["doc"]
    warnings, questions, facts_added = [], [], []
    try:
        doc = st.get_document(ref)
        if doc.subject_id != sid:
            raise ToolError(f"document {ref} belongs to another dossier")
        status, message = "in_dossier", ""
    except KeyError:
        doc, status, message = _import(ref, sid, st)
    if doc is None:
        raise ToolError(message or "document could not be imported")
    fields, doubt = dict(doc.fields or {}), dict(doc.doubt or {})
    text = str(fields.get("text") or "")
    if doc.kind is None and not text:  # unknown kind: route on the page text (text layer or replay OCR)
        from ..document import state_text
        try:
            text = state_text({"doc": _ref(doc)}, {**ctx, "subject_id": sid})[0]
        except ToolError:
            text = ""
    kind, routed_by = _route(doc, text, ctx)
    read_path = doc.read_path or ("barcode" if status == "ok" and doc.kind else "recorded at import" if fields else None)
    if kind == STATEMENT and read_path != "barcode":
        if str(doc.path).lower().endswith(".pdf") and not str(doc.path).startswith("placeholder:"):
            from ..document import decode
            try:
                ech = decode({"doc": _ref(doc)}, {**ctx, "subject_id": sid})[0]["ech0196"]
            except ToolError:
                ech = None
            if ech:
                fields.update(ech["fields"])
                doubt, read_path = {}, "barcode"
        if read_path != "barcode":
            ai, doubt, read_path = _ai_read(doc, {**ctx, "subject_id": sid}, warnings)
            fields.update({k: v for k, v in ai.items() if v not in (None, "")})
    doubtful = sorted(f for f, p in doubt.items() if (p or 0) > DOUBT)
    year = doc.year or (int(fields["taxPeriod"]) if str(fields.get("taxPeriod", "")).isdigit() else None)
    issuer = doc.issuer or fields.get("institution") or fields.get("insurer") or fields.get("employer")

    # proposed facts (status ok = the connector just proposed the exact barcode facts; a duplicate adds nothing)
    if kind == STATEMENT and status not in ("ok", "duplicate") and issuer:
        for field, measure in FIELDS.items():
            v = fields.get(field)
            try:
                v = float(str(v).replace("'", ""))
            except (TypeError, ValueError):
                continue
            facts_added.append(remember(st, sid, f"tax.statement.{measure}.{_slug(issuer)}", v,
                                        str(year) if year else None, doc.id,
                                        doubt.get(field, 0.0 if read_path == "barcode" else None)))
    # duplicates and wrong year
    others = [d for d in st.documents(sid) if d.id != doc.id]
    dups = [d.id for d in others if d.sha256 == doc.sha256 or (kind and d.kind == kind and d.year == year
                                                                and _slug(d.issuer) == _slug(issuer))]
    expected = int(args["period"]) if str(args.get("period", "")).isdigit() else day.year - 1
    wrong_year = kind in YEAR_KINDS and year is not None and year != expected
    if status == "duplicate":
        dups = [doc.id] + dups
    if dups:
        warnings.append(t(lg, f"doublon probable de {', '.join(dups) or 'un document du dossier'} : comptez-le une seule "
                              "fois", f"wahrscheinlich doppelt ({', '.join(dups)}): nur einmal zählen",
                          f"probabile doppione ({', '.join(dups)}): contarlo una sola volta"))
    if wrong_year:
        warnings.append(t(lg, f"document de {year}, attendu {expected} : il ne compte pas pour la déclaration {expected}",
                          f"Dokument von {year}, erwartet {expected}", f"documento del {year}, atteso {expected}"))
    if doubtful:
        questions.append(question(f"{kind or 'document'}.{doubtful[0]}", t(
            lg, f"Pouvez-vous vérifier sur l'original : {', '.join(f'{f} = {fields.get(f)}' for f in doubtful)} ?",
            f"Bitte am Original prüfen: {', '.join(f'{f} = {fields.get(f)}' for f in doubtful)}",
            f"Può verificare sull'originale: {', '.join(f'{f} = {fields.get(f)}' for f in doubtful)}?")))
    from ordner.rules import payment_check
    risk = payment_check({"fields": fields}, others, st.facts(sid), doc.id)
    if risk["suspicious"]:
        warnings.append(f"{risk['warning'][lg if lg in risk['warning'] else 'fr']} : {'; '.join(risk['reasons'])}")

    # where it belongs: the open case whose card needs this kind, else the applicable card to open
    from ordner.procedures.catalog import load_cards
    cards = sorted((c for c in load_cards(subject.canton) if kind and kind in c.required_documents),
                   key=lambda c: (c.nature != "obligation", c.jurisdiction == "CH"))  # cantonal obligation first
    cases = [x for x in st.cases(sid) if x.state != "closed" and x.card_id in {c.id for c in cards}]
    case = next((x for x in cases if x.period in (str(year), None)), cases[0] if cases else None)
    belongs = {"case_id": case.id if case else None, "card_id": case.card_id if case else (cards[0].id if cards else None)}
    understood = {"kind": kind, "kind_label": label(kind, lg) if kind else None, "routed_by": routed_by, "issuer": issuer,
                  "year": year, "read_path": read_path,
                  "values": {k: v for k, v in fields.items() if k not in ("text", "accounts", "securities", "liabilities")
                             and not isinstance(v, (dict, list))}}
    summary = t(lg, f"{understood['kind_label'] or 'Document non reconnu'}{f' de {issuer}' if issuer else ''}"
                    f"{f' ({year})' if year else ''}, lu par {read_path or 'aucune voie'}"
                    + (f" ; valeurs douteuses : {', '.join(doubtful)}" if doubtful else "")
                    + (f" ; rattaché à {belongs['card_id']}" if belongs["card_id"] else "") + ".",
                f"{understood['kind_label'] or 'Unbekanntes Dokument'}{f' von {issuer}' if issuer else ''}"
                f"{f' ({year})' if year else ''}, gelesen via {read_path or '-'}"
                + (f"; unsicher: {', '.join(doubtful)}" if doubtful else "")
                + (f"; gehört zu {belongs['card_id']}" if belongs["card_id"] else "") + ".",
                f"{understood['kind_label'] or 'Documento non riconosciuto'}{f' di {issuer}' if issuer else ''}"
                f"{f' ({year})' if year else ''}, letto via {read_path or '-'}"
                + (f"; valori dubbi: {', '.join(doubtful)}" if doubtful else "")
                + (f"; collegato a {belongs['card_id']}" if belongs["card_id"] else "") + ".")
    c = card(belongs["card_id"]) if belongs["card_id"] else None
    return (result(summary, status=status if status in ("duplicate", "needs_ai_read") else "read", card_id=belongs["card_id"],
                   questions=questions, document_id=doc.id, understood=understood, doubtful=doubtful,
                   duplicates=dups, wrong_year=wrong_year, facts_proposed=[f for f in facts_added if f],
                   belongs_to=belongs, qualification=c.qualification if c else None),
            warnings, {"source": "connectors.inbox / document.decode / expert.run", "routed_by": routed_by})


TOOLS = [(ToolSpec(
    "piece.recevoir",
    "Take in a document (new file or dossier document: tax statement, bill, letter, scan, photo): reads it (barcode first, "
    "else OCR + AI), proposes its values as facts, flags doubtful values, duplicates and wrong year, and says which "
    "procedure or case it belongs to.",
    {"type": "object", "properties": {
        "subject_id": {"type": "string"},
        "doc": {"type": "string", "description": "dossier document id, or a file path"},
        "period": {"type": "string", "description": "expected year, e.g. 2025 (default: last year)"}},
     "required": ["subject_id", "doc"]},
    {"type": "object", "description": "summary, understood, doubtful, duplicates, wrong_year, facts_proposed, belongs_to"},
), recevoir)]
