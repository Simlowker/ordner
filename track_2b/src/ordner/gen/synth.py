"""Synthetic eCH-0196 tax statements (fictional institutions, clients, positions)."""

import random
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from opensteuerauszug.util import round_accounting

NS = "http://www.ech.ch/xmlns/eCH-0196/2"
ET.register_namespace("", NS)
ET.register_namespace("eCH-0097", "http://www.ech.ch/xmlns/eCH-0097/4")
ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")

TAX_YEAR = 2025
FIELDS = (
    "totalTaxValue", "totalGrossRevenueA", "totalGrossRevenueB", "totalWithHoldingTaxClaim",
    "institution", "canton", "taxPeriod", "client_last_name",
)
NUMERIC = FIELDS[:4]

CANTONS = {"ZH": "de", "BE": "de", "LU": "de", "ZG": "de", "BS": "de", "SG": "de", "AG": "de", "GR": "de",
           "VD": "fr", "GE": "fr", "NE": "fr", "FR": "fr", "VS": "fr", "JU": "fr", "TI": "it"}
CANTON_W = {c: (4 if c == "TI" else 1) for c in CANTONS}  # ~44 % de, 33 % fr, 22 % it

FX = {"CHF": Decimal("1"), "EUR": Decimal("0.9312"), "USD": Decimal("0.7925")}
RATE = {"CHF": (0.0005, 0.0075), "EUR": (0.002, 0.02), "USD": (0.005, 0.035)}

ROOT_A = ["Vel", "Mor", "Tal", "Cor", "Lun", "Bris", "Sel", "Var", "Fen", "Orl", "Grav", "Quin", "Zel", "Arv"]
ROOT_B = ["mira", "vessa", "dorn", "bruck", "lin", "olt", "feld", "mont", "ival", "stein", "aro", "enza"]
BANK_SUFFIX = {
    "de": ["Privatbank AG", "Bank AG", "Vermögensbank AG", "Handelsbank AG"],
    "fr": ["Banque Privée SA", "Banque SA", "Banque de Gestion SA"],
    "it": ["Banca Privata SA", "Banca SA", "Banca di Gestione SA"],
}
FIRST = {
    "de": ["Lukas", "Anna", "Noah", "Mia", "Elias", "Lea", "Jonas", "Laura", "Simon", "Nina", "Reto", "Urs", "Brigitte", "Jürg"],
    "fr": ["Camille", "Louis", "Chloé", "Gabriel", "Léa", "Hugo", "Manon", "Julien", "Élodie", "Nicolas", "Sophie", "Mathieu"],
    "it": ["Luca", "Giulia", "Marco", "Sofia", "Matteo", "Chiara", "Alessandro", "Elena", "Davide", "Sara", "Fabio", "Martina"],
}
LAST = {
    "de": ["Müller", "Meier", "Schmid", "Keller", "Weber", "Huber", "Schneider", "Steiner", "Brunner", "Baumann",
           "Gerber", "Frei", "Wyss", "Graf", "Bühler", "Moser", "Bachmann", "Hofstetter", "Lüthi", "Zürcher"],
    "fr": ["Favre", "Rochat", "Bonvin", "Pittet", "Jaquet", "Perret", "Chevalley", "Mottier", "Dubois", "Rey",
           "Morand", "Délèze", "Berthoud", "Cuénod", "Vuilleumier", "Gay"],
    "it": ["Bernasconi", "Rossi", "Ferrari", "Pedrazzini", "Lurati", "Bianchi", "Galli", "Fontana", "Cattaneo",
           "Righetti", "Bernardi", "Mozzetti", "Quadri", "Pozzi"],
}
ACCOUNT_NAME = {
    "de": {"CHF": ["Privatkonto", "Sparkonto", "Vorsorgesparkonto"], "EUR": ["Fremdwährungskonto EUR"], "USD": ["Fremdwährungskonto USD"]},
    "fr": {"CHF": ["Compte privé", "Compte épargne", "Compte épargne plus"], "EUR": ["Compte en devises EUR"], "USD": ["Compte en devises USD"]},
    "it": {"CHF": ["Conto privato", "Conto risparmio", "Conto deposito"], "EUR": ["Conto in valuta EUR"], "USD": ["Conto in valuta USD"]},
}
LOAN_NAME = {"de": ["Hypothek", "Privatkredit"], "fr": ["Hypothèque", "Crédit privé"], "it": ["Ipoteca", "Credito privato"]}
INTEREST = {"de": "Zinsgutschrift", "fr": "Crédit d'intérêts", "it": "Accredito interessi"}
DEBIT_INTEREST = {"de": "Schuldzins", "fr": "Intérêts débiteurs", "it": "Interessi passivi"}
DIVIDEND = {"de": "Dividende", "fr": "Dividende", "it": "Dividendo"}

