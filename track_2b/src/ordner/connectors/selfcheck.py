"""python -m ordner.connectors.selfcheck: QR-bills (generated), camt + matching, eCH-0196 fast path on a real PDF,
OFSP comparator on a fixture, .eml drafts, inbox dedupe and video page picking. Offline."""
import email
import random
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from email import policy
from email.utils import parsedate_to_datetime
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageFilter

from ordner.connectors import camt, ech0196, email_drafts, inbox, ofsp_premiums, qrbill
from ordner.core.schema import Action

ROOT = Path(__file__).resolve().parents[3]
S = "subj_selfcheck"
CRED = {"name": "Max Muster & Söhne", "street": "Musterstrasse", "house_num": "123", "pcode": "8000",
        "city": "Seldwyla", "country": "CH"}
DEBT = {"name": "Simon Muster", "street": "Musterstrasse", "house_num": "1", "pcode": "8000", "city": "Seldwyla",
        "country": "CH"}
QRR = "210000000003139471430009017"       # SIX IG v2.3, annex A, example 2 (with QR-IBAN CH4431999123000889012)


def check_qrbill(tmp):
    assert qrbill.mod10r(QRR[:26]) == int(QRR[26]) and qrbill.mod97("CH9300762011623852957")
    assert qrbill.is_qr_iban("CH4431999123000889012") and not qrbill.is_qr_iban("CH9300762011623852957")
    base = "00000000000000000000123456"
    qrr2 = base + str(qrbill.mod10r(base))
    specs = {
        "qrr": dict(account="CH44 3199 9123 0008 8901 2", creditor=CRED, amount="1949.75", debtor=DEBT,
                    reference=QRR, message="Ordre du 15.10.2020"),
        "scor": dict(account="CH9300762011623852957", creditor={**CRED, "name": "Régie Lémanique SA"},
                     amount="250.00", reference="RF18539007547034", message="Loyer octobre"),
        "non": dict(account="CH5604835012345678009", creditor={**CRED, "name": "Club de gym"}, amount="80.00"),
        "open": dict(account="CH4431999123000889012", creditor={**CRED, "name": "Assurance Exemple SA"},
                     amount="120.50", reference=qrr2, message="Prime novembre"),
    }
    bills, payloads = {}, {}
    for name, spec in specs.items():
        payloads[name] = qrbill.make_test_bill(tmp / f"bill_{name}", **spec)
        for ext in ("png", "pdf"):
            r = qrbill.read(tmp / f"bill_{name}.{ext}", S)
            assert r.status == "ok" and r.data["valid"] and r.document.kind == qrbill.KIND, (name, ext, r.message)
            b = r.data["bills"][0]
            assert b["amount"] == spec["amount"] and b["creditor"]["name"] == spec["creditor"]["name"], b
        bills[name] = b
    q = bills["qrr"]
    assert q["qr_iban"] and q["reference_type"] == "QRR" and q["reference"] == QRR and q["debtor"]["town"] == "Seldwyla"
    assert bills["scor"]["reference_type"] == "SCOR" and not bills["scor"]["qr_iban"]
    assert bills["non"]["reference_type"] == "NON" and bills["non"]["reference"] == ""
    facts = {f.key: f for f in qrbill.read(tmp / "bill_qrr.png", S).facts}
    assert facts[f"bill.{QRR}.amount"].value == 1949.75 and facts[f"bill.{QRR}.amount"].unit == "CHF"
    assert facts[f"bill.{QRR}.amount"].actor == "connector" and facts[f"bill.{QRR}.amount"].status == "proposed"

    p = payloads["qrr"]
    bad = {
        "iban": p.replace("CH4431999123000889012", "CH4431999123000889013"),
        "qrr": p.replace(QRR, QRR[:-1] + str((int(QRR[-1]) + 1) % 10)),
        "qrr_on_iban": p.replace("CH4431999123000889012", "CH9300762011623852957"),
        "currency": p.replace("\r\nCHF\r\n", "\r\nUSD\r\n"),
        "amount": p.replace("1949.75", "1949,75"),
    }
    for name, payload in bad.items():
        assert qrbill.parse(payload)["errors"], name
    assert not qrbill.parse(p.replace("\r\n", "\n"))["errors"]                     # LF-only separators are valid
    k = qrbill.parse(p.replace("\r\nS\r\nMax", "\r\nK\r\nMax"))
    assert not k["errors"] and k["warnings"]                                       # combined address: warn only
    assert qrbill.parse("SPC\r\n0200")["errors"]
    print("ok  qrbill: 4 generated bills decoded from PNG and PDF, 5 tampered payloads rejected")
    return bills


