"""python -m ordner.tools.selfcheck  (replay mode, no model loaded; uses W1/W2/W3/W6 when importable, else checks that
the tool reports the missing module clearly). The dossier is the fictional demo persona in a temporary database."""
import importlib
import json
import re
import tempfile
from pathlib import Path

import numpy as np
import zxingcpp
from PIL import Image

from ordner.core.schema import Action, new_id

from .base import ROOT
from .document import jsonl
from .registry import SPECS, call, openai_tools

PDF = "work/pdf/s0000-A.pdf"
QR_BILL = "\n".join(["SPC", "0200", "1", "CH4431999123000889012", "S", "Robert Schneider AG", "Rue du Lac", "1268",
                     "2501", "Biel", "CH", *[""] * 7, "199.95", "CHF", "S", "Pia-Maria Rutschmann-Schnyder",
                     "Grosse Marktgasse", "28", "9400", "Rorschach", "CH", "QRR", "210000000003139471430009017",
                     "Order of 15.06.2020", "EPD"])  # example values of the SIX implementation guidelines


def available(module):
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        return False


def ok(name, args, ctx):
    r = call(name, args, ctx)
    assert {"ok", "data", "warnings", "provenance"} <= set(r) and r["ok"], (name, r)
    json.dumps(r)
    return r


def refused(name, args, ctx, needle):
    r = call(name, args, ctx)
    assert not r["ok"] and needle in r["error"], (name, r)
    return r


def check_registry():
    names = [s.name for s in SPECS]
    assert len(names) == len(set(names)) == 11, names
    for t in openai_tools():
        assert re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", t["function"]["name"]) and t["function"]["parameters"]["type"] == "object"
    assert not any(s.side_effect for s in SPECS), "no tool may execute an external effect"
    refused("nope", {}, {}, "unknown tool")
    refused("knowledge_search", {"query": 3, "x": 1}, {}, "query must be string")  # OpenAI alias + validation
    refused("decision.score", {"questions": [{"id": "q"}]}, {}, "missing questions[0].type")
    print(f"registry ok: {len(SPECS)} tools, OpenAI format, argument validation")


def check_document(ctx, tmp):
    r = ok("document.read", {"doc": PDF, "pages": [1]}, ctx)
    assert r["provenance"]["source"] == "pdf_text_layer" and "Velfeld Banque SA" in r["data"]["pages"][0]["text"]
    r = ok("document.read", {"doc": PDF, "method": "ocr", "max_chars": 500}, ctx)
    assert r["provenance"]["source"] == "replay_ocr_cache" and r["data"]["pages"][0]["page_id"].startswith("s0000-A")
    assert len(r["data"]["pages"][0]["text"]) == 500 and any("truncated" in w for w in r["warnings"])
    refused("document.read", {"doc": "nowhere.pdf"}, ctx, "unknown document")

    gold = next(d["oracle"] for d in jsonl(ROOT / "work/docs.jsonl") if d["doc_id"] == "s0000-A")
    got = ok("document.decode", {"doc": PDF}, ctx)["data"]["ech0196"]["fields"]
    assert got == {k: gold[k] for k in got}, (got, gold)

    if available("ordner.connectors.qrbill"):
        img = tmp / "bill.png"
        Image.fromarray(np.asarray(zxingcpp.create_barcode(QR_BILL, zxingcpp.BarcodeFormat.QRCode).to_image(scale=6))).save(img)
        bill = ok("document.decode", {"doc": str(img)}, {})["data"]["qr_bill"]  # no dossier session: any file
        assert bill["iban_valid"] and bill["qr_iban"] and bill["amount"] == "199.95" and not bill["errors"], bill
        Image.fromarray(np.asarray(zxingcpp.create_barcode(QR_BILL.replace("889012", "889013"),
                                                           zxingcpp.BarcodeFormat.QRCode).to_image(scale=6))).save(img)
        r = ok("document.decode", {"doc": str(img)}, {})
        assert not r["data"]["qr_bill"]["iban_valid"] and any("IBAN" in w for w in r["warnings"])
    else:
        refused("document.decode", {"doc": "work/png/s0000-A-p1-d1.png"}, ctx, "not available")
    print("document ok: text layer, replay OCR, eCH-0196 barcode = oracle, QR-bill parsed and validated")


