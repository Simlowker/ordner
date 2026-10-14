"""Swiss QR-bill: decode the QR (zxing-cpp), parse the SPC payload, validate it against SIX IG v2.3.

Source: SIX, Implementation Guidelines suisses pour QR-facture, v2.3, valid from 21.11.2025
https://www.six-group.com/dam/download/banking-services/standardization/qr-bill/ig-qr-bill-v2.3-fr.pdf
(checked 2026-10-14: QR-IID 30000-31999; QRR = 27 digits, modulo 10 recursive; SCOR = ISO 11649 modulo 97-10;
amount 0.01-999999999.99, CHF/EUR only; address type "S" only since the combined type was removed; CR+LF or LF).
Fact keys: bill.<reference or doc sha>.{amount,creditor,iban,reference,message}.
"""
import re

import pypdfium2 as pdfium
import zxingcpp
from PIL import Image

from ordner.connectors import Parsed, fact, new_document

KIND = "qr_bill_invoice"
ADDR = ("adr_type", "name", "street_or_line1", "building_or_line2", "postal_code", "town", "country")
MOD10 = (0, 9, 4, 6, 8, 2, 7, 1, 3, 5)


def mod97(s: str) -> bool:
    """IBAN and ISO 11649 creditor reference: move the first 4 characters to the end, letters -> 10..35, mod 97 == 1."""
    s = s[4:] + s[:4]
    return s.isalnum() and s.isascii() and int("".join(str(int(c, 36)) for c in s)) % 97 == 1


def mod10r(digits: str) -> int:
    carry = 0
    for d in digits:
        carry = MOD10[(carry + int(d)) % 10]
    return (10 - carry) % 10


def is_qr_iban(iban: str) -> bool:
    return iban[4:9].isdigit() and 30000 <= int(iban[4:9]) <= 31999


def qrr_ok(ref: str) -> bool:
    return len(ref) == 27 and ref.isdigit() and mod10r(ref[:26]) == int(ref[26])


def scor_ok(ref: str) -> bool:
    return 5 <= len(ref) <= 25 and ref[:2].upper() == "RF" and mod97(ref.upper())


def page_images(path, scale=3):
    with open(path, "rb") as f:
        is_pdf = f.read(5) == b"%PDF-"
    if not is_pdf:
        return [Image.open(path)]
    pdf = pdfium.PdfDocument(str(path))
    try:
        return [pdf[i].render(scale=scale).to_pil() for i in range(len(pdf))]
    finally:
        pdf.close()


def decode_images(images) -> list[str]:
    return [r.text for img in images for r in zxingcpp.read_barcodes(img, formats=zxingcpp.BarcodeFormat.QRCode)
            if r.text.startswith("SPC")]


def parse(text: str) -> dict:
    """SPC payload -> dict with `errors` (invalid per IG) and `warnings` (readable but non-standard)."""
    lines = text.replace("\r\n", "\n").split("\n")
    if len(lines) < 31:
        return {"errors": [f"{len(lines)} lines, at least 31 expected"], "warnings": []}
    L = lines + [""] * (34 - len(lines))
    b = {
        "qr_type": L[0], "version": L[1], "coding": L[2], "iban": L[3].replace(" ", "").upper(),
        "creditor": dict(zip(ADDR, L[4:11])), "ultimate_creditor": dict(zip(ADDR, L[11:18])),
        "amount": L[18], "currency": L[19], "debtor": dict(zip(ADDR, L[20:27])),
        "reference_type": L[27], "reference": L[28].replace(" ", ""), "message": L[29], "trailer": L[30],
        "billing_info": L[31], "alt_procedures": [x for x in L[32:34] if x],
    }
    err, warn = [], []
    if b["qr_type"] != "SPC" or not b["version"].startswith("02") or b["coding"] != "1" or b["trailer"] != "EPD":
        err.append(f"header/trailer: {b['qr_type']}/{b['version']}/{b['coding']}/{b['trailer']}")
    iban = b["iban"]
    b["iban_valid"] = len(iban) == 21 and iban[:2] in ("CH", "LI") and mod97(iban)
    b["qr_iban"] = b["iban_valid"] and is_qr_iban(iban)
    if not b["iban_valid"]:
        err.append(f"IBAN {iban}: must be CH/LI, 21 characters, mod 97 == 1")
    rt, ref = b["reference_type"], b["reference"]
    if b["qr_iban"] and rt != "QRR":
        err.append("a QR-IBAN requires reference type QRR")
    if rt == "QRR":
        if not b["qr_iban"]:
            err.append("reference type QRR requires a QR-IBAN (QR-IID 30000-31999)")
        if not qrr_ok(ref):
            err.append(f"QR reference {ref}: 27 digits with modulo 10 recursive check digit expected")
    elif rt == "SCOR":
        if not scor_ok(ref):
            err.append(f"creditor reference {ref}: ISO 11649 RF + modulo 97-10 expected")
    elif rt == "NON":
        if ref:
            err.append("reference type NON must have an empty reference")
    else:
        err.append(f"unknown reference type {rt!r}")
    if b["amount"]:
        if not re.fullmatch(r"\d{1,9}(\.\d{1,2})?", b["amount"]) or not 0.01 <= float(b["amount"]) <= 999999999.99:
            err.append(f"amount {b['amount']!r}: 0.01-999999999.99 with '.' as decimal separator")
    if b["currency"] not in ("CHF", "EUR"):
        err.append(f"currency {b['currency']!r}: only CHF and EUR")
    for role in ("creditor", "debtor"):
        a = b[role]
        if role == "creditor" and not a["name"]:
            err.append("creditor name is mandatory")
        if any(a.values()) and a["adr_type"] != "S":
            (warn if a["adr_type"] == "K" else err).append(
                f"{role} address type {a['adr_type']!r}: only 'S' (structured) is allowed by IG v2.3")
    if any(b["ultimate_creditor"].values()):
        warn.append("ultimate creditor is reserved for future use and should be empty")
    b["errors"], b["warnings"] = err, warn
    return b


