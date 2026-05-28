"""
HTAPBenchmark: 01_descriptive_stats.py
Deskriptivna statistika rezultata benchmarka

Izlaz:
  - Results/descriptive_summary.csv   - srednja vrijednost, SD, percentili po grupama
  - Results/descriptive_summary.xlsx  - formatirana Excel verzija
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
import numpy as np
from pathlib import Path

SUMMARY_CSV  = Path("../Results/summary.csv")
OUTPUT_CSV   = Path("../Results/descriptive_summary.csv")
OUTPUT_XLSX  = Path("../Results/descriptive_summary.xlsx")

CONFIGS = ["baseline", "cs", "im", "htap"]
RATIOS  = ["80_20", "50_50", "20_80"]
CONCURRENCIES = [4, 16, 32]

CONFIG_LABELS = {
    "baseline": "Baseline (B-tree)",
    "cs":       "CS (Columnstore)",
    "im":       "IM (In-Memory)",
    "htap":     "HTAP (IM+CS)",
}


def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Fajl nije pronađen: {path}\n"
            "Pokrenite benchmark aplikaciju da generirate results/summary.csv"
        )
    df = pd.read_csv(path)
    df["Configuration"] = pd.Categorical(df["Configuration"], categories=CONFIGS, ordered=True)
    df["OltpOlapRatio"]  = pd.Categorical(df["OltpOlapRatio"], categories=RATIOS, ordered=True)
    return df


def compute_group_stats(df: pd.DataFrame, metric: str, group_cols: list) -> pd.DataFrame:
    """Izračun deskriptivne statistike za zadanu metriku."""
    return df.groupby(group_cols)[metric].agg(
        N="count",
        Mean="mean",
        Median="median",
        SD="std",
        Min="min",
        P25=lambda x: np.percentile(x, 25),
        P75=lambda x: np.percentile(x, 75),
        P95=lambda x: np.percentile(x, 95),
        P99=lambda x: np.percentile(x, 99),
        Max="max",
        CV=lambda x: x.std() / x.mean() * 100 if x.mean() != 0 else 0  # koeficijent varijacije
    ).reset_index()


def main():
    print("=" * 60)
    print("HTAPBenchmark: Deskriptivna statistika")
    print("=" * 60)

    df = load_data(SUMMARY_CSV)

    print(f"\nUčitano {len(df)} runova iz {SUMMARY_CSV}")
    print(f"Konfiguracije: {df['Configuration'].unique().tolist()}")
    print(f"Ratio-i:       {df['OltpOlapRatio'].unique().tolist()}")
    print(f"Concurrency:   {sorted(df['ConcurrencyLevel'].unique().tolist())}")

    group_cols = ["Configuration", "OltpOlapRatio", "ConcurrencyLevel"]

    # ----------------------------------------------------------------
    # 1. OLTP Throughput (ops/s)
    # ----------------------------------------------------------------
    oltp_stats = compute_group_stats(df, "OltpThroughput", group_cols)
    oltp_stats.insert(0, "Metrika", "OLTP_Throughput_ops_s")

    # ----------------------------------------------------------------
    # 2. OLAP Throughput (q/s)
    # ----------------------------------------------------------------
    olap_stats = compute_group_stats(df, "OlapThroughput", group_cols)
    olap_stats.insert(0, "Metrika", "OLAP_Throughput_q_s")

    # ----------------------------------------------------------------
    # 3. OLTP Latencija P50 (ms)
    # ----------------------------------------------------------------
    oltp_p50 = compute_group_stats(df, "OltpLatencyP50", group_cols)
    oltp_p50.insert(0, "Metrika", "OLTP_Latency_P50_ms")

    # ----------------------------------------------------------------
    # 4. OLTP Latencija P95 (ms)
    # ----------------------------------------------------------------
    oltp_p95 = compute_group_stats(df, "OltpLatencyP95", group_cols)
    oltp_p95.insert(0, "Metrika", "OLTP_Latency_P95_ms")

    # ----------------------------------------------------------------
    # 5. OLAP Latencija P50 (ms)
    # ----------------------------------------------------------------
    olap_p50 = compute_group_stats(df, "OlapLatencyP50", group_cols)
    olap_p50.insert(0, "Metrika", "OLAP_Latency_P50_ms")

    # ----------------------------------------------------------------
    # 6. OLAP Latencija P95 (ms)
    # ----------------------------------------------------------------
    olap_p95 = compute_group_stats(df, "OlapLatencyP95", group_cols)
    olap_p95.insert(0, "Metrika", "OLAP_Latency_P95_ms")

    all_stats = pd.concat([oltp_stats, olap_stats, oltp_p50, oltp_p95, olap_p50, olap_p95],
                          ignore_index=True)

    # Zaokruži brojeve
    numeric_cols = ["Mean", "Median", "SD", "Min", "P25", "P75", "P95", "P99", "Max", "CV"]
    all_stats[numeric_cols] = all_stats[numeric_cols].round(4)

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    all_stats.to_csv(OUTPUT_CSV, index=False)
    print(f"\nDeskriptivna statistika pohranjena: {OUTPUT_CSV}")

    # Excel export s formatiranjem
    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        for metrika in all_stats["Metrika"].unique():
            subset = all_stats[all_stats["Metrika"] == metrika].drop(columns=["Metrika"])
            sheet_name = metrika[:31]  # Excel ograničenje naziva sheeta
            subset.to_excel(writer, sheet_name=sheet_name, index=False)
    print(f"Excel export pohranjen:            {OUTPUT_XLSX}")

    # ----------------------------------------------------------------
    # Ispiši pivot tabelu za brzi pregled
    # ----------------------------------------------------------------
    print("\n" + "=" * 60)
    print("PIVOT: OLTP Throughput (ops/s) - Mean ± SD po konfiguraciji i concurrency-u")
    print("=" * 60)

    pivot_oltp = df.groupby(["Configuration", "ConcurrencyLevel"])["OltpThroughput"].agg(
        ["mean", "std"]).round(2)
    pivot_oltp.columns = ["Mean", "SD"]
    pivot_oltp["Mean ± SD"] = pivot_oltp.apply(
        lambda r: f"{r['Mean']:.1f} ± {r['SD']:.1f}", axis=1)
    print(pivot_oltp["Mean ± SD"].unstack(level="ConcurrencyLevel").to_string())

    print("\n" + "=" * 60)
    print("PIVOT: OLAP Latency P50 (ms) - Mean ± SD po konfiguraciji i ratio-u")
    print("=" * 60)

    pivot_olap = df.groupby(["Configuration", "OltpOlapRatio"])["OlapLatencyP50"].agg(
        ["mean", "std"]).round(1)
    pivot_olap.columns = ["Mean", "SD"]
    pivot_olap["Mean ± SD"] = pivot_olap.apply(
        lambda r: f"{r['Mean']:.0f} ± {r['SD']:.0f}", axis=1)
    print(pivot_olap["Mean ± SD"].unstack(level="OltpOlapRatio").to_string())

    print("\nZavršeno. Pogledajte Results/ direktorij za izlazne fajlove.")


if __name__ == "__main__":
    main()
