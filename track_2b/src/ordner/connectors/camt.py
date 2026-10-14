"""ISO 20022 camt.053 (statement) / camt.054 (debit-credit notification) -> transactions; match payments to QR-bills.

Namespace-agnostic ({*}): handles .001.04 (Cdtr/Nm, AmtDtls/TxAmt) and .001.08 (Cdtr/Pty/Nm, TxDtls/Amt).
Fact key: bank.balance.closing.<iban> (period = statement end date).
"""
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

from ordner.connectors import Parsed, fact, new_document


def _t(el, *paths):
    for p in paths:
        v = el.findtext(p)
        if v:
            return v.strip()
    return None


def _first(*candidates):
    for el, path in candidates:
        found = el.find(path) if el is not None else None
        if found is not None:          # Element truthiness means "has children": never use `or` on elements
            return found
    return None


def _date(el, path):
    return (_t(el, f"{path}/{{*}}Dt", f"{path}/{{*}}DtTm") or "")[:10] or None


def parse_xml(xml_bytes) -> dict:
    root = ET.fromstring(xml_bytes)
    ns = root.tag[1:].split("}")[0] if root.tag.startswith("{") else ""
    msg = ns.rsplit(":", 1)[-1] or root.tag
    out = {"message_type": msg, "statements": []}
    for st in root.findall("{*}*/{*}Stmt") + root.findall("{*}*/{*}Ntfctn") + root.findall("{*}*/{*}Rpt"):
        iban = _t(st, "{*}Acct/{*}Id/{*}IBAN", "{*}Acct/{*}Id/{*}Othr/{*}Id")
        bals = {}
        for b in st.findall("{*}Bal"):
            sign = -1 if _t(b, "{*}CdtDbtInd") == "DBIT" else 1
            bals[_t(b, "{*}Tp/{*}CdOrPrtry/{*}Cd")] = {"amount": sign * float(_t(b, "{*}Amt")),
                                                     "currency": b.find("{*}Amt").get("Ccy"), "date": _date(b, "{*}Dt")}
        txs = []
        for n in st.findall("{*}Ntry"):
            direction = "debit" if _t(n, "{*}CdtDbtInd") == "DBIT" else "credit"
            base = {"iban": iban, "date": _date(n, "{*}BookgDt"), "value_date": _date(n, "{*}ValDt"),
                    "direction": direction, "status": _t(n, "{*}Sts/{*}Cd", "{*}Sts"),
                    "booking_ref": _t(n, "{*}AcctSvcrRef")}
            details = n.findall("{*}NtryDtls/{*}TxDtls") or [None]
            for d in details:
                src = d if d is not None else n
                amt = _first((d, "{*}Amt"), (d, "{*}AmtDtls/{*}TxAmt/{*}Amt"), (n, "{*}Amt"))
                party = "Cdtr" if direction == "debit" else "Dbtr"
                txs.append({**base, "amount": float(amt.text), "currency": amt.get("Ccy"),
                            "counterparty": _t(src, f"{{*}}RltdPties/{{*}}{party}/{{*}}Pty/{{*}}Nm",
                                               f"{{*}}RltdPties/{{*}}{party}/{{*}}Nm"),
                            "counterparty_iban": _t(src, f"{{*}}RltdPties/{{*}}{party}Acct/{{*}}Id/{{*}}IBAN"),
                            "reference": _t(src, "{*}RmtInf/{*}Strd/{*}CdtrRefInf/{*}Ref"),
                            "end_to_end_id": _t(src, "{*}Refs/{*}EndToEndId"),
                            "remittance": " ".join(u.text.strip() for u in src.findall("{*}RmtInf/{*}Ustrd") if u.text)
                            or _t(src, "{*}AddtlTxInf") or _t(n, "{*}AddtlNtryInf")})
        out["statements"].append({"id": _t(st, "{*}Id"), "iban": iban, "currency": _t(st, "{*}Acct/{*}Ccy"),
                                  "from": _t(st, "{*}FrToDt/{*}FrDtTm", "{*}FrToDt/{*}FrDt"),
                                  "to": _t(st, "{*}FrToDt/{*}ToDtTm", "{*}FrToDt/{*}ToDt"),
                                  "balances": bals, "transactions": txs})
    return out


def read(path, subject_id, channel="camt", digest=None) -> Parsed:
    doc = new_document(path, subject_id, channel, digest)
    with open(path, "rb") as f:
        data = parse_xml(f.read())
    if not data["message_type"].startswith("camt.05"):
        return Parsed(doc, status="unsupported", message=f"not camt.05x: {data['message_type']}")
    doc.kind = "bank_statement_camt053" if data["message_type"].startswith("camt.053") else "bank_notification_camt054"
    doc.read_path = "structured"
    facts = []
    for st in data["statements"]:
        end = (st["to"] or "")[:10] or None
        if end and not doc.year:
            doc.year = int(end[:4])
        cl = st["balances"].get("CLBD")
        if cl and st["iban"]:
            facts.append(fact(doc, f"bank.balance.closing.{st['iban']}", cl["amount"], cl["currency"], end, 0.0))
    txs = [t for st in data["statements"] for t in st["transactions"]]
    doc.fields = {"message_type": data["message_type"], "accounts": [st["iban"] for st in data["statements"]],
                  "transactions": len(txs)}
    return Parsed(doc, facts, data={**data, "transactions": txs})


