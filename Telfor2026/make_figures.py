#!/usr/bin/env python3
"""
Generates the English-labelled, print-ready figures for the TELFOR 2026 paper
directly from the raw measurement file Results/summary.csv.

Output: Telfor2026/figures/*.pdf (vector, Type-42 fonts, IEEE column widths)

Usage:  python3 Telfor2026/make_figures.py      (run from the repository root)
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ----------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
SUMMARY = ROOT / "Results" / "summary.csv"
OUTDIR = Path(__file__).resolve().parent / "figures"
OUTDIR.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------
# IEEE two-column style: 3.5 in single column, 7.16 in double column
# ----------------------------------------------------------------------
COL_W = 3.45
DBL_W = 7.16

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Liberation Serif", "Times New Roman", "Nimbus Roman", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 8,
    "axes.labelsize": 8,
    "axes.titlesize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 7,
    "axes.linewidth": 0.6,
    "grid.linewidth": 0.4,
    "lines.linewidth": 1.1,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "figure.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.01,
})

CONFIGS = ["BASELINE", "CS", "IM", "HTAP"]
LABELS = {
    "BASELINE": "Baseline (B-tree)",
    "CS": "CS (columnstore)",
    "IM": "IM (Hekaton)",
    "HTAP": "HTAP (dual-store)",
}
# Bosanska varijanta oznaka za prijevod rada
LABELS_BS = {
    "BASELINE": "Baseline (B-stablo)",
    "CS": "CS (columnstore)",
    "IM": "IM (Hekaton)",
    "HTAP": "HTAP (dual-store)",
}
# Colour-blind-safe, and separable in grayscale (light -> dark)
COLOR = {"BASELINE": "#BFBFBF", "CS": "#7FB1D3", "IM": "#F0A73A", "HTAP": "#1B5E8C"}
HATCH = {"BASELINE": "///", "CS": "\\\\\\", "IM": "xxx", "HTAP": ""}
MARKER = {"BASELINE": "o", "CS": "s", "IM": "^", "HTAP": "D"}
RATIOS = ["80_20", "50_50", "20_80"]
RATIO_TITLE = {
    "80_20": "(a) OLTP 80\\% / OLAP 20\\%",
    "50_50": "(b) OLTP 50\\% / OLAP 50\\%",
    "20_80": "(c) OLTP 20\\% / OLAP 80\\%",
}
LEVELS = [4, 16, 32]


def load() -> pd.DataFrame:
    df = pd.read_csv(SUMMARY)
    df["Configuration"] = df["Configuration"].str.upper()
    return df


def degradation(df: pd.DataFrame, cfg: str, level: int) -> np.ndarray:
    """Relative OLTP throughput loss when moving from the 80/20 to the 50/50 mix."""
    base = df[(df.Configuration == cfg) & (df.OltpOlapRatio == "80_20")
              & (df.ConcurrencyLevel == level)].set_index("RunNumber")["OltpThroughput"]
    mixed = df[(df.Configuration == cfg) & (df.OltpOlapRatio == "50_50")
               & (df.ConcurrencyLevel == level)].set_index("RunNumber")["OltpThroughput"]
    common = base.index.intersection(mixed.index)
    return ((base[common] - mixed[common]) / base[common] * 100.0).values


# ----------------------------------------------------------------------
# Fig. 1 - OLTP throughput scaling, one panel per workload mix (2 columns)
# ----------------------------------------------------------------------
def fig_oltp_scaling(df: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(DBL_W, 1.85), sharex=True, sharey=True)
    for ax, ratio in zip(axes, RATIOS):
        for cfg in CONFIGS:
            sub = df[(df.Configuration == cfg) & (df.OltpOlapRatio == ratio)]
            means = [sub[sub.ConcurrencyLevel == c]["OltpThroughput"].mean() for c in LEVELS]
            sds = [sub[sub.ConcurrencyLevel == c]["OltpThroughput"].std() for c in LEVELS]
            ax.errorbar(LEVELS, means, yerr=sds, marker=MARKER[cfg], markersize=3.2,
                        capsize=1.8, elinewidth=0.6, color=COLOR[cfg],
                        markeredgecolor="black", markeredgewidth=0.35, label=LABELS[cfg])
        ax.set_xscale("log", base=2)
        ax.set_yscale("log")
        ax.set_xticks(LEVELS)
        ax.set_xticklabels([str(c) for c in LEVELS])
        ax.set_xlabel("Concurrency level $C$ (threads)")
        ax.set_title(RATIO_TITLE[ratio].replace("\\%", "%"), pad=3)
        ax.grid(True, which="major", ls=":", alpha=0.55)
        ax.grid(True, which="minor", ls=":", alpha=0.22)
    axes[0].set_ylabel("OLTP throughput (ops/s)")
    axes[0].legend(loc="lower right", frameon=True, framealpha=0.92,
                   handlelength=1.6, borderpad=0.28, labelspacing=0.22)
    fig.tight_layout(pad=0.25, w_pad=0.6)
    fig.savefig(OUTDIR / "fig1_oltp_scaling.pdf")
    plt.close(fig)


# ----------------------------------------------------------------------
# Fig. 2 - OLAP P50 latency distribution at C = 32 (single column)
# ----------------------------------------------------------------------
def fig_olap_latency(df: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(COL_W, 1.28))
    data = [df[(df.Configuration == c) & (df.ConcurrencyLevel == 32)]["OlapLatencyP50"].values
            for c in CONFIGS]
    bp = ax.boxplot(data, patch_artist=True, widths=0.55, showfliers=True,
                    flierprops=dict(marker=".", markersize=1.8, markerfacecolor="0.35",
                                    markeredgecolor="0.35", alpha=0.55),
                    medianprops=dict(color="black", linewidth=1.0),
                    whiskerprops=dict(linewidth=0.6), capprops=dict(linewidth=0.6),
                    boxprops=dict(linewidth=0.6))
    for patch, cfg in zip(bp["boxes"], CONFIGS):
        patch.set_facecolor(COLOR[cfg])
        patch.set_hatch(HATCH[cfg])
        patch.set_alpha(0.95)
    for i, cfg in enumerate(CONFIGS, start=1):
        med = np.median(df[(df.Configuration == cfg) & (df.ConcurrencyLevel == 32)]["OlapLatencyP50"])
        ax.text(i, med * 1.06, f"{med:,.0f}".replace(",", " "), ha="center", va="bottom",
                fontsize=6.4)
    ax.set_yscale("log")
    ax.set_xticks(range(1, len(CONFIGS) + 1))
    ax.set_xticklabels(["Baseline", "CS", "IM", "HTAP"])
    ax.set_ylabel("OLAP latency $P_{50}$ (ms)")
    ax.set_xlabel("Storage configuration ($C = 32$, all workload mixes)")
    ax.grid(True, axis="y", which="major", ls=":", alpha=0.55)
    fig.tight_layout(pad=0.25)
    fig.savefig(OUTDIR / "fig2_olap_latency.pdf")
    plt.close(fig)


# ----------------------------------------------------------------------
# Fig. 3 - OLTP throughput degradation 80/20 -> 50/50 (single column)
# ----------------------------------------------------------------------
def fig_degradation(df: pd.DataFrame, lang: str = "en") -> None:
    bs = lang == "bs"
    labels = LABELS_BS if bs else LABELS
    fig, ax = plt.subplots(figsize=(COL_W, 1.28))
    width = 0.2
    xs = np.arange(len(LEVELS))
    for i, cfg in enumerate(CONFIGS):
        means = [degradation(df, cfg, c).mean() for c in LEVELS]
        sds = [degradation(df, cfg, c).std(ddof=1) for c in LEVELS]
        ax.bar(xs + (i - 1.5) * width, means, width, yerr=sds, capsize=1.6,
               color=COLOR[cfg], hatch=HATCH[cfg], edgecolor="black", linewidth=0.45,
               error_kw=dict(elinewidth=0.6), label=labels[cfg])
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"$C = {c}$" for c in LEVELS])
    ax.set_ylabel("Pad OLTP propusnosti (%)" if bs else "OLTP throughput loss (%)")
    ax.set_xlabel("Razina konkurentnosti" if bs else "Concurrency level")
    ax.grid(True, axis="y", ls=":", alpha=0.55)
    ax.legend(loc="lower left", ncol=2, frameon=True, framealpha=0.92,
              handlelength=1.4, borderpad=0.25, labelspacing=0.2, columnspacing=0.9)
    ax.set_ylim(-45, 108)
    fig.tight_layout(pad=0.25)
    fig.savefig(OUTDIR / ("fig3_degradation_bs.pdf" if bs else "fig3_degradation.pdf"))
    plt.close(fig)


def main() -> None:
    df = load()
    fig_oltp_scaling(df)
    fig_olap_latency(df)
    fig_degradation(df, lang="en")
    fig_degradation(df, lang="bs")
    print(f"Figures written to {OUTDIR}")


if __name__ == "__main__":
    main()
