"""Deterministic deductions checklist: data/rules/deductions_<year>.json + a user profile -> triggered rules.

Rule conditions (`when`, all must hold): "key" (truthy), "!key" (falsy), "key=value", "key!=value", "key>number".
Estimate (optional): clamp(fixed + profile[base] * prod(factors), min, max), rounded to CHF.
"""
import json
import math
from pathlib import Path

DATA = Path(__file__).resolve().parents[3] / "data"
ENUMS = {
    "income_type": ("employee", "self_employed", "none"),
    "commute_mode": ("public", "car", "moto", "bike"),
    "meals": ("none", "out", "canteen"),
}
NUMBERS = {"net_income": 10_000_000, "commute_km": 500, "children": 20}
BOOLS = ("pension_fund", "pays_3a", "gap_3a_2025", "lpp_buyin", "training", "married", "both_earn", "childcare")


def load_rules(year=2026, data=DATA):
    return json.loads((data / "rules" / f"deductions_{year}.json").read_text(encoding="utf-8"))


def clean_profile(raw):
    """Trust boundary: the profile comes from the browser."""
    raw = raw if isinstance(raw, dict) else {}
    p = {k: raw.get(k) is True for k in BOOLS}
    for k, hi in NUMBERS.items():
        try:
            v = float(raw.get(k) or 0)
        except (TypeError, ValueError):
            v = 0.0
        p[k] = min(max(v, 0.0), hi) if math.isfinite(v) else 0.0
    for k, allowed in ENUMS.items():
        p[k] = raw.get(k) if raw.get(k) in allowed else allowed[0]
    p["contributes_2_3a"] = p["pension_fund"] or p["pays_3a"]
    return p


def holds(cond, p):
    for op in ("!=", "=", ">"):
        if op in cond:
            key, value = cond.split(op, 1)
            if op == ">":
                return float(p.get(key) or 0) > float(value)
            return (str(p.get(key)) == value) == (op == "=")
    if cond.startswith("!"):
        return not p.get(cond[1:])
    return bool(p.get(cond))


def estimate(spec, p):
    if not spec:
        return None
    v = spec.get("fixed", 0)
    if "base" in spec:
        v += p.get(spec["base"], 0) * math.prod(spec.get("factors", [1]))
    if not v:
        return None  # nothing known to compute from (e.g. income left empty)
    return round(min(max(v, spec.get("min", v)), spec.get("max", v)))


def evaluate(raw_profile, rules=None):
    rules = rules or load_rules()
    p = clean_profile(raw_profile)
    items = []
    for r in rules["rules"]:
        if all(holds(c, p) for c in r["when"]):
            item = {k: v for k, v in r.items() if k not in ("when", "estimate")}
            item["sources"] = [{"id": s, **rules["sources"][s]} for s in r["sources"]]
            item["estimate"] = estimate(r.get("estimate"), p)
            items.append(item)
    return {"tax_year": rules["tax_year"], "scope": rules["scope"], "disclaimer": rules["disclaimer"], "items": items}


if __name__ == "__main__":
    rules = load_rules()
    for r in rules["rules"]:
        for key in ("title", "amount", "condition", "legal_basis") + (("unverified_note",) if "unverified_note" in r else ()):
            assert set(r[key]) == {"fr", "de", "it"}, (r["id"], key)
        assert all(s in rules["sources"] for s in r["sources"]), r["id"]
        assert r["verification"] in ("primary", "secondary", "unverified"), r["id"]
        assert r["verification"] == "primary" or "unverified_note" in r, r["id"]

    family = {"income_type": "employee", "net_income": 60000, "pension_fund": True, "commute_km": 12,
              "commute_mode": "car", "married": True, "both_earn": True, "children": 2, "childcare": True}
    got = {i["id"]: i["estimate"] for i in evaluate(family, rules)["items"]}
    assert set(got) == {"pillar_3a_lpp", "commuting_car", "professional_flat", "insurance_married_with",
                        "child", "childcare", "dual_income", "married"}, got
    assert got["commuting_car"] == 3300  # 12 km * 0.75 * 2 * 220 = 3960, capped
    assert got["professional_flat"] == 2000  # 3 % of 60'000 = 1'800, floored at 2'000
    assert got["insurance_married_with"] == 3700 + 2 * 700
    assert got["child"] == 2 * 6800

    student = {"income_type": "none", "children": "abc", "net_income": float("nan"), "married": "yes"}
    got = {i["id"]: i["estimate"] for i in evaluate(student, rules)["items"]}
    assert set(got) == {"insurance_single_without"}, got
    assert got["insurance_single_without"] == 2700

    freelance = {"income_type": "self_employed", "net_income": 250000, "pays_3a": True}
    got = {i["id"]: i["estimate"] for i in evaluate(freelance, rules)["items"]}
    assert got["pillar_3a_no_lpp"] == 36288 and "insurance_single_with" in got and "professional_flat" not in got
    assert evaluate({"income_type": "self_employed"}, rules)["items"][0]["estimate"] is None  # income unknown
    print("deductions self-check ok")