def _norm(ref):
    return (ref or "").replace(" ", "").upper()


def match(transactions, bills) -> list[dict]:
    """Bills are `qrbill.parse` dicts. Match debits on the QRR/SCOR reference, else on creditor IBAN + amount.
    status: paid | amount_mismatch (partial or over payment) | open."""
    debits = [t for t in transactions if t["direction"] == "debit"]
    out = []
    for b in bills:
        ref, amount = _norm(b.get("reference")), float(b["amount"]) if b.get("amount") else None
        hits, by = ([t for t in debits if _norm(t["reference"]) == ref], "reference") if ref else ([], None)
        if not hits and amount is not None:
            hits, by = [t for t in debits if t["counterparty_iban"] == b["iban"] and round(t["amount"], 2) == amount
                        and t["currency"] == b["currency"]], "iban+amount"
        paid = round(sum(t["amount"] for t in hits), 2)
        status = "open" if not hits else "paid" if amount is None or paid == amount else "amount_mismatch"
        out.append({"reference": b.get("reference"), "creditor": b["creditor"]["name"], "amount": amount,
                    "paid": paid if hits else None, "status": status, "matched_by": by if hits else None,
                    "transactions": hits})
    return out


def make_sample_camt053(path, iban, entries, opening=0.0, currency="CHF", owner="Test Person", period=("", "")):
    """Synthetic camt.053.001.08. entries: dicts with date, amount, direction (debit|credit), counterparty,
    counterparty_iban, reference, reference_type (QRR|SCOR), remittance."""
    closing = round(opening + sum(e["amount"] * (-1 if e["direction"] == "debit" else 1) for e in entries), 2)
    frm, to = period if all(period) else (min(e["date"] for e in entries), max(e["date"] for e in entries))

    def bal(code, amount, date):
        return (f"<Bal><Tp><CdOrPrtry><Cd>{code}</Cd></CdOrPrtry></Tp><Amt Ccy=\"{currency}\">{abs(amount):.2f}</Amt>"
                f"<CdtDbtInd>{'DBIT' if amount < 0 else 'CRDT'}</CdtDbtInd><Dt><Dt>{date}</Dt></Dt></Bal>")

    ntries = []
    for i, e in enumerate(entries, 1):
        party, debit = ("Cdtr", True) if e["direction"] == "debit" else ("Dbtr", False)
        ref = (f"<Strd><CdtrRefInf><Tp><CdOrPrtry><Prtry>{e.get('reference_type', 'QRR')}</Prtry></CdOrPrtry></Tp>"
               f"<Ref>{escape(e['reference'])}</Ref></CdtrRefInf></Strd>") if e.get("reference") else ""
        ust = f"<Ustrd>{escape(e['remittance'])}</Ustrd>" if e.get("remittance") else ""
        acct = (f"<{party}Acct><Id><IBAN>{e['counterparty_iban']}</IBAN></Id></{party}Acct>"
                if e.get("counterparty_iban") else "")
        ntries.append(
            f"<Ntry><Amt Ccy=\"{currency}\">{e['amount']:.2f}</Amt><CdtDbtInd>{'DBIT' if debit else 'CRDT'}</CdtDbtInd>"
            f"<Sts><Cd>BOOK</Cd></Sts><BookgDt><Dt>{e['date']}</Dt></BookgDt><ValDt><Dt>{e['date']}</Dt></ValDt>"
            f"<AcctSvcrRef>SAMPLE-{i:04d}</AcctSvcrRef><BkTxCd><Domn><Cd>PMNT</Cd><Fmly>"
            f"<Cd>{'ICDT' if debit else 'RCDT'}</Cd><SubFmlyCd>DMCT</SubFmlyCd></Fmly></Domn></BkTxCd>"
            f"<NtryDtls><TxDtls><Refs><EndToEndId>E2E-{i:04d}</EndToEndId></Refs>"
            f"<Amt Ccy=\"{currency}\">{e['amount']:.2f}</Amt><CdtDbtInd>{'DBIT' if debit else 'CRDT'}</CdtDbtInd>"
            f"<RltdPties><{party}><Pty><Nm>{escape(e['counterparty'])}</Nm></Pty></{party}>{acct}</RltdPties>"
            f"<RmtInf>{ust}{ref}</RmtInf></TxDtls></NtryDtls></Ntry>")
    xml = (f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
           f"<Document xmlns=\"urn:iso:std:iso:20022:tech:xsd:camt.053.001.08\"><BkToCstmrStmt>"
           f"<GrpHdr><MsgId>SAMPLE-{to}</MsgId><CreDtTm>{to}T23:59:59</CreDtTm></GrpHdr>"
           f"<Stmt><Id>STMT-{to}</Id><ElctrncSeqNb>1</ElctrncSeqNb><CreDtTm>{to}T23:59:59</CreDtTm>"
           f"<FrToDt><FrDtTm>{frm}T00:00:00</FrDtTm><ToDtTm>{to}T23:59:59</ToDtTm></FrToDt>"
           f"<Acct><Id><IBAN>{iban}</IBAN></Id><Ccy>{currency}</Ccy><Ownr><Nm>{escape(owner)}</Nm></Ownr></Acct>"
           f"{bal('OPBD', opening, frm)}{bal('CLBD', closing, to)}{''.join(ntries)}</Stmt></BkToCstmrStmt></Document>\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)
    return closing
