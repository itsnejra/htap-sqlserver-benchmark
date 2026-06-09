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
# Graf 7: OLTP throughput heatmap
# ----------------------------------------------------------------
def plot_oltp_heatmap(df: pd.DataFrame):
    """Heatmap srednje OLTP propusnosti po svim kombinacijama config × ratio × concurrency."""
    pivot = df.groupby(["Configuration", "OltpOlapRatio", "ConcurrencyLevel"])["OltpThroughput"].mean().reset_index()
    pivot["Label"] = pivot["OltpOlapRatio"] + "  C=" + pivot["ConcurrencyLevel"].astype(str)
    heatmap_data = pivot.pivot(index="Configuration", columns="Label", values="OltpThroughput")
    cols = sorted(heatmap_data.columns,
                  key=lambda x: (x.split("  ")[0], int(x.split("C=")[1])))
    heatmap_data = heatmap_data[cols]

    fig, ax = plt.subplots(figsize=(14, 5))
    sns.heatmap(
        heatmap_data, ax=ax,
        annot=True, fmt=".0f", annot_kws={"size": 9},
        cmap="Blues",
        linewidths=0.5, linecolor="white",
        cbar_kws={"label": "Srednja OLTP propusnost (ops/s)"}
    )
    ax.set_title("Heatmap: Srednja OLTP propusnost (ops/s) po svim kombinacijama",
                 fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("OLTP/OLAP omjer + konkurentnost")
    ax.set_ylabel("Konfiguracija")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    save_fig("07_oltp_throughput_heatmap")


# ----------------------------------------------------------------
# Graf 8: Grouped bar chart -- OLTP propusnost po konfiguraciji i konkurentnosti
# ----------------------------------------------------------------
def plot_oltp_grouped_bar(df: pd.DataFrame):
    """
    Grupirani stupičasti dijagram srednje OLTP propusnosti.
    X-os: razine konkurentnosti; grupe: konfiguracije.
    Agregiran po svim omjerima opterećenja.
    """
    agg = df.groupby(["Configuration", "ConcurrencyLevel"])["OltpThroughput"].agg(["mean", "std"]).reset_index()
    concurrencies = sorted(agg["ConcurrencyLevel"].unique())
    n_configs = len(CONFIGS_ORDER)
    x = np.arange(len(concurrencies))
    width = 0.18
    offsets = np.linspace(-(n_configs - 1) / 2, (n_configs - 1) / 2, n_configs) * width

    fig, ax = plt.subplots(figsize=(10, 6))

    for i, config in enumerate(CONFIGS_ORDER):
        cdata = agg[agg["Configuration"] == config].set_index("ConcurrencyLevel")
        means = [cdata.loc[c, "mean"] if c in cdata.index else 0 for c in concurrencies]
        stds  = [cdata.loc[c, "std"]  if c in cdata.index else 0 for c in concurrencies]
        bars = ax.bar(x + offsets[i], means, width,
                      yerr=stds, capsize=4,
                      label=config.upper(),
                      color=CONFIG_COLORS[config],
                      edgecolor="black", linewidth=0.6, alpha=0.85,
                      error_kw={"elinewidth": 1.2, "ecolor": "black"})
        # Vrijednosti iznad stupaca
        for bar, mean in zip(bars, means):
            if mean > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(stds) * 0.05,
                        f"{mean/1000:.1f}k", ha="center", va="bottom",
                        fontsize=7.5, color=CONFIG_COLORS[config], fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([f"C = {c}" for c in concurrencies])
    ax.set_xlabel("Razina konkurentnosti")
    ax.set_ylabel("OLTP propusnost (ops/s)")
    ax.set_title("Srednja OLTP propusnost po konfiguraciji i razini konkurentnosti\n"
                 "(agregirano po svim omjerima opterećenja)",
                 fontsize=13, fontweight="bold")
    ax.legend(title="Konfiguracija", loc="upper left")
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v/1000:.0f}k"))
    plt.tight_layout()
    save_fig("08_oltp_grouped_bar")


