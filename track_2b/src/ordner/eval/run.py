"""Replay evaluation used by `make run`: reads only data/ (items.jsonl + probe/*.npz), refits the probe and the combined
doubt model on train+dev, evaluates on test, writes data/results/{results.json, table.md, *.png}.
python -m ordner.eval.run --data data

Bootstrap: 10 000 cluster resamples by statement (stmt_id), drawn once and shared by every statistic (paired
comparisons). AUROC is computed for all resamples at once as a weighted Mann-Whitney statistic (no refitting inside
the bootstrap: models are fit once on train+dev, the bootstrap measures test-set sampling variability)."""

import argparse
import json
import time
from pathlib import Path

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, cross_val_predict, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .metrics import FIELDS, NUMERIC_FIELDS, auroc, norm_number, read_jsonl, triage_share
from .probe import probe_model

SYSTEMS = ["regex", "apertus-base", "apertus-lora"]
NAMES = {"regex": "OCR + rules/regex (no LLM)", "apertus-base": "OCR + Apertus 1.5 8B zero-shot",
         "apertus-lora": "OCR + Apertus 1.5 8B + LoRA"}
# doubt signal -> (item column, sign): higher score = more likely wrong
SINGLE = {"min token prob": ("lp_min", -1), "mean token prob": ("lp_mean", -1), "mean entropy": ("ent_mean", 1),
          "first-token entropy": ("ent_first", 1), "d1 validation": ("d1_p_yes", -1), "rules": ("rule_doubt", 1)}
COMBO_COLS = ["lp_min", "lp_mean", "ent_mean", "ent_first", "d1_p_yes", "rule_false", "rule_none"]
CS = (0.01, 0.1, 1.0, 10.0)
CATCH = (0.8, 0.9, 0.95)
CHF_THRESHOLD = 100


def load(data):
    items = read_jsonl(data / "items.jsonl")
    col = {k: np.array([it[k] for it in items], dtype=object) for k in
           ("system", "split", "stmt_id", "page_id", "field", "layout", "degradation", "language", "pred", "gold")}
    col["degradation"] = col["degradation"].astype(int)
    col["correct"] = np.array([bool(it["correct"]) for it in items])
    col["error"] = np.array([bool(it.get("error")) for it in items])
    for k in ("lp_min", "lp_mean", "ent_mean", "ent_first", "d1_p_yes"):
        v = np.array([np.nan if it[k] is None else float(it[k]) for it in items])
        col[k] = np.where(np.isfinite(v), v, np.nan)  # non-finite (e.g. -inf log-prob) counted as missing
    rule = [it["rule_ok"] for it in items]
    col["rule_doubt"] = np.array([0.5 if r is None else float(not r) for r in rule])
    col["rule_false"] = np.array([float(r is False) for r in rule])
    col["rule_none"] = np.array([float(r is None) for r in rule])
    probes = {}
    for pos in ("A", "B"):
        p = data / "probe" / f"{pos}.npz"
        if p.exists():
            z = np.load(p)
            probes[pos] = {"X": z["X"].astype(np.float32), "idx": z["item_idx"], "C": float(z["C"]),
                           "layer": int(z["layer"])}
    return col, probes


