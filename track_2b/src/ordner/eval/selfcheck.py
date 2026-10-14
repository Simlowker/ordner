"""python -m ordner.eval.selfcheck  (asserts on synthetic fixtures written to work/fixtures/; real-size item counts)"""

import json
import shutil
import time
from pathlib import Path

import numpy as np

from . import build_items, probe, regex_baseline, rules, run
from .metrics import FIELDS, NUMERIC_FIELDS, auroc

LAYERS = [4, 8, 12, 16, 20, 24, 28, 32]
PLANTED_LAYER = 16

FR_A = """1962258356001002

# Velfeld Banque SA

créé avec OpenSteuerauszug

## Relevé fiscal en CHF 31.12.2025

<table>
  <tr>
    <th>Valeur fiscale de valeurs A et B au 31.12.2025</th>
    <th>A</th>
    <th>Revenu brut 2025 valeurs avec IA-déduction</th>
    <th>B</th>
    <th>Revenu brut 2025 valeurs sans IA-déduction</th>
    <th>Retenue à la source</th>
  </tr>
  <tr>
    <td>67'443 (1)</td><td></td><td>512</td><td></td><td>862</td><td>179.36</td>
  </tr>
  <tr>
    <th>Total valeur fiscale de valeurs A, B, DA-1 et USA au 31.12.2025</th>
    <td>67'443</td>
    <th>Total revenu brut 2025 valeurs A avec IA-déduction</th>
    <td>512</td>
    <th>Total revenu brut 2025 valeurs B, DA-1 et USA sans IA-déduction</th>
    <td>862</td>
    <th>Total revenu brut 2025 valeurs A, B, DA-1 et USA</th>
    <td>1'375</td>
  </tr>
</table>

**Client** Élodie Rey
**Période du** 01.01.2025 - 31.12.2025
**Canton** VS
(1) Dont A 31'655 et B 35'788
"""
DE_A = """# Selmira Vermögensbank AG
<table>
  <tr><th>Steuерwert der A- und B-Werte am 31.12.2025</th><th>Bruttoertrag 2025 Werte mit VSt.-Abzug</th>
  <th>Bruttoertrag 2025 Werte ohne VSt.-Abzug</th><th>Verrechnungs- steueranspruch</th></tr>
  <tr><td>A</td><td>B</td><td></td><td></td></tr>
  <tr><td>130’710<sup>(1)</sup></td><td>73</td><td>1'014</td><td>25.70</td></tr>
  <tr><td>Total Steuewert der A, B, DA-1 und USA-Werte am 31.12.2025</td><td>Total Bruttoertrag 2025 A-Werte mit VSt.-Abzug</td>
  <td>Total Bruttoertrag 2025 B, DA-1 und USA-Werte ohne VSt.-Abzug</td><td>Total Bruttoertrag 2025 A, B, DA-1 und USA-Werte</td></tr>
  <tr><td>130'710</td><td>73</td><td>1'014</td><td>1'088</td></tr>
</table>
Kunde: Reto Steiner
Periode: 01.01.2025 - 31.12.2025
Danton von: 04.02.2026
GR
"""
IT_B = """Quinmira Banca Privata SA
Attestato fiscale 2025
Titolare Giulia Galli Periodo 01.01.2025 – 31.12.2025
Cantone di domicilio TI
Redditi soggetti all'imposta preventiva (A) 27.02
Imposta preventiva rimborsabile 35 % 9.46
Redditi non soggetti all'imposta preventiva (B) 563.65
Averi in conto (3 conti) 1’000.00
Titoli (1 posizioni) 104’132.99
Valore fiscale totale 105’132.99
"""


