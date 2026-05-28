"""
HTAPBenchmark: 03_visualizations.py
Vizualizacije rezultata benchmarka

Grafovi:
  1. Violin plot distribucije OLTP latencija po konfiguraciji i concurrency-u
  2. Violin plot distribucije OLAP latencija
  3. Throughput-Latency trade-off krivulje (OLTP)
  4. Throughput-Latency trade-off krivulje (OLAP)
  5. Degradacija OLTP throughputa pri miješanom opterećenju
  6. Heatmap: median latencija po svim kombinacijama

Izlaz: Results/figures/*.png  (300 DPI, pogodno za publikaciju)
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns

matplotlib.rcParams.update({
    "font.family":       "DejaVu Serif",
    "font.size":         11,
    "axes.titlesize":    12,
    "axes.labelsize":    11,
    "xtick.labelsize":   10,
    "ytick.labelsize":   10,
    "legend.fontsize":   10,
    "figure.dpi":        150,
    "savefig.dpi":       300,
    "axes.spines.top":   False,
    "axes.spines.right": False,
})

SUMMARY_CSV  = Path("../Results/summary.csv")
FIGURES_DIR  = Path("../Results/figures")

CONFIG_COLORS = {
    "baseline": "#4E79A7",
    "cs":       "#F28E2B",
    "im":       "#59A14F",
    "htap":     "#E15759",
}
CONFIG_LABELS = {
    "baseline": "Baseline\n(B-tree)",
    "cs":       "CS\n(Columnstore)",
    "im":       "IM\n(In-Memory)",
    "htap":     "HTAP\n(IM+CS)",
}
CONFIGS_ORDER = ["baseline", "cs", "im", "htap"]


def load_data() -> pd.DataFrame:
    if not SUMMARY_CSV.exists():
        raise FileNotFoundError(
            f"Fajl nije pronađen: {SUMMARY_CSV}\n"
            "Pokrenite benchmark aplikaciju i statistički test."
        )
    df = pd.read_csv(SUMMARY_CSV)
    df["Configuration"] = pd.Categorical(df["Configuration"], categories=CONFIGS_ORDER, ordered=True)
    return df


def save_fig(name: str):
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / f"{name}.png"
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    print(f"  Sačuvano: {path}")


# ----------------------------------------------------------------
# Graf 1 & 2: Violin plot latencija
# ----------------------------------------------------------------
def plot_latency_violin(df: pd.DataFrame, metric: str, title: str, ylabel: str, filename: str):
    """Violin plot distribucije latencija po konfiguraciji, facet = ConcurrencyLevel."""
    concurrencies = sorted(df["ConcurrencyLevel"].unique())
    n_cols = len(concurrencies)

    fig, axes = plt.subplots(1, n_cols, figsize=(5 * n_cols, 6), sharey=False)
    if n_cols == 1:
        axes = [axes]

    for ax, concurrency in zip(axes, concurrencies):
        subset = df[df["ConcurrencyLevel"] == concurrency].sort_values("Configuration")
        data   = [subset[subset["Configuration"] == c][metric].dropna().values
                  for c in CONFIGS_ORDER if c in subset["Configuration"].values]
        labels = [CONFIG_LABELS[c] for c in CONFIGS_ORDER
                  if c in subset["Configuration"].values]
        colors = [CONFIG_COLORS[c] for c in CONFIGS_ORDER
                  if c in subset["Configuration"].values]

        vparts = ax.violinplot(data, positions=range(len(data)),
                               showmedians=True, showextrema=True)

        for i, (body, color) in enumerate(zip(vparts["bodies"], colors)):
            body.set_facecolor(color)
            body.set_alpha(0.75)
            body.set_edgecolor("black")
            body.set_linewidth(0.8)

        vparts["cmedians"].set_color("black")
        vparts["cmedians"].set_linewidth(2)
        vparts["cmaxes"].set_color("black")
        vparts["cmins"].set_color("black")
        vparts["cbars"].set_color("black")

        # Overlay: scatter jitter
        for i, (vals, color) in enumerate(zip(data, colors)):
            if len(vals) > 0:
                jitter = np.random.default_rng(42).uniform(-0.1, 0.1, size=len(vals))
                ax.scatter(np.full_like(vals, i) + jitter, vals,
                           color=color, alpha=0.4, s=15, zorder=3)

        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels)
        ax.set_title(f"Konkurentnost = {concurrency}", fontweight="bold")
        ax.set_ylabel(ylabel if ax == axes[0] else "")
        ax.grid(axis="y", linestyle="--", alpha=0.5)

    fig.suptitle(title, fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    save_fig(filename)


# ----------------------------------------------------------------
# Graf 3 & 4: Throughput-Latency trade-off krivulje
# ----------------------------------------------------------------
def plot_throughput_latency(df: pd.DataFrame, tp_metric: str, lat_metric: str,
                            title: str, xlabel: str, ylabel: str, filename: str):
    """
    Throughput-Latency krivulja: x=throughput, y=latency P95
    Jedna linija po konfiguraciji, točke = prosječne vrijednosti po ConcurrencyLevel
    """
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=False)
    ratios = ["80_20", "50_50", "20_80"]
    ratio_labels = {"80_20": "OLTP 80% / OLAP 20%",
                    "50_50": "OLTP 50% / OLAP 50%",
                    "20_80": "OLTP 20% / OLAP 80%"}

    for ax, ratio in zip(axes, ratios):
        subset = df[df["OltpOlapRatio"] == ratio]

        for config in CONFIGS_ORDER:
            cdata = subset[subset["Configuration"] == config].sort_values("ConcurrencyLevel")
            if cdata.empty:
                continue

            agg = cdata.groupby("ConcurrencyLevel").agg(
                TpMean=(tp_metric, "mean"),
                TpSD=(tp_metric, "std"),
                LatMean=(lat_metric, "mean"),
                LatSD=(lat_metric, "std")
            ).reset_index()

            ax.errorbar(
                agg["TpMean"], agg["LatMean"],
                xerr=agg["TpSD"], yerr=agg["LatSD"],
                label=config.upper(),
                color=CONFIG_COLORS[config],
                marker="o", markersize=7,
                linewidth=2, capsize=4,
            )
            # Označi concurrency razine
            for _, row in agg.iterrows():
                ax.annotate(f"C={int(row['ConcurrencyLevel'])}",
                            (row["TpMean"], row["LatMean"]),
                            textcoords="offset points", xytext=(5, -8),
                            fontsize=8, color=CONFIG_COLORS[config])

        ax.set_title(ratio_labels[ratio], fontweight="bold")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel if ax == axes[0] else "")
        ax.legend(title="Konfiguracija", fontsize=9)
        ax.grid(linestyle="--", alpha=0.5)

    fig.suptitle(title, fontsize=14, fontweight="bold")
    plt.tight_layout()
    save_fig(filename)


# ----------------------------------------------------------------
# Graf 5: Degradacija OLTP throughputa
# ----------------------------------------------------------------
def plot_degradation(df: pd.DataFrame):
    """
    Boxplot degradacije OLTP throughputa:
    degradacija[%] = (throughput_80_20 - throughput_50_50) / throughput_80_20 * 100
    """
    records = []
    for config in CONFIGS_ORDER:
        for concurrency in sorted(df["ConcurrencyLevel"].unique()):
            base  = df[(df["Configuration"] == config) &
                       (df["ConcurrencyLevel"] == concurrency) &
                       (df["OltpOlapRatio"] == "80_20")]["OltpThroughput"].values
            mixed = df[(df["Configuration"] == config) &
                       (df["ConcurrencyLevel"] == concurrency) &
                       (df["OltpOlapRatio"] == "50_50")]["OltpThroughput"].values
            n = min(len(base), len(mixed))
            if n > 0:
                degrad = (base[:n] - mixed[:n]) / np.where(base[:n] != 0, base[:n], 1) * 100
                for val in degrad:
                    records.append({
                        "Configuration":  config,
                        "ConcurrencyLevel": concurrency,
                        "Degradation_pct": val
                    })

    if not records:
        print("  Nema podataka za degradacijski graf.")
        return

    degrad_df = pd.DataFrame(records)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
    concurrencies = sorted(degrad_df["ConcurrencyLevel"].unique())

    for ax, concurrency in zip(axes, concurrencies):
        subset = degrad_df[degrad_df["ConcurrencyLevel"] == concurrency]
        data   = [subset[subset["Configuration"] == c]["Degradation_pct"].values
                  for c in CONFIGS_ORDER]
        labels = [c.upper() for c in CONFIGS_ORDER]
        colors = [CONFIG_COLORS[c] for c in CONFIGS_ORDER]

        bp = ax.boxplot(data, labels=labels, patch_artist=True,
                        medianprops={"color": "black", "linewidth": 2})
        for patch, color in zip(bp["boxes"], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.75)

        ax.axhline(y=0, color="red", linestyle="--", linewidth=1, alpha=0.7)
        ax.set_title(f"Konkurentnost = {concurrency}", fontweight="bold")
        ax.set_xlabel("Konfiguracija")
        ax.set_ylabel("Degradacija OLTP propusnosti (%)" if ax == axes[0] else "")
        ax.grid(axis="y", linestyle="--", alpha=0.5)

    fig.suptitle(
        "Degradacija OLTP propusnosti pri prelasku s 80/20 na 50/50 opterećenje",
        fontsize=14, fontweight="bold"
    )
    plt.tight_layout()
    save_fig("05_oltp_degradation")


# ----------------------------------------------------------------
# Graf 6: Heatmap latencija
# ----------------------------------------------------------------
def plot_latency_heatmap(df: pd.DataFrame):
    """
    Heatmap: median OLAP latencija P50 po svim kombinacijama (config × concurrency × ratio)
    """
    pivot = df.groupby(["Configuration", "OltpOlapRatio", "ConcurrencyLevel"])["OlapLatencyP50"].median().reset_index()
    pivot["Label"] = pivot["OltpOlapRatio"] + " C=" + pivot["ConcurrencyLevel"].astype(str)
    heatmap_data = pivot.pivot(index="Configuration", columns="Label", values="OlapLatencyP50")

    # Sortiraj kolone logički
    cols = sorted(heatmap_data.columns,
                  key=lambda x: (x.split(" ")[0], int(x.split("C=")[1])))
    heatmap_data = heatmap_data[cols]

    fig, ax = plt.subplots(figsize=(14, 5))
    sns.heatmap(
        heatmap_data, ax=ax,
        annot=True, fmt=".0f", annot_kws={"size": 9},
        cmap="YlOrRd",
        linewidths=0.5, linecolor="white",
        cbar_kws={"label": "Median OLAP Latencija P50 (ms)"}
    )
    ax.set_title("Heatmap: Median OLAP latencija P50 (ms) po svim kombinacijama",
                 fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("OLTP/OLAP ratio + konkurentnost")
    ax.set_ylabel("Konfiguracija")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    save_fig("06_latency_heatmap")


# ----------------------------------------------------------------
# Glavni program
# ----------------------------------------------------------------

def main():
    print("=" * 60)
    print("HTAPBenchmark: Vizualizacije")
    print("=" * 60)

    np.random.seed(42)
    df = load_data()
    print(f"Učitano {len(df)} redova iz {SUMMARY_CSV}")

    print("\n1. OLTP latencija violin plot...")
    plot_latency_violin(
        df, "OltpLatencyP50",
        title="Distribucija OLTP latencije P50 po konfiguraciji i razini konkurentnosti",
        ylabel="OLTP Latencija P50 (ms)",
        filename="01_oltp_latency_violin"
    )

    print("2. OLAP latencija violin plot...")
    plot_latency_violin(
        df, "OlapLatencyP50",
        title="Distribucija OLAP latencije P50 po konfiguraciji i razini konkurentnosti",
        ylabel="OLAP Latencija P50 (ms)",
        filename="02_olap_latency_violin"
    )

    print("3. OLTP throughput-latency krivulje...")
    plot_throughput_latency(
        df,
        tp_metric="OltpThroughput",
        lat_metric="OltpLatencyP95",
        title="OLTP Throughput-Latency trade-off po konfiguraciji i omjeru opterećenja",
        xlabel="OLTP Throughput (ops/s)",
        ylabel="OLTP Latencija P95 (ms)",
        filename="03_oltp_throughput_latency"
    )

    print("4. OLAP throughput-latency krivulje...")
    plot_throughput_latency(
        df,
        tp_metric="OlapThroughput",
        lat_metric="OlapLatencyP95",
        title="OLAP Throughput-Latency trade-off po konfiguraciji i omjeru opterećenja",
        xlabel="OLAP Throughput (q/s)",
        ylabel="OLAP Latencija P95 (ms)",
        filename="04_olap_throughput_latency"
    )

    print("5. OLTP degradacija boxplot...")
    plot_degradation(df)

    print("6. Latencija heatmap...")
    plot_latency_heatmap(df)

    print(f"\nSvi grafovi pohraneni u: {FIGURES_DIR.resolve()}")
    print("Završeno.")


if __name__ == "__main__":
    main()
