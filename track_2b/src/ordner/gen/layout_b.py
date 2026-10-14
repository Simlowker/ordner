"""Layout B: our own one-page summary of an eCH-0196 statement (test split only)."""

import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from reportlab.lib.colors import Color, black, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .synth import NS

L = {
    "de": dict(
        doc="Steuerausweis", sub="Übersicht für die Steuererklärung {y}", holder="Kontoinhaber/in", no="Kunden-Nr.",
        canton="Wohnkanton", period="Zeitraum", ref="Referenz", issued="Ausgestellt am", cur="Beträge in CHF",
        s_rev="1  Erträge {y}", s_wealth="2  Vermögen per {d}", s_debt="3  Schulden",
        rev_a="Erträge mit Verrechnungssteuerabzug (A)", wht="Rückforderbare Verrechnungssteuer 35 %",
        rev_b="Erträge ohne Verrechnungssteuerabzug (B)", bank="Kontoguthaben ({n} Konten)",
        sec="Wertschriften ({n} Positionen)", total="Steuerwert total", debt="Schulden per {d}", debt_int="Schuldzinsen {y}",
        none="keine", note=("Übertragen Sie die Beträge in das Wertschriftenverzeichnis Ihrer Steuererklärung. "
                            "Die Verrechnungssteuer wird nur bei vollständiger Deklaration zurückerstattet."),
        page="Seite 1 von 1"),
    "fr": dict(
        doc="Attestation fiscale", sub="Récapitulatif pour la déclaration d'impôt {y}", holder="Titulaire",
        no="N° de client", canton="Canton de domicile", period="Période", ref="Référence", issued="Établi le",
        cur="Montants en CHF", s_rev="1  Rendements {y}", s_wealth="2  Fortune au {d}", s_debt="3  Dettes",
        rev_a="Rendements soumis à l'impôt anticipé (A)", wht="Impôt anticipé récupérable 35 %",
        rev_b="Rendements non soumis à l'impôt anticipé (B)", bank="Avoirs en compte ({n} comptes)",
        sec="Titres ({n} positions)", total="Valeur fiscale totale", debt="Dettes au {d}", debt_int="Intérêts passifs {y}",
        none="aucune", note=("Reportez ces montants dans l'état des titres de votre déclaration d'impôt. "
                             "L'impôt anticipé n'est remboursé qu'en cas de déclaration complète."),
        page="Page 1 sur 1"),
    "it": dict(
        doc="Attestato fiscale", sub="Riepilogo per la dichiarazione d'imposta {y}", holder="Titolare",
        no="N. cliente", canton="Cantone di domicilio", period="Periodo", ref="Riferimento", issued="Emesso il",
        cur="Importi in CHF", s_rev="1  Redditi {y}", s_wealth="2  Sostanza al {d}", s_debt="3  Debiti",
        rev_a="Redditi soggetti all'imposta preventiva (A)", wht="Imposta preventiva rimborsabile 35 %",
        rev_b="Redditi non soggetti all'imposta preventiva (B)", bank="Averi in conto ({n} conti)",
        sec="Titoli ({n} posizioni)", total="Valore fiscale totale", debt="Debiti al {d}", debt_int="Interessi passivi {y}",
        none="nessuno", note=("Riportate questi importi nell'elenco dei titoli della vostra dichiarazione d'imposta. "
                              "L'imposta preventiva è rimborsata solo in caso di dichiarazione completa."),
        page="Pagina 1 di 1"),
}

SHADE = Color(0.92, 0.92, 0.88)
DARK = Color(0.18, 0.22, 0.30)


def fmt(v):
    """Layout-B amount format: 2 decimals, typographic apostrophe as thousands separator."""
    d = Decimal(v).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return f"{d:,.2f}".replace(",", "’")


