"""eCH-0196 e-tax statement: PDF417 fast path (exact) -> XML -> proposed facts, or a clean `needs_ai_read` signal.

Fact keys put the measure before the institution so `facts(key_prefix="tax.statement.total_tax_value")` returns one
fact per bank, ready to sum:
  tax.statement.{total_tax_value,gross_revenue_a,gross_revenue_b,withholding_tax_claim,period,canton}.<institution>
  tax.accounts.tax_value.<institution>.<account>     tax.securities.tax_value.<institution>.<isin|valor>
  tax.liabilities.{tax_value,interest}.<institution>
plus the card keys tax.period, tax.securities.{total_tax_value,withholding_tax_total} for this statement only:
with several banks they are not summed here (to verify by the dossier / rules).
"""
import re
import xml.etree.ElementTree as ET
import zlib

from ordner.connectors import Parsed, fact, new_document
from ordner.gen.oracle import decode_pdf417

KIND = "swiss_tax_statement_eCH0196"
TOTALS = {"totalTaxValue": "total_tax_value", "totalGrossRevenueA": "gross_revenue_a",
          "totalGrossRevenueB": "gross_revenue_b", "totalWithHoldingTaxClaim": "withholding_tax_claim"}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", (s or "unknown").lower()).strip("_")


def num(x):
    return float(x) if x not in (None, "") else None


def read(path, subject_id, channel="inbox", digest=None) -> Parsed:
    doc = new_document(path, subject_id, channel, digest)
    try:
        xml = decode_pdf417(path)
    except (ValueError, zlib.error, RuntimeError) as e:   # RuntimeError covers pdfium.PdfiumError
        return Parsed(doc, status="needs_ai_read", message=f"no readable eCH-0196 barcode ({e}); use the AI read path")
    return from_xml(xml, doc)


def from_xml(xml_bytes, doc) -> Parsed:
    root = ET.fromstring(xml_bytes)
    if not root.tag.endswith("taxStatement"):
        return Parsed(doc, status="unsupported", message=f"not an eCH-0196 taxStatement: {root.tag}")
    inst_el = root.find("{*}institution")
    inst = inst_el.get("name") if inst_el is not None else None
    client = root.find("{*}client")
    doc.kind, doc.read_path, doc.issuer = KIND, "barcode", inst
    doc.year = int(root.get("taxPeriod")) if root.get("taxPeriod") else None

    def position(el, **extra):
        tv = el.find("{*}taxValue")
        pays = el.findall("{*}payment")
        return {**extra, "currency": el.get("bankAccountCurrency") or el.get("currency"),
                "tax_value": tv.get("value") if tv is not None else None,
                "quantity": tv.get("quantity") if tv is not None else None,
                "gross_revenue_a": el.get("totalGrossRevenueA") or _sum(pays, "grossRevenueA"),
                "gross_revenue_b": el.get("totalGrossRevenueB") or _sum(pays, "grossRevenueB"),
                "withholding_tax_claim": el.get("totalWithHoldingTaxClaim") or _sum(pays, "withHoldingTaxClaim")}

    accounts = [position(a, number=a.get("bankAccountNumber"), name=a.get("bankAccountName"))
                for a in root.iterfind("{*}listOfBankAccounts/{*}bankAccount")]
    securities = [position(s, isin=s.get("isin"), valor=s.get("valorNumber"), name=s.get("securityName"),
                           category=s.get("securityCategory"), depot=d.get("depotNumber"))
                  for d in root.iterfind("{*}listOfSecurities/{*}depot") for s in d.iterfind("{*}security")]
    liabilities = [position(a, number=a.get("bankAccountNumber"), name=a.get("bankAccountName"))
                   for a in root.iterfind("{*}listOfLiabilities/{*}liabilityAccount")]
    lia = root.find("{*}listOfLiabilities")
    doc.fields = {
        "statement_id": root.get("id"), "institution": inst, "canton": root.get("canton"),
        "tax_period": root.get("taxPeriod"), "period_from": root.get("periodFrom"), "period_to": root.get("periodTo"),
        "client_number": client.get("clientNumber") if client is not None else None,
        **{v: root.get(k) for k, v in TOTALS.items()},
        "accounts": accounts, "securities": securities, "liabilities": liabilities,
    }

    i = slug(inst)
    facts = [fact(doc, f"tax.statement.{v}.{i}", num(root.get(k)), "CHF", doubt=0.0) for k, v in TOTALS.items()
             if root.get(k) is not None]
    facts += [fact(doc, f"tax.statement.period.{i}", f"{root.get('periodFrom')}/{root.get('periodTo')}", doubt=0.0),
              fact(doc, f"tax.statement.canton.{i}", root.get("canton"), doubt=0.0)]
    facts += [fact(doc, f"tax.accounts.tax_value.{i}.{slug(a['number'])}", num(a["tax_value"]), "CHF", doubt=0.0)
              for a in accounts]
    facts += [fact(doc, f"tax.securities.tax_value.{i}.{slug(s['isin'] or s['valor'])}", num(s["tax_value"]), "CHF",
                   doubt=0.0) for s in securities]
    sec = root.find("{*}listOfSecurities")
    facts.append(fact(doc, "tax.period", root.get("taxPeriod"), doubt=0.0))
    if sec is not None:     # un-namespaced keys read by the tax.withholding.refund card: per statement, not summed
        facts += [fact(doc, "tax.securities.total_tax_value", num(sec.get("totalTaxValue")), "CHF", doubt=0.0),
                  fact(doc, "tax.securities.withholding_tax_total", num(sec.get("totalWithHoldingTaxClaim")), "CHF",
                       doubt=0.0)]
    if lia is not None:
        facts += [fact(doc, f"tax.liabilities.tax_value.{i}", num(lia.get("totalTaxValue")), "CHF", doubt=0.0),
                  fact(doc, f"tax.liabilities.interest.{i}", num(lia.get("totalGrossRevenueB")), "CHF", doubt=0.0)]

    warnings = _check_totals(root)
    return Parsed(doc, facts, message="; ".join(warnings), data={"xml": xml_bytes.decode("utf-8", "replace"), "warnings": warnings})


def _sum(payments, attr):
    vals = [float(p.get(attr)) for p in payments if p.get(attr)]
    return str(round(sum(vals), 2)) if vals else None


def _check_totals(root):
    """Statement totals = bank accounts + securities (liabilities are separate); flag a mismatch, never fix it."""
    out = []
    parts = [root.find("{*}listOfBankAccounts"), root.find("{*}listOfSecurities")]
    for k in TOTALS:
        if root.get(k) is None:
            continue
        s = sum(float(p.get(k) or 0) for p in parts if p is not None)
        if abs(s - float(root.get(k))) > 0.05:
            out.append(f"{k}: statement {root.get(k)} != accounts + securities {s:.2f}")
    return out
