"""
HTAPBenchmark: 05_regression_anova.py
Regresijska i ANOVA analiza rezultata benchmarka

Analize:
  1. OLS regresija: log(OltpThroughput) ~ Konfiguracija + Omjer + Konkurentnost
     - Procjena koeficijenata, T-statistike, p-vrijednosti, R²
     - Konfiguracija "baseline" je referentna kategorija

  2. OLS regresija: log(OlapLatencyP50) ~ Konfiguracija + Omjer + Konkurentnost

  3. Jednosmjerna ANOVA: razlike throughputa unutar svake konfiguracije
     po omjeru opterećenja (F-statistika, p-vrijednost, eta²)

  4. Dvofaktorska ANOVA: Konfiguracija × OltpOlapRatio interakcija

Izlaz:
  - Results/regression_oltp_throughput.csv
  - Results/regression_olap_latency.csv
  - Results/anova_results.csv
  - Results/regression_report.txt
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import stats as scipy_stats

try:
    import statsmodels.formula.api as smf
    import statsmodels.api as sm
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False
    print("UPOZORENJE: statsmodels nije instaliran. Pokrenite: pip install statsmodels")
    print("           Analiza će se izvršiti s reduciranim skupom testova.\n")

SUMMARY_CSV = Path("../Results/summary.csv")
OUTPUT_DIR  = Path("../Results")

CONFIGS = ["baseline", "cs", "im", "htap"]
RATIOS  = ["80_20", "50_50", "20_80"]


def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Fajl nije pronađen: {path}")
    df = pd.read_csv(path)
    df["Configuration"] = pd.Categorical(df["Configuration"], categories=CONFIGS, ordered=True)
    df["OltpOlapRatio"]  = pd.Categorical(df["OltpOlapRatio"], categories=RATIOS, ordered=True)
    # Log-transformacija za regresiju (normalizira desno-skošenu distribuciju throughputa)
    df["LogOltpThroughput"] = np.log(df["OltpThroughput"].replace(0, np.nan))
    df["LogOlapLatencyP50"] = np.log(df["OlapLatencyP50"].replace(0, np.nan))
    df["LogConcurrency"]    = np.log(df["ConcurrencyLevel"])
    return df.dropna(subset=["LogOltpThroughput", "LogOlapLatencyP50"])


def eta_squared(groups) -> float:
    """Izračun eta² (veličina efekta za ANOVA): SS_between / SS_total"""
    all_vals  = np.concatenate(groups)
    grand_mean = np.mean(all_vals)
    ss_total   = np.sum((all_vals - grand_mean) ** 2)
    ss_between = sum(len(g) * (np.mean(g) - grand_mean) ** 2 for g in groups)
    return ss_between / ss_total if ss_total > 0 else 0.0


def run_one_way_anova(df: pd.DataFrame, metric: str, factor: str, report_lines: list) -> pd.DataFrame:
    """
    Jednosmjerna ANOVA: testira razlike u `metric` po razinama `factor`
    unutar svake konfiguracije.
    """
    results = []
    for config in CONFIGS:
        subset = df[df["Configuration"] == config]
        groups = [grp[metric].dropna().values for _, grp in subset.groupby(factor)]
        groups = [g for g in groups if len(g) >= 3]

        if len(groups) < 2:
            continue

        f_stat, p_val = scipy_stats.f_oneway(*groups)
        eta2 = eta_squared(groups)
        sig  = "✓ ZNAČAJNO" if p_val < 0.05 else "✗ nije značajno"

        line = (f"  {config:>8} | {factor:>16}: F={f_stat:>9.3f}  p={p_val:.6f}  "
                f"η²={eta2:.4f}  {sig}")
        print(line)
        report_lines.append(line)
        results.append({
            "Test":          "One-Way ANOVA",
            "Configuration": config,
            "Metrika":       metric,
            "Faktor":        factor,
            "F":             round(f_stat, 4),
            "p_value":       round(p_val, 6),
            "eta_squared":   round(eta2, 4),
            "Significant":   p_val < 0.05,
        })

    return pd.DataFrame(results)


def run_ols_regression(df: pd.DataFrame, formula: str, name: str,
                       report_lines: list) -> pd.DataFrame:
    """
    OLS regresija s dummijima za kategoričke varijable.
    Referentna kategorija: Configuration='baseline', OltpOlapRatio='80_20'
    """
    if not HAS_STATSMODELS:
        report_lines.append(f"  [{name}] Preskočeno — statsmodels nije dostupan.")
        return pd.DataFrame()

    model  = smf.ols(formula, data=df).fit()

    report_lines.append(f"\n  Zavisna varijabla: {name}")
    report_lines.append(f"  Formula: {formula}")
    report_lines.append(f"  N = {int(model.nobs)},  R² = {model.rsquared:.4f},  "
                        f"Adj. R² = {model.rsquared_adj:.4f}")
    report_lines.append(f"  F-statistika modela: {model.fvalue:.2f}  (p={model.f_pvalue:.2e})")
    report_lines.append("")
    report_lines.append(f"  {'Parametar':<40} {'Koeficijent':>12} {'Std.greška':>11} "
                        f"{'T-stat':>9} {'p-vrijednost':>13} {'Sig.':>6}")
    report_lines.append("  " + "-" * 95)

    rows = []
    for param, coef, se, t, p in zip(
        model.params.index,
        model.params,
        model.bse,
        model.tvalues,
        model.pvalues
    ):
        sig = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else ""))
        report_lines.append(
            f"  {param:<40} {coef:>12.4f} {se:>11.4f} {t:>9.3f} {p:>13.6f} {sig:>6}"
        )
        rows.append({
            "Model":        name,
            "Parametar":    param,
            "Koeficijent":  round(coef, 6),
            "StdGreska":    round(se, 6),
            "T_stat":       round(t, 4),
            "p_value":      round(p, 6),
            "Significant":  p < 0.05,
            "R_squared":    round(model.rsquared, 4),
            "Adj_R_squared": round(model.rsquared_adj, 4),
            "N":            int(model.nobs),
        })

    return pd.DataFrame(rows)


def main():
    print("=" * 70)
    print("HTAPBenchmark: Regresijska i ANOVA analiza (05_regression_anova)")
    print("=" * 70)

    df = load_data(SUMMARY_CSV)
    print(f"Učitano {len(df)} runova.")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_lines = []

    def log(line: str = ""):
        print(line)
        report_lines.append(line)

    log("=" * 70)
    log("HTAPBenchmark: Regresijska i ANOVA analiza")
    log(f"N = {len(df)} runova | Alpha = 0.05")
    log("=" * 70)

    # ================================================================
    # 1. JEDNOSMJERNA ANOVA
    # ================================================================
    log("\n" + "─" * 70)
    log("1. JEDNOSMJERNA ANOVA")
    log("─" * 70)

    anova_results = []

    log("\n  1a. Uticaj OltpOlapRatio na OltpThroughput (po konfiguraciji):")
    r1 = run_one_way_anova(df, "OltpThroughput", "OltpOlapRatio", report_lines)
    anova_results.append(r1)

    log("\n  1b. Uticaj ConcurrencyLevel na OltpThroughput (po konfiguraciji):")
    r2 = run_one_way_anova(df, "OltpThroughput", "ConcurrencyLevel", report_lines)
    anova_results.append(r2)

    log("\n  1c. Uticaj OltpOlapRatio na OlapLatencyP50 (po konfiguraciji):")
    r3 = run_one_way_anova(df, "OlapLatencyP50", "OltpOlapRatio", report_lines)
    anova_results.append(r3)

    log("\n  1d. Uticaj ConcurrencyLevel na OlapLatencyP50 (po konfiguraciji):")
    r4 = run_one_way_anova(df, "OlapLatencyP50", "ConcurrencyLevel", report_lines)
    anova_results.append(r4)

    anova_df = pd.concat(anova_results, ignore_index=True)

    # ================================================================
    # 2. OLS REGRESIJA — OLTP Throughput
    # ================================================================
    log("\n" + "─" * 70)
    log("2. OLS REGRESIJA: log(OltpThroughput)")
    log("─" * 70)
    log("   Referentna kategorija: Configuration='baseline', OltpOlapRatio='80_20'")

    formula_oltp = (
        "LogOltpThroughput ~ "
        "C(Configuration, Treatment(reference='baseline')) + "
        "C(OltpOlapRatio, Treatment(reference='80_20')) + "
        "LogConcurrency"
    )

    oltp_reg = run_ols_regression(df, formula_oltp,
                                  "log(OltpThroughput)", report_lines)

    # ================================================================
    # 3. OLS REGRESIJA — OLAP Latency P50
    # ================================================================
    log("\n" + "─" * 70)
    log("3. OLS REGRESIJA: log(OlapLatencyP50)")
    log("─" * 70)

    formula_olap = (
        "LogOlapLatencyP50 ~ "
        "C(Configuration, Treatment(reference='baseline')) + "
        "C(OltpOlapRatio, Treatment(reference='80_20')) + "
        "LogConcurrency"
    )

    olap_reg = run_ols_regression(df, formula_olap,
                                  "log(OlapLatencyP50)", report_lines)

    # ================================================================
    # 4. TUMAČENJE — brzi pregled
    # ================================================================
    log("\n" + "─" * 70)
    log("4. BRZI PREGLED REZULTATA")
    log("─" * 70)

    for config in ["cs", "im", "htap"]:
        oltp_rows = oltp_reg[oltp_reg["Parametar"].str.contains(config, case=False)]
        if not oltp_rows.empty:
            row = oltp_rows.iloc[0]
            pct  = (np.exp(row["Koeficijent"]) - 1) * 100
            sig  = "✓" if row["Significant"] else "✗"
            log(f"  OLTP {config:>8} vs baseline: {pct:+.1f}%  (p={row['p_value']:.4f}) {sig}")

    # ================================================================
    # Pohrana rezultata
    # ================================================================
    anova_df.to_csv(OUTPUT_DIR / "anova_results.csv", index=False)
    log(f"\nANOVA rezultati:          {OUTPUT_DIR / 'anova_results.csv'}")

    if not oltp_reg.empty:
        oltp_reg.to_csv(OUTPUT_DIR / "regression_oltp_throughput.csv", index=False)
        log(f"Regresija OLTP:           {OUTPUT_DIR / 'regression_oltp_throughput.csv'}")

    if not olap_reg.empty:
        olap_reg.to_csv(OUTPUT_DIR / "regression_olap_latency.csv", index=False)
        log(f"Regresija OLAP latencija: {OUTPUT_DIR / 'regression_olap_latency.csv'}")

    report_path = OUTPUT_DIR / "regression_report.txt"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    log(f"Izvještaj pohranjen:       {report_path}")

    log("\nZavršeno.")


if __name__ == "__main__":
    main()