def check_camt(tmp, bills):
    entries = [
        dict(date="2026-09-05", amount=1949.75, direction="debit", counterparty="Max Muster & Söhne",
             counterparty_iban="CH4431999123000889012", reference=QRR, remittance="Ordre du 15.10.2020"),
        dict(date="2026-09-10", amount=200.00, direction="debit", counterparty="Régie Lémanique SA",
             counterparty_iban="CH9300762011623852957", reference="RF18 5390 0754 7034", reference_type="SCOR"),
        dict(date="2026-09-12", amount=80.00, direction="debit", counterparty="Club de gym",
             counterparty_iban="CH5604835012345678009", remittance="Cotisation"),
        dict(date="2026-09-25", amount=5200.00, direction="credit", counterparty="Employeur SA",
             remittance="Salaire septembre"),
    ]
    closing = camt.make_sample_camt053(tmp / "camt053.xml", "CH9300762011623852957", entries, opening=3000.0)
    assert closing == round(3000 - 1949.75 - 200 - 80 + 5200, 2)
    r = camt.read(tmp / "camt053.xml", S)
    assert r.status == "ok" and r.document.kind == "bank_statement_camt053" and r.document.year == 2026
    txs = r.data["transactions"]
    assert len(txs) == 4 and txs[0]["counterparty"] == "Max Muster & Söhne" and txs[0]["reference"] == QRR
    assert txs[3]["direction"] == "credit" and txs[3]["counterparty"] == "Employeur SA" and txs[3]["amount"] == 5200.0
    assert r.facts[0].key == "bank.balance.closing.CH9300762011623852957" and r.facts[0].value == closing
    m = {x["creditor"]: x for x in camt.match(txs, list(bills.values()))}
    assert m["Max Muster & Söhne"]["status"] == "paid" and m["Max Muster & Söhne"]["matched_by"] == "reference"
    assert m["Régie Lémanique SA"]["status"] == "amount_mismatch" and m["Régie Lémanique SA"]["paid"] == 200.0
    assert m["Club de gym"]["status"] == "paid" and m["Club de gym"]["matched_by"] == "iban+amount"
    assert m["Assurance Exemple SA"]["status"] == "open"

    v04 = b"""<?xml version="1.0"?><Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.054.001.04"><BkToCstmrDbtCdtNtfctn>
<Ntfctn><Id>N1</Id><Acct><Id><IBAN>CH9300762011623852957</IBAN></Id></Acct><Ntry><Amt Ccy="CHF">99.90</Amt>
<CdtDbtInd>DBIT</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>2026-10-01</Dt></BookgDt><NtryDtls><TxDtls>
<AmtDtls><TxAmt><Amt Ccy="CHF">99.90</Amt></TxAmt></AmtDtls><RltdPties><Cdtr><Nm>Telco AG</Nm></Cdtr></RltdPties>
<RmtInf><Strd><CdtrRefInf><Ref>""" + QRR.encode() + b"""</Ref></CdtrRefInf></Strd></RmtInf></TxDtls></NtryDtls></Ntry>
</Ntfctn></BkToCstmrDbtCdtNtfctn></Document>"""
    d = camt.parse_xml(v04)
    t = d["statements"][0]["transactions"][0]
    assert d["message_type"] == "camt.054.001.04" and t["counterparty"] == "Telco AG" and t["amount"] == 99.9
    assert t["status"] == "BOOK" and t["reference"] == QRR and t["date"] == "2026-10-01"
    print("ok  camt: camt.053.001.08 sample parsed, 4 bills matched (paid / mismatch / iban+amount / open), .054.001.04")


