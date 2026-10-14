import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation

import numpy as np
from sklearn.metrics import roc_auc_score

NUMERIC_FIELDS = ("totalTaxValue", "totalGrossRevenueA", "totalGrossRevenueB", "totalWithHoldingTaxClaim")
TEXT_FIELDS = ("institution", "canton", "taxPeriod", "client_last_name")
FIELDS = NUMERIC_FIELDS + TEXT_FIELDS


def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def gold_fields(doc):
    """Gold = values as displayed on the page: oracle_page for amounts, oracle for the text fields."""
    return {**{k: doc["oracle"][k] for k in TEXT_FIELDS}, **{k: doc["oracle_page"][k] for k in NUMERIC_FIELDS}}


def norm_number(v):
    if v is None:
        return None
    s = str(v).strip().replace("'", "").replace("’", "").replace(" ", "").replace(" ", "").replace(" ", "")
    if s.count(",") == 1 and "." not in s:
        s = s.replace(",", ".")
    s = s.replace(",", "")
    try:
        return Decimal(s).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def norm_text(v):
    if v is None:
        return None
    s = unicodedata.normalize("NFKC", str(v)).casefold()
    return re.sub(r"\s+", " ", s).strip() or None


def field_correct(field, pred, gold):
    if field in NUMERIC_FIELDS:
        p, g = norm_number(pred), norm_number(gold)
    else:
        p, g = norm_text(pred), norm_text(gold)
    return p is not None and p == g


def auroc(y_wrong, score):
    y = np.asarray(y_wrong)
    if y.min() == y.max():
        return float("nan")
    return float(roc_auc_score(y, score))


def bootstrap_ci(groups, stat, n=10_000, seed=0):
    """groups: list of per-document payloads; stat: fn(list_of_payloads) -> float. Cluster bootstrap by document."""
    rng = np.random.default_rng(seed)
    k = len(groups)
    vals = np.array([stat([groups[i] for i in rng.integers(0, k, k)]) for _ in range(n)])
    vals = vals[~np.isnan(vals)]
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def triage_share(y_wrong, score, catch=0.9):
    """Share of items to review (highest doubt first) to catch `catch` of the wrong items."""
    y = np.asarray(y_wrong)[np.argsort(-np.asarray(score), kind="stable")]
    total = y.sum()
    if total == 0:
        return 0.0
    k = int(np.searchsorted(np.cumsum(y), np.ceil(catch * total))) + 1
    return k / len(y)


if __name__ == "__main__":
    assert norm_number("39'351.02") == Decimal("39351.02")
    assert norm_number("39’351,0") == Decimal("39351.00")
    assert norm_number("1,234.5") == Decimal("1234.50")
    assert norm_number("abc") is None
    assert field_correct("institution", " Alpen  Bank AG", "alpen bank ag")
    assert not field_correct("totalTaxValue", None, "1.00")
    y, s = [0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]
    assert auroc(y, s) == 1.0
    assert triage_share(y, s, 1.0) == 0.5
    assert triage_share([1, 0, 0, 1], [0.9, 0.8, 0.1, 0.2], 1.0) == 0.75
    lo, hi = bootstrap_ci([1.0, 0.0, 1.0, 1.0], lambda g: float(np.mean(g)), n=500)
    assert 0.0 <= lo <= hi <= 1.0
    print("metrics self-check ok")
