"""
HTAPBenchmark: 04_per_operation_stats.py
Per-operacijska statistika iz sirovih mjerenja (measurements.csv)

Izračunava za svaku kombinaciju (Konfiguracija × Operacija):
  - N (broj izvršavanja)
  - averageExecutionTime  — prosječno vrijeme izvršavanja (ms)
  - minimumExecutionTime  — najkraće vrijeme izvršavanja (ms)
  - maximumExecutionTime  — najduže vrijeme izvršavanja (ms)
  - totalExecutionTime    — ukupno vrijeme izvršavanja (ms)
  - P50, P95, P99         — percentili latencije
  - SuccessRate           — stopa uspješnosti

Kategorizacija operacija (prema zahtjevu predmeta):
  Simple SELECT  → usp_GetPostById, usp_GetUserById
  Complex SELECT → OLAP_Q1 … OLAP_Q5  (JOIN, GROUP BY, ORDER BY, agregacije)
  Simple INSERT  → usp_InsertVote
  Complex INSERT → usp_InsertComment  (višetablični UPDATE + INSERT)
  Simple UPDATE  → usp_UpdatePostScore
  Complex UPDATE → usp_GetRecentUserPosts  (range scan s ORDER BY)
  Simple DELETE  → usp_DeleteVote          (ako je prisutan u podacima)
  Complex DELETE → usp_DeletePostVotes     (ako je prisutan)

Izlaz:
  - Results/per_operation_stats.csv
  - Results/per_operation_stats.xlsx
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
import numpy as np
from pathlib import Path

MEASUREMENTS_CSV = Path("../Results/measurements.csv")
OUTPUT_CSV       = Path("../Results/per_operation_stats.csv")
OUTPUT_XLSX      = Path("../Results/per_operation_stats.xlsx")

# Mapiranje naziva operacije → kategorija (zahtjev predmeta)
OPERATION_CATEGORY = {
    "usp_GetPostById":        "Simple SELECT",
    "usp_GetUserById":        "Simple SELECT",
    "usp_InsertVote":         "Simple INSERT",
    "usp_InsertComment":      "Complex INSERT",
    "usp_UpdatePostScore":    "Simple UPDATE",
    "usp_GetRecentUserPosts": "Complex SELECT (Range Scan)",
    "usp_DeleteVote":         "Simple DELETE",
    "usp_DeletePostVotes":    "Complex DELETE",
    # OLAP upiti — nazivi kako se pojavljuju u measurements.csv
    "Q1_MonthlyActivity":      "Complex SELECT (OLAP)",
    "Q2_TopContributors":      "Complex SELECT (OLAP)",
    "Q3_VoteDistribution":     "Complex SELECT (OLAP)",
    "Q4_TimeToAnswer":         "Complex SELECT (OLAP)",
    "Q5_UserCohortActivity":   "Complex SELECT (OLAP)",
}

CONFIGS = ["baseline", "cs", "im", "htap"]


def load_measurements(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Fajl nije pronađen: {path}\n"
            "Pokrenite benchmark aplikaciju da generirate measurements.csv"
        )
    print(f"Učitavam {path} ...")
    df = pd.read_csv(path, dtype={
        "Configuration":   "category",
        "OltpOlapRatio":   "category",
        "OperationType":   "category",
        "OperationName":   "category",
        "Success":         "int8"
    })
    print(f"  Ukupno redova: {len(df):,}")
    return df


def percentile(x, q):
    return np.percentile(x, q) if len(x) > 0 else np.nan


def compute_op_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Izračunava N, avg/min/max/total/P50/P95/P99 i SuccessRate
    po (Configuration, OperationType, OperationName).
    Filtrira samo uspješne operacije za statistiku latencije.
    """
    rows = []
    group_cols = ["Configuration", "OperationType", "OperationName"]

    for (config, op_type, op_name), grp in df.groupby(group_cols, observed=True):
        total_calls = len(grp)
        success_df  = grp[grp["Success"] == 1]
        n_success   = len(success_df)

        if n_success == 0:
            continue

        lat = success_df["LatencyMs"].values

        rows.append({
            "Configuration":       config,
            "OperationType":       op_type,
            "OperationName":       op_name,
            "Category":            OPERATION_CATEGORY.get(op_name, "Ostalo"),
            "N_total":             total_calls,
            "N_success":           n_success,
            "SuccessRate":         round(n_success / total_calls * 100, 2),
            # Zahtjev predmeta: avg / min / max / total
            "averageExecutionTime_ms": round(np.mean(lat),  4),
            "minimumExecutionTime_ms": round(np.min(lat),   4),
            "maximumExecutionTime_ms": round(np.max(lat),   4),
            "totalExecutionTime_ms":   round(np.sum(lat),   2),
            # Percentili
            "P50_ms":  round(percentile(lat, 50), 4),
            "P95_ms":  round(percentile(lat, 95), 4),
            "P99_ms":  round(percentile(lat, 99), 4),
        })

    return pd.DataFrame(rows)