def check_ech0196(tmp):
    pdfs = sorted((ROOT / "work" / "pdf").glob("*-A.pdf"))
    r = ech0196.read(tmp / "bill_qrr.pdf", S)
    assert r.status == "needs_ai_read" and not r.facts, r.status
    if not pdfs:
        print("SKIP eCH-0196 fast path: no real PDF in work/pdf/ (generate with `make data`); fallback signal ok")
        return None
    pdf = pdfs[0]
    r = ech0196.read(pdf, S)
    assert r.status == "ok" and r.document.read_path == "barcode" and r.document.kind == ech0196.KIND, r.message
    assert not r.data["warnings"], r.data["warnings"]
    truth = ROOT / "work" / "xml" / f"{pdf.stem.split('-')[0]}.xml"
    if truth.exists():                      # generator source XML: independent of the barcode path
        root = ET.parse(truth).getroot()
        inst = ech0196.slug(root.find("{*}institution").get("name"))
        facts = {f.key: f.value for f in r.facts}
        for attr, key in ech0196.TOTALS.items():
            assert facts[f"tax.statement.{key}.{inst}"] == float(root.get(attr)), key
        assert r.document.year == int(root.get("taxPeriod"))
        sec = root.find("{*}listOfSecurities")
        assert facts["tax.securities.withholding_tax_total"] == float(sec.get("totalWithHoldingTaxClaim"))
        assert facts["tax.period"] == root.get("taxPeriod")
        n_sec = len(root.findall(".//{*}security"))
        assert sum(k.startswith("tax.securities.tax_value.") for k in facts) == n_sec
    b = next(iter(sorted((ROOT / "work" / "pdf").glob("*-B.pdf"))), None)
    if b:
        assert ech0196.read(b, S).status == "needs_ai_read"          # layout B carries no barcode
    print(f"ok  eCH-0196: {pdf.name} read by barcode ({len(r.facts)} facts), totals equal to the source XML; fallback signalled")
    return pdf


def check_ofsp(tmp):
    head = ("Versicherer,Kanton,Hoheitsgebiet,Geschäftsjahr,Erhebungsjahr,Region,Altersklasse,Unfalleinschluss,"
            "Tarif,Tariftyp,Altersuntergruppe,Franchisestufe,Franchise,Prämie,isBaseP,isBaseF,Tarifbezeichnung")
    rows = [("1", "BASE", "B1", "01", "E_0300", "400.0"), ("1", "BASE", "B1", "06", "E_2500", "300.0"),
            ("2", "HAM", "H1", "01", "E_0300", "380.0"), ("2", "HAM", "H1", "06", "E_2500", "310.0")]
    lines = [head] + [f"{i},VD,P_OKPCH,2027,2026,PR_REG_1,AKA_03_ERW,OHN_UNF,{t},{m},E1,FRASTU_{s},FRA_{s}_{f},{p},0,0,X"
                      for i, m, t, s, f, p in rows]
    lines.append("1,VD,P_OKPCH,2027,2026,PR_REG_1,AKA_01_KIN,OHN_UNF,B1,BASE,K1,FRASTU_01,FRA_01_K_0000,100.0,0,0,X")
    lines.append("1,GE,P_OKPCH,2027,2026,PR_REG_0,AKA_03_ERW,OHN_UNF,B1,BASE,E1,FRASTU_01,FRA_01_E_0300,450.0,0,0,X")
    (tmp / "premiums.csv").write_text("﻿" + "\n".join(lines) + "\n", encoding="utf-8")
    data = ofsp_premiums.load(tmp / "premiums.csv", canton="VD")
    assert len(data) == 5 and data[0]["deductible"] == 300 and data[0]["region"] == 1 and data[0]["age"] == "adult"

    ac = ofsp_premiums.annual_cost
    assert ac(400, 300, 0) == 4800 and ac(400, 300, 1300) == 4800 + 300 + 100
    assert ac(400, 300, 20000) == 4800 + 300 + 700                       # co-pay cap, adults (OAMal 103 al. 2)
    assert ac(100, 0, 10000, "child") == 1200 + 350                      # co-pay cap, children
    offers = ofsp_premiums.compare(data, "VD", 1, "adult", expected_costs=0)
    assert [(o["insurer"], o["deductible"]) for o in offers][:2] == [("1", 2500), ("2", 2500)]
    offers = ofsp_premiums.compare(data, "VD", 1, "adult", expected_costs=5000)
    assert (offers[0]["insurer"], offers[0]["deductible"]) == ("2", 300) and offers[0]["total"] == 4560 + 300 + 470
    t = ofsp_premiums.deductible_table([o for o in offers if o["insurer"] == "1"], 1000)
    be = t["break_even"][0]["lower_is_cheaper_above"]                     # 12 x 100 = 0.9 x (C - 300)
    assert abs(be - (300 + 1200 / 0.9)) < 0.01 and t["best"]["deductible"] == 2500
    assert ofsp_premiums.break_even(400, 300, 400, 2500) == 0.0           # no premium saving: low deductible wins
    assert abs(ofsp_premiums.break_even(400, 300, 399.99, 2500) - (300 + 0.12 / 0.9)) < 0.01
    extra = ""
    real = ofsp_premiums.WORK / "Prämien_CH.csv"
    if real.exists():
        o = ofsp_premiums.compare(ofsp_premiums.load(real, "VD"), "VD", 1, "adult", expected_costs=1000)
        assert o and all(a["total"] <= b["total"] for a, b in zip(o, o[1:]))
        extra = f"; real {o[0]['year']} data: {len(o)} VD offers, cheapest {o[0]['total']:.0f} CHF/year at 1000 CHF costs"
    print(f"ok  ofsp: fixture comparator, caps 700/350, break-even {be:.2f} CHF{extra}")


