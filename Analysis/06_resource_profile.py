#!/usr/bin/env python3
"""
06_resource_profile.py — CPU iskorištenost i raspodjela čekanja po konfiguraciji.

SVRHA
    Rad tvrdi da row-mode OLAP skeniranja u IM konfiguraciji zasićuju procesor i
    time istiskuju OLTP niti. U dosadašnjoj verziji taj mehanizam bio je IZVEDEN
    iz modela izvršavanja upita, a ne izmjeren — što je i navedeno među
    ograničenjima. Ova skripta obrađuje direktna mjerenja iz
    sys.dm_os_schedulers i sys.dm_os_wait_stats i pretvara tvrdnju o mehanizmu
    u empirijski nalaz.

ULAZ
    Results/profile_resource_usage.csv   (CPU po runu)
    Results/profile_wait_stats.csv       (top čekanja po runu)
    Generiše: dotnet run --project HTAPBenchmark.Runner -- --experiment waits

IZLAZ
    Results/resource_profile_report.txt
    Results/resource_profile_summary.csv
    Results/figures/14_cpu_utilization.png
    Results/figures/15_wait_breakdown.png
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT        = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "Results"
FIGURES_DIR = RESULTS_DIR / "figures"

USAGE_CSV = RESULTS_DIR / "profile_resource_usage.csv"
WAITS_CSV = RESULTS_DIR / "profile_wait_stats.csv"

# Iste boje kao u ostatku rada, radi konzistentnosti figura.
COLORS = {
    "baseline": "#6B6054",
    "cs":       "#A23B72",
    "im":       "#F18F01",
    "htap":     "#2E86AB",
}

# Čekanja grupirana po mehanizmu koji uzrokuju. Grupiranje je nužno jer sirovi
# tipovi čekanja (~20 po runu) ne daju čitljivu figuru, a i sami po sebi ne
# odgovaraju na pitanje KOJI resurs je usko grlo.
WAIT_GROUPS = {
    "CPU (scheduler)":  ["SOS_SCHEDULER_YIELD", "CXPACKET", "CXCONSUMER", "CXSYNC_PORT",
                         "CXSYNC_CONSUMER", "EXCHANGE"],
    "Memorija (grant)": ["RESOURCE_SEMAPHORE", "RESOURCE_SEMAPHORE_QUERY_COMPILE",
                         "CMEMTHREAD", "MEMORY_GRANT_UPDATE"],
    "Disk I/O":         ["PAGEIOLATCH_SH", "PAGEIOLATCH_EX", "PAGEIOLATCH_UP",
                         "IO_COMPLETION", "ASYNC_IO_COMPLETION", "WRITELOG"],
    "Zaključavanje":    ["LCK_M_S", "LCK_M_X", "LCK_M_U", "LCK_M_IS", "LCK_M_IX",
                         "PAGELATCH_EX", "PAGELATCH_SH", "PAGELATCH_UP"],
    "In-Memory (XTP)":  ["WAIT_XTP_HOST_WAIT", "XTP_PREEMPTIVE_TASK", "WAIT_XTP_TX_COMMIT",
                         "WAIT_XTP_PROCEDURE_ENTRY"],
    "Mreža/klijent":    ["ASYNC_NETWORK_IO", "NETWORK_IO"],
}


def classify_wait(wait_type: str) -> str:
    for group, members in WAIT_GROUPS.items():
        if wait_type in members:
            return group
    return "Ostalo"


def base_config(label: str) -> str:
    """htap_md1 -> htap; htap_sync5 -> htap. Uvjet je kodiran u oznaku."""
    return label.split("_")[0]


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    missing = [p.name for p in (USAGE_CSV, WAITS_CSV) if not p.exists()]
    if missing:
        raise SystemExit(
            f"Nedostaju ulazne datoteke: {', '.join(missing)}\n"
            "Pokrenite prvo: dotnet run --project HTAPBenchmark.Runner -- --experiment waits"
        )

    usage = pd.read_csv(USAGE_CSV)
    waits = pd.read_csv(WAITS_CSV)

    for df in (usage, waits):
        df["ConfigBase"] = df["Configuration"].map(base_config)

    waits["WaitGroup"] = waits["WaitType"].map(classify_wait)
    return usage, waits


def cpu_summary(usage: pd.DataFrame) -> pd.DataFrame:
    return (
        usage.groupby(["ConfigBase", "OltpOlapRatio", "ConcurrencyLevel"])
        .agg(
            N=("SqlCpuUtilPct", "size"),
            CpuUtilPct_mean=("SqlCpuUtilPct", "mean"),
            CpuUtilPct_sd=("SqlCpuUtilPct", "std"),
            SignalWaitPct_mean=("SignalWaitPct", "mean"),
            TotalWaitMs_mean=("TotalWaitMs", "mean"),
        )
        .round(3)
        .reset_index()
    )


def plot_cpu(usage: pd.DataFrame) -> None:
    """CPU iskorištenost po razini konkurentnosti — ključna figura za mehanizam."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), sharey=True)
    ratios = ["80_20", "50_50", "20_80"]
    titles = {"80_20": "80%/20% (transakcijsko)",
              "50_50": "50%/50% (mješovito)",
              "20_80": "20%/80% (analitičko)"}

    for ax, ratio in zip(axes, ratios):
        subset = usage[usage["OltpOlapRatio"] == ratio]
        if subset.empty:
            ax.set_visible(False)
            continue

        for cfg in ["cs", "im", "htap"]:
            cfg_data = (
                subset[subset["ConfigBase"] == cfg]
                .groupby("ConcurrencyLevel")["SqlCpuUtilPct"]
                .agg(["mean", "std"])
                .reset_index()
            )
            if cfg_data.empty:
                continue

            ax.errorbar(
                cfg_data["ConcurrencyLevel"], cfg_data["mean"],
                yerr=cfg_data["std"].fillna(0),
                marker="o", capsize=4, linewidth=2,
                color=COLORS.get(cfg, "#333333"), label=cfg.upper(),
            )

        ax.set_title(titles[ratio])
        ax.set_xlabel("Razina konkurentnosti (C)")
        ax.set_xticks(sorted(subset["ConcurrencyLevel"].unique()))
        ax.grid(alpha=0.3, linestyle="--")
        ax.axhline(100, color="crimson", linestyle=":", linewidth=1.2)

    axes[0].set_ylabel("Iskorištenost CPU-a SQL Servera (%)")
    axes[0].legend(title="Konfiguracija", frameon=True)
    fig.suptitle(
        "Iskorištenost procesora po konfiguraciji (mjereno: sys.dm_os_schedulers)",
        fontsize=13, fontweight="bold",
    )
    fig.tight_layout()
    save(fig, "14_cpu_utilization")