def compute_op_stats_by_config(df: pd.DataFrame) -> pd.DataFrame:
    """
    Iste statistike ali stratificirano po konfiguraciji i omjeru opterećenja.
    Korisno za usporedbu Simple/Complex SELECT/INSERT/UPDATE/DELETE po konfiguraciji.
    """
    rows = []
    group_cols = ["Configuration", "OltpOlapRatio", "ConcurrencyLevel",
                  "OperationType", "OperationName"]

    for (config, ratio, concurrency, op_type, op_name), grp in df.groupby(group_cols, observed=True):
        success_df = grp[grp["Success"] == 1]
        n_success  = len(success_df)
        n_total    = len(grp)

        if n_success < 5:  # Premalo podataka za smislenu statistiku
            continue

        lat = success_df["LatencyMs"].values

        rows.append({
            "Configuration":       config,
            "OltpOlapRatio":       ratio,
            "ConcurrencyLevel":    concurrency,
            "OperationType":       op_type,
            "OperationName":       op_name,
            "Category":            OPERATION_CATEGORY.get(op_name, "Ostalo"),
            "N_success":           n_success,
            "SuccessRate":         round(n_success / n_total * 100, 2),
            "averageExecutionTime_ms": round(np.mean(lat),  4),
            "minimumExecutionTime_ms": round(np.min(lat),   4),
            "maximumExecutionTime_ms": round(np.max(lat),   4),
            "totalExecutionTime_ms":   round(np.sum(lat),   2),
            "P50_ms":  round(percentile(lat, 50), 4),
            "P95_ms":  round(percentile(lat, 95), 4),
            "P99_ms":  round(percentile(lat, 99), 4),
        })

    return pd.DataFrame(rows)


def print_summary_table(stats: pd.DataFrame):
    """Ispiši sažetak u konzolu — avg latencija po kategoriji i konfiguraciji."""
    print("\n" + "=" * 80)
    print("PROSJEČNO VRIJEME IZVRŠAVANJA po kategoriji operacije i konfiguraciji (ms)")
    print("=" * 80)

    # Pivot: redovi = kategorija, kolone = konfiguracija
    pivot = stats.groupby(["Category", "Configuration"])["averageExecutionTime_ms"].mean().unstack("Configuration")

    # Sortiraj po prosječnoj latenciji (baseline stupac ili prva kolona)
    first_col = pivot.columns[0]
    pivot = pivot.sort_values(first_col, ascending=True)

    # Formatiraj za ispis
    col_order = [c for c in CONFIGS if c in pivot.columns]
    pivot = pivot[col_order]
    print(pivot.round(3).to_string())

    print("\n" + "=" * 80)
    print("MIN / AVG / MAX / TOTAL (ms) — sve konfiguracije, sve operacije")
    print("=" * 80)

    summary = stats[["Category", "minimumExecutionTime_ms",
                      "averageExecutionTime_ms", "maximumExecutionTime_ms",
                      "totalExecutionTime_ms"]].groupby("Category").agg({
        "minimumExecutionTime_ms": "min",
        "averageExecutionTime_ms": "mean",
        "maximumExecutionTime_ms": "max",
        "totalExecutionTime_ms":   "sum",
    }).round(2)
    summary.columns = ["Min (ms)", "Avg (ms)", "Max (ms)", "Total (ms)"]
    print(summary.to_string())


def main():
    print("=" * 70)
    print("HTAPBenchmark: Per-operacijska statistika (04_per_operation_stats)")
    print("=" * 70)

    df = load_measurements(MEASUREMENTS_CSV)

    # ----------------------------------------------------------------
    # 1. Agregirane statistike po konfiguraciji + operaciji (sve ratios + concurrencies)
    # ----------------------------------------------------------------
    print("\nIzračun agregirane statistike ...")
    stats_agg = compute_op_stats(df)

    # ----------------------------------------------------------------
    # 2. Statistike stratificirane po omjeru i konkurentnosti
    # ----------------------------------------------------------------
    print("Izračun stratificirane statistike ...")
    stats_detailed = compute_op_stats_by_config(df)

    # ----------------------------------------------------------------
    # Ispis u konzolu
    # ----------------------------------------------------------------
    print_summary_table(stats_agg)

    # ----------------------------------------------------------------
    # Pohrana CSV i Excel
    # ----------------------------------------------------------------
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    stats_agg.to_csv(OUTPUT_CSV, index=False)
    print(f"\nAgregirane statistike pohranene:   {OUTPUT_CSV}")

    detailed_csv = OUTPUT_CSV.parent / "per_operation_stats_detailed.csv"
    stats_detailed.to_csv(detailed_csv, index=False)
    print(f"Detaljne statistike pohranene:     {detailed_csv}")

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        stats_agg.to_excel(writer, sheet_name="Agregirano", index=False)
        stats_detailed.to_excel(writer, sheet_name="Detaljno", index=False)

        # Posebni sheeti po kategoriji
        for category in stats_detailed["Category"].unique():
            subset = stats_detailed[stats_detailed["Category"] == category]
            sheet = category[:31]  # Excel ograničenje
            subset.to_excel(writer, sheet_name=sheet, index=False)

    print(f"Excel pohranjen:                   {OUTPUT_XLSX}")
    print("\nZavršeno.")


if __name__ == "__main__":
    main()