def check_drafts(tmp):
    a = Action(id="act_selfcheck_bank", case_id="case_x", kind="email_draft", payload={
        "template": "bank_document_request", "to": "Service clientèle <service@banque.example>",
        "from": "Élodie Rey <elodie@example.ch>",
        "vars": {"year": 2025, "client_number": "789353796", "sender_name": "Élodie Rey",
                 "sender_address": "Rue du Test 1, 1950 Sion", "recipient_name": "Velfeld Banque SA", "place": "Sion"}})
    out = email_drafts.draft(a, tmp / "drafts")
    msg = email.message_from_bytes(Path(out["eml"]).read_bytes(), policy=policy.default)
    assert msg["X-Unsent"] == "1" and msg["Subject"] == "Demande du relevé fiscal électronique 2025 (eCH-0196)"
    assert msg["To"].addresses[0].addr_spec == "service@banque.example" and msg["From"].addresses[0].display_name == "Élodie Rey"
    assert parsedate_to_datetime(msg["Date"]) and msg["Message-ID"].startswith("<") and msg.defects == []
    assert "789353796" in msg.get_content() and out["missing"] == [] and out["sent"] is False
    assert Path(out["pdf"]).read_bytes()[:5] == b"%PDF-" and "Sion, le" in Path(out["txt"]).read_text()
    lp = email_drafts.draft(Action(id="act_selfcheck_lp", case_id="case_y", kind="letter", payload={
        "template": "lp_opposition", "vars": {"number": "2026/1234", "creditor": "Exemple SA",
                                              "sender_name": "Élodie Rey", "contested_amount": "350.00"}}),
        tmp / "drafts")
    text = Path(lp["txt"]).read_text()
    assert lp["missing"] == ["notified_on"] and "[à compléter : notified_on]" in text and "opposition partielle" in text
    lamal = email_drafts.draft(Action(id="act_selfcheck_lamal", case_id="case_z", kind="email_draft", payload={
        "template": "lamal_termination", "to": "info@assureur.example",
        "vars": {"policy_number": "756.0000.0000.00", "end_date": "31.12.2026", "sender_name": "Élodie Rey"}}),
        tmp / "drafts")
    assert not lamal["missing"] and "art. 7" in Path(lamal["txt"]).read_text()
    assert "smtplib" not in Path(email_drafts.__file__).read_text()
    print("ok  email_drafts: 3 drafts (.eml parsed back without defects, .txt, .pdf), missing fields flagged")


def _frames(pages, seq, rng):
    """Handheld-like frames: per page a few jittered views (one sharp), two blurred frames per page turn."""
    def view(p, blur, dx, dy, rot):
        w, h = p.size
        c = Image.new("RGB", (w + 80, h + 80), (90, 80, 70))
        c.paste(p.rotate(rot, fillcolor=(90, 80, 70)), (40 + dx, 40 + dy))
        return c.filter(ImageFilter.GaussianBlur(blur)) if blur else c
    frames, truth = [], []
    for k, pi in enumerate(seq):
        n = rng.randint(3, 5)
        sharp = rng.randrange(n)
        for j in range(n):
            frames.append(view(pages[pi], 0 if j == sharp else rng.uniform(1, 3), rng.randint(-3, 3),
                               rng.randint(-3, 3), rng.uniform(-0.2, 0.2)))
            truth.append((pi, j == sharp))
        if k < len(seq) - 1:
            for a in (0.3, 0.7):
                frames.append(Image.blend(view(pages[pi], 5, 30, -20, 3), view(pages[seq[k + 1]], 5, -30, 20, -3), a))
                truth.append(("turn", False))
    return frames, truth