def check_regex():
    f = regex_baseline.extract(FR_A)
    assert f == {"totalTaxValue": "67443", "totalGrossRevenueA": "512", "totalGrossRevenueB": "862",
                 "totalWithHoldingTaxClaim": "179.36", "institution": "Velfeld Banque SA", "canton": "VS",
                 "taxPeriod": "2025", "client_last_name": "Rey"}, f
    f = regex_baseline.extract(DE_A)
    assert f == {"totalTaxValue": "130710", "totalGrossRevenueA": "73", "totalGrossRevenueB": "1014",
                 "totalWithHoldingTaxClaim": "25.70", "institution": "Selmira Vermögensbank AG", "canton": "GR",
                 "taxPeriod": "2025", "client_last_name": "Steiner"}, f
    f = regex_baseline.extract(IT_B)  # layout-B wording is unknown to the rules (only layout A + generic knowledge)
    assert f["totalGrossRevenueA"] is None and f["totalGrossRevenueB"] is None and f["totalWithHoldingTaxClaim"] is None, f
    for t in (FR_A, DE_A):
        r = rules.check(regex_baseline.extract(t), t)
        assert all(r.values()), r
    bad = rules.check({**regex_baseline.extract(FR_A), "totalTaxValue": "67444", "client_last_name": "Roy"}, FR_A)
    assert bad["totalTaxValue"] is False and bad["client_last_name"] is False and bad["canton"] is True


def make_fixtures(root, n_stmt=600, hidden=64, seed=0):
    """Synthetic docs/pages/extract/d1/acts with the real split design (test: layouts A, B at levels 0-3, C at 0 and 2).
    Planted doubt signals: ent_mean (strong), lp_mean and ent_first (pure noise), probe position A at layer 16
    (strong), position B (noise). Every 97th apertus-base page is a failed extraction (`error`, empty fields); on every
    50th page its canton has no value span (no doubt features, no activations); its withholding claim errs more often."""
    rng = np.random.default_rng(seed)
    root = Path(root)
    shutil.rmtree(root, ignore_errors=True)
    (root / "acts" / "apertus-base").mkdir(parents=True)
    order = rng.permutation(n_stmt)
    split = {int(i): "test" if r < 0.2 * n_stmt else "dev" if r < 0.3 * n_stmt else "train" for r, i in enumerate(order)}
    docs, pages = [], []
    for i in range(n_stmt):
        sid = f"s{i:04d}"
        a = round(float(rng.uniform(0, 2000)), 2)
        vals = {"totalTaxValue": round(float(rng.uniform(1e3, 2e5)), 2), "totalGrossRevenueA": a,
                "totalGrossRevenueB": round(float(rng.uniform(0, 2000)), 2), "totalWithHoldingTaxClaim": round(0.35 * a, 3)}
        text = {"institution": f"Bank {i} AG", "canton": str(rng.choice(["ZH", "VD", "TI"])), "taxPeriod": "2025",
                "client_last_name": f"Name{i}"}
        lang = str(rng.choice(["de", "fr", "it"]))
        for layout in (["A", "B", "C"] if split[i] == "test" else ["A"]):
            prec = {k: (2 if layout != "A" or k == "totalWithHoldingTaxClaim" else 0) for k in NUMERIC_FIELDS}
            doc_id = f"{sid}-{layout}"
            docs.append({"doc_id": doc_id, "stmt_id": sid, "split": split[i], "layout": layout, "language": lang,
                         "oracle": {**{k: str(v) for k, v in vals.items()}, **text},
                         "oracle_page": {k: f"{vals[k]:.{prec[k]}f}" for k in NUMERIC_FIELDS}})
            levels = [0, 2] if layout == "C" else [0, 1, 2, 3] if split[i] == "test" else [int(rng.integers(0, 4))]
            for lvl in levels:
                pages.append({"page_id": f"{doc_id}-p1-d{lvl}", "doc_id": doc_id, "stmt_id": sid, "split": split[i],
                              "layout": layout, "page_no": 1, "png_path": "", "degradation": lvl})
    dump = lambda name, rows: (root / name).write_text("".join(json.dumps(r) + "\n" for r in rows))  # noqa: E731
    dump("docs.jsonl", docs)
    dump("pages.jsonl", pages)
    dump("ocr.0of1.jsonl", [{"page_id": p["page_id"], "model": "fixture", "text": None, "seconds": 2.0} for p in pages])
    gold = {d["doc_id"]: {**{k: d["oracle"][k] for k in FIELDS[4:]}, **d["oracle_page"]} for d in docs}
    err = {"regex": (0.03, 0.04, 0.5), "apertus-base": (0.05, 0.05, 0.1), "apertus-lora": (0.02, 0.02, 0.05)}
    truth = {}
    for system, (e0, e_lvl, e_b) in err.items():
        ext, d1 = [], []
        for n, p in enumerate(pages):
            g = gold[p["doc_id"]]
            fields, doubt, acts = {}, {}, {}
            for f in FIELDS:
                field_effect = 0.15 if system == "apertus-base" and f == "totalWithHoldingTaxClaim" else 0
                wrong = rng.random() < e0 + e_lvl * p["degradation"] + (e_b if p["layout"] != "A" else 0) + field_effect
                truth[(system, p["page_id"], f)] = wrong
                v = g[f]
                if f in NUMERIC_FIELDS:
                    fields[f] = float(v) + 1 if wrong else (v if system == "regex" else float(v))
                else:
                    fields[f] = f"{v}x" if wrong else v
                doubt[f] = {"lp_min": -float(0.5 * wrong + abs(rng.normal(0, 0.5))), "lp_mean": float(rng.normal()),
                            "ent_mean": float(wrong + rng.normal(0, 0.1)), "ent_first": float(rng.normal())}
                d1.append({"page_id": p["page_id"], "field": f, "seconds": 0.5,
                           "p_yes": float(1 / (1 + np.exp(-(2 - 2 * wrong + rng.normal()))))})
                if system == "apertus-base":
                    xa = rng.normal(size=(len(LAYERS), hidden))
                    xa[LAYERS.index(PLANTED_LAYER), :4] += 1.5 * wrong
                    acts[f"{f}_A"] = xa.astype(np.float16)
                    acts[f"{f}_B"] = rng.normal(size=(len(LAYERS), hidden)).astype(np.float16)
            row = {"page_id": p["page_id"], "model": system, "fields": fields, "raw": None,
                   "doubt": None if system == "regex" else doubt, "seconds": 1.0,
                   **({"seconds_hidden": 0.25} if system == "apertus-base" else {})}
            if system == "apertus-base" and n % 50 == 1:
                del doubt["canton"], acts["canton_A"], acts["canton_B"]
            if system == "apertus-base" and n % 97 == 0:
                row.update(fields={}, doubt=None, error="generation failed")
                truth.update({(system, p["page_id"], f): True for f in FIELDS})
                acts = {}
            ext.append(row)
            if acts:
                np.savez(root / "acts" / "apertus-base" / f"{p['page_id']}.npz", layers=np.array(LAYERS), **acts)
        dump(f"extract.{system}.jsonl", ext)
        if system != "regex":
            dump(f"d1.{system}.jsonl", d1)
    return pages, truth