def plot_waits(waits: pd.DataFrame) -> None:
    """Raspodjela čekanja po mehanizmu — pokazuje KOJI resurs je usko grlo."""
    highest = waits["ConcurrencyLevel"].max()
    subset = waits[
        (waits["ConcurrencyLevel"] == highest) & (waits["OltpOlapRatio"] == "50_50")
    ]
    if subset.empty:
        print("  [preskačem 15_wait_breakdown: nema podataka za 50_50 pri najvišem C]")
        return

    pivot = (
        subset.groupby(["ConfigBase", "WaitGroup"])["WaitTimeMs"].mean().unstack(fill_value=0)
    )
    # Udio umjesto apsolutnih ms: konfiguracije se razlikuju po ukupnom broju
    # operacija, pa apsolutna čekanja nisu direktno usporediva.
    share = pivot.div(pivot.sum(axis=1), axis=0) * 100
    share = share.reindex([c for c in ["cs", "im", "htap"] if c in share.index])

    fig, ax = plt.subplots(figsize=(9, 5.2))
    share.plot(kind="barh", stacked=True, ax=ax, colormap="tab20", width=0.6)

    ax.set_xlabel("Udio ukupnog vremena čekanja (%)")
    ax.set_ylabel("")
    ax.set_yticklabels([c.upper() for c in share.index])
    ax.set_xlim(0, 100)
    ax.legend(title="Mehanizam", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=9)
    ax.set_title(
        f"Raspodjela čekanja po mehanizmu — omjer 50%/50%, C={highest}\n"
        "(mjereno: sys.dm_os_wait_stats, delta mjernog prozora)",
        fontsize=12, fontweight="bold",
    )
    ax.grid(axis="x", alpha=0.3, linestyle="--")
    fig.tight_layout()
    save(fig, "15_wait_breakdown")


