'''
Figures for the soundness and preservation results (Experiment 1).

Reads the CSVs written by soundness_roa.py and writes a vector PDF sized for
the thesis text block, so it can be included at \\textwidth with no scaling.

    python soundness_plots.py --nested soundness_nested_minimal.csv \\
                              --deep soundness_deep_minimal.csv --out figures/

soundness_outcomes.pdf splits the pooled states of every arm into the outcomes
of the membership test. Shares are pooled over all problems, so each bar is
(state count with that outcome) / (total pooled states).

soundness_tradeoff.pdf plots each arm's share of solvable states solved
against its node ratio. Its denominator is the solvable states only, the
pooled states from which any plan reaches the goal.
'''
import argparse
import csv
import math
import os
import random
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch


# Thesis geometry: \the\textwidth = 433.62pt, 72.27pt per inch
TEXTWIDTH_IN = 433.62 / 72.27

plt.rcParams.update({
    "font.size": 10,
    "axes.titlesize": 10,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": "#6b6b66",
    "axes.linewidth": 0.6,
    "xtick.color": "#4a4a46",
    "ytick.color": "#4a4a46",
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "grid.color": "#e4e3dd",
    "grid.linewidth": 0.5,
    "axes.axisbelow": True,
})

if shutil.which("latex"):
    plt.rcParams.update({"text.usetex": True, "font.family": "serif",
                         "font.serif": ["Computer Modern Roman"]})
else:
    # Bundled CM glyphs; close to the thesis font without a TeX install
    plt.rcParams.update({"text.usetex": False, "font.family": "serif",
                         "font.serif": ["cmr10"], "mathtext.fontset": "cm",
                         "axes.formatter.use_mathtext": True})

INK, MUTED = "#2b2b28", "#8c8b84"

# Validated colourblind-safe set. Failure is a neutral grey because it is the
# honest outcome, so the two coloured bands are the ones that need attention.
OUTCOMES = [
    # (label, colour, text colour inside the bar)
    ("Member",          "#2a78d6", "white"),
    ("Honest failure",  "#bdbcb5", INK),
    ("Violation",       "#eb6834", "white"),
    ("Cycle",           "#1baf7a", "white"),
]

# Bars from top to bottom. The reference sits on top so every arm reads
# against it.
BARS = [("dnf", "DNF reference"),
        ("unified", "Unified, off"),
        ("protect_l", "Unified, left"),
        ("protect_s", "Unified, symmetric")]

ARM_COLUMNS = {"Member": "solved", "Honest failure": "failure",
               "Violation": "violations", "Cycle": "cycle"}
REF_COLUMNS = {"Honest failure": "ref_failure", "Violation": "ref_violations",
               "Cycle": "ref_cycle"}

LABEL_MIN = 0.07        # Only print a share inside a segment at least this wide


def loadShares(path):
    rows = list(csv.DictReader(open(path)))

    missing = [c for c in REF_COLUMNS.values() if c not in rows[0]]
    if missing:
        raise ValueError(f"{path} lacks {missing}; rerun soundness_roa.py with the reference columns")

    # Every arm is scored on the same pools, so the unified rows give the total
    ref_rows = [r for r in rows if r["arm"] == "unified"]
    pool = sum(int(r["pool_size"]) for r in ref_rows)

    shares = {}

    for arm, _ in BARS:
        if arm == "dnf":
            counts = {"Member": sum(int(r["both"]) + int(r["ref_only"]) for r in ref_rows)}
            counts.update({k: sum(int(r[c]) for r in ref_rows) for k, c in REF_COLUMNS.items()})
        else:
            arm_rows = [r for r in rows if r["arm"] == arm]
            counts = {k: sum(int(r[c]) for r in arm_rows) for k, c in ARM_COLUMNS.items()}
            if sum(int(r["cap"]) for r in arm_rows):
                raise ValueError(f"{arm} has capped states, which this figure does not show")

        if sum(counts.values()) != pool:
            raise ValueError(f"{arm} outcomes do not sum to the pool ({sum(counts.values())} vs {pool})")

        shares[arm] = {k: v / pool for k, v in counts.items()}

    problems = len({r["problem_id"] for r in rows})
    return shares, problems, pool


def drawPanel(ax, shares, title):
    for row, (arm, _) in enumerate(BARS):
        left = 0.0

        for label, colour, text_colour in OUTCOMES:
            width = shares[arm][label]
            if width <= 0:
                continue

            ax.barh(row, width, left=left, height=0.62, color=colour,
                    edgecolor="white", linewidth=0.8)

            if width >= LABEL_MIN:
                ax.text(left + width / 2, row, f"{100 * width:.1f}",
                        ha="center", va="center", fontsize=8, color=text_colour)

            left += width

    ax.set_ylim(len(BARS) - 0.5, -0.5)          # First bar on top
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", "25", "50", "75", "100"])
    ax.set_xlabel(r"Share of pooled states (\%)" if plt.rcParams["text.usetex"]
                  else "Share of pooled states (%)")
    ax.set_title(title, color=INK)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)


def outcomeFigure(nested_path, deep_path, out_path):
    nested, n_nested, _ = loadShares(nested_path)
    deep, n_deep, _ = loadShares(deep_path)

    fig, ax = plt.subplots(1, 2, figsize=(TEXTWIDTH_IN, 2.5), sharey=True)
    fig.subplots_adjust(left=0.19, right=0.985, bottom=0.18, top=0.78, wspace=0.13)

    drawPanel(ax[0], nested, f"Nested goals ($n={n_nested}$)")
    drawPanel(ax[1], deep, f"Deep goals ($n={n_deep}$)")

    ax[0].set_yticks(range(len(BARS)))
    ax[0].set_yticklabels([name for _, name in BARS])

    handles = [Patch(facecolor=c, edgecolor="none", label=l) for l, c, _ in OUTCOMES]
    fig.legend(handles=handles, loc="upper center", ncol=len(OUTCOMES),
               frameon=False, bbox_to_anchor=(0.58, 1.0), handlelength=1.2,
               columnspacing=1.4)

    fig.savefig(out_path)
    plt.close(fig)