CO_A = ["Alto", "Brena", "Cresta", "Dolvi", "Elmar", "Ferro", "Gotta", "Helio", "Iselt", "Junta", "Karst", "Lavor",
        "Monta", "Nerio", "Ostra", "Pirel", "Rovan", "Sarto", "Teval", "Ulma", "Vigor", "Wendt"]
CO_B = ["tec", "pharm", "werk", "chem", "log", "vest", "net", "bau", "med", "energ"]
CH_SUFFIX = ["Holding AG N", "AG Namenaktie", "Gruppe AG", "Holding SA", "Industrie AG", "SA nom."]
FOREIGN = {"DE": ("EUR", ["AG", "SE"]), "FR": ("EUR", ["SA"]), "NL": ("EUR", ["NV"]), "AT": ("EUR", ["AG"]),
           "IE": ("USD", ["plc", "UCITS ETF"]), "LU": ("EUR", ["SICAV", "UCITS ETF"])}


def q2(x):
    return Decimal(x).quantize(Decimal("0.01"), ROUND_HALF_UP)


def dec(rng, lo, hi):
    return q2(str(rng.uniform(lo, hi)))


def isin(country, rng):
    body = country + "".join(str(rng.randint(0, 9)) for _ in range(9))
    digits = "".join(str(int(c, 36)) for c in body)
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch) * (2 if i % 2 == 0 else 1)
        total += d - 9 if d > 9 else d
    return body + str((10 - total % 10) % 10)


def rand_date(rng, m0, m1):
    start = date(TAX_YEAR, m0, 1)
    end = date(TAX_YEAR, m1, 28)
    return start + timedelta(days=rng.randint(0, (end - start).days))


def fx_on(rng, cur):
    if cur == "CHF":
        return Decimal("1")
    return (FX[cur] * Decimal(str(1 + rng.uniform(-0.03, 0.03)))).quantize(Decimal("0.000001"))


def s(v):
    return str(v)


