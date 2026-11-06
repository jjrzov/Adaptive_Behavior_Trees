'''
Figures for the compactness results (Experiment 2).

Reads the CSVs written by depth_roa.py and writes vector PDFs sized for the
thesis text block, so they can be included at their natural width with no
scaling and the fonts match the body text.

    python plot_compactness.py --sweep thesis_compactness.csv --grid grid_dk.csv --out figures/

With --slides it instead writes transparent PNGs sized for a 16:9 slide, with
the two rows of the sweep figure split into separate figures:

    python compactness_plots.py --sweep compactness.csv --slides --out slides/

    compactness_counts.png  node counts of both arms (upper row of Figure 5.1)
    compactness_ratio.png   node ratio against its ceiling (lower row)

Both figures plot total node counts, the tree-size metric of Cai et al. (2021).
The curves are the exact closed forms, checked against every row on load:

    unified  N_u = 4(d+1) + 2k(2m+1)
    DNF      N_d = k(4(d+1)(m+1) - 2) + 1
'''
import argparse
import csv
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm


# Thesis geometry: \the\textwidth = 433.62pt, 72.27pt per inch
TEXTWIDTH_IN = 433.62 / 72.27

plt.rcParams.update({
    "text.usetex": True,
    "font.family": "serif",
    "font.serif": ["Computer Modern Roman"],
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

# Validated colourblind-safe pair; marker shape carries identity in greyscale
UNIFIED, DNF = "#2a78d6", "#eb6834"
INK, MUTED = "#2b2b28", "#8c8b84"

# Mark sizes and annotation size. The thesis values are the defaults; --slides
# swaps in larger ones so the figure reads from the back of a room.
STYLE = {"lw": 1.0, "ms": 3.8, "ratio_ms": 3.2, "mew": 0.5, "ref_lw": 0.8, "note": 8}

# A 16:9 slide is 10 x 5.625 in, so a point on the figure is a point on the slide
SLIDE_FIGSIZE = (9.4, 3.9)
SLIDE_DPI = 300

BASE = {"chain_depth": 3, "branch_depth": 2, "n_branches": 2}
AXES = [("chain_depth", "d", "Chain depth"),
        ("branch_depth", "m", "Branch depth"),
        ("n_branches", "k", "Branch count")]


def useSlideStyle():
    # Sans text to match the deck, larger type and marks, no LaTeX dependency
    plt.rcParams.update({
        "text.usetex": False,
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "mathtext.fontset": "dejavusans",
        "font.size": 16,
        "axes.titlesize": 17,
        "axes.labelsize": 16,
        "xtick.labelsize": 14,
        "ytick.labelsize": 14,
        "legend.fontsize": 15,
        "axes.linewidth": 1.2,
        "xtick.major.width": 1.2,
        "ytick.major.width": 1.2,
        "xtick.major.size": 5,
        "ytick.major.size": 5,
        "grid.linewidth": 1.0,
        "savefig.transparent": True,
    })
    STYLE.update({"lw": 2.4, "ms": 9, "ratio_ms": 8, "mew": 1.0, "ref_lw": 1.6, "note": 14})


def nodesUnified(d, m, k):
    return 4 * (d + 1) + 2 * k * (2 * m + 1)


def nodesDNF(d, m, k):
    return k * (4 * (d + 1) * (m + 1) - 2) + 1


def ratioCeiling(axis, d, m, k):
    # Limit of N_d / N_u as the swept parameter grows with the other two fixed
    if axis == "chain_depth":
        return k * (m + 1), r"$k(m+1)$"
    if axis == "branch_depth":
        return d + 1, r"$d+1$"
    return (4 * (d + 1) * (m + 1) - 2) / (2 * (2 * m + 1)), r"$\frac{4(d+1)(m+1)-2}{2(2m+1)}$"


def loadRows(path):
    rows = list(csv.DictReader(open(path)))

    # Refuse to plot data the closed forms do not describe
    for r in rows:
        d, m, k = int(r["chain_depth"]), int(r["branch_depth"]), int(r["n_branches"])
        if (int(r["u_nodes"]), int(r["d_nodes"])) != (nodesUnified(d, m, k), nodesDNF(d, m, k)):
            raise ValueError(f"row ({d}, {m}, {k}) does not match the closed forms")
        if int(r["both"]) != int(r["pool_size"]):
            raise ValueError(f"row ({d}, {m}, {k}) does not have full ROA in both arms")

    return rows


def params(axis, value):
    p = dict(BASE)
    p[axis] = value
    return p["chain_depth"], p["branch_depth"], p["n_branches"]


def sweepData(rows, axis):
    # Measured points along one axis, and the closed forms on a fine grid
    pts = sorted((r for r in rows if r["axis"] == axis), key=lambda r: int(r[axis]))
    x = np.array([int(r[axis]) for r in pts])
    xs = np.linspace(x.min(), x.max(), 200)

    nu = np.array([nodesUnified(*params(axis, v)) for v in xs])
    nd = np.array([nodesDNF(*params(axis, v)) for v in xs])
    return pts, x, xs, nu, nd


def panelTitle(axis, sym):
    held = [f"${s}={BASE[a]}$" for a, s, _ in AXES if a != axis]
    return f"Vary ${sym}$ ({', '.join(held)})"


def setXTicks(ax, axis, x):
    ax.set_xticks([0, 10, 20, 30, 40] if axis == "chain_depth" else x)


def drawCounts(ax, axis, pts, x, xs, nu, nd):
    # Node counts, measured markers on closed-form curves
    ax.plot(xs, nd, color=DNF, lw=STYLE["lw"], zorder=1)
    ax.plot(xs, nu, color=UNIFIED, lw=STYLE["lw"], zorder=1)
    ax.plot(x, [int(r["d_nodes"]) for r in pts], "s", ms=STYLE["ms"], color=DNF,
            mec="white", mew=STYLE["mew"], label="DNF", zorder=2)
    ax.plot(x, [int(r["u_nodes"]) for r in pts], "o", ms=STYLE["ms"], color=UNIFIED,
            mec="white", mew=STYLE["mew"], label="Unified", zorder=2)
    ax.set_ylim(bottom=0)
    ax.grid(axis="y")


def drawRatio(ax, axis, pts, x, xs, nu, nd):
    # Node ratio against its single-axis ceiling
    ceil, _ = ratioCeiling(axis, BASE["chain_depth"], BASE["branch_depth"], BASE["n_branches"])
    ax.axhline(ceil, color=MUTED, lw=STYLE["ref_lw"], ls=(0, (4, 3)), zorder=1)
    ax.axhline(1, color=MUTED, lw=0.75 * STYLE["ref_lw"], ls=":", zorder=1)
    ax.plot(xs, nd / nu, color=INK, lw=STYLE["lw"], zorder=2)
    ax.plot(x, [float(r["node_ratio"]) for r in pts], "D", ms=STYLE["ratio_ms"], color=INK,
            mec="white", mew=0.8 * STYLE["mew"], zorder=3)
    ax.text(x.max(), ceil * 1.03, f"ceiling ${ceil:g}$",
            ha="right", va="bottom", fontsize=STYLE["note"], color=MUTED)
    ax.text(x.max(), 0.94, "equal size",
            ha="right", va="top", fontsize=STYLE["note"], color=MUTED)
    ax.set_ylim(0, ceil * 1.22)
    ax.grid(axis="y")


def sweepFigure(rows, out_path):
    fig, ax = plt.subplots(2, 3, figsize=(TEXTWIDTH_IN, 4.2), sharex="col", layout="constrained",
                           gridspec_kw={"height_ratios": [1.3, 1]})
    # Gap between the count row and the ratio row (API moved in matplotlib 3.6)
    if hasattr(fig, "get_layout_engine"):
        fig.get_layout_engine().set(hspace=0.09)
    else:
        fig.set_constrained_layout_pads(hspace=0.09)

    for col, (axis, sym, name) in enumerate(AXES):
        data = sweepData(rows, axis)

        top = ax[0, col]
        drawCounts(top, axis, *data)
        top.set_title(panelTitle(axis, sym), color=INK)

        bot = ax[1, col]
        drawRatio(bot, axis, *data)
        bot.set_xlabel(f"{name} ${sym}$")
        setXTicks(bot, axis, data[1])

    ax[0, 0].set_ylabel("Nodes")
    ax[1, 0].set_ylabel("Node ratio (DNF/unified)")
    ax[0, 0].legend(frameon=False, loc="upper left", handletextpad=0.3)

    fig.savefig(out_path)
    plt.close(fig)


def slideRowFigure(rows, out_path, draw, ylabel, legend=False):
    # One row of the sweep figure on its own, three panels across a slide
    fig, ax = plt.subplots(1, 3, figsize=SLIDE_FIGSIZE, layout="constrained")

    for col, (axis, sym, name) in enumerate(AXES):
        data = sweepData(rows, axis)
        draw(ax[col], axis, *data)
        ax[col].set_title(panelTitle(axis, sym), color=INK)
        ax[col].set_xlabel(f"{name} ${sym}$")
        setXTicks(ax[col], axis, data[1])

    ax[0].set_ylabel(ylabel)
    if legend:
        ax[0].legend(frameon=False, loc="upper left", handletextpad=0.3)

    fig.savefig(out_path, dpi=SLIDE_DPI, transparent=True)
    plt.close(fig)


def heatmapFigure(rows, out_path, width_frac=0.62):
    ds = sorted({int(r["chain_depth"]) for r in rows})
    ks = sorted({int(r["n_branches"]) for r in rows})
    m = int(rows[0]["branch_depth"])

    ratio = np.zeros((len(ds), len(ks)))
    for r in rows:
        ratio[ds.index(int(r["chain_depth"])), ks.index(int(r["n_branches"]))] = float(r["node_ratio"])

    # Diverging on log(ratio), neutral at 1: orange where unified is larger,
    # blue where DNF is larger. Log because the ratio is multiplicative.
    cmap = LinearSegmentedColormap.from_list(
        "div", ["#eb6834", "#f7d9cb", "#eeeeea", "#b7d3f6", "#5598e7", "#1c5cab", "#0d366b"])
    norm = TwoSlopeNorm(vmin=np.log(0.8), vcenter=0.0, vmax=np.log(ratio.max()))

    width = TEXTWIDTH_IN * width_frac
    fig, ax = plt.subplots(figsize=(width, width * 0.9), layout="constrained")
    im = ax.imshow(np.log(ratio), cmap=cmap, norm=norm, origin="lower", aspect="auto")

    for i in range(len(ds)):
        for j in range(len(ks)):
            v = ratio[i, j]
            light_text = np.log(v) > 0.55 * np.log(ratio.max())
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8,
                    color="white" if light_text else INK)

    if BASE["chain_depth"] in ds and BASE["n_branches"] in ks and m == BASE["branch_depth"]:
        bi, bj = ds.index(BASE["chain_depth"]), ks.index(BASE["n_branches"])
        ax.add_patch(plt.Rectangle((bj - 0.5, bi - 0.5), 1, 1, fill=False, ec=INK, lw=1.2))

    ax.set_xticks(range(len(ks)), ks)
    ax.set_yticks(range(len(ds)), ds)
    ax.set_xlabel("Branch count $k$")
    ax.set_ylabel("Chain depth $d$")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    cb = fig.colorbar(im, ax=ax, fraction=0.05, pad=0.03)
    ticks = [0.85, 1, 2, 4, 8]
    cb.set_ticks(np.log(ticks), labels=[f"{t:g}" for t in ticks])
    cb.set_label(f"Node ratio (DNF/unified), $m={m}$")
    cb.outline.set_visible(False)
    cb.ax.tick_params(length=0)

    fig.savefig(out_path)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sweep", default="thesis_compactness.csv")
    parser.add_argument("--grid", default="grid_dk.csv")
    parser.add_argument("--out", default=".")
    parser.add_argument("--slides", action="store_true",
                        help="write transparent slide PNGs, one per row of the sweep figure")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    if args.slides:
        useSlideStyle()
        rows = loadRows(args.sweep)
        slideRowFigure(rows, os.path.join(args.out, "compactness_counts.png"), drawCounts,
                       "Nodes", legend=True)
        slideRowFigure(rows, os.path.join(args.out, "compactness_ratio.png"), drawRatio,
                       "Node ratio (DNF/unified)")
        return

    sweepFigure(loadRows(args.sweep), os.path.join(args.out, "compactness_sweep.pdf"))
    heatmapFigure(loadRows(args.grid), os.path.join(args.out, "compactness_heatmap.pdf"))


if __name__ == "__main__":
    main()