"""Hidden-state probe features for apertus-base: per position (A = value tokens, B = token before), choose the layer
and C by grouped CV (groups = stmt_id) on train+dev, fit scaler + PCA on train items only, write
data/probe/{A,B}.npz.  python -m ordner.eval.probe --work work --data data"""

import argparse
import time
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .metrics import read_jsonl

SYSTEM = "apertus-base"
CS = (0.001, 0.01, 0.1, 1.0)
N_COMPONENTS = 256


def probe_model(C):
    return make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=2000))


def load_acts(acts_dir, items, idx, pos, layer_i=None):
    """Stack activations of items[idx] at one position -> (kept item indices, array [n, L, H] or [n, H])."""
    keep, rows, log, cache_pid, npz = [], [], Counter(), None, None
    for i in idx:
        it = items[i]
        if it["page_id"] != cache_pid:
            cache_pid = it["page_id"]
            path = acts_dir / f"{cache_pid}.npz"
            npz = np.load(path) if path.exists() else None
        k = f"{it['field']}_{pos}"
        if npz is None:
            log["no npz for page"] += 1
            continue
        if k not in npz.files:
            log[f"no {k}"] += 1
            continue
        a = npz[k]
        rows.append((a if layer_i is None else a[layer_i]).astype(np.float16 if np.abs(a).max() < 65000 else np.float32))
        keep.append(i)
    return np.array(keep, dtype=np.int64), (np.stack(rows) if rows else None), log


def fit_pca(x_train, n_components):
    scaler = StandardScaler().fit(x_train)
    pca = PCA(n_components, random_state=0).fit(scaler.transform(x_train))
    # Fold the scaler into the projection: X = (x - mean) @ components.T
    mean = scaler.mean_ + scaler.scale_ * pca.mean_
    comps = pca.components_ / scaler.scale_
    return mean.astype(np.float32), comps.astype(np.float32)


def project(x, mean, comps):
    return (np.asarray(x, np.float32) - mean) @ comps.T


def run(work, data, system=SYSTEM):
    work, data = Path(work), Path(data)
    items = read_jsonl(data / "items.jsonl")
    acts_dir = work / "acts" / system
    base = [i for i, it in enumerate(items) if it["system"] == system]
    print(f"{system}: {len(base)} items, acts dir {acts_dir}")
    if not base or not acts_dir.exists():
        print("nothing to do (no items or no activations)")
        return {}
    out = {}
    for pos in ("A", "B"):
        t0 = time.time()
        fit_idx = [i for i in base if items[i]["split"] in ("train", "dev")]
        keep, acts, log = load_acts(acts_dir, items, fit_idx, pos)
        for k, n in sorted(log.items()):
            print(f"  [{pos}] train+dev items excluded, {k}: {n}")
        if acts is None:
            print(f"  [{pos}] no activations for train+dev")
            continue
        layers = list(np.load(next(acts_dir.glob("*.npz")))["layers"])
        y = np.array([not items[i]["correct"] for i in keep], int)
        groups = np.array([items[i]["stmt_id"] for i in keep])
        is_train = np.array([items[i]["split"] == "train" for i in keep])
        print(f"  [{pos}] fit items: {len(keep)} (train {is_train.sum()}, dev {(~is_train).sum()}), wrong {y.sum()}")
        if y.min() == y.max():
            print(f"  [{pos}] single class, skipped")
            continue
        n_comp = min(N_COMPONENTS, int(is_train.sum()), acts.shape[-1])
        cv = GroupKFold(n_splits=5)
        auc = np.full((len(layers), len(CS)), np.nan)
        for li in range(len(layers)):
            mean, comps = fit_pca(acts[is_train, li].astype(np.float32), n_comp)
            z = project(acts[:, li], mean, comps)
            for ci, C in enumerate(CS):
                auc[li, ci] = cross_val_score(probe_model(C), z, y, groups=groups, cv=cv, scoring="roc_auc").mean()
            print(f"  [{pos}] layer {layers[li]:2d}: CV AUROC " + " ".join(f"C={C}:{a:.3f}" for C, a in zip(CS, auc[li])))
        li, ci = np.unravel_index(np.nanargmax(auc), auc.shape)
        mean, comps = fit_pca(acts[is_train, li].astype(np.float32), n_comp)
        del acts
        all_keep, x, log = load_acts(acts_dir, items, base, pos, layer_i=li)
        for k, n in sorted(log.items()):
            print(f"  [{pos}] items without activations (all splits), {k}: {n}")
        X = project(x, mean, comps).astype(np.float16)
        (data / "probe").mkdir(parents=True, exist_ok=True)
        np.savez(data / "probe" / f"{pos}.npz", X=X, item_idx=all_keep, layer=int(layers[li]), C=CS[ci],
                 pca_mean=mean, pca_components=comps, cv_auc=auc, layers=np.array(layers), Cs=np.array(CS))
        out[pos] = {"layer": int(layers[li]), "C": CS[ci], "cv_auc": float(auc[li, ci]), "n": len(all_keep)}
        print(f"  [{pos}] selected layer {layers[li]} C={CS[ci]} (CV AUROC {auc[li, ci]:.3f}); "
              f"X {X.shape} -> {data / 'probe' / f'{pos}.npz'} ({time.time() - t0:.0f}s)")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="work")
    ap.add_argument("--data", default="data")
    args = ap.parse_args(argv)
    run(args.work, args.data)


if __name__ == "__main__":
    main()
