"""
HTAPBenchmark: 02_statistical_tests.py
Statistički testovi za provjeru hipoteza

Testovi:
  1. Kruskal-Wallis H-test: globalne razlike između 4 konfiguracije
  2. Mann-Whitney U test + Bonferroni korekcija: parne usporedbe
  3. Cohen's d: veličina efekta za svaki par

Hipoteze:
  H1: CS vs HTAP latencija pri niskoj vs visokoj konkurentnosti
  H2: Degradacija OLTP throughputa pri miješanom opterećenju (CS vs HTAP)
  H3: HTAP vs IM throughput pri transakcijskom opterećenju

Izlaz:
  - Results/statistical_tests.csv
  - Results/hypothesis_results.txt
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

import itertools
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")

SUMMARY_CSV  = Path("../Results/summary.csv")
OUTPUT_CSV   = Path("../Results/statistical_tests.csv")
HYPOTHESIS_TXT = Path("../Results/hypothesis_results.txt")

CONFIGS = ["baseline", "cs", "im", "htap"]
ALPHA   = 0.05  # razina značajnosti


# ----------------------------------------------------------------
# Pomoćne funkcije
# ----------------------------------------------------------------

def cohen_d(x: np.ndarray, y: np.ndarray) -> float:
    """Cohen's d = (mean_x - mean_y) / pooled_std"""
    nx, ny   = len(x), len(y)
    if nx < 2 or ny < 2:
        return np.nan
    var_x, var_y = np.var(x, ddof=1), np.var(y, ddof=1)
    pooled_std = np.sqrt(((nx - 1) * var_x + (ny - 1) * var_y) / (nx + ny - 2))
    if pooled_std == 0:
        return 0.0
    return (np.mean(x) - np.mean(y)) / pooled_std


def effect_size_label(d: float) -> str:
    """Cohen-ova konvencija: |d| < 0.2 = trivijalan, 0.2-0.5 = mali, 0.5-0.8 = srednji, >0.8 = veliki"""
    ad = abs(d)
    if ad < 0.20: return "trivijalan"
    if ad < 0.50: return "mali"
    if ad < 0.80: return "srednji"
    return "veliki"


def kruskal_wallis_test(df: pd.DataFrame, metric: str, group_col: str = "Configuration") -> dict:
    """Kruskal-Wallis H-test za zadanu metriku i grupirajuću kolonu."""
    groups = [g[metric].dropna().values for _, g in df.groupby(group_col)]
    if len(groups) < 2:
        return {"H": np.nan, "p_value": np.nan, "df": np.nan}
    h_stat, p_val = stats.kruskal(*groups)
    return {"H": round(h_stat, 4), "p_value": round(p_val, 6), "df": len(groups) - 1}


def mann_whitney_pairwise(
    df: pd.DataFrame,
    metric: str,
    group_col: str = "Configuration",
    alternative: str = "two-sided"
) -> pd.DataFrame:
    """
    Mann-Whitney U test za sve parove, s Bonferroni korekcijom.
    Vraća DataFrame s kolonama: Group1, Group2, U, p_raw, p_bonferroni, CohenD, EffectSize, Significant
    """
    groups_list = df[group_col].unique().tolist()
    pairs = list(itertools.combinations(groups_list, 2))
    n_pairs = len(pairs)
    results = []

    for g1, g2 in pairs:
        x = df[df[group_col] == g1][metric].dropna().values
        y = df[df[group_col] == g2][metric].dropna().values

        if len(x) < 3 or len(y) < 3:
            continue

        u_stat, p_raw = stats.mannwhitneyu(x, y, alternative=alternative)
        p_bonf = min(p_raw * n_pairs, 1.0)
        d      = cohen_d(x, y)

        results.append({
            "Group1":       g1,
            "Group2":       g2,
            "N1":           len(x),
            "N2":           len(y),
            "U":            round(u_stat, 2),
            "p_raw":        round(p_raw, 6),
            "p_bonferroni": round(p_bonf, 6),
            "CohenD":       round(d, 4),
            "EffectSize":   effect_size_label(d),
            "Significant":  p_bonf < ALPHA
        })

    return pd.DataFrame(results)


