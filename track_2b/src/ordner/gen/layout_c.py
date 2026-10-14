"""Layout C: a bank-letter style statement (test split only), unlike A and B.

Totals are split over two blocks: total tax value in a side panel, revenues and withholding claim
in a box at the bottom. Position-level tables add realistic distractor amounts.
"""

import os
import random
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

import reportlab
from reportlab.lib.colors import Color, black, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .synth import NS

_FONTS = os.path.join(os.path.dirname(reportlab.__file__), "fonts")  # Bitstream Vera, ships with reportlab
for _name, _file in (("Vera", "Vera.ttf"), ("Vera-Bold", "VeraBd.ttf"), ("Vera-Italic", "VeraIt.ttf")):
    pdfmetrics.registerFont(TTFont(_name, os.path.join(_FONTS, _file)))

CITY = {"ZH": ("8001", "Zürich"), "BE": ("3011", "Bern"), "LU": ("6003", "Luzern"), "ZG": ("6300", "Zug"),
        "BS": ("4051", "Basel"), "SG": ("9000", "St. Gallen"), "AG": ("5000", "Aarau"), "GR": ("7000", "Chur"),
        "VD": ("1003", "Lausanne"), "GE": ("1204", "Genève"), "NE": ("2000", "Neuchâtel"), "FR": ("1700", "Fribourg"),
        "VS": ("1950", "Sion"), "JU": ("2800", "Delémont"), "TI": ("6900", "Lugano")}
STREET = {"de": ["Seestrasse", "Hauptgasse", "Marktplatz", "Postgasse", "Lindenweg", "Kirchstrasse"],
          "fr": ["Rue du Lac", "Place du Marché", "Avenue de la Gare", "Rue Centrale", "Chemin des Vignes"],
          "it": ["Via Cantonale", "Piazza del Mercato", "Via della Stazione", "Corso San Gottardo", "Via ai Ronchi"]}

L = {
    "de": dict(
        title="Steuerverzeichnis {y}", sub="Stichtag {d}  ·  Kanton {c}", client_no="Kundennummer",
        ref="Dokument-Nr.", period="Berichtsperiode",
        intro=("Sehr geehrte Kundin, sehr geehrter Kunde. Nachstehend erhalten Sie die steuerrelevanten Angaben "
               "zu Ihren Konten und Depots für das Steuerjahr {y}."),
        accounts="Konten", cur="Whg.", balance="Saldo", value="Steuerwert", income="Ertrag", unit="Werte in CHF",
        depot="Depot {n}", qty="Anzahl", subtotal="Zwischentotal", no_sec="Keine Wertschriften im Depot.",
        side="Auf einen Blick", side_total="Total Steuerwert", side_acc="davon Konten", side_sec="davon Wertschriften",
        side_debt="Schulden", side_debt_int="Schuldzinsen",
        box="Angaben für Ihre Steuererklärung {y}", box_a="Bruttoertrag mit Verrechnungssteuer",
        box_b="Bruttoertrag ohne Verrechnungssteuer", box_wht="Verrechnungssteueranspruch (35 %)",
        footer="Dieses Dokument wurde elektronisch erstellt und ist ohne Unterschrift gültig."),
    "fr": dict(
        title="Relevé fiscal {y}", sub="Date de référence {d}  ·  Canton {c}", client_no="Numéro de client",
        ref="N° de document", period="Période",
        intro=("Madame, Monsieur, vous trouverez ci-dessous les informations fiscales relatives à vos comptes "
               "et dépôts pour l'année fiscale {y}."),
        accounts="Comptes", cur="Monn.", balance="Solde", value="Val. fiscale", income="Revenu", unit="Valeurs en CHF",
        depot="Dépôt {n}", qty="Nombre", subtotal="Sous-total", no_sec="Aucun titre en dépôt.",
        side="En bref", side_total="Total de la valeur imposable", side_acc="dont comptes", side_sec="dont titres",
        side_debt="Dettes", side_debt_int="Intérêts débiteurs",
        box="Données pour votre déclaration d'impôt {y}", box_a="Revenus bruts avec impôt anticipé",
        box_b="Revenus bruts sans impôt anticipé", box_wht="Droit au remboursement de l'impôt anticipé (35 %)",
        footer="Ce document a été établi électroniquement et est valable sans signature."),
    "it": dict(
        title="Estratto fiscale {y}", sub="Data di riferimento {d}  ·  Cantone {c}", client_no="Numero cliente",
        ref="N. documento", period="Periodo",
        intro=("Gentile cliente, di seguito trova le informazioni fiscali relative ai suoi conti e depositi "
               "per l'anno fiscale {y}."),
        accounts="Conti", cur="Div.", balance="Saldo", value="Val. fiscale", income="Reddito", unit="Valori in CHF",
        depot="Deposito {n}", qty="Quantità", subtotal="Subtotale", no_sec="Nessun titolo in deposito.",
        side="In breve", side_total="Totale valore imponibile", side_acc="di cui conti", side_sec="di cui titoli",
        side_debt="Debiti", side_debt_int="Interessi debitori",
        box="Dati per la sua dichiarazione d'imposta {y}", box_a="Reddito lordo con imposta preventiva",
        box_b="Reddito lordo senza imposta preventiva", box_wht="Diritto al rimborso dell'imposta preventiva (35 %)",
        footer="Il presente documento è stato allestito elettronicamente ed è valido senza firma."),
}