# ----------------------------------------------------------------
# Graf 9: OLTP vs OLAP throughput scatter (tradeoff)
# ----------------------------------------------------------------
def plot_oltp_olap_scatter(df: pd.DataFrame):
    """
    Scatter dijagram: x = srednja OLAP propusnost, y = srednja OLTP propusnost.
    Svaka točka = (config, concurrency), linije spajaju iste konfiguracije po porastu C.
    Vizualizira tradeoff: HTAP bi trebao biti gore-desno.
    """
    agg = df.groupby(["Configuration", "ConcurrencyLevel"]).agg(
        OltpMean=("OltpThroughput", "mean"),
        OlapMean=("OlapThroughput", "mean"),
    ).reset_index()

    concurrencies = sorted(agg["ConcurrencyLevel"].unique())
    marker_map = {c: m for c, m in zip(concurrencies, ["o", "s", "^"])}

    fig, ax = plt.subplots(figsize=(9, 7))

    for config in CONFIGS_ORDER:
        cdata = agg[agg["Configuration"] == config].sort_values("ConcurrencyLevel")
        ax.plot(cdata["OlapMean"], cdata["OltpMean"],
                color=CONFIG_COLORS[config], linewidth=1.8,
                linestyle="--", alpha=0.5, zorder=1)
        for _, row in cdata.iterrows():
            ax.scatter(row["OlapMean"], row["OltpMean"],
                       color=CONFIG_COLORS[config],
                       marker=marker_map[row["ConcurrencyLevel"]],
                       s=100, zorder=3, edgecolors="black", linewidths=0.5)
            ax.annotate(f"C={int(row['ConcurrencyLevel'])}",
                        (row["OlapMean"], row["OltpMean"]),
                        textcoords="offset points", xytext=(6, 4),
                        fontsize=8, color=CONFIG_COLORS[config])

    # Legenda konfiguracije
    legend_patches = [mpatches.Patch(color=CONFIG_COLORS[c], label=c.upper())
                      for c in CONFIGS_ORDER]
    ax.legend(handles=legend_patches, title="Konfiguracija", loc="upper left")

    ax.set_xlabel("Srednja OLAP propusnost (q/s)", fontsize=11)
    ax.set_ylabel("Srednja OLTP propusnost (ops/s)", fontsize=11)
    ax.set_title("OLTP vs OLAP propusnost -- tradeoff po konfiguraciji i konkurentnosti\n"
                 "(gore-desno = bolje na oba radna toka)",
                 fontsize=13, fontweight="bold")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v/1000:.0f}k"))
    ax.grid(linestyle="--", alpha=0.4)
    plt.tight_layout()
    save_fig("09_oltp_olap_scatter")


# ----------------------------------------------------------------
# Graf 10: Per-operation latency -- grupirani bar chart
# ----------------------------------------------------------------
PER_OP_CSV = Path("../Results/per_operation_stats.csv")