class Boot:
    """Cluster bootstrap weights W [B, K]: W[b, k] = times statement k is drawn in resample b."""

    def __init__(self, clusters, n=10_000, seed=0):
        self.keys = sorted(set(clusters))
        self.pos = {c: i for i, c in enumerate(self.keys)}
        k = len(self.keys)
        self.W = np.random.default_rng(seed).multinomial(k, np.full(k, 1 / k), size=n).astype(np.float32)

    def idx(self, clusters):
        return np.array([self.pos[c] for c in clusters])

    def ratio(self, clusters, num, den=None):
        """Resampled sum(num)/sum(den) (den defaults to ones)."""
        cl, k = self.idx(clusters), len(self.keys)
        s = np.bincount(cl, weights=np.asarray(num, float), minlength=k)
        d = np.bincount(cl, weights=None if den is None else np.asarray(den, float), minlength=k)
        with np.errstate(invalid="ignore", divide="ignore"):
            return (self.W @ s) / (self.W @ d)

    def auroc(self, clusters, y, score):
        num, den = self.auroc_parts(clusters, y, score)
        with np.errstate(invalid="ignore", divide="ignore"):
            return num / den

    def auroc_parts(self, clusters, y, score):
        """Resampled AUROC (Mann-Whitney, ties = 1/2) for all B resamples, as (concordant pairs, pairs). Weights
        depend only on the cluster: num_b = w_b' A w_b with A[k, l] = concordant (pos in k, neg in l) pairs."""
        cl, k, y = self.idx(clusters), len(self.keys), np.asarray(y, bool)
        _, g = np.unique(score, return_inverse=True)
        P, N = np.zeros((k, g.max() + 1)), np.zeros((k, g.max() + 1))
        np.add.at(P, (cl[y], g[y]), 1)
        np.add.at(N, (cl[~y], g[~y]), 1)
        A = P @ (np.cumsum(N, axis=1) - 0.5 * N).T
        W = self.W.astype(np.float64)
        return ((W @ A) * W).sum(1), (W @ P.sum(1)) * (W @ N.sum(1))

    def median(self, clusters, values, chunk=2000):
        """Resampled (weighted, lower) median."""
        order = np.argsort(values, kind="stable")
        v, cl = np.asarray(values)[order], self.idx(clusters)[order]
        out = []
        for b in range(0, len(self.W), chunk):
            c = np.cumsum(self.W[b:b + chunk][:, cl], axis=1)
            out.append(v[(c >= c[:, -1:] / 2).argmax(1)])
        return np.concatenate(out)


def ci(vals):
    v = vals[~np.isnan(vals)]
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if len(v) else [None, None]


def doubt_score(col, name, mask):
    c, sign = SINGLE[name]
    v = sign * col[c][mask]
    if np.isnan(v).all():
        return None, 0
    n_missing = int(np.isnan(v).sum())
    return np.where(np.isnan(v), np.nanmax(v) + 1, v), n_missing  # missing value = maximal doubt


def field_prior(col, fit):
    """P(wrong | field) on the fit rows, as a score for every item (constant within a field)."""
    rate = {f: float(np.mean(~col["correct"][fit & (col["field"] == f)])) for f in FIELDS if (fit & (col["field"] == f)).any()}
    return np.array([rate.get(f, np.nan) for f in col["field"]])


def chf_error(col, mask):
    """Per page: sum over the 4 amounts of |pred - gold| in CHF (missing or unparseable pred = whole gold amount)."""
    err, stmt = {}, {}
    for i in np.flatnonzero(mask & np.isin(col["field"], NUMERIC_FIELDS)):
        g, p = norm_number(col["gold"][i]), norm_number(col["pred"][i])
        err[col["page_id"][i]] = err.get(col["page_id"][i], 0.0) + float(abs(g) if p is None else abs(p - g))
        stmt[col["page_id"][i]] = col["stmt_id"][i]
    return np.array(list(err.values())), np.array([stmt[k] for k in err])


def combo_model(C):
    return make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler(),
                         LogisticRegression(C=C, max_iter=2000))


def fit_select(X, y, groups, make, cs=CS):
    """Choose C by grouped 5-fold CV AUROC, refit on all rows."""
    cv = GroupKFold(n_splits=min(5, len(set(groups))))
    scores = [cross_val_score(make(C), X, y, groups=groups, cv=cv, scoring="roc_auc").mean() for C in cs]
    best = cs[int(np.nanargmax(scores))]
    return make(best).fit(X, y), best, dict(zip(map(str, cs), map(float, scores)))


