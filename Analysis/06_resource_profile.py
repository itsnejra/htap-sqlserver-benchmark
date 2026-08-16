"""
HTAPBenchmark: 06_resource_profile.py
Analiza direktno izmjerenog profila resursa SQL Servera

Svrha: tvrdnja da row-mode OLAP skenovi u IM konfiguraciji zasićuju procesor
u glavnom radu je IZVEDENA iz modela izvršavanja upita. Ovaj skript je provjerava
mjerenjem, koristeći podatke koje prikuplja ResourceMonitor:

  1. Pritisak na CPU po konfiguraciji i razini konkurentnosti
     - AvgRunnableTasksPerScheduler (zadaci spremni za izvršavanje, čekaju CPU)
     - AvgSqlCpuPercent (udio kapaciteta svih jezgara potrošen na korisničke sesije)
     - SignalWaitPercent (udio čekanja koji otpada na čekanje procesora)

  2. Statistička usporedba IM vs HTAP pri 80/20 opterećenju
     - Mann-Whitney U + Cohenov d nad izmjerenim CPU pokazateljima
     - ako je mehanizam iz rada tačan, IM mora pokazati veći CPU pritisak

  3. Dominantni tipovi čekanja po konfiguraciji (udio ukupnog wait vremena)
     - očekivano: RESOURCE_SEMAPHORE kod CS, SOS_SCHEDULER_YIELD kod IM

Ulaz:
  - Results/resource_profile.csv  (nastaje kada je CollectResourceProfile = true)

Izlaz:
  - Results/resource_profile_summary.csv
  - Results/resource_waits_summary.csv
  - Results/resource_profile_report.txt
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

import warnings
warnings.filterwarnings("ignore")

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

PROFILE_CSV = Path("../Results/resource_profile.csv")
SUMMARY_CSV = Path("../Results/resource_profile_summary.csv")
WAITS_CSV   = Path("../Results/resource_waits_summary.csv")
REPORT_TXT  = Path("../Results/resource_profile_report.txt")

CONFIGS = ["baseline", "cs", "im", "htap"]

# Pokazatelji koji se odnose na cijeli run (identični u svakom redu tog runa)
RUN_LEVEL_COLS = [
    "AvgRunnableTasksPerScheduler",
    "MaxRunnableTasksPerScheduler",
    "AvgActiveWorkersPerScheduler",
    "AvgSqlCpuPercent",
    "MaxSqlCpuPercent",
    "AvgTotalCpuPercent",
    "SignalWaitPercent",
    "SampleCount",
]

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


def effect_label(d: float) -> str:
    a = abs(d)
    if np.isnan(a):
        return "n/a"
    if a < 0.2:
        return "trivijalan"
    if a < 0.5:
        return "mali"
    if a < 0.8:
        return "srednji"
    return "veliki"


def main() -> None:
    if not PROFILE_CSV.exists():
        raise FileNotFoundError(
            f"Fajl nije pronađen: {PROFILE_CSV}\n"
            "Pokrenite benchmark s CollectResourceProfile = true u appsettings.json."
        )

    df = pd.read_csv(PROFILE_CSV)
    df["Configuration"] = df["Configuration"].str.lower()

    # Jedan red po runu: TOTAL red nosi agregate i ukupno wait vrijeme
    runs = df[df["WaitType"] == "TOTAL"].copy()
    if runs.empty:
        raise ValueError("resource_profile.csv ne sadrži TOTAL redove — profil je nepotpun.")

    log("=" * 70)
    log("HTAPBenchmark: profil resursa (direktno mjerenje)")
    log(f"Runova s profilom: {len(runs)}")
    log("=" * 70)

    # ------------------------------------------------------------------
    # 1. Pregled po konfiguraciji i razini konkurentnosti
    # ------------------------------------------------------------------
    log("")
    log("─" * 70)
    log("1. CPU PRITISAK PO KONFIGURACIJI I KONKURENTNOSTI")
    log("─" * 70)

    summary = (runs.groupby(["Configuration", "OltpOlapRatio", "ConcurrencyLevel"])[RUN_LEVEL_COLS]
               .agg(["mean", "std"])
               .round(4))
    summary.columns = [f"{c}_{s}" for c, s in summary.columns]
    summary = summary.reset_index()
    SUMMARY_CSV.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_CSV, index=False)

    pivot_runnable = runs.pivot_table(index="ConcurrencyLevel", columns="Configuration",
                                      values="AvgRunnableTasksPerScheduler", aggfunc="mean")
    pivot_cpu = runs.pivot_table(index="ConcurrencyLevel", columns="Configuration",
                                 values="AvgSqlCpuPercent", aggfunc="mean")
    pivot_signal = runs.pivot_table(index="ConcurrencyLevel", columns="Configuration",
                                    values="SignalWaitPercent", aggfunc="mean")

    order = [c for c in CONFIGS if c in pivot_runnable.columns]

    log("")
    log("  Prosječan broj runnable zadataka po scheduleru (>1 = čekanje na CPU):")
    log(pivot_runnable[order].round(3).to_string())
    log("")
    log("  Prosječna iskorištenost CPU-a korisničkih sesija (% svih jezgara):")
    log(pivot_cpu[order].round(2).to_string())
    log("")
    log("  Signal wait kao udio ukupnog čekanja (%) — konvencionalni prag CPU pritiska ~25 %:")
    log(pivot_signal[order].round(2).to_string())

    # ------------------------------------------------------------------
    # 2. IM vs HTAP pri 80/20 — provjera mehanizma iz rada
    # ------------------------------------------------------------------
    log("")
    log("─" * 70)
    log("2. IM vs HTAP PRI 80/20 — PROVJERA TVRDNJE O CPU SATURACIJI")
    log("─" * 70)
    log("")
    log("  Hipoteza mehanizma: u IM konfiguraciji analitički upiti rade u row-modu")
    log("  i troše više CPU ciklusa po redu, pa OLTP niti čekaju na procesor.")
    log("  Ako je tačna, IM mora imati VEĆI CPU pritisak od HTAP-a.")
    log("")

    metrics = ["AvgRunnableTasksPerScheduler", "AvgSqlCpuPercent", "SignalWaitPercent"]
    heavy = runs[runs["OltpOlapRatio"] == "80_20"]

    for concurrency in sorted(heavy["ConcurrencyLevel"].unique()):
        subset = heavy[heavy["ConcurrencyLevel"] == concurrency]
        log(f"  Konkurentnost C = {concurrency}:")
        for metric in metrics:
            im = subset[subset["Configuration"] == "im"][metric].dropna().values
            ht = subset[subset["Configuration"] == "htap"][metric].dropna().values
            if len(im) < 3 or len(ht) < 3:
                log(f"    {metric:32s}: nedovoljno podataka")
                continue
            _, p = stats.mannwhitneyu(im, ht, alternative="two-sided")
            d = cohen_d(im, ht)
            verdict = "IM veći ✓" if np.median(im) > np.median(ht) else "IM manji ✗"
            log(f"    {metric:32s}: IM={np.median(im):8.3f} HTAP={np.median(ht):8.3f} "
                f"| p={p:.4f} | d={d:+.3f} ({effect_label(d)}) | {verdict}")
        log("")

    log("  Tumačenje: mehanizam iz rada potvrđen je samo ako je IM sistematski veći")
    log("  po sva tri pokazatelja, uz p < 0,05 i veliki efekt. Suprotan ili neznačajan")
    log("  nalaz znači da objašnjenje CPU saturacijom treba revidirati.")

    # ------------------------------------------------------------------
    # 3. Dominantni tipovi čekanja
    # ------------------------------------------------------------------
    log("")
    log("─" * 70)
    log("3. DOMINANTNI TIPOVI ČEKANJA PO KONFIGURACIJI")
    log("─" * 70)

    waits = df[df["WaitType"] != "TOTAL"].copy()
    wait_summary = (waits.groupby(["Configuration", "WaitType"])
                    .agg(WaitTimeMs=("WaitTimeMs", "sum"),
                         SignalWaitTimeMs=("SignalWaitTimeMs", "sum"),
                         WaitingTasks=("WaitingTasksCount", "sum"))
                    .reset_index())
    totals = wait_summary.groupby("Configuration")["WaitTimeMs"].transform("sum")
    wait_summary["SharePercent"] = (wait_summary["WaitTimeMs"] / totals * 100).round(2)
    wait_summary = wait_summary.sort_values(["Configuration", "WaitTimeMs"], ascending=[True, False])
    wait_summary.to_csv(WAITS_CSV, index=False)

    for cfg in [c for c in CONFIGS if c in wait_summary["Configuration"].values]:
        top = wait_summary[wait_summary["Configuration"] == cfg].head(8)
        log("")
        log(f"  {cfg.upper()} — 8 najvećih tipova čekanja:")
        for _, row in top.iterrows():
            log(f"    {row['WaitType']:32s} {row['SharePercent']:6.2f} %  "
                f"({row['WaitTimeMs']:12,.0f} ms, {int(row['WaitingTasks']):,} zadataka)")

    log("")
    log("  Za rad su relevantni:")
    log("    SOS_SCHEDULER_YIELD  → zadatak je iscrpio svoj kvant i vratio se u red na CPU")
    log("    RESOURCE_SEMAPHORE   → čekanje na memorijski grant (batch-mode upiti)")
    log("    CXPACKET / CXSYNC_*  → sinhronizacija paralelnih planova")
    log("    PAGEIOLATCH_*        → čitanje stranica s diska (disk-zasnovane konfiguracije)")
    log("    WRITELOG             → upis u transakcijski log")

    REPORT_TXT.write_text("\n".join(report_lines), encoding="utf-8")
    log("")
    log(f"Sažetak po runu:   {SUMMARY_CSV}")
    log(f"Sažetak čekanja:   {WAITS_CSV}")
    log(f"Izvještaj:         {REPORT_TXT}")


if __name__ == "__main__":
    main()
