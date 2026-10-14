"""OFSP/BAG health-insurance premiums (open data) -> offline LAMal comparator and deductible break-even.

Data: OFSP/BAG « Primes de l'assurance-maladie », https://ckan.opendata.swiss/dataset/health-insurance-premiums
(opendata.swiss "terms_by": free use, the source must be cited). The CKAN API answers 403 without a User-Agent.
Download once (`python -m ordner.connectors.ofsp_premiums download`, into work/ofsp, not committed), compare offline.

Cost sharing, verified with tools/fedlex.py on 2026-10-14 (consolidation 2026-08-01):
- LAMal art. 64 al. 2 (RS 832.10): « a. un montant fixe par année (franchise); et b. 10 % des coûts qui dépassent
  la franchise (quote-part) ». https://www.fedlex.admin.ch/eli/cc/1995/1328_1328_1328/fr#art_64
- OAMal art. 103 al. 2 (RS 832.102): « Le montant maximal annuel de la quote-part [...] s'élève à 700 francs pour
  les adultes et à 350 francs pour les enfants. » https://www.fedlex.admin.ch/eli/cc/1995/3867_3867_3867/fr#art_103
Not modelled: hospital daily contribution (LAMal art. 64 al. 5), family caps for several children (OAMal art. 93 al. 3).
"""
import argparse
import base64
import csv
import hashlib
import json
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

CKAN = "https://ckan.opendata.swiss/api/3/action/package_show?id=health-insurance-premiums"
SOURCE = "OFSP/BAG, Primes de l'assurance-maladie (opendata.swiss, health-insurance-premiums)"
UA = {"User-Agent": "Ordner/0.1 (offline LAMal comparator; Hack Apertus 2026)"}
FILES = ("Prämien_CH.csv", "Tarife.csv")
WORK = Path(__file__).resolve().parents[3] / "work" / "ofsp"
QUOTE_PART, CAP = 0.10, {"adult": 700.0, "young_adult": 700.0, "child": 350.0}
AGE = {"AKA_01_KIN": "child", "AKA_02_JUG": "young_adult", "AKA_03_ERW": "adult"}


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def download(out_dir=WORK, files=FILES) -> dict:
    """Fetch the current CSVs listed in the CKAN package; write them and a manifest (URL, sha256, date, source)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pkg = json.loads(_get(CKAN))["result"]
    manifest = {"source": SOURCE, "license": "opendata.swiss terms_by (cite the source)", "dataset": CKAN,
                "modified": pkg.get("modified"), "downloaded": date.today().isoformat(), "files": {}}
    for res in pkg["resources"]:
        url = res.get("download_url") or res.get("url") or ""
        enc = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("path", [""])[0]
        name = base64.b64decode(enc + "=" * (-len(enc) % 4)).decode("utf-8", "replace").rsplit("/", 1)[-1] if enc else ""
        if name in files:
            body = _get(url)
            (out_dir / name).write_bytes(body)
            manifest["files"][name] = {"url": url, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
    missing = set(files) - set(manifest["files"])
    if missing:
        raise RuntimeError(f"not found in the CKAN package: {sorted(missing)}")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def load(path=WORK / "Prämien_CH.csv", canton=None) -> list[dict]:
    """Prämien_CH.csv -> rows with monthly premium in CHF; `canton` filters while reading (the file is ~25 MB)."""
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if canton and r["Kanton"] != canton:
                continue
            rows.append({"insurer": r["Versicherer"], "canton": r["Kanton"], "year": int(r["Geschäftsjahr"]),
                         "region": int(r["Region"].rsplit("_", 1)[-1]), "age": AGE.get(r["Altersklasse"], r["Altersklasse"]),
                         "age_subgroup": r["Altersuntergruppe"], "accident": r["Unfalleinschluss"] == "MIT_UNF",
                         "tariff": r["Tarif"], "model": r["Tariftyp"], "tariff_name": r["Tarifbezeichnung"],
                         "deductible": int(r["Franchise"].rsplit("_", 1)[-1]), "monthly": float(r["Prämie"])})
    return rows


def tariff_names(path=WORK / "Tarife.csv", lang="FR") -> dict:
    """(insurer, tariff code) -> model name in `lang` (DE/FR/IT/EN) from Tarife.csv."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {(r["Versicherer"], r["Tarif"]): r[f"Name_{lang}"] for r in csv.DictReader(f) if r["Kategorie"] == "MOD"}


