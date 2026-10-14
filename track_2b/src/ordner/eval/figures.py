"""Figures from results.json (numpy + matplotlib only).  python -m ordner.eval.figures data/results/results.json"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
SYSTEM_COLOR = {"regex": SERIES[0], "apertus-base": SERIES[1], "apertus-lora": SERIES[2]}
NAMES = {"regex": "OCR + regex", "apertus-base": "Apertus zero-shot", "apertus-lora": "Apertus + LoRA"}
FIELD_ORDER = ["totalTaxValue", "totalGrossRevenueA", "totalGrossRevenueB", "totalWithHoldingTaxClaim", "institution",
               "canton", "taxPeriod", "client_last_name"]
CURVE_SIGNALS = ["min token prob", "mean entropy", "d1 validation", "rules", "probe A", "combined"]


def _style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.xaxis.label.set_color(INK2)
    ax.yaxis.label.set_color(INK2)
    ax.title.set_color(INK)


def _fig(w, h, n=1):
    fig, axes = plt.subplots(1, n, figsize=(w, h), facecolor=SURFACE, squeeze=False)
    for ax in axes[0]:
        _style(ax)
    return fig, axes[0]


def _err(d):
    lo, hi = d["ci"]
    return (d["acc"] - lo, hi - d["acc"]) if lo is not None else (0, 0)


def accuracy_by_degradation(res, out):
    br = res.get("breakdown", {})
    layouts = sorted({k[0] for s in br.values() for k in s.get("layout_degradation", {})})
    if not layouts:
        return
    fig, axes = _fig(4.2 * len(layouts), 3.4, len(layouts))
    for ax, lay in zip(axes, layouts):
        for s, b in br.items():
            pts = sorted((int(k[1:]), v) for k, v in b["layout_degradation"].items() if k[0] == lay)
            if not pts:
                continue
            x = [p[0] for p in pts]
            y = [p[1]["acc"] for p in pts]
            e = list(zip(*[_err(p[1]) for p in pts]))
            ax.errorbar(x, y, yerr=e, color=SYSTEM_COLOR.get(s, INK2), linewidth=2, marker="o", markersize=6,
                        capsize=3, label=NAMES.get(s, s))
        ax.set_title(f"Layout {lay} ({'seen in training' if lay == 'A' else 'never seen'})", fontsize=10)
        ax.set_xticks([0, 1, 2, 3])
        ax.set_xlabel("Degradation level")
        ax.set_ylim(0, 1.02)
    axes[0].set_ylabel("Field accuracy (test)")
    axes[0].legend(frameon=False, fontsize=8, labelcolor=INK)
    fig.tight_layout()
    fig.savefig(out / "accuracy_by_degradation.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


def accuracy_by_field(res, out):
    br = res.get("breakdown", {})
    if not br:
        return
    systems = list(br)
    seen = next(iter(br.values()))["field"]
    fields = [f for f in FIELD_ORDER if f in seen] + [f for f in seen if f not in FIELD_ORDER]
    fig, (ax,) = _fig(6.5, 0.45 * len(fields) * len(systems) / 2 + 1.2)
    h = 0.8 / len(systems)
    for i, s in enumerate(systems):
        f = br[s]["field"]
        ys = [j + i * h for j in range(len(fields))]
        vals = [f[k]["acc"] if k in f else 0 for k in fields]
        errs = list(zip(*[_err(f[k]) if k in f else (0, 0) for k in fields]))
        ax.barh(ys, vals, height=h - 0.03, xerr=errs, color=SYSTEM_COLOR.get(s, INK2), label=NAMES.get(s, s),
                error_kw={"ecolor": INK2, "elinewidth": 1, "capsize": 2})
    ax.set_yticks([j + 0.4 - h / 2 for j in range(len(fields))])
    ax.set_yticklabels(fields)
    ax.invert_yaxis()
    ax.set_xlim(0, 1.0)
    ax.set_xlabel("Field accuracy (test)")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK, loc="lower center", bbox_to_anchor=(0.5, 1.0),
              ncol=len(systems))
    fig.tight_layout()
    fig.savefig(out / "accuracy_by_field.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


def accuracy_by_layout(res, out):
    br = res.get("breakdown", {})
    if not br:
        return
    unseen = sorted({lay for b in br.values() for lay in b["layout"] if lay != "A"})
    cats = [("A (seen)", "layout", "A")] + [(lay, "layout", lay) for lay in unseen]
    if len(unseen) > 1:
        cats.append((" ∪ ".join(unseen) + " (unseen)", "layout_group", "unseen"))
    systems = list(br)
    fig, (ax,) = _fig(1.6 * len(cats) + 2.2, 3.6)
    w = 0.8 / len(systems)
    for i, s in enumerate(systems):
        ds = [br[s][by].get(k) for _, by, k in cats]
        xs = [j + (i - (len(systems) - 1) / 2) * w for j in range(len(cats))]
        ax.bar(xs, [d["acc"] if d else 0 for d in ds], width=w - 0.03, color=SYSTEM_COLOR.get(s, INK2),
               yerr=list(zip(*[_err(d) if d else (0, 0) for d in ds])), label=NAMES.get(s, s),
               error_kw={"ecolor": INK2, "elinewidth": 1, "capsize": 2})
    ax.set_xticks(range(len(cats)))
    ax.set_xticklabels([c[0] for c in cats])
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Field accuracy (test)")
    ax.set_xlabel("Layout")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK, loc="lower center", bbox_to_anchor=(0.5, 1.0),
              ncol=len(systems))
    fig.tight_layout()
    fig.savefig(out / "accuracy_by_layout.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


def triage_curves(res, out):
    curves = res.get("curves", {})
    names = [n for n in CURVE_SIGNALS if n in curves]
    if not names:
        return
    fig, (ax,) = _fig(4.8, 4.2)
    ax.plot([0, 1], [0, 1], color=INK2, linewidth=1, linestyle="--", label="random order")
    for i, n in enumerate(names):
        x, y = zip(*curves[n])
        auc = res["doubt"]["apertus-base"][n]["auroc"]
        ax.plot(x, y, color=SERIES[i], linewidth=2, label=f"{n} (AUROC {auc:.2f})")
    for c in (0.8, 0.9, 0.95):
        ax.axhline(c, color=GRID, linewidth=1)
    ax.set_xlabel("Share of fields sent to human review")
    ax.set_ylabel("Share of extraction errors caught")
    ax.set_title("Triage, Apertus zero-shot (test)", fontsize=10)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.01)
    ax.legend(frameon=False, fontsize=7.5, labelcolor=INK, loc="lower right")
    fig.tight_layout()
    fig.savefig(out / "triage_curves.png", dpi=160, facecolor=SURFACE)
    plt.close(fig)


def plot(res, out):
    out = Path(out)
    accuracy_by_degradation(res, out)
    accuracy_by_layout(res, out)
    accuracy_by_field(res, out)
    triage_curves(res, out)


if __name__ == "__main__":
    p = Path(sys.argv[1] if len(sys.argv) > 1 else "data/results/results.json")
    plot(json.loads(p.read_text()), p.parent)
    print(f"figures written to {p.parent}")
