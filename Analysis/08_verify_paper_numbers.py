"""
08_verify_paper_numbers.py — revizija svake brojke koja se pojavljuje u radu.

SVRHA
-----
Brojke u radu i u koncept-dokumentu prepisane su iz izvjestaja koji je generisao
06_maxdop_control.py. Ova skripta ih ne cita iz tog izvjestaja nego ih
PONOVO IZRACUNAVA iz sirovih CSV-ova, i poredi s vrijednostima koje su
zapisane u radu. Time se lanac povjerenja skracuje na sirove podatke.

Svaka neslaganja se ispisuju kao GRESKA. Ako skripta zavrsi bez greske, svaka
brojka u radu je potvrdjena iz podataka.

ULAZ
----
  Results/summary.csv          glavni set
  Results/summary_arm_d2.csv   kontrolna ruka (IM, analitika na MAXDOP 2)

Provjere koje zavise od ruke se preskacu uz jasnu napomenu ako taj fajl
nedostaje, umjesto da skripta padne.

POKRETANJE
----------
  python Analysis/08_verify_paper_numbers.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "Results"

RATIO = "80_20"
CONCS = [4, 16, 32]
TOL = 0.01          # 1 % odstupanja zbog zaokruzivanja u radu

# Vrijednosti kako su zapisane u radu i u koncept-dokumentu.
CLAIMS_THROUGHPUT = {
    "im":    [3027, 7726, 6325],
    "htap":  [10083, 35914, 43751],
    "im@d2": [3658, 18939, 22808],
}
CLAIM_LEVER1 = [1.21, 2.45, 3.61]          # im@d2 / im
CLAIM_LEVER2 = [2.76, 1.90, 1.92]          # htap / im@d2
CLAIM_UNCONTROLLED = [3.33, 4.65, 6.92]    # htap / im
CLAIM_COHEN_D = [4.51, 5.33, 7.52]         # htap vs im@d2
CLAIM_CPU_SHARE = [0.909, 0.825, 0.849]
CLAIM_YIELD_S = [0.4, 4.3, 56.4]
CLAIM_CPU_UTIL_C32 = 26.8
CLAIM_OLAP_P50 = {"im": [641, 2126, 3292], "htap": [832, 1045, 1768]}
CLAIM_VALID_RUNS = 1070

failures: list[str] = []
skipped: list[str] = []


def check(label: str, computed: float, claimed: float, unit: str = "", tol: float = TOL) -> None:
    if not np.isfinite(computed):
        skipped.append(f"{label}: nema podataka")
        print(f"  ?  {label:<44} nema podataka")
        return

    denom = abs(claimed) if claimed else 1.0
    rel = abs(computed - claimed) / denom
    ok = rel <= tol
    mark = "OK " if ok else "!! "
    print(f"  {mark}{label:<44} izracunato {computed:>10,.2f}{unit}   "
          f"u radu {claimed:>10,.2f}{unit}   odstupanje {rel * 100:>5.2f} %")
    if not ok:
        failures.append(f"{label}: izracunato {computed:,.2f}, u radu {claimed:,.2f}")


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return float("nan")
    sp = np.sqrt(((n1 - 1) * a.std(ddof=1) ** 2 + (n2 - 1) * b.std(ddof=1) ** 2) / (n1 + n2 - 2))
    return (a.mean() - b.mean()) / sp if sp > 0 else float("nan")


def load() -> pd.DataFrame:
    if not (RESULTS / "summary.csv").exists():
        raise SystemExit(f"Nedostaje {RESULTS / 'summary.csv'}.")

    frames = [pd.read_csv(RESULTS / "summary.csv")]
    for arm in sorted(RESULTS.glob("summary_arm_*.csv")):
        frames.append(pd.read_csv(arm))
        print(f"  ucitano: {arm.name}")

    df = pd.concat(frames, ignore_index=True)
    df["Configuration"] = df["Configuration"].str.strip().str.lower()
    return df[df["OltpSuccessRate"] >= 0.90]


def series(df: pd.DataFrame, cfg: str, col: str, ratio: str | None = RATIO) -> np.ndarray:
    sel = (df.Configuration == cfg) & (df.OltpOlapRatio == ratio) if ratio \
        else (df.Configuration == cfg)
    return df.loc[sel, col].to_numpy()


def med(df: pd.DataFrame, cfg: str, col: str, conc: int, ratio: str | None = RATIO) -> float:
    sel = (df.Configuration == cfg) & (df.ConcurrencyLevel == conc)
    if ratio is not None:
        sel &= df.OltpOlapRatio == ratio
    v = df.loc[sel, col]
    return float(v.median()) if len(v) else float("nan")


def print_medians(df: pd.DataFrame) -> None:
    """
    Ispisuje tacne medijane serverskih brojaca, u obliku spremnom za prepis u rad.

    Postoji jer su te brojke prvobitno preuzete iz aritmetickih sredina, dok rad
    svugdje drugdje koristi medijane; ovo daje vrijednosti bez posrednika.
    """
    print("TACNI MEDIJANI SERVERSKIH BROJACA (ruka im@d2, omjer 80/20)\n")
    if "im@d2" not in set(df.Configuration.unique()) or "OlapCpuShare" not in df.columns:
        print("  Ruka im@d2 ili kolone brojaca nisu dostupni.")
        return

    print(f"  {'C':>3}  {'udio analitike u CPU':>22}  {'scheduler yield':>18}  {'iskoristenost CPU':>19}")
    for c in CONCS:
        share = med(df, "im@d2", "OlapCpuShare", c)
        yld = med(df, "im@d2", "SchedulerYieldMs", c) / 1000
        util = med(df, "im@d2", "CpuUtilizationPct", c)
        print(f"  {c:>3}  {share * 100:>21.2f}%  {yld:>16.2f} s  {util:>18.2f}%")


def main() -> None:
    df = load()

    if "--print-medians" in sys.argv:
        print_medians(df)
        return

    print("REVIZIJA BROJKI IZ RADA\n")
    present = set(df.Configuration.unique())
    print(f"  konfiguracije: {', '.join(sorted(present))}\n")

    print("1. OBIM GLAVNOG SETA")
    main_rows = int((df.Configuration.isin({"baseline", "cs", "im", "htap"})).sum())
    check("validnih runova u glavnom setu", main_rows, CLAIM_VALID_RUNS, tol=0.005)

    print("\n2. MEDIJALNA OLTP PROPUSNOST (omjer 80/20)")
    for cfg, claims in CLAIMS_THROUGHPUT.items():
        if cfg not in present:
            skipped.append(f"propusnost {cfg}: ruka nije izmjerena")
            print(f"  ?  {cfg:<10} nije prisutan — preskacem")
            continue
        for c, claimed in zip(CONCS, claims):
            check(f"{cfg} @ C={c}", med(df, cfg, "OltpThroughput", c), claimed, " ops/s")

    print("\n3. POLUGA 1 — paralelizam (im@d2 / im)")
    if "im@d2" in present:
        for c, claimed in zip(CONCS, CLAIM_LEVER1):
            a, b = med(df, "im@d2", "OltpThroughput", c), med(df, "im", "OltpThroughput", c)
            check(f"dobitak @ C={c}", a / b if b else float("nan"), claimed, "x")
    else:
        skipped.append("poluga 1: ruka im@d2 nije izmjerena")
        print("  ?  ruka im@d2 nije prisutna — preskacem")

    print("\n4. POLUGA 2 — smjestaj (htap / im@d2)")
    if "im@d2" in present:
        for c, claimed in zip(CONCS, CLAIM_LEVER2):
            a, b = med(df, "htap", "OltpThroughput", c), med(df, "im@d2", "OltpThroughput", c)
            check(f"dobitak @ C={c}", a / b if b else float("nan"), claimed, "x")
        print("\n   velicina efekta (Cohenov d)")
        for c, claimed in zip(CONCS, CLAIM_COHEN_D):
            h = series(df[df.ConcurrencyLevel == c], "htap", "OltpThroughput")
            i = series(df[df.ConcurrencyLevel == c], "im@d2", "OltpThroughput")
            check(f"d @ C={c}", cohens_d(h, i), claimed, "", tol=0.03)
            if len(h) > 2 and len(i) > 2:
                _, p = stats.mannwhitneyu(h, i, alternative="two-sided")
                flag = "OK " if p < 0.001 else "!! "
                print(f"  {flag}p-vrijednost @ C={c:<32} p = {p:.2e}   (rad tvrdi p < 0,001)")
                if p >= 0.001:
                    failures.append(f"p @ C={c} = {p:.2e}, rad tvrdi p < 0,001")
    else:
        skipped.append("poluga 2: ruka im@d2 nije izmjerena")
        print("  ?  ruka im@d2 nije prisutna — preskacem")

    print("\n5. NEKONTROLIRANA USPOREDBA (htap / im)")
    for c, claimed in zip(CONCS, CLAIM_UNCONTROLLED):
        a, b = med(df, "htap", "OltpThroughput", c), med(df, "im", "OltpThroughput", c)
        check(f"jaz @ C={c}", a / b if b else float("nan"), claimed, "x")

    print("\n6. SERVERSKI BROJACI (ruka im@d2)")
    if "im@d2" in present and "OlapCpuShare" in df.columns:
        for c, claimed in zip(CONCS, CLAIM_CPU_SHARE):
            check(f"udio analitike u CPU @ C={c}", med(df, "im@d2", "OlapCpuShare", c), claimed)
        for c, claimed in zip(CONCS, CLAIM_YIELD_S):
            check(f"scheduler yield @ C={c}",
                  med(df, "im@d2", "SchedulerYieldMs", c) / 1000, claimed, " s", tol=0.05)
        check("iskoristenost CPU @ C=32",
              med(df, "im@d2", "CpuUtilizationPct", 32), CLAIM_CPU_UTIL_C32, " %")
    else:
        skipped.append("serverski brojaci: ruka im@d2 ili kolone nedostaju")
        print("  ?  brojaci nisu dostupni — preskacem")

    print("\n7. ANALITICKA LATENCIJA P50 (svi omjeri)")
    for cfg, claims in CLAIM_OLAP_P50.items():
        for c, claimed in zip(CONCS, claims):
            check(f"{cfg} OLAP P50 @ C={c}",
                  med(df, cfg, "OlapLatencyP50", c, ratio=None), claimed, " ms")

    print("\n" + "=" * 70)
    if failures:
        print(f"NEUSKLADJENO: {len(failures)}")
        for f in failures:
            print(f"  - {f}")
        print("\nBrojke u radu treba uskladiti s izracunatim vrijednostima.")
    else:
        print("SVE PROVJERENE BROJKE SE POKLAPAJU S PODACIMA.")

    if skipped:
        print(f"\nPRESKOCENO: {len(skipped)} (podaci nisu dostupni)")
        for s in skipped:
            print(f"  - {s}")
        print("\nPreskocene stavke NISU potvrdjene — izmjerite ruku pa ponovite.")

    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
