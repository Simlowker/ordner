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

from .metrics import FIELDS, auroc, read_jsonl, triage_share
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


def load(data):
    items = read_jsonl(data / "items.jsonl")
    col = {k: np.array([it[k] for it in items], dtype=object) for k in
           ("system", "split", "stmt_id", "page_id", "field", "layout", "degradation", "language")}
    col["degradation"] = col["degradation"].astype(int)
    col["correct"] = np.array([bool(it["correct"]) for it in items])
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
        """Resampled AUROC (Mann-Whitney, ties = 1/2) for all B resamples. Weights depend only on the cluster, so
        AUROC_b = w_b' A w_b / ((w_b . n_pos)(w_b . n_neg)) with A[k, l] = concordant (pos in k, neg in l) pairs."""
        cl, k, y = self.idx(clusters), len(self.keys), np.asarray(y, bool)
        _, g = np.unique(score, return_inverse=True)
        P, N = np.zeros((k, g.max() + 1)), np.zeros((k, g.max() + 1))
        np.add.at(P, (cl[y], g[y]), 1)
        np.add.at(N, (cl[~y], g[~y]), 1)
        A = P @ (np.cumsum(N, axis=1) - 0.5 * N).T
        W = self.W.astype(np.float64)
        with np.errstate(invalid="ignore", divide="ignore"):
            return ((W @ A) * W).sum(1) / ((W @ P.sum(1)) * (W @ N.sum(1)))


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
    if (data / "costs.json").exists():
        res["costs"] = json.loads((data / "costs.json").read_text())
    if not test.any():
        res["note"] = "no test items"
        return res, col
    boot = Boot(col["stmt_id"][test], n=n_boot)
    res["bootstrap"]["clusters"] = len(boot.keys)

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
        br = {}
        for by in ("degradation", "layout", "field", "language"):
            br[by] = {}
            for g in sorted(set(col[by][m])):
                mg = m & (col[by] == g)
                br[by][str(g)] = {"acc": float(col["correct"][mg].mean()), "n": int(mg.sum()),
                                  "ci": ci(boot.ratio(col["stmt_id"][mg], col["correct"][mg]))}
        br["layout_degradation"] = {}
        for lay in sorted(set(col["layout"][m])):
            for d in sorted(set(col["degradation"][m])):
                mg = m & (col["layout"] == lay) & (col["degradation"] == d)
                if mg.any():
                    br["layout_degradation"][f"{lay}{d}"] = {
                        "acc": float(col["correct"][mg].mean()), "n": int(mg.sum()),
                        "ci": ci(boot.ratio(col["stmt_id"][mg], col["correct"][mg]))}
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

    # Doubt signals
    res["doubt"], res["curves"] = {}, {}
    fit_base = (col["system"] == "apertus-base") & np.isin(col["split"], ["train", "dev"])
    test_base = test & (col["system"] == "apertus-base")
    extra = {}
    if test_base.any():
        for pos in ("A", "B"):
            sc, info = probe_scores(col, probes, pos, fit_base, test_base)
            if info:
                extra[f"probe {pos}"] = sc
                res.setdefault("probe", {})[pos] = info
        X = np.column_stack([col[c] for c in COMBO_COLS] + ([extra["probe A"]] if "probe A" in extra else []))
        y_fit = ~col["correct"][fit_base]
        if fit_base.any() and 0 < y_fit.sum() < len(y_fit):
            model, C, cvs = fit_select(X[fit_base], y_fit, col["stmt_id"][fit_base], combo_model)
            extra["combined"] = np.full(len(X), np.nan)
            extra["combined"][test_base] = model.predict_proba(X[test_base])[:, 1]
            res["combined"] = {"system": "apertus-base", "fit_on": "train+dev", "C": C, "cv_auc": cvs,
                               "features": COMBO_COLS + (["probe A (out-of-fold)"] if "probe A" in extra else [])}
    fit_lora = (col["system"] == "apertus-lora") & (col["split"] == "dev")
    test_lora = test & (col["system"] == "apertus-lora")
    extra_lora = {}
    y_dev = ~col["correct"][fit_lora]
    if test_lora.any() and fit_lora.sum() and 0 < y_dev.sum() < len(y_dev):
        X = np.column_stack([col[c] for c in COMBO_COLS])
        model, C, cvs = fit_select(X[fit_lora], y_dev, col["stmt_id"][fit_lora], combo_model)
        extra_lora["combined (no probe)"] = np.full(len(X), np.nan)
        extra_lora["combined (no probe)"][test_lora] = model.predict_proba(X[test_lora])[:, 1]
        res["combined_lora"] = {"system": "apertus-lora", "fit_on": "dev", "C": C, "cv_auc": cvs, "features": COMBO_COLS}

    boot_auc = {}
    for s in systems:
        m = test & (col["system"] == s)
        if not m.any():
            continue
        y = ~col["correct"][m]
        if y.min() == y.max():
            res["doubt"][s] = {"note": "single class on test"}
            continue
        cl = col["stmt_id"][m]
        scores = {}
        for name in SINGLE:
            sc, n_missing = doubt_score(col, name, m)
            if sc is not None:
                scores[name] = (sc, n_missing)
        for name, sc in {**(extra if s == "apertus-base" else {}), **(extra_lora if s == "apertus-lora" else {})}.items():
            v = sc[m]
            if not np.isnan(v).all():
                scores[name] = (np.where(np.isnan(v), np.nanmax(v) + 1, v), int(np.isnan(v).sum()))
        res["doubt"][s] = {}
        for name, (sc, n_missing) in scores.items():
            vals = boot.auroc(cl, y, sc)
            boot_auc[(s, name)] = vals
            res["doubt"][s][name] = {"auroc": auroc(y, sc), "ci": ci(vals), "n_missing": n_missing,
                                     "triage": {str(c): triage_share(y, sc, c) for c in CATCH}}
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
        out += ["## Extraction: field-level exact match", "",
                "| System | Field accuracy | Page fully correct | Layout A (seen) | Layout B (unseen) | Items |",
                "|---|---|---|---|---|---|"]
        for s, a in acc.items():
            lay = res["breakdown"][s]["layout"]
            out.append(f"| {NAMES.get(s, s)} | {fmt_ci(a)} | {a['page_all_ok']:.3f} [{a['page_all_ok_ci'][0]:.3f}, "
                       f"{a['page_all_ok_ci'][1]:.3f}] | {fmt_ci(lay['A']) if 'A' in lay else '-'} | "
                       f"{fmt_ci(lay['B']) if 'B' in lay else '-'} | {a['n_items']} |")
        out.append("")
        if res.get("h1"):
            h = res["h1"]
            out += [f"**H1** LoRA − zero-shot accuracy: {h['diff']:+.3f} [{h['ci'][0]:+.3f}, {h['ci'][1]:+.3f}] "
                    f"({h['n_items_paired']} paired items) → {'supported' if h['supported'] else 'not supported'}", ""]
    for s, sig in res.get("doubt", {}).items():
        if "note" in sig:
            continue
        n = sig["_n"]
        out += [f"## Doubt signals, {NAMES.get(s, s)}: AUROC for \"field is wrong\" ({n['wrong']} wrong / {n['items']})",
                "", "| Signal | AUROC [95 % CI] | Review to catch 80 % | 90 % | 95 % |", "|---|---|---|---|---|"]
        for name, d in sig.items():
            if name.startswith("_"):
                continue
            t = d["triage"]
            out.append(f"| {name} | {fmt_ci(d, 'auroc')} | {t['0.8']:.3f} | {t['0.9']:.3f} | {t['0.95']:.3f} |")
        out.append("")
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
    if res.get("costs"):
        c = res["costs"]
        out += ["", f"## Cost per page, {c['hardware']} ({c['unit']})", "", "| Stage | Pages | Mean | Median | p95 |",
                "|---|---|---|---|---|"]
        for stage, d in c["stages"].items():
            if d.get("n_pages"):
                name = f"**{stage}** ({' + '.join(d['components'])})" if "components" in d else stage
                out.append(f"| {name} | {d['n_pages']} | {d['mean']:.3f} | {d['median']:.3f} | {d['p95']:.3f} |")
    for s, br in res.get("breakdown", {}).items():
        out += ["", f"## Breakdown, {NAMES.get(s, s)}", "", "| Group | Value | Accuracy [95 % CI] | Items |", "|---|---|---|---|"]
        for by in ("degradation", "layout", "language", "field"):
            for g, d in br[by].items():
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