ACCENT = Color(0.05, 0.35, 0.33)
PANEL = Color(0.93, 0.95, 0.94)
GREY = Color(0.45, 0.45, 0.45)


def fmt(v, style):
    """'nbsp': 12 345.60 (no-break space, the fonts here have no thin space); 'plain': 12345.60."""
    d = Decimal(v).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return f"{d:,.2f}".replace(",", " ") if style == "nbsp" else f"{d:.2f}"


def _sum(els, attr):
    return sum((Decimal(e.get(attr, "0")) for e in els), Decimal(0))


def render(xml_path, pdf_path, lang, key):
    """Render the one-page statement; returns the number style used ('nbsp' or 'plain')."""
    rng = random.Random(key)
    style = rng.choice(["nbsp", "plain"])
    root = ET.parse(xml_path).getroot()
    n = {"e": NS}
    t = L[lang]
    y, canton = root.get("taxPeriod"), root.get("canton")
    d_end = datetime.strptime(root.get("periodTo"), "%Y-%m-%d").strftime("%d.%m.%Y")
    d_from = datetime.strptime(root.get("periodFrom"), "%Y-%m-%d").strftime("%d.%m.%Y")
    created = datetime.fromisoformat(root.get("creationDate")).strftime("%d.%m.%Y")
    inst = root.find("e:institution", n).get("name")
    cl = root.find("e:client", n)
    banks = root.find("e:listOfBankAccounts", n)
    secs = root.find("e:listOfSecurities", n)
    liab = root.find("e:listOfLiabilities", n)
    f = lambda v: fmt(v, style)  # noqa: E731
    chf = lambda v: f"CHF {f(v)}"  # noqa: E731

    W, H = A4
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    c.setTitle(t["title"].format(y=y))
    zip_, city = CITY[canton]

    # letterhead with text logo
    initials = "".join(w[0] for w in inst.split()[:2]).upper()
    c.setFillColor(ACCENT)
    c.roundRect(40, H - 78, 36, 36, 6, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Vera-Bold", 15)
    c.drawCentredString(58, H - 66, initials)
    c.setFillColor(black)
    c.setFont("Vera-Bold", 14)
    c.drawString(86, H - 58, inst)
    c.setFont("Vera", 7.5)
    c.setFillColor(GREY)
    c.drawString(86, H - 72, f"{rng.choice(STREET[lang])} {rng.randint(1, 60)}  ·  {zip_} {city}")
    c.drawRightString(W - 40, H - 58, f"{city}, {created}")
    c.setFillColor(black)

    # reference block (left) and address window (right)
    c.setFont("Vera", 7.5)
    for i, (k, v) in enumerate([(t["client_no"], cl.get("clientNumber")), (t["ref"], root.get("id")),
                                (t["period"], f"{d_from} – {d_end}")]):
        c.setFillColor(GREY)
        c.drawString(40, H - 140 - i * 12, k)
        c.setFillColor(black)
        c.drawString(115, H - 140 - i * 12, v)
    c.setFont("Vera", 10)
    for i, line in enumerate([f"{cl.get('firstName')} {cl.get('lastName')}",
                              f"{rng.choice(STREET[lang])} {rng.randint(1, 120)}", f"{zip_} {city}"]):
        c.drawString(330, H - 140 - i * 13, line)

    c.setFont("Vera-Bold", 16)
    c.drawString(40, H - 225, t["title"].format(y=y))
    c.setFont("Vera", 8.5)
    c.setFillColor(ACCENT)
    c.drawString(40, H - 240, t["sub"].format(d=d_end, c=canton))
    c.setFillColor(black)
    c.setFont("Vera", 8)
    words, line, yy = t["intro"].format(y=y).split(), "", H - 262
    for w in words:
        if c.stringWidth(f"{line} {w}", "Vera", 8) > 515:
            c.drawString(40, yy, line.strip())
            line, yy = "", yy - 11
        line = f"{line} {w}"
    c.drawString(40, yy, line.strip())

    # position tables (main column 40..390)
    x_cur, x_bal, x_val, x_inc = 205, 272, 335, 390

    def header(yy, cols):
        c.setFont("Vera-Bold", 6.5)
        c.setFillColor(GREY)
        for x, txt, right in cols:
            (c.drawRightString if right else c.drawString)(x, yy, txt)
        c.setFillColor(black)
        c.setLineWidth(0.5)
        c.line(40, yy - 4, x_inc, yy - 4)

    def subtotal(yy, val, inc):
        c.setLineWidth(0.5)
        c.line(40, yy + 9, x_inc, yy + 9)
        c.setFont("Vera-Bold", 7.5)
        c.drawString(40, yy, t["subtotal"])
        c.drawRightString(x_val, yy, f(val))
        c.drawRightString(x_inc, yy, f(inc))

    yy = H - 305
    c.setFont("Vera-Bold", 9.5)
    c.setFillColor(ACCENT)
    c.drawString(40, yy, t["accounts"])
    c.setFillColor(GREY)
    c.setFont("Vera-Italic", 6.5)
    c.drawRightString(x_inc, yy, t["unit"])
    c.setFillColor(black)
    yy -= 15
    header(yy, [(40, "", False), (x_cur, t["cur"], False), (x_bal, t["balance"], True), (x_val, t["value"], True),
                (x_inc, t["income"], True)])
    accs = banks.findall("e:bankAccount", n) if banks is not None else []
    yy -= 14
    for a in accs:
        tv = a.find("e:taxValue", n)
        c.setFont("Vera", 7)
        c.drawString(40, yy, a.get("bankAccountName"))
        c.drawString(x_cur, yy, a.get("bankAccountCurrency"))
        c.drawRightString(x_bal, yy, f(tv.get("balance")))
        c.drawRightString(x_val, yy, f(a.get("totalTaxValue")))
        c.drawRightString(x_inc, yy, f(a.get("totalGrossRevenueB")))
        yy -= 13
    subtotal(yy - 2, banks.get("totalTaxValue"), banks.get("totalGrossRevenueB"))

    yy -= 30
    c.setFont("Vera-Bold", 9.5)
    c.setFillColor(ACCENT)
    depot = secs.find("e:depot", n).get("depotNumber") if secs is not None else cl.get("clientNumber")
    c.drawString(40, yy, t["depot"].format(n=depot))
    c.setFillColor(black)
    yy -= 15
    if secs is None:
        c.setFont("Vera-Italic", 7.5)
        c.drawString(40, yy, t["no_sec"])
    else:
        header(yy, [(40, "", False), (x_cur, t["cur"], False), (x_bal, t["qty"], True), (x_val, t["value"], True),
                    (x_inc, t["income"], True)])
        yy -= 14
        for s_ in secs.findall(".//e:security", n):
            pays = s_.findall("e:payment", n)
            c.setFont("Vera", 7)
            c.drawString(40, yy, s_.get("securityName"))
            c.drawString(x_cur, yy, s_.get("currency"))
            c.drawRightString(x_bal, yy, s_.find("e:taxValue", n).get("quantity"))
            c.drawRightString(x_val, yy, f(s_.find("e:taxValue", n).get("value")))
            c.drawRightString(x_inc, yy, f(_sum(pays, "grossRevenueA") + _sum(pays, "grossRevenueB")))
            c.setFont("Vera", 6)
            c.setFillColor(GREY)
            c.drawString(40, yy - 8, f"ISIN {s_.get('isin')}  ·  Valor {s_.get('valorNumber')}")
            c.setFillColor(black)
            yy -= 20
        subtotal(yy - 4, secs.get("totalTaxValue"),
                 Decimal(secs.get("totalGrossRevenueA")) + Decimal(secs.get("totalGrossRevenueB")))

    # side panel (block 1): total tax value
    px, pw, ptop = 410, 145, H - 295
    c.setFillColor(PANEL)
    c.rect(px, ptop - 190, pw, 190, fill=1, stroke=0)
    c.setFillColor(ACCENT)
    c.rect(px, ptop - 3, pw, 3, fill=1, stroke=0)
    c.setFont("Vera-Bold", 9.5)
    c.drawString(px + 10, ptop - 20, t["side"])
    c.setFillColor(black)
    c.setFont("Vera", 7.5)
    c.drawString(px + 10, ptop - 42, t["side_total"])
    c.setFont("Vera-Bold", 12)
    c.drawRightString(px + pw - 10, ptop - 60, chf(root.get("totalTaxValue")))
    rows = [(t["side_acc"], banks.get("totalTaxValue") if banks is not None else "0"),
            (t["side_sec"], secs.get("totalTaxValue") if secs is not None else "0"),
            (t["side_debt"], liab.get("totalTaxValue") if liab is not None else "0"),
            (t["side_debt_int"], liab.get("totalGrossRevenueB") if liab is not None else "0")]
    yy = ptop - 85
    for k, v in rows:
        c.setFont("Vera", 7)
        c.setFillColor(GREY)
        c.drawString(px + 10, yy, k)
        c.setFillColor(black)
        c.setFont("Vera", 8)
        c.drawRightString(px + pw - 10, yy - 11, chf(v))
        yy -= 26

    # bottom box (block 2): revenues and withholding claim
    bx, bw, btop = 40, W - 80, 205
    c.setStrokeColor(ACCENT)
    c.setLineWidth(1.2)
    c.rect(bx, btop - 95, bw, 95, fill=0, stroke=1)
    c.setStrokeColor(black)
    c.setFont("Vera-Bold", 9.5)
    c.setFillColor(ACCENT)
    c.drawString(bx + 12, btop - 18, t["box"].format(y=y))
    c.setFillColor(black)
    for i, (k, attr) in enumerate([("box_a", "totalGrossRevenueA"), ("box_b", "totalGrossRevenueB"),
                                   ("box_wht", "totalWithHoldingTaxClaim")]):
        row = btop - 42 - i * 20
        c.setFont("Vera", 8.5)
        c.drawString(bx + 12, row, t[k])
        c.setFont("Vera-Bold", 9.5)
        c.drawRightString(bx + bw - 12, row, chf(root.get(attr)))
        if i < 2:
            c.setLineWidth(0.3)
            c.setStrokeColor(GREY)
            c.line(bx + 12, row - 7, bx + bw - 12, row - 7)
            c.setStrokeColor(black)

    c.setFont("Vera", 6.5)
    c.setFillColor(GREY)
    c.drawString(40, 45, t["footer"])
    c.drawString(40, 35, inst)
    c.drawRightString(W - 40, 35, "1/1")
    c.showPage()
    c.save()
    return style