def plot_per_operation_bar():
    """
    Grupirani stupičasti dijagram prosječne latencije po tipu operacije i konfiguraciji.
    Čita Results/per_operation_stats.csv.
    """
    if not PER_OP_CSV.exists():
        print(f"  Preskačem graf 10: {PER_OP_CSV} nije pronađen.")
        return

    df = pd.read_csv(PER_OP_CSV)
    df["Configuration"] = pd.Categorical(df["Configuration"], categories=CONFIGS_ORDER, ordered=True)

    # Odabir reprezentativnih operacija i željeni redoslijed
    op_map = {
        "usp_GetPostById":         "Simple\nSELECT",
        "usp_GetRecentUserPosts":  "Complex\nSELECT",
        "usp_InsertVote":          "Complex\nINSERT",
        "usp_InsertComment":       "Simple\nINSERT",
        "usp_UpdatePostScore":     "Simple\nUPDATE",
    }
    olap_cats = ["Complex SELECT (OLAP)"]

    # OLTP operacije
    oltp = df[df["OperationName"].isin(op_map.keys())].copy()
    oltp["OpLabel"] = oltp["OperationName"].map(op_map)

    # OLAP: agregiraj sve OLAP upite po konfiguraciji (prosječna latencija)
    olap = df[df["Category"].isin(olap_cats)].groupby("Configuration")["averageExecutionTime_ms"].mean().reset_index()
    olap["OpLabel"] = "OLAP\n(prosjek)"

    # Spoji
    plot_df = pd.concat([
        oltp[["Configuration", "OpLabel", "averageExecutionTime_ms"]],
        olap[["Configuration", "OpLabel", "averageExecutionTime_ms"]]
    ], ignore_index=True)

    op_order = list(op_map.values()) + ["OLAP\n(prosjek)"]
    plot_df["OpLabel"] = pd.Categorical(plot_df["OpLabel"], categories=op_order, ordered=True)
    plot_df = plot_df.dropna(subset=["OpLabel"])

    n_ops = len(op_order)
    n_configs = len(CONFIGS_ORDER)
    x = np.arange(n_ops)
    width = 0.18
    offsets = np.linspace(-(n_configs - 1) / 2, (n_configs - 1) / 2, n_configs) * width

    # Razdvoj OLTP i OLAP u dva panela zbog razlike u skalama (~ms vs ~sekunde)
    oltp_ops  = [op for op in op_order if op != "OLAP\n(prosjek)"]
    olap_ops  = ["OLAP\n(prosjek)"]

    fig, (ax_oltp, ax_olap) = plt.subplots(1, 2, figsize=(14, 6),
                                            gridspec_kw={"width_ratios": [5, 1.2]})

    for ax, ops_subset, title_suffix in [
        (ax_oltp, oltp_ops,  "OLTP operacije"),
        (ax_olap, olap_ops,  "OLAP (prosjek)"),
    ]:
        x_sub = np.arange(len(ops_subset))
        off_sub = np.linspace(-(n_configs - 1) / 2, (n_configs - 1) / 2, n_configs) * width

        for i, config in enumerate(CONFIGS_ORDER):
            cdata = plot_df[plot_df["Configuration"] == config].set_index("OpLabel")
            vals = [cdata.loc[op, "averageExecutionTime_ms"] if op in cdata.index else 0
                    for op in ops_subset]
            bars = ax.bar(x_sub + off_sub[i], vals, width,
                          label=config.upper(),
                          color=CONFIG_COLORS[config],
                          edgecolor="black", linewidth=0.6, alpha=0.85)

        ax.set_xticks(x_sub)
        ax.set_xticklabels(ops_subset, fontsize=10)
        ax.set_ylabel("Prosječna latencija (ms)")
        ax.set_title(title_suffix, fontweight="bold")
        ax.grid(axis="y", linestyle="--", alpha=0.4)

    ax_oltp.legend(title="Konfiguracija", loc="upper right", fontsize=9)
    fig.suptitle("Prosječna latencija po tipu operacije i konfiguraciji\n"
                 "(agregirano po svim omjerima opterećenja i razinama konkurentnosti)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    save_fig("10_per_operation_latency")


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

    print("7. OLTP throughput heatmap...")
    plot_oltp_heatmap(df)

    print("8. OLTP grupirani bar chart...")
    plot_oltp_grouped_bar(df)

    print("9. OLTP vs OLAP scatter (tradeoff)...")
    plot_oltp_olap_scatter(df)

    print("10. Per-operation latencija bar chart...")
    plot_per_operation_bar()

    print(f"\nSvi grafovi pohraneni u: {FIGURES_DIR.resolve()}")
    print("Završeno.")


if __name__ == "__main__":
    main()
