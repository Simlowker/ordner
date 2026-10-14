"""Deterministic consistency checks per extracted field: True (consistent), False (inconsistent), None (no check)."""

import re
from decimal import Decimal

from .metrics import FIELDS, NUMERIC_FIELDS, norm_number, norm_text
from .regex_baseline import CANTONS, flat_lines, grid, grid_value, key, normalize, numbers

# Layout B (test only) is unknown here: checks use generic knowledge (35 %, cantons, display precision) and layout-A
# structure detected in the text itself, never the page's layout label.
WHT_RATE = Decimal("0.35")
TOTAL_ALL = ([r"total", r"bruttoertrag|revenu brut|reddito lordo", r"\ba\b.*\bb\b.*da-1"], [r"\b(?:mit|avec|con)\b"])


def _step(*values):
    """Half of the display step: amounts shown as whole CHF may be rounded by up to 0.5, otherwise by 0.005."""
    return Decimal("0.5") if all(v == v.to_integral_value() for v in values) else Decimal("0.005")


def _ab_footnote(flat):
    """Layout A footnote under the tax value: '(1) Davon A x und B y' / 'Dont A x et B y' / 'Di cui A x e B y'."""
    m = re.search(r"(?:davon|dont|di cui)\s+a\s+(\S+)\s+(?:und|et|e)\s+b\s+(\S+)", key(flat))
    if not m:
        return None
    a, b = numbers(flat[m.start(1):m.end(1)]), numbers(flat[m.start(2):m.end(2)])
    return Decimal(a[0]) + Decimal(b[0]) if a and b else None


def _year_end(flat):
    m = re.search(r"\d{1,2}\.\d{1,2}\.(\d{4})\s*[-–—]+\s*\d{1,2}\.\d{1,2}\.(\d{4})", flat)
    return m.group(2) if m else None


def check(fields, text=None):
    """fields: {field: value} as extracted; text: OCR text of the page. Returns {field: True/False/None}."""
    checks = {f: [] for f in FIELDS}
    num = {f: norm_number(fields.get(f)) for f in NUMERIC_FIELDS}
    for f in NUMERIC_FIELDS:
        checks[f].append(num[f] is not None and num[f] >= 0)

    a, b, w, tv = num["totalGrossRevenueA"], num["totalGrossRevenueB"], num["totalWithHoldingTaxClaim"], num["totalTaxValue"]
    if a is not None and w is not None:
        ok = abs(w - WHT_RATE * a) <= WHT_RATE * _step(a) + Decimal("0.006")
        checks["totalGrossRevenueA"].append(ok)
        checks["totalWithHoldingTaxClaim"].append(ok)

    if text is not None:
        t = normalize(text)
        rows, lines = grid(t), flat_lines(t)
        flat = "\n".join(lines)
        on_page = [Decimal(n) for n in numbers(t)]
        tot = grid_value(rows, *TOTAL_ALL)  # layout-A totals row present -> each total is printed twice
        for f in NUMERIC_FIELDS:
            if num[f] is not None:
                n_seen = sum(x == num[f] for x in on_page)
                checks[f].append(n_seen > 0)
                if tot is not None and f != "totalWithHoldingTaxClaim":
                    checks[f].append(n_seen >= 2)
        ab = _ab_footnote(flat)
        if ab is not None and tv is not None:
            checks["totalTaxValue"].append(abs(ab - tv) <= 2 * _step(tv, ab))
        if tot is not None and a is not None and b is not None:
            ok = abs(Decimal(tot) - a - b) <= 2 * _step(a, b, Decimal(tot))
            checks["totalGrossRevenueA"].append(ok)
            checks["totalGrossRevenueB"].append(ok)

        k = norm_text(key(flat))
        for f in ("institution", "client_last_name"):
            v = norm_text(fields.get(f))
            checks[f].append(v is not None and re.search(rf"(?<!\w){re.escape(key(v))}(?!\w)", k) is not None)
        c = fields.get("canton")
        checks["canton"].append(c is not None and re.search(rf"\b{re.escape(str(c).strip().upper())}\b", flat) is not None)
        y = _year_end(flat)
        if y is not None:
            checks["taxPeriod"].append(norm_number(fields.get("taxPeriod")) == Decimal(y))

    c = fields.get("canton")
    checks["canton"].append(c is not None and str(c).strip().upper() in CANTONS)
    y = norm_number(fields.get("taxPeriod"))
    checks["taxPeriod"].append(y is not None and y == y.to_integral_value() and 2000 <= y <= 2035)
    for f in ("institution", "client_last_name"):
        if not checks[f]:
            checks[f].append(norm_text(fields.get(f)) is not None)
    return {f: (all(v) if v else None) for f, v in checks.items()}


if __name__ == "__main__":
    good = {"totalTaxValue": 67443, "totalGrossRevenueA": 512, "totalGrossRevenueB": 862,
            "totalWithHoldingTaxClaim": 179.36, "institution": "Velfeld Banque SA", "canton": "VS", "taxPeriod": 2025,
            "client_last_name": "Rey"}
    r = check(good)
    assert all(r.values()), r
    r = check({**good, "totalWithHoldingTaxClaim": 17.94, "canton": "XX", "taxPeriod": 1925})
    assert not r["totalWithHoldingTaxClaim"] and not r["totalGrossRevenueA"] and r["totalTaxValue"]
    assert not r["canton"] and not r["taxPeriod"]
    assert check({**good, "totalTaxValue": None})["totalTaxValue"] is False
    print("rules self-check ok")