def read(path, subject_id, channel="inbox", digest=None, images=None) -> Parsed:
    doc = new_document(path, subject_id, channel, digest)
    payloads = decode_images(images if images is not None else page_images(path))
    if not payloads:
        return Parsed(doc, status="needs_ai_read", message="no Swiss QR code found")
    bills = [parse(p) for p in payloads]
    b = bills[0]
    doc.kind, doc.read_path, doc.issuer = KIND, "barcode", b.get("creditor", {}).get("name")
    doc.fields = {**b, "payload": payloads[0], "other_bills": bills[1:]}
    facts = []
    for bill in bills:
        if "iban" not in bill:
            continue
        bid = bill["reference"] or f"doc{doc.sha256[:10]}"
        doubt = 0.0 if not bill["errors"] else 0.5    # read exactly, but the content fails validation
        facts += [fact(doc, f"bill.{bid}.creditor", bill["creditor"]["name"], doubt=doubt),
                  fact(doc, f"bill.{bid}.iban", bill["iban"], doubt=doubt),
                  fact(doc, f"bill.{bid}.reference", bill["reference"] or None, doubt=doubt),
                  fact(doc, f"bill.{bid}.message", bill["message"] or None, doubt=doubt)]
        if bill["amount"]:
            facts.append(fact(doc, f"bill.{bid}.amount", float(bill["amount"]), bill["currency"], doubt=doubt))
    errors = [e for bill in bills for e in bill["errors"]]
    return Parsed(doc, facts, message="; ".join(errors + [w for bill in bills for w in bill["warnings"]]),
                  data={"bills": bills, "valid": not errors})


def make_test_bill(out_stem, account, creditor, amount=None, currency="CHF", debtor=None, reference=None,
                   message="", title="Facture"):
    """Write <out_stem>.png (the Swiss QR code) and <out_stem>.pdf (a one-page invoice) using the `qrbill` package."""
    import qrcode
    from qrbill import QRBill          # the PyPI package (absolute import), not this module
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    bill = QRBill(account=account, creditor=creditor, amount=amount, currency=currency, debtor=debtor,
                  reference_number=reference, additional_information=message)
    payload = bill.qr_data()
    img = qrcode.make(payload, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    img.save(f"{out_stem}.png")
    c = canvas.Canvas(f"{out_stem}.pdf", pagesize=A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20 * mm, 270 * mm, title)
    c.setFont("Helvetica", 10)
    for i, line in enumerate([creditor["name"], f"{creditor.get('pcode', '')} {creditor.get('city', '')}",
                              f"Montant : {amount or '-'} {currency}", f"Compte : {account}", message]):
        c.drawString(20 * mm, (255 - 6 * i) * mm, line)
    c.drawString(5 * mm, 100 * mm, "Section paiement")
    c.drawImage(ImageReader(img.get_image()), 67 * mm, 42 * mm, 46 * mm, 46 * mm)
    c.save()
    return payload