def probe_scores(col, probes, pos, mask_fit, mask_test):
    """Probe P(wrong): out-of-fold on the fit rows, model refit on all fit rows for the test rows. NaN if no acts."""
    n = len(col["correct"])
    out = np.full(n, np.nan)
    if pos not in probes:
        return out, None
    p = probes[pos]
    has = np.zeros(n, bool)
    has[p["idx"]] = True
    row = np.full(n, -1)
    row[p["idx"]] = np.arange(len(p["idx"]))
    fit = np.flatnonzero(mask_fit & has)
    y = ~col["correct"][fit]
    groups = col["stmt_id"][fit]
    X = p["X"][row[fit]]
    out[fit] = cross_val_predict(probe_model(p["C"]), X, y, groups=groups, cv=GroupKFold(5), method="predict_proba")[:, 1]
    model = probe_model(p["C"]).fit(X, y)
    test = np.flatnonzero(mask_test & has)
    out[test] = model.predict_proba(p["X"][row[test]])[:, 1]
    return out, {"layer": p["layer"], "C": p["C"], "n_fit": len(fit), "n_test": len(test)}


def curve(y, score, n_points=101):
    yy = np.asarray(y)[np.argsort(-score, kind="stable")]
    caught = np.r_[0, np.cumsum(yy)] / max(yy.sum(), 1)
    x = np.linspace(0, 1, n_points)
    return [[float(a), float(caught[int(round(a * len(yy)))])] for a in x]