def make_statement(seed, idx, attempt=0):
    """Return (xml_bytes, truth, meta). Deterministic in (seed, idx, attempt)."""
    rng = random.Random(f"{seed}:{idx}" + (f":{attempt}" if attempt else ""))
    canton = rng.choices(list(CANTON_W), list(CANTON_W.values()))[0]
    lang = CANTONS[canton]
    inst = f"{rng.choice(ROOT_A)}{rng.choice(ROOT_B)} {rng.choice(BANK_SUFFIX[lang])}"
    first, last = rng.choice(FIRST[lang]), rng.choice(LAST[lang])
    client_no = f"{rng.randint(0, 999_999_999):09d}"
    org_nr = f"{rng.randint(10000, 99999)}"
    abbr = (inst.replace(" ", "").upper() + "XXXX")[:4]
    stmt_id = f"CH{org_nr}{abbr}{client_no}X{TAX_YEAR}123101"
    created = datetime(TAX_YEAR + 1, 1, 5) + timedelta(minutes=rng.randint(0, 80 * 24 * 60))
    ye = f"{TAX_YEAR}-12-31"

    # --- bank accounts ---
    accounts = []
    for k in range(rng.randint(1, 4)):
        cur = "CHF" if k == 0 else rng.choices(["CHF", "EUR", "USD"], [5, 3, 2])[0]
        balance = max(q2(str(rng.lognormvariate(9.3, 1.3))), Decimal("50.00"))
        rate = FX[cur]
        payments = []
        if rng.random() < 0.8:
            n_pay = rng.choice([1, 1, 2, 4])
            annual = balance * Decimal(str(rng.uniform(*RATE[cur])))
            months = {1: [12], 2: [6, 12], 4: [3, 6, 9, 12]}[n_pay]
            for m in months:
                amount = q2(annual / n_pay)
                if amount <= 0:
                    continue
                er = fx_on(rng, cur)
                payments.append(dict(date=f"{TAX_YEAR}-{m:02d}-{28 if m != 12 else 31}", amount=amount, cur=cur, er=er,
                                     b=amount * er))
        accounts.append(dict(
            number=f"{rng.randint(1000, 9999)}-{rng.randint(100000, 999999)}.{rng.randint(10, 99)}",
            name=f"{rng.choice(ACCOUNT_NAME[lang][cur])}", cur=cur, balance=balance, er=rate, value=balance * rate,
            payments=payments))

    # --- securities ---
    securities = []
    for pos in range(rng.choices(range(7), [15, 15, 15, 15, 15, 13, 12])[0]):
        name_root = rng.choice(CO_A) + rng.choice(CO_B)
        if rng.random() < 0.55:
            country, cur = "CH", "CHF"
            name = f"{name_root.capitalize()} {rng.choice(CH_SUFFIX)}"
        else:
            country = rng.choice(list(FOREIGN))
            cur, suf = FOREIGN[country]
            name = f"{name_root.capitalize()} {rng.choice(suf)}"
        price = dec(rng, 15, 450)
        er = FX[cur]
        qty = max(1, round(rng.lognormvariate(9.0, 1.1) / float(price * er)))
        pays = []
        if rng.random() < 0.85:
            dpu = q2(price * Decimal(str(rng.uniform(0.01, 0.05))))
            amount = dpu * qty
            pdate = rand_date(rng, 3, 6) if country == "CH" else rand_date(rng, 2, 11)
            per = fx_on(rng, cur)
            if country == "CH":
                pays.append(dict(date=pdate, dpu=dpu, amount=amount, cur=cur, er=per, a=amount, b=Decimal(0),
                                 wht=amount * Decimal("0.35")))
            else:
                pays.append(dict(date=pdate, dpu=dpu, amount=amount, cur=cur, er=per, a=Decimal(0), b=amount * per,
                                 wht=Decimal(0)))
        securities.append(dict(pos=pos + 1, country=country, cur=cur, name=name[:60], valor=rng.randint(1_000_000, 99_999_999),
                               isin=isin(country, rng), qty=qty, price=price, er=er, value=qty * price * er,
                               cat=rng.choice(["SHARE", "SHARE", "SHARE", "FUND"]), payments=pays))

    # --- liabilities ---
    liabilities = []
    if rng.random() < 0.25:
        bal = q2(rng.choice([rng.uniform(5_000, 60_000), rng.uniform(150_000, 900_000)]))
        interest = q2(bal * Decimal(str(rng.uniform(0.012, 0.028))))
        liabilities.append(dict(number=f"{rng.randint(100000, 999999)}.{rng.randint(10, 99)}",
                                name=rng.choice(LOAN_NAME[lang]), balance=bal, interest=interest))

    # --- totals (mirrors OSA TotalCalculator, verified there in build) ---
    acc_tot = [dict(tv=round_accounting(a["value"]), b=round_accounting(sum((p["b"] for p in a["payments"]), Decimal(0))))
               for a in accounts]
    bank = dict(tv=round_accounting(sum((t["tv"] for t in acc_tot), Decimal(0))), a=round_accounting(0),
                b=round_accounting(sum((t["b"] for t in acc_tot), Decimal(0))), wht=round_accounting(0))
    sec = None
    if securities:
        allp = [p for x in securities for p in x["payments"]]
        sec = dict(tv=round_accounting(sum((x["value"] for x in securities), Decimal(0))),
                   a=round_accounting(sum((p["a"] for p in allp), Decimal(0))),
                   b=round_accounting(sum((p["b"] for p in allp), Decimal(0))),
                   wht=round_accounting(sum((p["wht"] for p in allp), Decimal(0))))
    lists = [bank] + ([sec] if sec else [])
    tot = {k: round_accounting(sum((x[k] for x in lists), Decimal(0))) for k in ("tv", "a", "b", "wht")}

    # --- XML ---
    root = ET.Element(f"{{{NS}}}taxStatement", {
        "id": stmt_id, "creationDate": created.isoformat(), "taxPeriod": str(TAX_YEAR),
        "periodFrom": f"{TAX_YEAR}-01-01", "periodTo": ye, "country": "CH", "canton": canton,
        "totalTaxValue": s(tot["tv"]), "totalGrossRevenueA": s(tot["a"]), "totalGrossRevenueB": s(tot["b"]),
        "totalWithHoldingTaxClaim": s(tot["wht"]), "minorVersion": "22"})
    ET.SubElement(root, f"{{{NS}}}institution", {"name": inst})
    ET.SubElement(root, f"{{{NS}}}client", {"clientNumber": client_no, "firstName": first, "lastName": last})

    lba = ET.SubElement(root, f"{{{NS}}}listOfBankAccounts", {
        "totalTaxValue": s(bank["tv"]), "totalGrossRevenueA": s(bank["a"]), "totalGrossRevenueB": s(bank["b"]),
        "totalWithHoldingTaxClaim": s(bank["wht"])})
    for a, t in zip(accounts, acc_tot):
        el = ET.SubElement(lba, f"{{{NS}}}bankAccount", {
            "bankAccountNumber": a["number"], "bankAccountName": f"{a['name']} {a['number']}", "bankAccountCountry": "CH",
            "bankAccountCurrency": a["cur"], "totalTaxValue": s(t["tv"]), "totalGrossRevenueA": s(round_accounting(0)),
            "totalGrossRevenueB": s(t["b"]), "totalWithHoldingTaxClaim": s(round_accounting(0))})
        ET.SubElement(el, f"{{{NS}}}taxValue", {"referenceDate": ye, "balanceCurrency": a["cur"], "balance": s(a["balance"]),
                                                 "exchangeRate": s(a["er"]), "value": s(a["value"])})
        for p in a["payments"]:
            ET.SubElement(el, f"{{{NS}}}payment", {
                "paymentDate": p["date"], "name": INTEREST[lang], "amountCurrency": p["cur"], "amount": s(p["amount"]),
                "exchangeRate": s(p["er"]), "grossRevenueA": "0", "grossRevenueB": s(p["b"]), "withHoldingTaxClaim": "0"})

    if liabilities:
        l_tv = round_accounting(sum((x["balance"] for x in liabilities), Decimal(0)))
        l_b = round_accounting(sum((x["interest"] for x in liabilities), Decimal(0)))
        lol = ET.SubElement(root, f"{{{NS}}}listOfLiabilities", {"totalTaxValue": s(l_tv), "totalGrossRevenueB": s(l_b)})
        for x in liabilities:
            el = ET.SubElement(lol, f"{{{NS}}}liabilityAccount", {
                "bankAccountNumber": x["number"], "bankAccountName": f"{x['name']} {x['number']}", "bankAccountCountry": "CH",
                "bankAccountCurrency": "CHF", "totalTaxValue": s(round_accounting(x["balance"])),
                "totalGrossRevenueB": s(round_accounting(x["interest"]))})
            ET.SubElement(el, f"{{{NS}}}taxValue", {"referenceDate": ye, "balanceCurrency": "CHF", "balance": s(x["balance"]),
                                                     "exchangeRate": "1", "value": s(x["balance"])})
            ET.SubElement(el, f"{{{NS}}}payment", {"paymentDate": ye, "name": DEBIT_INTEREST[lang], "amountCurrency": "CHF",
                                                    "amount": s(x["interest"]), "exchangeRate": "1",
                                                    "grossRevenueB": s(x["interest"])})

    if sec:
        los = ET.SubElement(root, f"{{{NS}}}listOfSecurities", {
            "totalTaxValue": s(sec["tv"]), "totalGrossRevenueA": s(sec["a"]), "totalGrossRevenueB": s(sec["b"]),
            "totalWithHoldingTaxClaim": s(sec["wht"]), "totalLumpSumTaxCredit": "0.000", "totalNonRecoverableTax": "0.000",
            "totalAdditionalWithHoldingTaxUSA": "0.000", "totalGrossRevenueIUP": "0.000",
            "totalGrossRevenueConversion": "0.000"})
        depot = ET.SubElement(los, f"{{{NS}}}depot", {"depotNumber": f"{client_no}-D1"})
        for x in securities:
            el = ET.SubElement(depot, f"{{{NS}}}security", {
                "positionId": str(x["pos"]), "country": x["country"], "currency": x["cur"], "quotationType": "PIECE",
                "securityCategory": x["cat"], "securityName": x["name"], "valorNumber": str(x["valor"]), "isin": x["isin"]})
            ET.SubElement(el, f"{{{NS}}}taxValue", {
                "referenceDate": ye, "quotationType": "PIECE", "quantity": str(x["qty"]), "balanceCurrency": x["cur"],
                "unitPrice": s(x["price"]), "exchangeRate": s(x["er"]), "value": s(x["value"])})
            for p in x["payments"]:
                ET.SubElement(el, f"{{{NS}}}payment", {
                    "paymentDate": p["date"].isoformat(), "exDate": (p["date"] - timedelta(days=2)).isoformat(),
                    "name": DIVIDEND[lang], "quotationType": "PIECE", "quantity": str(x["qty"]),
                    "amountCurrency": p["cur"], "amountPerUnit": s(p["dpu"]), "amount": s(p["amount"]),
                    "exchangeRate": s(p["er"]), "grossRevenueA": s(p["a"]), "grossRevenueB": s(p["b"]),
                    "withHoldingTaxClaim": s(p["wht"])})
            ET.SubElement(el, f"{{{NS}}}stock", {"referenceDate": f"{TAX_YEAR}-01-01", "mutation": "0",
                                                  "quotationType": "PIECE", "quantity": str(x["qty"]),
                                                  "balanceCurrency": x["cur"]})

    ET.indent(root)
    xml = ET.tostring(root, encoding="UTF-8", xml_declaration=True)
    truth = {"totalTaxValue": s(tot["tv"]), "totalGrossRevenueA": s(tot["a"]), "totalGrossRevenueB": s(tot["b"]),
             "totalWithHoldingTaxClaim": s(tot["wht"]), "institution": inst, "canton": canton,
             "taxPeriod": str(TAX_YEAR), "client_last_name": last}
    meta = {"language": lang, "attempt": attempt, "statement_id": stmt_id, "n_accounts": len(accounts), "n_securities": len(securities),
            "n_liabilities": len(liabilities)}
    return xml, truth, meta