def check_knowledge(ctx):
    hits = ok("knowledge.search", {"query": "Rückerstattung der Verrechnungssteuer", "lang": "de"}, ctx)["data"]["passages"]
    assert hits and all(h["lang"] == "de" and h["url"].startswith("https://") for h in hits)
    assert any("Verrechnungssteuer" in h["text"] for h in hits)
    hits = ok("knowledge.search", {"query": "valeur fiscale des titres", "canton": "TI", "k": 8}, ctx)["data"]["passages"]
    assert hits and {h["jurisdiction"] for h in hits} <= {"CH", "TI"}
    # retrieval sanity on the procedure cards' own verified sources (demo subject: canton VD -> VD + federal, French)
    vd = {} if ctx.get("subject_id") else {"canton": "VD", "lang": "fr"}
    top = lambda q: ok("knowledge.search", {"query": q, **vd}, ctx)["data"]["passages"][0]
    h = top("délai de dépôt de la déclaration d'impôt")
    assert "vd.ch" in h["url"] and h["card_id"] == "tax.return.VD", h
    h = top("délai pour former opposition au commandement de payer")
    assert "art. 74" in h["title"] and h["card_id"] == "debt.payment_order.opposition", h
    h = top("changer de caisse maladie pour l'an prochain")
    assert "bag.admin.ch" in h["url"] or ("LAMal" in h["title"] and "art. 7," in h["title"]), h
    print("knowledge ok: BM25 over the official corpus + card sources, language and canton filters, urls, "
          "VD deadline / LP art. 74 / LAMal change found")


def check_decision(ctx):
    qs = [{"id": "kind", "type": "doc_type"},
          {"id": "wht", "type": "yes_no", "question": "Is 179.36 the withholding tax claim?", "value": "179.36"},
          {"id": "free", "type": "yes_no", "question": "Is the client married?"}]
    r = ok("decision.score", {"doc": "s0000-A-p1-d1", "questions": qs}, ctx)
    a = r["data"]["answers"]
    assert a["kind"]["answer"] == "swiss_tax_statement_eCH0196" and a["kind"]["source"].startswith("replay: d1-3B")
    assert a["wht"]["answer"] == "yes" and a["wht"]["source"].startswith("heuristic")
    assert a["free"]["answer"] == "unknown" and r["warnings"]
    refused("decision.score", {"text": "x", "questions": [{"id": "c", "type": "choice", "question": "?"}]}, ctx,
            "at least 2")
    print("decision ok: cached d1 routing, heuristics labelled as such, unknown when nothing supports an answer")


def check_expert(ctx):
    r = ok("expert.run", {"process": "tax_statement_extraction", "doc": PDF}, ctx)
    assert r["provenance"]["source"] == "replay" and r["provenance"]["model"].startswith("apertus")
    assert r["data"]["fields"]["institution"] == "Velfeld Banque SA" and set(r["data"]["checks"]) == set(r["data"]["fields"])
    r = ok("expert.run", {"process": "tax_statement_extraction", "text": "Relevé fiscal\nCanton VS"}, ctx)
    assert r["provenance"]["source"] == "regex_baseline" and any("not from Apertus" in w for w in r["warnings"])
    assert "totalTaxValue" in r["data"]["to_verify"]
    refused("expert.run", {"process": "tax_statement_extraction", "text": "x"}, {**ctx, "mode": "live"}, "llm_url")
    print("expert ok: replayed Apertus extraction with consistency checks, labelled rule-based fallback")