def degradation_ratio(
    df: pd.DataFrame,
    config: str,
    oltp_metric: str,
    baseline_ratio: str,
    mixed_ratio: str
) -> np.ndarray:
    """Izračun degradacije: (baseline_oltp - mixed_oltp) / baseline_oltp * 100"""
    base   = df[(df["Configuration"] == config) & (df["OltpOlapRatio"] == baseline_ratio)][oltp_metric].values
    mixed  = df[(df["Configuration"] == config) & (df["OltpOlapRatio"] == mixed_ratio)][oltp_metric].values
    n = min(len(base), len(mixed))
    if n == 0:
        return np.array([])
    return (base[:n] - mixed[:n]) / np.where(base[:n] != 0, base[:n], 1) * 100


# ----------------------------------------------------------------
# Glavni program
# ----------------------------------------------------------------

def main():
    if not SUMMARY_CSV.exists():
        raise FileNotFoundError(
            f"Fajl nije pronađen: {SUMMARY_CSV}\n"
            "Pokrenite benchmark aplikaciju."
        )

    df = pd.read_csv(SUMMARY_CSV)
    all_results = []
    report_lines = []

    def log(line: str = ""):
        print(line)
        report_lines.append(line)

    log("=" * 70)
    log("HTAPBenchmark: Statistički testovi")
    log(f"Ukupno runova: {len(df)}")
    log(f"Alpha (razina značajnosti): {ALPHA}")
    log(f"Korekcija višestrukih usporedbi: Bonferroni")
    log("=" * 70)

    # ================================================================
    # BLOK 1: Kruskal-Wallis za globalne razlike
    # ================================================================
    log("\n" + "─" * 70)
    log("1. KRUSKAL-WALLIS H-TEST (globalne razlike između konfiguracija)")
    log("─" * 70)

    kw_metrics = [
        ("OltpThroughput",  "OLTP Throughput (ops/s)"),
        ("OlapThroughput",  "OLAP Throughput (q/s)"),
        ("OltpLatencyP50",  "OLTP Latencija P50 (ms)"),
        ("OltpLatencyP95",  "OLTP Latencija P95 (ms)"),
        ("OlapLatencyP50",  "OLAP Latencija P50 (ms)"),
        ("OlapLatencyP95",  "OLAP Latencija P95 (ms)"),
    ]

    for metric, label in kw_metrics:
        for concurrency in sorted(df["ConcurrencyLevel"].unique()):
            subset = df[df["ConcurrencyLevel"] == concurrency]
            kw = kruskal_wallis_test(subset, metric)
            sig = "✓ ZNAČAJNO" if kw["p_value"] < ALPHA else "✗ nije značajno"
            log(f"  {label:<35} C={concurrency:>2}:  H={kw['H']:>9.3f}  p={kw['p_value']:.6f}  {sig}")
            all_results.append({
                "Test":         "Kruskal-Wallis",
                "Metrika":      metric,
                "ConcurrencyLevel": concurrency,
                "OltpOlapRatio": "sve",
                "Group1":       "sve",
                "Group2":       "sve",
                **kw
            })

    # ================================================================
    # BLOK 2: Mann-Whitney + Bonferroni za parne usporedbe
    # ================================================================
    log("\n" + "─" * 70)
    log("2. MANN-WHITNEY U TEST + BONFERRONI KOREKCIJA (parne usporedbe)")
    log("─" * 70)

    for metric, label in kw_metrics:
        log(f"\n  Metrika: {label}")
        for ratio in sorted(df["OltpOlapRatio"].unique()):
            for concurrency in sorted(df["ConcurrencyLevel"].unique()):
                # Stratificiramo po omjeru opterećenja da izbjegnemo confounding
                subset = df[(df["ConcurrencyLevel"] == concurrency) &
                            (df["OltpOlapRatio"]    == ratio)]
                pairwise = mann_whitney_pairwise(subset, metric)

                if pairwise.empty:
                    continue

                for _, row in pairwise.iterrows():
                    sig = "✓" if row["Significant"] else "✗"
                    log(f"    {ratio} C={concurrency}: {row['Group1']:>8} vs {row['Group2']:<8} | "
                        f"U={row['U']:>12,.0f} | p_bonf={row['p_bonferroni']:.4f} | "
                        f"d={row['CohenD']:>+6.3f} ({row['EffectSize']}) {sig}")

                    all_results.append(row.to_dict() | {
                        "Test":            "Mann-Whitney",
                        "Metrika":         metric,
                        "OltpOlapRatio":   ratio,
                        "ConcurrencyLevel": concurrency,
                    })

    # ================================================================
    # BLOK 3: Testiranje hipoteza
    # ================================================================
    log("\n" + "═" * 70)
    log("3. PROVJERA HIPOTEZA")
    log("═" * 70)

    # ------- H1: CS vs HTAP latencija pri niskoj vs visokoj konkurentnosti -------
    log("\n  H1: Latencija CS ≈ HTAP pri niskoj konkurentnosti,")
    log("       ali razlika je značajna pri visokoj konkurentnosti.")

    for concurrency, concurrency_label in [(4, "NISKA (C=4)"), (32, "VISOKA (C=32)")]:
        subset = df[(df["ConcurrencyLevel"] == concurrency) & (df["OltpOlapRatio"] == "50_50")]
        cs_lat   = subset[subset["Configuration"] == "cs"]["OlapLatencyP50"].dropna().values
        htap_lat = subset[subset["Configuration"] == "htap"]["OlapLatencyP50"].dropna().values

        if len(cs_lat) >= 3 and len(htap_lat) >= 3:
            _, p = stats.mannwhitneyu(cs_lat, htap_lat, alternative="two-sided")
            p_bonf = min(p * 6, 1.0)
            d = cohen_d(cs_lat, htap_lat)
            sig = p_bonf < ALPHA
            log(f"    Konkurentnost {concurrency_label}: CS P50={np.median(cs_lat):.1f}ms, "
                f"HTAP P50={np.median(htap_lat):.1f}ms | "
                f"p_bonf={p_bonf:.4f} | d={d:.3f} ({effect_size_label(d)}) | "
                f"{'POTVRĐENO' if sig else 'NIJE POTVRĐENO'}")

    # ------- H2: Degradacija OLTP throughputa CS vs HTAP -------
    log("\n  H2: Degradacija OLTP propusnosti pri miješanom opterećenju je veća")
    log("       kod CS nego kod HTAP konfiguracije.")

    degrad_cs   = degradation_ratio(df[df["ConcurrencyLevel"] == 16], "cs",   "OltpThroughput", "80_20", "50_50")
    degrad_htap = degradation_ratio(df[df["ConcurrencyLevel"] == 16], "htap", "OltpThroughput", "80_20", "50_50")

    if len(degrad_cs) >= 3 and len(degrad_htap) >= 3:
        _, p = stats.mannwhitneyu(degrad_cs, degrad_htap, alternative="greater")
        p_bonf = min(p * 6, 1.0)
        d = cohen_d(degrad_cs, degrad_htap)
        log(f"    CS degradacija:   {np.mean(degrad_cs):.2f}% ± {np.std(degrad_cs):.2f}%")
        log(f"    HTAP degradacija: {np.mean(degrad_htap):.2f}% ± {np.std(degrad_htap):.2f}%")
        log(f"    Mann-Whitney (CS > HTAP): p_bonf={p_bonf:.4f} | d={d:.3f} | "
            f"{'POTVRĐENO' if p_bonf < ALPHA else 'NIJE POTVRĐENO'}")

    # ------- H3: HTAP vs IM throughput pri OLTP-teškom opterećenju -------
    log("\n  H3: HTAP ne ostvaruje statistički značajno veću OLTP propusnost")
    log("       od IM konfiguracije pri transakcijskom opterećenju (80/20).")

    for concurrency in [4, 16, 32]:
        subset = df[(df["ConcurrencyLevel"] == concurrency) & (df["OltpOlapRatio"] == "80_20")]
        im_thr   = subset[subset["Configuration"] == "im"]["OltpThroughput"].dropna().values
        htap_thr = subset[subset["Configuration"] == "htap"]["OltpThroughput"].dropna().values

        if len(im_thr) >= 3 and len(htap_thr) >= 3:
            _, p = stats.mannwhitneyu(im_thr, htap_thr, alternative="two-sided")
            p_bonf = min(p * 6, 1.0)
            d = cohen_d(im_thr, htap_thr)
            sig = p_bonf < ALPHA
            log(f"    C={concurrency}: IM={np.median(im_thr):.1f}ops/s, HTAP={np.median(htap_thr):.1f}ops/s | "
                f"p_bonf={p_bonf:.4f} | d={d:.3f} | "
                f"{'ODBAČENA' if sig else 'NIJE ODBAČENA (H3 potvrđena)'}")

    # ================================================================
    # Pohrana rezultata
    # ================================================================
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    results_df = pd.DataFrame(all_results)
    results_df.to_csv(OUTPUT_CSV, index=False)
    log(f"\nSvi rezultati pohraneni: {OUTPUT_CSV}")

    HYPOTHESIS_TXT.write_text("\n".join(report_lines), encoding="utf-8")
    log(f"Izvještaj pohranjen:     {HYPOTHESIS_TXT}")


if __name__ == "__main__":
    main()
