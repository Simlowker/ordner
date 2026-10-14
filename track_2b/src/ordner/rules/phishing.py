"""Deterministic phishing guard for payment requests (QR-bill, e-mail text, prepared payment), no model involved.

A request is suspicious when its IBAN was never seen in the dossier, when a known creditor shows up with another
IBAN, when the creditor is unknown, or when the text pushes urgency together with a link. Suspicious never blocks:
the payment may still be prepared, but only with WARNING attached (the person checks the sender and pays herself).
"""
import re
import unicodedata

WARNING = {"fr": "possible hameçonnage — vérifiez l'expéditeur", "de": "möglicher Phishing-Versuch — prüfen Sie den Absender",
           "it": "possibile phishing — verifichi il mittente"}
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4})(?: ?\d{4}){1,6}(?: ?\d{1,3})?\b")
LINK = re.compile(r"https?://\S+|\bwww\.\S+", re.I)
# ponytail: phrase list in fr/de/it/en; a d1-3B decision.score if real phishing gets subtler
URGENT = re.compile(
    r"\burgent|immédiatement|sans délai|dernier (rappel|avertissement)|\b(24|48) ?h|aujourd'hui|suspendu|bloqué|poursuite"
    r"|sofort|dringend|letzte mahnung|gesperrt|innert 24|heute noch|betreibung"
    r"|subito|urgente|immediatamente|ultimo (avviso|sollecito)|bloccat|sospes"
    r"|immediately|final notice|suspended|within 24", re.I)


def _norm(s):
    s = "".join(c for c in unicodedata.normalize("NFKD", str(s).casefold()) if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", s))


def _iban(s):
    return re.sub(r"\s", "", s).upper()


def _g(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def extract(content) -> dict:
    """{"creditor", "iban", "text"} of any JSON-like content: a QR-bill parse, document fields, a tool result, the
    details of a prepared payment (recipient, body)."""
    out, texts = {"creditor": None, "iban": None}, []

    def walk(o):
        if isinstance(o, dict):
            if isinstance(o.get("iban"), str) and o["iban"].strip() and not out["iban"]:
                out["iban"] = _iban(o["iban"])
            cred = o.get("creditor") or o.get("recipient")
            if not out["creditor"] and cred:
                out["creditor"] = cred.get("name") if isinstance(cred, dict) else cred if isinstance(cred, str) else None
            for k, v in o.items():
                if k != "payload":  # raw QR payload repeats the parsed fields
                    walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)
        elif isinstance(o, str):
            texts.append(o)
    walk(content)
    out["text"] = "\n".join(texts)[:20000]
    if not out["iban"] and (m := IBAN.search(out["text"])):
        out["iban"] = _iban(m.group())
    return out


def known(documents, facts, exclude_doc=None):
    """(IBANs, creditor names) already in the dossier, outside the document under examination."""
    ibans, names = set(), set()
    for d in documents:
        if exclude_doc and _g(d, "id") == exclude_doc:
            continue
        fields = _g(d, "fields") or {}
        if _g(d, "issuer"):
            names.add(_norm(_g(d, "issuer")))
        e = extract({k: fields.get(k) for k in ("iban", "creditor")})
        if e["iban"]:
            ibans.add(e["iban"])
        if e["creditor"]:
            names.add(_norm(e["creditor"]))
    for f in facts:
        if (exclude_doc and _g(f, "source_doc") == exclude_doc) or _g(f, "status") == "rejected" or not isinstance(_g(f, "value"), str):
            continue
        key = _g(f, "key") or ""
        if key.endswith(".iban"):
            ibans.add(_iban(_g(f, "value")))
        elif key.endswith((".creditor", ".insurer", ".employer")):
            names.add(_norm(_g(f, "value")))
    return ibans, names - {""}


def _same(a, names):
    return any(len(min(a, n, key=len)) >= 4 and (a in n or n in a) for n in names)


def payment_check(content, documents=(), facts=(), doc_id=None, payment=False) -> dict:
    """{"request": is this a payment request, "suspicious", "reasons" (fr), "warning" ({fr,de,it} or None),
    "creditor", "iban"}. `doc_id`: the document under examination, left out of what the dossier already knows.
    `payment`: the content is a payment for sure (a prepared payment action), even without IBAN or link."""
    e = extract(content)
    urgent, link = URGENT.search(e["text"]), LINK.search(e["text"])
    request = payment or bool(e["iban"]) or bool(urgent and link)
    reasons = []
    if request:
        ibans, names = known(documents, facts, doc_id)
        creditor_known = bool(e["creditor"]) and _same(_norm(e["creditor"]), names)
        if e["iban"] and e["iban"] not in ibans:
            reasons.append(f"IBAN {e['iban']} jamais vu dans le dossier"
                           + (f" (le nom « {e['creditor']} » est connu : un IBAN changé est le piège classique)"
                              if creditor_known else ""))
        if e["creditor"] and not creditor_known:
            reasons.append(f"bénéficiaire « {e['creditor']} » jamais vu dans le dossier")
        if urgent and link:
            reasons.append(f"ton pressant (« {urgent.group()} ») avec un lien ({link.group()[:60]})")
    return {"request": request, "suspicious": bool(reasons), "reasons": reasons,
            "warning": dict(WARNING) if reasons else None, "creditor": e["creditor"], "iban": e["iban"]}