def recompute_totals(xml_bytes):
    """Independent recomputation of the statement totals from leaf values (for checks)."""
    root = ET.fromstring(xml_bytes)
    n = {"e": NS}
    D = lambda el, k: Decimal(el.get(k, "0"))  # noqa: E731
    lists = []
    for acc_list in root.findall("e:listOfBankAccounts", n):
        accs = acc_list.findall("e:bankAccount", n)
        tv = sum((round_accounting(sum((D(v, "value") for v in a.findall("e:taxValue", n)), Decimal(0))) for a in accs), Decimal(0))
        b = sum((round_accounting(sum((D(p, "grossRevenueB") for p in a.findall("e:payment", n)), Decimal(0))) for a in accs), Decimal(0))
        lists.append({"tv": tv, "a": Decimal(0), "b": b, "wht": Decimal(0)})
    for sec_list in root.findall("e:listOfSecurities", n):
        secs = sec_list.findall(".//e:security", n)
        pays = [p for x in secs for p in x.findall("e:payment", n)]
        lists.append({"tv": sum((D(x.find("e:taxValue", n), "value") for x in secs), Decimal(0)),
                      "a": sum((D(p, "grossRevenueA") for p in pays), Decimal(0)),
                      "b": sum((D(p, "grossRevenueB") for p in pays), Decimal(0)),
                      "wht": sum((D(p, "withHoldingTaxClaim") for p in pays), Decimal(0))})
    keys = {"tv": "totalTaxValue", "a": "totalGrossRevenueA", "b": "totalGrossRevenueB", "wht": "totalWithHoldingTaxClaim"}
    return {keys[k]: round_accounting(sum((round_accounting(x[k]) for x in lists), Decimal(0))) for k in keys}