def annual_cost(monthly, deductible, expected_costs, age="adult"):
    """12 premiums + franchise + 10 % co-pay above it, capped (OAMal art. 103 al. 2)."""
    over = max(expected_costs - deductible, 0.0)
    return 12 * monthly + min(expected_costs, deductible) + min(QUOTE_PART * over, CAP[age])


def break_even(monthly_low, ded_low, monthly_high, ded_high, age="adult"):
    """Expected yearly costs above which the lower deductible becomes cheaper (None: the higher one always wins).
    cost(high) - cost(low) is non-decreasing in the costs, so bisection is exact to the cent."""
    diff = lambda c: annual_cost(monthly_high, ded_high, c, age) - annual_cost(monthly_low, ded_low, c, age)
    lo, hi = 0.0, 100_000.0
    if diff(lo) >= 0:
        return 0.0
    if diff(hi) < 0:
        return None
    while hi - lo > 0.005:
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if diff(mid) < 0 else (lo, mid)
    return round(hi, 2)


def compare(rows, canton, region, age="adult", accident=False, model=None, deductible=None, expected_costs=0.0,
            age_subgroup=None):
    """Offers for one profile, cheapest total first. Default subgroup = the first one (E1/J1/K1: no extra discount)."""
    sub = age_subgroup or {"adult": "E1", "young_adult": "J1", "child": "K1"}[age]
    out = [{**r, "annual_premium": round(12 * r["monthly"], 2),
            "total": round(annual_cost(r["monthly"], r["deductible"], expected_costs, age), 2)}
           for r in rows if r["canton"] == canton and r["region"] == region and r["age"] == age
           and r["accident"] == accident and r["age_subgroup"] == sub
           and (model is None or r["model"] == model) and (deductible is None or r["deductible"] == deductible)]
    return sorted(out, key=lambda o: (o["total"], o["insurer"], o["tariff"]))


def deductible_table(offers, expected_costs=0.0, age="adult"):
    """For one insurer + tariff (offers across deductibles): total per deductible, best choice, break-even points."""
    by = sorted({o["deductible"]: o for o in offers}.values(), key=lambda o: o["deductible"])
    table = [{"deductible": o["deductible"], "monthly": o["monthly"],
              "total": round(annual_cost(o["monthly"], o["deductible"], expected_costs, age), 2)} for o in by]
    edges = [{"from": a["deductible"], "to": b["deductible"],
              "lower_is_cheaper_above": break_even(a["monthly"], a["deductible"], b["monthly"], b["deductible"], age)}
             for a, b in zip(by, by[1:])]
    return {"expected_costs": expected_costs, "table": table, "best": min(table, key=lambda t: t["total"]) if table else None,
            "break_even": edges, "source": SOURCE}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m ordner.connectors.ofsp_premiums")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("download")
    c = sp.add_parser("compare")
    c.add_argument("--canton", required=True)
    c.add_argument("--region", type=int, default=0)
    c.add_argument("--age", choices=list(CAP), default="adult")
    c.add_argument("--accident", action="store_true")
    c.add_argument("--model")
    c.add_argument("--deductible", type=int)
    c.add_argument("--costs", type=float, default=0.0, help="expected yearly health costs in CHF")
    c.add_argument("--top", type=int, default=10)
    a = ap.parse_args(argv)
    if a.cmd == "download":
        print(json.dumps(download(), ensure_ascii=False, indent=2))
        return
    if not (WORK / "Prämien_CH.csv").exists():
        raise SystemExit(f"{WORK / 'Prämien_CH.csv'} missing: run `python -m ordner.connectors.ofsp_premiums download`")
    rows, names = load(canton=a.canton), tariff_names()
    offers = compare(rows, a.canton, a.region, a.age, a.accident, a.model, a.deductible, a.costs)
    print(f"{SOURCE}; premiums {offers[0]['year'] if offers else '?'}; insurer = OFSP number (names not in the data)")
    for o in offers[: a.top]:
        print(f"{o['total']:>9.2f}  insurer {o['insurer']:>5}  {o['model']:<8} {o['deductible']:>5}  "
              f"{o['monthly']:>7.2f}/month  {names.get((o['insurer'], o['tariff']), o['tariff_name'])}")
    if offers:
        best = offers[0]
        same = [o for o in compare(rows, a.canton, a.region, a.age, a.accident, expected_costs=a.costs)
                if o["insurer"] == best["insurer"] and o["tariff"] == best["tariff"]]
        print(json.dumps(deductible_table(same, a.costs, a.age), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
