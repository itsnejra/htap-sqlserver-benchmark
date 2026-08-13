"""
make_figures.py — figure za Telfor 2026 rad, iz Results/summary.csv.

Format je prilagođen IEEE dvokolonskom radu: širina jedne kolone (3,4 in),
serif font, veličine 7-8 pt, bez naslova iznad slike (caption ide u LaTeX).

Pokretanje:
    python Paper/Telfor2026/make_figures.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
SUMMARY = ROOT / "Results" / "summary.csv"
OUT = Path(__file__).resolve().parent / "figures"

COL_W = 3.4       # širina jedne IEEE kolone u inčima
CONCS = [4, 16, 32]

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 7.5,
    "axes.labelsize": 7.5,
    "axes.titlesize": 8,
    "legend.fontsize": 7,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.4,
    "axes.axisbelow": True,
})


def load() -> pd.DataFrame:
    df = pd.read_csv(SUMMARY)
    df["Configuration"] = df["Configuration"].str.strip().str.lower()
    return df[df["OltpSuccessRate"] >= 0.90]


def fig_throughput_gap(df: pd.DataFrame) -> None:
    """Fig. 1 — OLTP propusnost IM vs HTAP kroz konkurentnost, omjer 80/20."""
    sub = df[df["OltpOlapRatio"] == "80_20"]
    x = np.arange(len(CONCS))
    width = 0.36

    im = [sub.loc[(sub.Configuration == "im") & (sub.ConcurrencyLevel == c), "OltpThroughput"].median()
          for c in CONCS]
    ht = [sub.loc[(sub.Configuration == "htap") & (sub.ConcurrencyLevel == c), "OltpThroughput"].median()
          for c in CONCS]

    fig, ax = plt.subplots(figsize=(COL_W, 2.3))
    b1 = ax.bar(x - width / 2, im, width, label="IM (row-mode OLAP)",
                color="#8c8c8c", edgecolor="black", linewidth=0.4)
    b2 = ax.bar(x + width / 2, ht, width, label="HTAP (offloaded OLAP)",
                color="#2b6cb0", edgecolor="black", linewidth=0.4)
    ax.bar_label(b1, fmt="%.0f", fontsize=6, padding=1)
    ax.bar_label(b2, fmt="%.0f", fontsize=6, padding=1)

    for xi, (a, b) in enumerate(zip(im, ht)):
        ax.text(xi, max(a, b) * 1.28, f"{b / a:.1f}$\\times$",
                ha="center", fontsize=7, fontweight="bold")

    ax.set_xticks(x, [f"C = {c}" for c in CONCS])
    ax.set_ylabel("OLTP throughput [ops/s]")
    ax.set_ylim(0, max(ht) * 1.45)
    ax.legend(loc="upper left", frameon=False)
    fig.tight_layout(pad=0.3)
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "fig1_throughput_gap.pdf")
    fig.savefig(OUT / "fig1_throughput_gap.png", dpi=300)
    plt.close(fig)
    print("  fig1_throughput_gap")


def fig_olap_crossover(df: pd.DataFrame) -> None:
    """
    Fig. 2 — OLAP P50 latencija IM vs HTAP kroz konkurentnost.

    Ključ argumenta: pri C=4 IM je konkurentan (podaci su u RAM-u), a jaz se
    otvara tek kad row-mode skeniranje počne trošiti procesor koji treba OLTP-u.
    Ista tačka u kojoj OLAP zaostaje jest tačka u kojoj OLTP propada.
    """
    fig, ax = plt.subplots(figsize=(COL_W, 2.3))

    for cfg, label, style in [("im", "IM (row-mode)", dict(color="#8c8c8c", marker="s", ls="--")),
                              ("htap", "HTAP (batch-mode)", dict(color="#2b6cb0", marker="o", ls="-"))]:
        vals = [df.loc[(df.Configuration == cfg) & (df.ConcurrencyLevel == c),
                       "OlapLatencyP50"].median() for c in CONCS]
        ax.plot(CONCS, vals, lw=1.2, ms=3.5, label=label, **style)
        for c, v in zip(CONCS, vals):
            ax.annotate(f"{v:.0f}", (c, v), textcoords="offset points",
                        xytext=(0, 6), ha="center", fontsize=6)

    ax.set_xscale("log", base=2)
    ax.set_xticks(CONCS, [str(c) for c in CONCS])
    ax.set_xlabel("Concurrency level")
    ax.set_ylabel("OLAP latency P50 [ms]")
    ax.legend(loc="upper left", frameon=False)
    fig.tight_layout(pad=0.3)
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "fig2_olap_crossover.pdf")
    fig.savefig(OUT / "fig2_olap_crossover.png", dpi=300)
    plt.close(fig)
    print("  fig2_olap_crossover")


def fig_oltp_latency(df: pd.DataFrame) -> None:
    """Fig. 3 — OLTP P95 latencija: cijena koju transakcije plaćaju za lokalnu analitiku."""
    sub = df[df["OltpOlapRatio"] == "80_20"]
    x = np.arange(len(CONCS))
    width = 0.36

    im = [sub.loc[(sub.Configuration == "im") & (sub.ConcurrencyLevel == c), "OltpLatencyP95"].median()
          for c in CONCS]
    ht = [sub.loc[(sub.Configuration == "htap") & (sub.ConcurrencyLevel == c), "OltpLatencyP95"].median()
          for c in CONCS]

    fig, ax = plt.subplots(figsize=(COL_W, 2.1))
    b1 = ax.bar(x - width / 2, im, width, label="IM", color="#8c8c8c",
                edgecolor="black", linewidth=0.4)
    b2 = ax.bar(x + width / 2, ht, width, label="HTAP", color="#2b6cb0",
                edgecolor="black", linewidth=0.4)
    ax.bar_label(b1, fmt="%.1f", fontsize=6, padding=1)
    ax.bar_label(b2, fmt="%.1f", fontsize=6, padding=1)

    ax.set_xticks(x, [f"C = {c}" for c in CONCS])
    ax.set_ylabel("OLTP latency P95 [ms]")
    ax.set_ylim(0, max(im) * 1.25)
    ax.legend(loc="upper left", frameon=False)
    fig.tight_layout(pad=0.3)
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "fig3_oltp_latency.pdf")
    fig.savefig(OUT / "fig3_oltp_latency.png", dpi=300)
    plt.close(fig)
    print("  fig3_oltp_latency")


def main() -> None:
    if not SUMMARY.exists():
        raise SystemExit(f"Nedostaje {SUMMARY}.")
    df = load()
    print(f"Figure iz {len(df)} validnih runova:")
    fig_throughput_gap(df)
    fig_olap_crossover(df)
    fig_oltp_latency(df)
    print(f"Izlaz: {OUT}")


if __name__ == "__main__":
    main()
