"""RFC 5322 .eml DRAFTS + letter (.txt, .pdf) from prepared Actions. Ordner never sends: no SMTP here, the person sends.

Action.payload: {"template": <TEMPLATES key>, "to": addr?, "from": addr?, "vars": {...}}. Variable names follow the
last segment of the card fact keys (lp_opposition: debt.payment_order.{number,notified_on,creditor}, contested_amount).
Common vars: sender_name, sender_address, recipient_name, recipient_address, place. A missing variable is
written as « [à compléter : name] » and listed in `missing`, never guessed. Legal basis (verified with tools/fedlex.py
on 2026-10-14): LAMal art. 7 al. 2 and al. 5 (RS 832.10); LP art. 74 al. 1-3 (RS 281.1).
"""
import textwrap
from datetime import date
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from ordner.core.schema import Action

TEMPLATES = {
    "bank_document_request": {
        "subject": "Demande du relevé fiscal électronique {year} (eCH-0196)",
        "body": """Madame, Monsieur,

Titulaire de la relation n° {client_number}, je vous prie de me faire parvenir le relevé fiscal électronique
(e-relevé fiscal selon la norme eCH-0196, PDF avec codes-barres) pour l'année fiscale {year}, couvrant l'ensemble
de mes comptes et dépôts auprès de votre établissement.

Je vous remercie par avance et vous prie d'agréer, Madame, Monsieur, mes salutations distinguées.""",
        "notes": [],
    },
    "lamal_termination": {
        "subject": "Résiliation de l'assurance obligatoire des soins au {end_date}",
        "body": """Madame, Monsieur,

Je résilie mon assurance obligatoire des soins (n° d'assuré {policy_number}) pour le {end_date}, conformément à
l'art. 7 LAMal. Mon affiliation prendra fin dès que mon nouvel assureur vous aura communiqué qu'il m'assure sans
interruption de la protection d'assurance (art. 7 al. 5 LAMal).

La présente résiliation ne concerne pas mes éventuelles assurances complémentaires.

Je vous remercie de me confirmer la réception de cette résiliation et vous prie d'agréer, Madame, Monsieur,
mes salutations distinguées.""",
        "notes": ["LAMal art. 7 al. 2 : changement pour la fin du mois qui précède la nouvelle prime, « moyennant un "
                  "préavis d'un mois » ; l'échéance exacte est calculée par ordner.rules. Envoi recommandé conseillé.",
                  "https://www.fedlex.admin.ch/eli/cc/1995/1328_1328_1328/fr#art_7"],
    },
    "lp_opposition": {
        "subject": "Opposition au commandement de payer n° {number}",
        "body": """Madame, Monsieur,

{opposition_sentence}

Je vous prie de bien vouloir m'en donner acte (art. 74 al. 3 LP).

Veuillez agréer, Madame, Monsieur, mes salutations distinguées.""",
        "notes": ["LP art. 74 al. 1 : opposition à l'office « dans les dix jours à compter de la notification du "
                  "commandement de payer ». L'échéance exacte est calculée par ordner.rules.",
                  "L'acceptation d'un courriel par l'office n'est pas vérifiée : préférer la lettre signée ou la "
                  "déclaration au guichet.", "https://www.fedlex.admin.ch/eli/cc/11/529_488_529/fr#art_74"],
    },
}


class _Vars(dict):
    def __init__(self, *a):
        super().__init__(*a)
        self.missing = []

    def __missing__(self, key):
        self.missing.append(key)
        return f"[à compléter : {key}]"


def _opposition(v):
    head = (f"Je forme opposition au commandement de payer n° {v['number']}, notifié le {v['notified_on']}, "
            f"dans la poursuite introduite par {v['creditor']}")
    if v.get("contested_amount"):       # LP art. 74 al. 2: a partial opposition must state the exact amount
        return f"{head}, pour un montant contesté de CHF {v['contested_amount']} (opposition partielle, art. 74 al. 2 LP)."
    return f"{head}. Je conteste la dette dans sa totalité (art. 74 LP)."


def render(template: str, vars: dict) -> dict:
    t = TEMPLATES[template]
    v = _Vars(vars)
    if template == "lp_opposition":
        v["opposition_sentence"] = _opposition(v)
    subject = t["subject"].format_map(v)
    body = "\n\n".join(" ".join(par.split("\n")) for par in t["body"].format_map(v).split("\n\n"))  # client wraps
    signature = "\n".join(x for x in (v["sender_name"], v.get("sender_address", "")) if x)
    return {"subject": subject, "text": body, "signature": signature, "body": f"{body}\n\n{signature}\n",
            "missing": sorted(set(v.missing)), "notes": t["notes"]}


def draft(action: Action, out_dir) -> dict:
    """Write <action.id>.eml (draft, X-Unsent), .txt and .pdf; return paths, missing variables and notes."""
    p = action.payload
    r = render(p["template"], p.get("vars", {}))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = out / action.id

    msg = EmailMessage()
    if p.get("from"):
        msg["From"] = p["from"]
    if p.get("to"):
        msg["To"] = p["to"]
    msg["Subject"] = r["subject"]
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="ordner.local")
    msg["X-Unsent"] = "1"                  # opened as an editable draft by Outlook / Thunderbird / Apple Mail
    msg["X-Ordner-Action"] = action.id
    msg["X-Ordner-Status"] = "draft, never sent by Ordner"
    msg.set_content(r["body"])
    stem.with_suffix(".eml").write_bytes(bytes(msg))

    v = p.get("vars", {})
    recipient = "\n".join(x for x in (v.get("recipient_name", ""), v.get("recipient_address", "")) if x)
    sender, place = r["signature"], v.get("place", "")
    letter = (f"{sender}\n\n{recipient}\n\n{place + ', ' if place else ''}le {date.today().strftime('%d.%m.%Y')}\n\n"
              f"{r['subject']}\n\n{r['body']}")
    stem.with_suffix(".txt").write_text(letter, encoding="utf-8")
    _pdf(stem.with_suffix(".pdf"), sender, recipient, place, r["subject"], r["text"])
    return {"eml": str(stem.with_suffix(".eml")), "txt": str(stem.with_suffix(".txt")),
            "pdf": str(stem.with_suffix(".pdf")), "missing": r["missing"], "notes": r["notes"], "sent": False}


def _pdf(path, sender, recipient, place, subject, body):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=A4)
    c.setFont("Helvetica", 10)
    for i, line in enumerate(sender.splitlines()):
        c.drawString(20 * mm, (275 - 5 * i) * mm, line)
    for i, line in enumerate(recipient.splitlines()):      # right-hand window of a Swiss C5 envelope
        c.drawString(118 * mm, (245 - 5 * i) * mm, line)
    c.drawString(20 * mm, 215 * mm, f"{place + ', ' if place else ''}le {date.today().strftime('%d.%m.%Y')}")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20 * mm, 200 * mm, subject)
    c.setFont("Helvetica", 10)
    y = 188
    for para in body.split("\n\n"):
        for line in textwrap.wrap(para, 95) or [""]:
            c.drawString(20 * mm, y * mm, line)
            y -= 5
        y -= 3
    c.drawString(20 * mm, (y - 15) * mm, "Signature : ______________________")
    for i, line in enumerate(sender.splitlines()):
        c.drawString(20 * mm, (y - 22 - 5 * i) * mm, line)
    c.save()