def save(fig, name: str) -> None:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / f"{name}.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Figura: {path.relative_to(ROOT)}")


def write_report(usage: pd.DataFrame, waits: pd.DataFrame, summary: pd.DataFrame) -> None:
    lines: list[str] = []
    add = lines.append

    add("=" * 78)
    add("HTAPBenchmark: profil potrošnje resursa")
    add(f"N runova: {len(usage)}")
    add("=" * 78)
    add("")
    add("Mjereno instance-wide iz sys.dm_os_schedulers i sys.dm_os_wait_stats.")
    add("Vrijednosti vrijede uz pretpostavku da je benchmark jedino opterećenje")
    add("na instanci — što je uvjet i za svaki drugi alat koji koristi te DMV-ove.")
    add("")

    add("-" * 78)
    add("1. ISKORIŠTENOST CPU-a (% kapaciteta dostupnog SQL Serveru)")
    add("-" * 78)
    for ratio in ["80_20", "50_50", "20_80"]:
        rows = summary[summary["OltpOlapRatio"] == ratio]
        if rows.empty:
            continue
        add(f"\n  Omjer {ratio}:")
        for c in sorted(rows["ConcurrencyLevel"].unique()):
            add(f"    C={c}:")
            for _, r in rows[rows["ConcurrencyLevel"] == c].iterrows():
                add(f"      {r['ConfigBase']:<10} CPU={r['CpuUtilPct_mean']:6.1f}% "
                    f"(SD={r['CpuUtilPct_sd']:5.1f})  signal_wait={r['SignalWaitPct_mean']:5.1f}%")

    add("")
    add("-" * 78)
    add("2. NAJVEĆA ČEKANJA PO KONFIGURACIJI (prosjek ms po runu)")
    add("-" * 78)
    for cfg in sorted(waits["ConfigBase"].unique()):
        add(f"\n  {cfg.upper()}:")
        top = (
            waits[waits["ConfigBase"] == cfg]
            .groupby("WaitType")["WaitTimeMs"].mean()
            .sort_values(ascending=False).head(8)
        )
        for wait_type, ms in top.items():
            add(f"    {wait_type:<34} {ms:12.1f} ms   [{classify_wait(wait_type)}]")

    add("")
    add("-" * 78)
    add("3. INTERPRETACIJA")
    add("-" * 78)
    add("  Visok SOS_SCHEDULER_YIELD i visok udio signal waita = CPU je usko grlo")
    add("  (niti su spremne za izvršavanje, ali čekaju scheduler).")
    add("  Visok RESOURCE_SEMAPHORE = čekanje na dodjelu memorije za batch-mode upite.")
    add("  Visok PAGEIOLATCH_* = disk I/O je usko grlo.")
    add("")
    add("  Tvrdnja rada da row-mode OLAP u IM konfiguraciji zasićuje CPU potvrđena je")
    add("  ako IM pokazuje istovremeno (a) višu iskorištenost CPU-a i (b) veći udio")
    add("  CPU-vezanih čekanja od HTAP-a pri istom opterećenju.")

    path = RESULTS_DIR / "resource_profile_report.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Izvještaj: {path.relative_to(ROOT)}")


def main() -> None:
    print("=" * 78)
    print("06: Profil potrošnje resursa (CPU + čekanja)")
    print("=" * 78)

    usage, waits = load()
    summary = cpu_summary(usage)

    out_csv = RESULTS_DIR / "resource_profile_summary.csv"
    summary.to_csv(out_csv, index=False)
    print(f"  Tabela: {out_csv.relative_to(ROOT)}")

    plot_cpu(usage)
    plot_waits(waits)
    write_report(usage, waits, summary)

    print("\nGotovo.")


if __name__ == "__main__":
    main()
