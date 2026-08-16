"""
HTAPBenchmark: 07_h3_maxdop_control.py
Kontrolni eksperiment za hipotezu H3 — izjednačen stepen paralelizma

Problem: u glavnom mjerenju HTAP izvodi analitičke upite s OPTION (MAXDOP 2),
a IM s OPTION (MAXDOP 1), jer paralelni planovi nad Hekaton tablicama izazivaju
CXSYNC_PORT čekanja. Razlika u paralelizmu je zato confounding varijabla:
izmjereni jaz u OLTP propusnosti (3,3–6,9×) dijelom može poticati od nje,
a ne isključivo od dual-store arhitekture.

Kontrola: SQL/10_H3_MaxDop_Control.sql kreira _Dop1 varijante OLAP procedura
u kojima OBJE konfiguracije rade pri MAXDOP 1. Ovaj skript uspoređuje jaz
izmjeren u toj kontroli s jazom iz glavnog mjerenja i računa koliki dio
originalne razlike preživi izjednačavanje.

Ulaz:
  - Results/summary.csv             (glavno mjerenje, MAXDOP 2 vs 1)
  - Results/h3_control_summary.csv  (kontrola, MAXDOP 1 vs 1)

Izlaz:
  - Results/h3_control_report.txt
  - Results/h3_control_comparison.csv
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

import warnings
warnings.filterwarnings("ignore")

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

MAIN_CSV     = Path("../Results/summary.csv")
CONTROL_CSV  = Path("../Results/h3_control_summary.csv")
REPORT_TXT   = Path("../Results/h3_control_report.txt")
COMPARE_CSV  = Path("../Results/h3_control_comparison.csv")

RATIO = "80_20"          # H3 se tiče transakcijsko-intenzivnog opterećenja
ALPHA = 0.05
BONFERRONI_PAIRS = 6     # ista korekcija kao u 02_statistical_tests.py

report_lines: list[str] = []


def log(msg: str = "") -> None:
    print(msg)
    report_lines.append(msg)


def cohen_d(x: np.ndarray, y: np.ndarray) -> float:
    nx, ny = len(x), len(y)
    if nx < 2 or ny < 2:
        return float("nan")
    pooled = np.sqrt(((nx - 1) * np.var(x, ddof=1) + (ny - 1) * np.var(y, ddof=1)) / (nx + ny - 2))
    return 0.0 if pooled == 0 else (np.mean(x) - np.mean(y)) / pooled


def load(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Fajl nije pronađen: {path}\n"
            f"({label}) Pokrenite: dotnet run --project HTAPBenchmark.Runner "
            f"-- --settings appsettings.H3Control.json"
        )
    df = pd.read_csv(path)
    df["Configuration"] = df["Configuration"].str.lower()
    return df[df["OltpOlapRatio"] == RATIO]


def compare(df: pd.DataFrame, concurrency: int) -> dict | None:
    subset = df[df["ConcurrencyLevel"] == concurrency]
    im = subset[subset["Configuration"] == "im"]["OltpThroughput"].dropna().values
    ht = subset[subset["Configuration"] == "htap"]["OltpThroughput"].dropna().values
    if len(im) < 3 or len(ht) < 3:
        return None

    _, p = stats.mannwhitneyu(im, ht, alternative="two-sided")
    return {
        "ConcurrencyLevel": concurrency,
        "N_im": len(im),
        "N_htap": len(ht),
        "Median_im": float(np.median(im)),
        "Median_htap": float(np.median(ht)),
        "Ratio_htap_over_im": float(np.median(ht) / np.median(im)) if np.median(im) > 0 else float("nan"),
        "CohensD": cohen_d(im, ht),
        "P_bonferroni": min(p * BONFERRONI_PAIRS, 1.0),
    }


def main() -> None:
    main_df = load(MAIN_CSV, "glavno mjerenje")
    ctrl_df = load(CONTROL_CSV, "kontrolno mjerenje")

    log("=" * 78)
    log("H3 KONTROLNI EKSPERIMENT: HTAP vs IM pri izjednačenom MAXDOP-u")
    log(f"Omjer opterećenja: {RATIO} | Bonferroni korekcija: α' = {ALPHA}/{BONFERRONI_PAIRS}")
    log("=" * 78)
    log("")
    log("  Glavno mjerenje: HTAP OLAP = MAXDOP 2, IM OLAP = MAXDOP 1  (confound)")
    log("  Kontrola:        HTAP OLAP = MAXDOP 1, IM OLAP = MAXDOP 1  (izjednačeno)")
    log("")

    rows = []
    for concurrency in sorted(main_df["ConcurrencyLevel"].unique()):
        m = compare(main_df, concurrency)
        c = compare(ctrl_df, concurrency)
        if m is None or c is None:
            log(f"  C = {concurrency}: nedovoljno podataka — preskačem.")
            continue

        # Koliki dio originalne prednosti preživi izjednačavanje paralelizma.
        # Mjeri se na višku iznad pariteta (1,0), jer je faktor 1,0 = nema prednosti.
        main_excess = m["Ratio_htap_over_im"] - 1.0
        ctrl_excess = c["Ratio_htap_over_im"] - 1.0
        retained = (ctrl_excess / main_excess * 100.0) if main_excess > 0 else float("nan")

        rows.append({
            "ConcurrencyLevel": concurrency,
            "Main_Median_im": m["Median_im"],
            "Main_Median_htap": m["Median_htap"],
            "Main_Ratio": m["Ratio_htap_over_im"],
            "Main_CohensD": m["CohensD"],
            "Main_P": m["P_bonferroni"],
            "Control_Median_im": c["Median_im"],
            "Control_Median_htap": c["Median_htap"],
            "Control_Ratio": c["Ratio_htap_over_im"],
            "Control_CohensD": c["CohensD"],
            "Control_P": c["P_bonferroni"],
            "RetainedAdvantagePercent": retained,
        })

        log("─" * 78)
        log(f"  KONKURENTNOST C = {concurrency}")
        log("─" * 78)
        log(f"    Glavno:   IM = {m['Median_im']:9.0f} ops/s | HTAP = {m['Median_htap']:9.0f} ops/s "
            f"| {m['Ratio_htap_over_im']:.2f}× | d = {m['CohensD']:+.2f} | p = {m['P_bonferroni']:.2e}")
        log(f"    Kontrola: IM = {c['Median_im']:9.0f} ops/s | HTAP = {c['Median_htap']:9.0f} ops/s "
            f"| {c['Ratio_htap_over_im']:.2f}× | d = {c['CohensD']:+.2f} | p = {c['P_bonferroni']:.2e}")

        if np.isnan(retained):
            log("    → glavno mjerenje ne pokazuje prednost HTAP-a; udio nije definisan.")
        else:
            log(f"    → nakon izjednačavanja paralelizma zadržano {retained:.1f} % originalne prednosti")

        if c["P_bonferroni"] < ALPHA and c["Ratio_htap_over_im"] > 1.0:
            log("    → H3 ODBAČENA i u kontroli: prednost HTAP-a nije artefakt MAXDOP-a.")
        elif c["P_bonferroni"] >= ALPHA:
            log("    → u kontroli razlika NIJE statistički značajna: originalni jaz se")
            log("      značajnim dijelom može pripisati razlici u stepenu paralelizma.")
        else:
            log("    → u kontroli je smjer razlike obrnut — nalaz zahtijeva reviziju.")
        log("")

    if not rows:
        log("Nema usporedivih kombinacija — provjerite ulazne CSV fajlove.")
        REPORT_TXT.write_text("\n".join(report_lines), encoding="utf-8")
        return

    comparison = pd.DataFrame(rows)
    COMPARE_CSV.parent.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(COMPARE_CSV, index=False)

    log("=" * 78)
    log("ZAKLJUČAK")
    log("=" * 78)

    ctrl_ratios = comparison["Control_Ratio"]
    main_ratios = comparison["Main_Ratio"]
    retained_mean = comparison["RetainedAdvantagePercent"].mean(skipna=True)
    all_significant = bool((comparison["Control_P"] < ALPHA).all())

    log(f"  Glavno mjerenje:  faktor {main_ratios.min():.1f}–{main_ratios.max():.1f}×")
    log(f"  Kontrola:         faktor {ctrl_ratios.min():.1f}–{ctrl_ratios.max():.1f}×")
    if not np.isnan(retained_mean):
        log(f"  Prosječno zadržano {retained_mean:.1f} % prednosti nakon izjednačavanja MAXDOP-a.")
    log(f"  Statistički značajno na svim razinama u kontroli: {'DA' if all_significant else 'NE'}")
    log("")
    log("  Formulacija za rad ovisi o ishodu:")
    log("    • kontrola značajna i faktor sličan → MAXDOP confound se može ukloniti iz")
    log("      ograničenja, a jaz pripisati fizičkoj separaciji slojeva;")
    log("    • kontrola značajna ali faktor bitno manji → navesti oba broja i reći koliki")
    log("      dio jaza otpada na paralelizam;")
    log("    • kontrola neznačajna → tvrdnju o dual-store prednosti pri 80/20 treba oslabiti.")

    REPORT_TXT.write_text("\n".join(report_lines), encoding="utf-8")
    log("")
    log(f"Izvještaj:  {REPORT_TXT}")
    log(f"Usporedba:  {COMPARE_CSV}")


if __name__ == "__main__":
    main()