def render(xml_path, pdf_path, lang):
    root = ET.parse(xml_path).getroot()
    n = {"e": NS}
    t = L[lang]
    y = root.get("taxPeriod")
    pf, pt = (datetime.strptime(root.get(k), "%Y-%m-%d").strftime("%d.%m.%Y") for k in ("periodFrom", "periodTo"))
    inst = root.find("e:institution", n).get("name")
    cl = root.find("e:client", n)
    banks = root.find("e:listOfBankAccounts", n)
    secs = root.find("e:listOfSecurities", n)
    liab = root.find("e:listOfLiabilities", n)
    n_acc = len(banks.findall("e:bankAccount", n)) if banks is not None else 0
    n_sec = len(secs.findall(".//e:security", n)) if secs is not None else 0

    W, H = A4
    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    c.setTitle(f"{t['doc']} {y}")

    c.setFillColor(DARK)
    c.rect(0, H - 22, W, 22, fill=1, stroke=0)
    c.setFillColor(black)
    c.setFont("Times-Bold", 20)
    c.drawString(50, H - 70, inst)
    c.setFont("Times-Italic", 11)
    c.drawString(50, H - 88, f"{t['doc']} {y}")
    c.setLineWidth(1.2)
    c.line(50, H - 98, W - 50, H - 98)

    info = [(t["holder"], f"{cl.get('firstName')} {cl.get('lastName')}"), (t["no"], cl.get("clientNumber")),
            (t["canton"], root.get("canton")), (t["period"], f"{pf} – {pt}"), (t["ref"], root.get("id")),
            (t["issued"], datetime.fromisoformat(root.get("creationDate")).strftime("%d.%m.%Y"))]
    yy = H - 122
    for i, (k, v) in enumerate(info):
        x, off = (50, 95) if i < 3 else (290, 80)
        row = yy - (i % 3) * 15
        c.setFont("Times-Roman", 9)
        c.drawString(x, row, k)
        c.setFont("Times-Bold", 10)
        c.drawString(x + off, row, v)

    c.setFont("Times-Bold", 14)
    c.drawCentredString(W / 2, H - 200, t["sub"].format(y=y))
    c.setFont("Times-Italic", 9)
    c.drawRightString(W - 50, H - 222, t["cur"])

    d = pt
    zero = "0"
    sections = [
        (t["s_rev"].format(y=y), [
            (t["rev_a"], root.get("totalGrossRevenueA"), True),
            (t["wht"], root.get("totalWithHoldingTaxClaim"), True),
            (t["rev_b"], root.get("totalGrossRevenueB"), True),
        ]),
        (t["s_wealth"].format(d=d), [
            (t["bank"].format(n=n_acc), banks.get("totalTaxValue") if banks is not None else zero, False),
            (t["sec"].format(n=n_sec), secs.get("totalTaxValue") if secs is not None else zero, False),
            (t["total"], root.get("totalTaxValue"), True),
        ]),
        (t["s_debt"], [
            (t["debt"].format(d=d), liab.get("totalTaxValue") if liab is not None else zero, False),
            (t["debt_int"].format(y=y), liab.get("totalGrossRevenueB") if liab is not None else zero, False),
        ]),
    ]
    yy = H - 240
    for title, rows in sections:
        c.setFillColor(DARK)
        c.rect(50, yy - 4, W - 100, 18, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Times-Bold", 11)
        c.drawString(56, yy + 1, title)
        c.setFillColor(black)
        yy -= 24
        for i, (label, val, bold) in enumerate(rows):
            if i % 2 == 0:
                c.setFillColor(SHADE)
                c.rect(50, yy - 5, W - 100, 19, fill=1, stroke=0)
                c.setFillColor(black)
            c.setFont("Times-Bold" if bold else "Times-Roman", 10.5)
            c.drawString(62, yy, label)
            c.setFont("Courier-Bold" if bold else "Courier", 10.5)
            c.drawRightString(W - 58, yy, fmt(val))
            yy -= 19
        c.setLineWidth(0.4)
        c.line(50, yy + 12, W - 50, yy + 12)
        yy -= 22

    c.setFont("Times-Roman", 8.5)
    words, line, yy = t["note"].split(), "", yy - 10
    for w in words:
        if c.stringWidth(f"{line} {w}", "Times-Roman", 8.5) > W - 100:
            c.drawString(50, yy, line.strip())
            line, yy = "", yy - 11
        line = f"{line} {w}"
    c.drawString(50, yy, line.strip())

    c.setFont("Times-Italic", 8)
    c.drawString(50, 30, inst)
    c.drawRightString(W - 50, 30, t["page"])
    c.showPage()
    c.save()