def main():
    check_regex()
    root = Path("work/fixtures")
    pages, truth = make_fixtures(root)
    data = root / "data"
    items = build_items.build(root, data)
    assert len(items) == len(pages) * len(FIELDS) * 3, (len(items), len(pages))
    assert all(it["correct"] == (not truth[(it["system"], it["page_id"], it["field"])]) for it in items)

    (data / "explain_eval.json").write_text(json.dumps({"generator": "fixture", "n_pages": 3, "rows": []}))
    cost = json.loads((data / "costs.json").read_text())["stages"]
    assert cost["apertus-base"] == {"n_pages": len(pages), "mean": 1.0, "median": 1.0, "p95": 1.0}, cost
    assert cost["d1 (apertus-base)"]["mean"] == 0.5 and cost["apertus-base hidden-state pass"]["mean"] == 0.25, cost
    assert [cost[f"total {s}"]["mean"] for s in ("regex", "apertus-base", "apertus-lora")] == [3.0, 3.75, 3.5], cost
    assert cost["total apertus-base"]["n_pages"] == len(pages), cost

    sel = probe.run(root, data)
    assert sel["A"]["layer"] == PLANTED_LAYER, sel

    # bootstrap AUROC == sklearn AUROC on the explicitly resampled items (ties included)
    rng = np.random.default_rng(1)
    y, s, cl = rng.random(500) < 0.3, rng.normal(size=500).round(1), rng.integers(0, 50, 500).astype(str)
    b = run.Boot(cl, n=4)
    b.W[0] = 1
    fast = b.auroc(cl, y, s)
    for i in range(4):
        rep = b.W[i, b.idx(cl)].astype(int)
        assert np.isclose(fast[i], auroc(np.repeat(y, rep), np.repeat(s, rep))), i

    t = time.time()
    res = run.main(["--data", str(data)])
    runtime = time.time() - t
    d = res["doubt"]["apertus-base"]
    assert d["mean entropy"]["auroc"] > 0.95, d["mean entropy"]
    assert 0.4 < d["mean token prob"]["auroc"] < 0.6 and 0.4 < d["first-token entropy"]["auroc"] < 0.6
    assert d["probe A"]["auroc"] > 0.85 and res["h3"]["supported"], d["probe A"]
    assert 0.4 < d["probe B"]["auroc"] < 0.6, d["probe B"]
    assert d["combined"]["auroc"] >= max(v["auroc"] for k, v in d.items() if k != "combined" and not k.startswith("_")) - 0.02
    assert res["position_b_vs_a"]["ci"][1] < 0
    acc = res["accuracy"]
    for s in ("regex", "apertus-base", "apertus-lora"):
        m = [not truth[(s, p["page_id"], f)] for p in pages if p["split"] == "test" for f in FIELDS]
        assert abs(acc[s]["acc"] - np.mean(m)) < 1e-9 and acc[s]["ci"][0] < acc[s]["acc"] < acc[s]["ci"][1]
    assert res["h1"]["supported"] and res["h1"]["diff"] > 0
    assert res["breakdown"]["regex"]["layout"]["B"]["acc"] < res["breakdown"]["regex"]["layout"]["A"]["acc"]
    assert res["costs"]["stages"]["apertus-lora"]["n_pages"] == len(pages)
    assert res["explain"]["n_pages"] == 3
    failed_test = sum(p["split"] == "test" for n, p in enumerate(pages) if n % 97 == 0)
    assert res["n_error_pages"]["apertus-base"]["test"] == failed_test > 0, res["n_error_pages"]
    for s in ("regex", "apertus-base"):
        g = res["breakdown"][s]["layout_group"]
        unseen = [not truth[(s, p["page_id"], f)] for p in pages if p["split"] == "test" and p["layout"] != "A"
                  for f in FIELDS]
        assert g["unseen"]["layouts"] == ["B", "C"] and abs(g["unseen"]["acc"] - np.mean(unseen)) < 1e-9, g
        assert set(res["breakdown"][s]["layout"]) == {"A", "B", "C"}
    assert set(res["breakdown"]["apertus-base"]["layout_degradation"]) >= {"C0", "C2"}
    assert not {"C1", "C3"} & set(res["breakdown"]["apertus-base"]["layout_degradation"])
    assert (data / "results" / "accuracy_by_layout.png").exists() and (data / "results" / "chf_error.png").exists()

    # field prior: informative across fields, exactly 0.5 within a field; planted signal stays ~1 within fields
    assert d["field prior"]["ci"][0] > 0.5 and d["field prior"]["within_field"]["auroc"] == 0.5, d["field prior"]
    assert d["mean entropy"]["within_field"]["auroc"] > 0.95 and len(d["mean entropy"]["per_field"]) == 8
    assert res["h2"]["best_single"] != "field prior" and "field prior" in res["combined"]["features"]
    no_span = sum(p["split"] == "test" for n, p in enumerate(pages) if n % 50 == 1 and n % 97)
    assert res["n_no_span"]["apertus-base"]["test"] == no_span > 0, res["n_no_span"]
    assert res["combined"]["n_missing_imputed"]["test"]["probe A"] >= no_span
    # CHF: wrong amounts are off by 1 CHF; failed pages lose whole amounts (> 100 CHF)
    test_pages = [p for p in pages if p["split"] == "test"]
    assert res["chf"]["apertus-base"]["share_gt_100"] == failed_test / len(test_pages), res["chf"]["apertus-base"]
    lora_err = [sum(truth[("apertus-lora", p["page_id"], f)] for f in NUMERIC_FIELDS) for p in test_pages]
    assert res["chf"]["apertus-lora"]["share_gt_100"] == 0 and res["chf"]["apertus-lora"]["mean"] == np.mean(lora_err)
    assert runtime < 120, runtime
    print(f"eval selfcheck ok (run.py {runtime:.1f} s on {len(items)} items, {res['bootstrap']['resamples']} resamples)")


if __name__ == "__main__":
    main()