def check_inbox_and_video(tmp, ech_pdf):
    box = tmp / "inbox"
    box.mkdir()
    for f in ("bill_qrr.pdf", "bill_scor.png", "camt053.xml"):
        shutil.copy(tmp / f, box / f)
    shutil.copy(tmp / "bill_qrr.pdf", box / "bill_qrr (copy).pdf")
    (box / "notes.txt").write_text("hello")
    if ech_pdf:
        shutil.copy(ech_pdf, box / ech_pdf.name)
    res = {Path(r.document.path).name: r for r in inbox.scan(box, S, settle=0)}
    assert [n for n, r in res.items() if r.status == "duplicate"] == ["bill_qrr.pdf"]   # "(copy)" sorts first
    assert res["bill_qrr (copy).pdf"].document.kind == qrbill.KIND and res["bill_scor.png"].status == "ok"
    assert res["camt053.xml"].document.kind == "bank_statement_camt053" and res["notes.txt"].status == "unsupported"
    if ech_pdf:
        assert res[ech_pdf.name].document.kind == ech0196.KIND
    seen = {r.document.sha256 for r in res.values()}
    assert inbox.import_file(box / "bill_scor.png", S, seen=seen)[0].status == "duplicate"   # share of a known file

    which = shutil.which
    shutil.which = lambda _: None                                     # simulate a machine without ffmpeg
    try:
        assert inbox.import_video(tmp / "bill_scor.png", S)[0].status == "skipped"
    finally:
        shutil.which = which

    rng = random.Random(7)
    pdf = pdfium.PdfDocument(str(tmp / "bill_qrr.pdf"))
    bill_page = pdf[0].render(scale=2).to_pil().convert("RGB")
    pdf.close()
    pages = [bill_page]
    if ech_pdf:
        pdf = pdfium.PdfDocument(str(ech_pdf))
        pages += [pdf[i].render(scale=1.2).to_pil().convert("RGB").resize(bill_page.size) for i in (0, 1)]
        pdf.close()
    else:
        pages += [Image.new("RGB", bill_page.size, "white"), Image.effect_noise(bill_page.size, 60).convert("RGB")]
    frames, truth = _frames(pages, [0, 1, 2, 0], rng)
    picked = inbox.pick_pages(frames)
    got = [truth[p["index"]] for p in picked]
    assert {g[0] for g in got} == {0, 1, 2} and all(g[1] for g in got), got   # every page, its sharpest frame
    msg = f"{len(frames)} frames -> {len(picked)} pages"

    if shutil.which("ffmpeg"):
        fdir = tmp / "frames"
        fdir.mkdir()
        for i, f in enumerate(frames):
            f.save(fdir / f"f{i:03d}.png")
        video = box / "scan.mp4"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-framerate", "4", "-i", str(fdir / "f%03d.png"), "-vf",
                        "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
                        str(video)], check=True)
        out = inbox.import_file(video, S, seen=set(), pages_dir=tmp / "pages")
        assert out[0].document.kind == "video_capture" and out[0].status == "ok", out[0].message
        bills = [r for r in out[1:] if r.status == "ok"]
        assert len(bills) == 1 and bills[0].data["bills"][0]["reference"] == QRR, [(r.status, r.message) for r in out]
        assert all(r.status in ("needs_ai_read", "duplicate") for r in out[1:] if r not in bills)
        msg += f"; ffmpeg mp4 -> {out[0].message}, QR read once"
    else:
        msg += "; SKIP ffmpeg video round trip (ffmpeg not installed)"
    print(f"ok  inbox: sha256 dedupe, type routing, share import; video: {msg}")


def main():
    with tempfile.TemporaryDirectory(prefix="ordner_connectors_") as d:
        tmp = Path(d)
        bills = check_qrbill(tmp)
        check_camt(tmp, bills)
        ech_pdf = check_ech0196(tmp)
        check_ofsp(tmp)
        check_drafts(tmp)
        check_inbox_and_video(tmp, ech_pdf)
    print("connectors selfcheck: all assertions passed")


if __name__ == "__main__":
    main()