def evaluate(data, n_boot=10_000):
    t0 = time.time()
    col, probes = load(data)
    test = col["split"] == "test"
    systems = [s for s in SYSTEMS if (col["system"] == s).any()] + \
              sorted(set(col["system"]) - set(SYSTEMS))
    res = {"n_items": {s: {sp: int(((col["system"] == s) & (col["split"] == sp)).sum())
                           for sp in ("train", "dev", "test")} for s in systems},
           "bootstrap": {"resamples": n_boot, "cluster": "stmt_id", "seed": 0}}
    for name, key in (("costs.json", "costs"), ("explain_eval.json", "explain")):
        if (data / name).exists():
            res[key] = json.loads((data / name).read_text())
    res["n_error_pages"] = {s: {sp: len(set(col["page_id"][(col["system"] == s) & (col["split"] == sp) & col["error"]]))
                                for sp in ("train", "dev", "test")} for s in systems}
    if not test.any():
        res["note"] = "no test items"
        return res, col
    boot = Boot(col["stmt_id"][test], n=n_boot)
    res["bootstrap"]["clusters"] = len(boot.keys)

    def group(mg):
        return {"acc": float(col["correct"][mg].mean()), "n": int(mg.sum()),
                "ci": ci(boot.ratio(col["stmt_id"][mg], col["correct"][mg]))}

    # Extraction accuracy (H1 and breakdowns)
    res["accuracy"], res["breakdown"] = {}, {}
    for s in systems:
        m = test & (col["system"] == s)
        if not m.any():
            continue
        cl, ok = col["stmt_id"][m], col["correct"][m]
        pages = {}
        for pid, c, good in zip(col["page_id"][m], cl, ok):
            pages.setdefault(pid, [c, True])[1] &= good
        pc = np.array([v[0] for v in pages.values()])
        pok = np.array([v[1] for v in pages.values()], float)
        res["accuracy"][s] = {"acc": float(ok.mean()), "ci": ci(boot.ratio(cl, ok)), "n_items": int(m.sum()),
                              "n_pages": len(pages), "page_all_ok": float(pok.mean()), "page_all_ok_ci": ci(boot.ratio(pc, pok))}
        e, es = chf_error(col, m)
        big = e > CHF_THRESHOLD
        xs = np.logspace(-2, 6, 81)
        res.setdefault("chf", {})[s] = {
            "n_pages": len(e), "median": float(np.median(e)), "median_ci": ci(boot.median(es, e)),
            "mean": float(e.mean()), "mean_ci": ci(boot.ratio(es, e)), "share_any": float(np.mean(e > 0)),
            f"share_gt_{CHF_THRESHOLD}": float(big.mean()), f"share_gt_{CHF_THRESHOLD}_ci": ci(boot.ratio(es, big)),
            "survival": [[float(x), float(np.mean(e > x))] for x in xs]}
        br = {}
        for by in ("degradation", "layout", "field", "language"):
            br[by] = {}
            for g in sorted(set(col[by][m])):
                br[by][str(g)] = group(m & (col[by] == g))
        # seen layout (A, in train) vs every layout never seen in training, pooled (B and C)
        br["layout_group"] = {}
        for name, mg in (("seen", m & (col["layout"] == "A")), ("unseen", m & (col["layout"] != "A"))):
            if mg.any():
                br["layout_group"][name] = {**group(mg), "layouts": sorted(set(col["layout"][mg]))}
        br["layout_degradation"] = {}
        for lay in sorted(set(col["layout"][m])):
            for d in sorted(set(col["degradation"][m])):
                mg = m & (col["layout"] == lay) & (col["degradation"] == d)
                if mg.any():
                    br["layout_degradation"][f"{lay}{d}"] = group(mg)
        res["breakdown"][s] = br

    res["h1"] = None
    if "apertus-base" in res["accuracy"] and "apertus-lora" in res["accuracy"]:
        key = lambda s: {(p, f): i for i, (p, f) in  # noqa: E731
                         enumerate(zip(col["page_id"], col["field"])) if test[i] and col["system"][i] == s}
        kb, kl = key("apertus-base"), key("apertus-lora")
        common = sorted(set(kb) & set(kl))
        ib, il = np.array([kb[k] for k in common]), np.array([kl[k] for k in common])
        d = col["correct"][il].astype(float) - col["correct"][ib].astype(float)
        vals = boot.ratio(col["stmt_id"][ib], d)
        lo, hi = ci(vals)
        res["h1"] = {"diff": float(d.mean()), "ci": [lo, hi], "n_items_paired": len(common),
                     "share_resamples_le_0": float(np.mean(vals[~np.isnan(vals)] <= 0)), "supported": bool(lo > 0)}

    # Doubt signals. Field prior = P(wrong | field) on the rows each system's doubt model is fit on.
    res["doubt"], res["curves"] = {}, {}
    trdev = np.isin(col["split"], ["train", "dev"])
    fit_rows = {s: (col["system"] == s) & (col["split"] == "dev" if s == "apertus-lora" else trdev) for s in systems}
    extra = {s: {"field prior": field_prior(col, fit_rows[s])} for s in systems}
    res["n_no_span"] = {s: {sp: int(((col["system"] == s) & (col["split"] == sp) & np.isnan(col["lp_min"])
                                     & ~col["error"]).sum()) for sp in ("train", "dev", "test")}
                        for s in systems if not np.isnan(col["lp_min"][col["system"] == s]).all()}

    def combine(s, fit, tst, use_probe):
        names = COMBO_COLS + ["field prior"] + (["probe A"] if use_probe and "probe A" in extra[s] else [])
        X = np.column_stack([col[c] for c in COMBO_COLS] + [extra[s][n] for n in names[len(COMBO_COLS):]])
        y = ~col["correct"][fit]
        if not fit.any() or not tst.any() or y.min() == y.max():
            return None, None
        if y.sum() < 5:  # grouped 5-fold CV needs errors in every fold
            return None, {"not_estimable": f"{int(y.sum())} wrong among {int(fit.sum())} fit items"}
        model, C, cvs = fit_select(X[fit], y, col["stmt_id"][fit], combo_model)
        sc = np.full(len(X), np.nan)
        sc[tst] = model.predict_proba(X[tst])[:, 1]
        missing = {part: {n: int(np.isnan(X[rows, j]).sum()) for j, n in enumerate(names)}
                   for part, rows in (("fit", fit), ("test", tst))}
        return sc, {"system": s, "C": C, "cv_auc": cvs, "features": names, "n_missing_imputed": missing,
                    "missing": "median imputation + missing-indicator features"}

    test_base = test & (col["system"] == "apertus-base")
    if test_base.any():
        for pos in ("A", "B"):
            sc, info = probe_scores(col, probes, pos, fit_rows["apertus-base"], test_base)
            if info:
                extra["apertus-base"][f"probe {pos}"] = sc
                res.setdefault("probe", {})[pos] = info
        sc, info = combine("apertus-base", fit_rows["apertus-base"], test_base, True)
        if info:
            extra["apertus-base"]["combined"] = sc
            res["combined"] = {**info, "fit_on": "train+dev (probe A out-of-fold)"}
    if "apertus-lora" in systems:
        sc, info = combine("apertus-lora", fit_rows["apertus-lora"], test & (col["system"] == "apertus-lora"), False)
        if sc is not None:
            extra["apertus-lora"]["combined (no probe)"] = sc
        if info:
            res["combined_lora"] = {**info, "fit_on": "dev"}

    boot_auc = {}
    for s in systems:
        m = test & (col["system"] == s)
        if not m.any():
            continue
        y = ~col["correct"][m]
        if y.min() == y.max():
            res["doubt"][s] = {"note": "single class on test"}
            continue
        cl, fld = col["stmt_id"][m], col["field"][m]
        scores = {}
        for name in SINGLE:
            sc, n_missing = doubt_score(col, name, m)
            if sc is not None:
                scores[name] = (sc, n_missing)
        for name, sc in extra.get(s, {}).items():
            v = sc[m]
            if not np.isnan(v).all():
                scores[name] = (np.where(np.isnan(v), np.nanmax(v) + 1, v), int(np.isnan(v).sum()))
        res["doubt"][s] = {}
        for name, (sc, n_missing) in scores.items():
            vals = boot.auroc(cl, y, sc)
            boot_auc[(s, name)] = vals
            # within-field AUROC: only pairs (wrong, right) of the same field, i.e. pair-weighted mean of per-field AUROCs
            per_field, num, den, pnum, pden = {}, 0, 0, 0.0, 0.0
            for f in FIELDS:
                mf = fld == f
                if not mf.any() or y[mf].min() == y[mf].max():
                    continue
                nb, db = boot.auroc_parts(cl[mf], y[mf], sc[mf])
                a, pairs = auroc(y[mf], sc[mf]), float(y[mf].sum() * (~y[mf]).sum())
                with np.errstate(invalid="ignore", divide="ignore"):  # resamples without a wrong item -> NaN, dropped
                    per_field[f] = {"auroc": a, "ci": ci(nb / db), "n": int(mf.sum()), "wrong": int(y[mf].sum())}
                num, den, pnum, pden = num + nb, den + db, pnum + a * pairs, pden + pairs
            with np.errstate(invalid="ignore", divide="ignore"):
                within = {"auroc": pnum / pden, "ci": ci(num / den)} if pden else None
            res["doubt"][s][name] = {"auroc": auroc(y, sc), "ci": ci(vals), "n_missing": n_missing,
                                     "triage": {str(c): triage_share(y, sc, c) for c in CATCH}, "per_field": per_field,
                                     "within_field": within}
            if s == "apertus-base":
                res["curves"][name] = curve(y, sc)
        res["doubt"][s]["_n"] = {"items": int(m.sum()), "wrong": int(y.sum())}

    def paired(s, a, b):
        d = boot_auc[(s, a)] - boot_auc[(s, b)]
        lo, hi = ci(d)
        return {"a": a, "b": b, "diff": res["doubt"][s][a]["auroc"] - res["doubt"][s][b]["auroc"], "ci": [lo, hi],
                "share_resamples_le_0": float(np.mean(d[~np.isnan(d)] <= 0)), "supported": bool(lo is not None and lo > 0)}

    base = res["doubt"].get("apertus-base", {})
    singles = [k for k in base if not k.startswith("_") and k != "combined"]
    res["h2"] = res["h3"] = res["position_b_vs_a"] = None
    if "combined" in base and singles:
        best = max(singles, key=lambda k: base[k]["auroc"])
        res["h2"] = {**paired("apertus-base", "combined", best), "best_single": best}
    if "probe A" in base:
        res["h3"] = {"auroc": base["probe A"]["auroc"], "ci": base["probe A"]["ci"],
                     "supported": bool(base["probe A"]["ci"][0] > 0.5)}
    if "probe A" in base and "probe B" in base:
        res["position_b_vs_a"] = paired("apertus-base", "probe B", "probe A")
    res["runtime_seconds"] = round(time.time() - t0, 1)
    return res, col