# Arms on the coverage figure: (arm, label, colour, marker)
TRADEOFF_ARMS = [("unified", "Off", "#eb6834", "o"),
                 ("protect_l", "Left", "#2a78d6", "s"),
                 ("protect_s", "Symmetric", "#1baf7a", "D")]

BOOTSTRAP = 2000        # Resamples of problems for the 95% intervals


def tradeoffStats(path, seed=0):
    # Per arm: geometric-mean node ratio and pooled coverage of solvable states,
    # each with a 95% interval from resampling whole problems
    rows = list(csv.DictReader(open(path)))

    if "solvable" not in rows[0]:
        raise ValueError(f"{path} lacks the solvable column; rerun soundness_roa.py")

    rng = random.Random(seed)       # Separate stream, so the intervals are reproducible
    stats = {}

    for arm, *_ in TRADEOFF_ARMS:
        per = [(int(r["solved"]), int(r["solvable"]), math.log(float(r["node_ratio"])))
               for r in rows if r["arm"] == arm]

        def coverage(sample):
            return sum(s for s, _, _ in sample) / sum(t for _, t, _ in sample)

        def geoMean(sample):
            return math.exp(sum(lg for _, _, lg in sample) / len(sample))

        boot_cov, boot_gm = [], []
        for _ in range(BOOTSTRAP):
            sample = [per[rng.randrange(len(per))] for _ in per]
            boot_cov.append(coverage(sample))
            boot_gm.append(geoMean(sample))

        boot_cov.sort()
        boot_gm.sort()
        lo, hi = int(0.025 * BOOTSTRAP), int(0.975 * BOOTSTRAP) - 1

        stats[arm] = {"ratio": geoMean(per), "ratio_ci": (boot_gm[lo], boot_gm[hi]),
                      "coverage": coverage(per), "coverage_ci": (boot_cov[lo], boot_cov[hi])}

    return stats


def drawTradeoffPanel(ax, stats, title, label_left=()):
    # Reference point: DNF covers every solvable state at its own size
    ax.axhline(100, color=MUTED, lw=0.7, ls=":", zorder=1)
    ax.axvline(1, color=MUTED, lw=0.7, ls=":", zorder=1)
    ax.plot(1, 100, "*", ms=9, color=INK, zorder=3)
    ax.annotate("DNF", (1, 100), xytext=(-7, -4), textcoords="offset points",
                fontsize=8.5, color=INK, ha="right", va="top")

    for arm, label, colour, marker in TRADEOFF_ARMS:
        s = stats[arm]
        x, (x_lo, x_hi) = s["ratio"], s["ratio_ci"]
        y, (y_lo, y_hi) = 100 * s["coverage"], [100 * v for v in s["coverage_ci"]]

        ax.errorbar(x, y, xerr=[[x - x_lo], [x_hi - x]], yerr=[[y - y_lo], [y_hi - y]],
                    fmt=marker, ms=5.5, color=colour, mec="white", mew=0.6,
                    ecolor=colour, elinewidth=0.9, capsize=0, zorder=3)

        left = arm in label_left
        ax.annotate(label, (x, y), xytext=(-7 if left else 7, 3), textcoords="offset points",
                    fontsize=8.5, color=INK, ha="right" if left else "left")

    ax.set_xscale("log")
    ax.set_xlim(0.7, 14)
    ax.set_xticks([1, 2, 4, 8])
    ax.set_xticklabels(["1", "2", "4", "8"])
    ax.minorticks_off()
    ax.set_ylim(35, 105)
    ax.grid(axis="both")
    ax.set_title(title, color=INK)
    ax.set_xlabel("Node ratio (DNF/arm), geometric mean")


def tradeoffFigure(nested_path, deep_path, out_path):
    nested, deep = tradeoffStats(nested_path), tradeoffStats(deep_path)

    fig, ax = plt.subplots(1, 2, figsize=(TEXTWIDTH_IN, 2.7), sharey=True)
    fig.subplots_adjust(left=0.1, right=0.985, bottom=0.17, top=0.9, wspace=0.12)

    drawTradeoffPanel(ax[0], nested, "Nested goals")
    drawTradeoffPanel(ax[1], deep, "Deep goals", label_left=("protect_s",))

    ax[0].set_ylabel(r"Solvable states solved (\%)" if plt.rcParams["text.usetex"]
                     else "Solvable states solved (%)")

    fig.savefig(out_path)
    plt.close(fig)

    # Values for the text, so they are quoted from the same computation
    for shape, stats in (("nested", nested), ("deep", deep)):
        for arm, label, *_ in TRADEOFF_ARMS:
            s = stats[arm]
            print(f"{shape:6} {label:9} node ratio {s['ratio']:.2f} "
                  f"[{s['ratio_ci'][0]:.2f}, {s['ratio_ci'][1]:.2f}]  "
                  f"coverage {s['coverage']:.1%} "
                  f"[{s['coverage_ci'][0]:.1%}, {s['coverage_ci'][1]:.1%}]")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--nested", default="soundness_nested_minimal.csv")
    parser.add_argument("--deep", default="soundness_deep_minimal.csv")
    parser.add_argument("--out", default=".")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    outcomeFigure(args.nested, args.deep, os.path.join(args.out, "soundness_outcomes.pdf"))
    tradeoffFigure(args.nested, args.deep, os.path.join(args.out, "soundness_tradeoff.pdf"))


if __name__ == "__main__":
    main()