def check_rules_case(ctx, tmp):
    if not available("ordner.rules"):
        refused("schedule.plan", {"due": "2027-03-31"}, ctx, "not available")
        print("rules: ordner.rules missing, clear error checked")
        return
    p = ok("schedule.plan", {"due": "2027-03-31"}, ctx)["data"]
    assert p["days_left"] == 39 and not p["overdue"] and p["next_resume"] == "2027-03-01", p
    assert ok("schedule.plan", {"due": "2027-01-31"}, ctx)["warnings"]
    if ctx.get("store") is None:
        refused("case.load", {"subject_id": "x"}, ctx, "not available")
        print("case: ordner.case missing, clear error checked")
        return
    st, sid = ctx["store"], ctx["subject_id"]
    snap = ok("case.load", {"subject_id": "someone_else"}, ctx)["data"]  # forced to the session's dossier
    assert snap["subject"]["id"] == sid
    doc = next(d for d in snap["documents"] if d["read_path"] == "barcode" and d["path"].endswith(".pdf"))
    assert ok("document.decode", {"doc": doc["id"]}, ctx)["data"]["ech0196"]["fields"]["institution"] == doc["issuer"]
    refused("document.read", {"doc": str(Path.home() / ".ssh" / "id_rsa.pdf")}, ctx, "unknown document")
    outside = tmp / "outside.pdf"
    outside.write_bytes((ROOT / PDF).read_bytes())
    refused("document.read", {"doc": str(outside)}, ctx, "only dossier documents")
    placeholder = next(d for d in snap["documents"] if d["path"].startswith("placeholder:"))
    assert ok("document.read", {"doc": placeholder["id"]}, ctx)["data"]["recorded"]["fields"] == placeholder["fields"]

    if available("ordner.procedures.catalog"):
        r = ok("rules.evaluate", {"card_id": "tax.return.ZH", "subject_id": sid, "period": "2025"}, ctx)["data"]
        assert r["status"] == "not_applicable" and r["sources"]  # Noa lives in VD
        assert r["evaluated_on"] == ctx["today"]  # scenario date, not the machine clock
        refused("rules.evaluate", {"card_id": "tax.return.XX", "subject_id": sid}, ctx, "unknown procedure card")
        r = ok("dossier.check", {"subject_id": sid, "period": "2025", "card_id": "tax.return.VD"}, ctx)
        c, t = r["data"]["completeness"], r["data"]["consolidation"]
        assert c["status"] == "incomplete" and [d["issuer"] for d in c["missing_documents"]] == ["Talbruck Banque Privée SA"]
        assert t["status"] != "final" and "Talbruck Banque Privée SA" in t["institutions_missing"]
        assert any("Talbruck" in w for w in r["warnings"])
        r = ok("dossier.check", {"subject_id": sid, "period": "2025"}, ctx)["data"]
        assert r["completeness"] is None and r["consolidation"]["totals"]["total_tax_value"]["total"]

    rec = lambda op, **p: call("case.record", {"subject_id": sid, "op": op, **p}, ctx)
    case_id = rec("open_case", card_id="tax.return.ZH", period="2025")["data"]["recorded"]["id"]
    fact = rec("propose_fact", key="tax.period", value="2025")["data"]["recorded"]
    assert fact["status"] == "proposed" and fact["actor"] == "model"
    assert "reserved to the person" in rec("confirm_fact", fact_id=fact["id"])["error"]
    assert "set_state needs: state" in rec("set_state", case_id=case_id)["error"]
    assert "must be one of" in rec("set_state", case_id=case_id, state="done")["error"]
    for state in ("ready_to_prepare", "ready_to_validate", "action_engaged"):
        assert rec("set_state", case_id=case_id, state=state)["ok"]
    assert rec("add_deadline", case_id=case_id, due="2026-03-31", rule_id="fixed_date")["ok"]

    a = st.add_action(Action(new_id("act"), case_id, "form_entry", {"summary": "tax return"}))  # as the coordinator does
    v = ok("receipt.verify", {"action_id": a.id, "case_id": case_id}, ctx)["data"]
    assert v["status"] == "unknown" and v["action_status"] == "prepared"
    assert "no recorded proof" in rec("set_state", case_id=case_id, state="result_verified")["error"]
    st.update_action(a.id, "validated", actor="user")
    st.update_action(a.id, "done_by_user", actor="user")
    r = ok("receipt.verify", {"action_id": a.id}, ctx)
    assert r["data"]["status"] == "unknown" and any("marked it done" in w for w in r["warnings"])
    st.update_action(a.id, "verified", actor="connector")  # e.g. camt.053 debit matched
    v = ok("receipt.verify", {"action_id": a.id}, ctx)["data"]
    assert v["status"] == "established" and v["proof"][0]["actor"] == "connector"
    assert rec("set_state", case_id=case_id, state="result_verified")["ok"]
    refused("receipt.verify", {"action_id": "act_nope"}, ctx, "no action")
    print("rules/case ok: schedule, dated applicability, completeness + consolidation, dossier writes, person-only "
          "confirmation, proof before verified")


def main():
    tmp = Path(tempfile.mkdtemp(prefix="ordner_tools_"))
    ctx = {"mode": "replay", "today": "2027-02-20"}
    if available("ordner.case"):
        from ordner.case import Store
        from ordner.case.demo_seed import seed

        ctx["store"] = Store(tmp / "ordner.db")
        ctx["subject_id"] = seed(ctx["store"])
    check_registry()
    check_document(ctx, tmp)
    check_knowledge(ctx)
    check_decision(ctx)
    check_expert(ctx)
    check_rules_case(ctx, tmp)
    print("tools self-check ok")


if __name__ == "__main__":
    main()