def fmt_ci(d, key="acc"):
    lo, hi = d["ci"]
    return f"{d[key]:.3f} [{lo:.3f}, {hi:.3f}]" if lo is not None else f"{d[key]:.3f}"


def table(res):
    out = ["# Baseline vs Ours (test split)", "",
           f"95 % CIs: cluster bootstrap by statement, {res['bootstrap']['resamples']} resamples, "
           f"{res['bootstrap'].get('clusters', 0)} statements.", ""]
    acc = res.get("accuracy", {})
    if acc:
        unseen = sorted({lay for br in res["breakdown"].values() for lay in br["layout"] if lay != "A"})
        cell = lambda d, k: fmt_ci(d[k]) if k in d else "-"  # noqa: E731
        group_cols = [("seen", "Seen layout (A)")] + ([("unseen", f"Unseen layouts ({', '.join(unseen)})")] if unseen else [])
        out += ["## Extraction: field-level exact match", "",
                "| System | Field accuracy | Page fully correct | " + "".join(f"{t} | " for _, t in group_cols)
                + "".join(f"Layout {lay} | " for lay in unseen) + "Items |",
                "|---|---|---|" + "---|" * (len(group_cols) + len(unseen)) + "---|"]
        for s, a in acc.items():
            br = res["breakdown"][s]
            out.append(f"| {NAMES.get(s, s)} | {fmt_ci(a)} | {a['page_all_ok']:.3f} [{a['page_all_ok_ci'][0]:.3f}, "
                       f"{a['page_all_ok_ci'][1]:.3f}] | " + "".join(f"{cell(br['layout_group'], g)} | " for g, _ in group_cols)
                       + "".join(f"{cell(br['layout'], lay)} | " for lay in unseen)
                       + f"{a['n_items']} |")
        out += ["", "Pages whose extraction failed (`error`, all fields counted wrong), test split: "
                + ", ".join(f"{NAMES.get(s, s)} {n['test']}" for s, n in res.get("n_error_pages", {}).items()), ""]
        if res.get("h1"):
            h = res["h1"]
            out += [f"**H1** LoRA − zero-shot accuracy: {h['diff']:+.3f} [{h['ci'][0]:+.3f}, {h['ci'][1]:+.3f}] "
                    f"({h['n_items_paired']} paired items) → {'supported' if h['supported'] else 'not supported'}", ""]
    for s, sig in res.get("doubt", {}).items():
        if "note" in sig:
            continue
        n = sig["_n"]
        out += [f"## Doubt signals, {NAMES.get(s, s)}: AUROC for \"field is wrong\" ({n['wrong']} wrong / {n['items']})",
                "", "| Signal | AUROC [95 % CI] | Within-field AUROC [95 % CI] | Review to catch 80 % | 90 % | 95 % |",
                "|---|---|---|---|---|---|"]
        for name, d in sig.items():
            if name.startswith("_"):
                continue
            t = d["triage"]
            wf = fmt_ci(d["within_field"], "auroc") if d.get("within_field") else "-"
            out.append(f"| {name} | {fmt_ci(d, 'auroc')} | {wf} | {t['0.8']:.3f} | {t['0.9']:.3f} | {t['0.95']:.3f} |")
        fields = [f for f in FIELDS if any(f in d.get("per_field", {}) for k, d in sig.items() if not k.startswith("_"))]
        out += ["", "AUROC per field (point estimates; CIs in results.json):", "",
                "| Signal | " + " | ".join(fields) + " |", "|---|" + "---|" * len(fields)]
        for name, d in sig.items():
            if not name.startswith("_"):
                pf = d.get("per_field", {})
                out.append(f"| {name} | " + " | ".join(f"{pf[f]['auroc']:.3f}" if f in pf else "-" for f in fields) + " |")
        out.append("")
    if res.get("n_no_span"):
        out.append("Items without a value span (no log-probs, no activations; maximal doubt for single signals, "
                   "median imputation + missing indicator in the combined score): "
                   + ", ".join(f"{NAMES.get(s, s)} test {n['test']} / train+dev {n['train'] + n['dev']}"
                               for s, n in res["n_no_span"].items()))
    if res.get("h2"):
        h = res["h2"]
        out.append(f"**H2** combined − best single ({h['best_single']}): {h['diff']:+.3f} "
                   f"[{h['ci'][0]:+.3f}, {h['ci'][1]:+.3f}] → {'supported' if h['supported'] else 'not supported'}")
    if res.get("h3"):
        h = res["h3"]
        out.append(f"**H3** probe A AUROC {h['auroc']:.3f} [{h['ci'][0]:.3f}, {h['ci'][1]:.3f}] → "
                   f"{'supported' if h['supported'] else 'not supported'}")
    if res.get("position_b_vs_a"):
        h = res["position_b_vs_a"]
        out.append(f"Position B − A (probe AUROC): {h['diff']:+.3f} [{h['ci'][0]:+.3f}, {h['ci'][1]:+.3f}]")
    if res.get("chf"):
        k = f"share_gt_{CHF_THRESHOLD}"
        out += ["", "## Consequence: CHF mis-reported per page (sum of |pred − gold| over the 4 amounts; missing = whole "
                "amount)", "", f"| System | Median CHF [95 % CI] | Mean CHF [95 % CI] | Pages with error > {CHF_THRESHOLD} CHF "
                "[95 % CI] | Pages with any error |", "|---|---|---|---|---|"]
        for s, c in res["chf"].items():
            out.append(f"| {NAMES.get(s, s)} | {c['median']:.2f} [{c['median_ci'][0]:.2f}, {c['median_ci'][1]:.2f}] | "
                       f"{c['mean']:.2f} [{c['mean_ci'][0]:.2f}, {c['mean_ci'][1]:.2f}] | {c[k]:.3f} [{c[k + '_ci'][0]:.3f}, "
                       f"{c[k + '_ci'][1]:.3f}] | {c['share_any']:.3f} |")
    if res.get("costs"):
        c = res["costs"]
        out += ["", f"## Cost per page, {c['hardware']} ({c['unit']})", "", "| Stage | Pages | Mean | Median | p95 |",
                "|---|---|---|---|---|"]
        for stage, d in c["stages"].items():
            if d.get("n_pages"):
                name = f"**{stage}** ({' + '.join(d['components'])})" if "components" in d else stage
                out.append(f"| {name} | {d['n_pages']} | {d['mean']:.3f} | {d['median']:.3f} | {d['p95']:.3f} |")
    if res.get("explain"):
        e = res["explain"]
        out += ["", "**Explanations**: " + ", ".join(f"{k} {v:.3f}" if isinstance(v, float) else f"{k} {v}"
                                                   for k, v in e.items() if isinstance(v, (str, int, float)))]
    for s, br in res.get("breakdown", {}).items():
        out += ["", f"## Breakdown, {NAMES.get(s, s)}", "", "| Group | Value | Accuracy [95 % CI] | Items |", "|---|---|---|---|"]
        for by in ("degradation", "layout", "layout_group", "language", "field"):
            for g, d in br[by].items():
                g = f"{g} ({', '.join(d['layouts'])})" if "layouts" in d else g
                out.append(f"| {by} | {g} | {fmt_ci(d)} | {d['n']} |")
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--boot", type=int, default=10_000)
    args = ap.parse_args(argv)
    data, t0 = Path(args.data), time.time()
    res, _ = evaluate(data, args.boot)
    out = data / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    md = table(res)
    (out / "table.md").write_text(md)
    try:
        from .figures import plot
        plot(res, out)
    except ImportError as e:
        print(f"figures skipped ({e})")
    print(md)
    print(f"run.py done in {time.time() - t0:.1f} s -> {out}")
    return res


if __name__ == "__main__":
    main()
