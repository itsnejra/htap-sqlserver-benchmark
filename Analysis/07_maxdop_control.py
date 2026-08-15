#!/usr/bin/env python3
"""
07_maxdop_control.py — izolacija efekta stepena paralelizma u usporedbi HTAP/IM.

SVRHA
    U glavnom eksperimentu IM koristi OPTION(MAXDOP 1), a HTAP OPTION(MAXDOP 2).
    Izmjereni jaz u OLTP propusnosti (3,3-6,9x) stoga miješa dva efekta:
    dual-store arhitekturu i stepen paralelizma analitičkih upita. Ova skripta
    obrađuje kontrolni 2x2 faktorijal (konfiguracija x MAXDOP) i razdvaja ih.

    Ključna usporedba: im_md1 naspram htap_md1. Pri identičnom stepenu paralelizma
    svaka preostala razlika pripisiva je isključivo tome GDJE se analitika izvršava.

ULAZ
    Results/maxdop_summary.csv
    Generiše: dotnet run --project HTAPBenchmark.Runner -- --experiment maxdop

IZLAZ
    Results/maxdop_control_report.txt
    Results/maxdop_control_tests.csv
    Results/figures/16_maxdop_control.png
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT        = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "Results"
FIGURES_DIR = RESULTS_DIR / "figures"
SUMMARY_CSV = RESULTS_DIR / "maxdop_summary.csv"

COLORS = {"im": "#F18F01", "htap": "#2E86AB"}


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Standardizovana razlika sredina; isti oblik kao u 02_statistical_tests.py."""
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return float("nan")
    s1, s2 = np.var(a, ddof=1), np.var(b, ddof=1)
    pooled = np.sqrt(((n1 - 1) * s1 + (n2 - 1) * s2) / (n1 + n2 - 2))
    return float("nan") if pooled == 0 else (np.mean(a) - np.mean(b)) / pooled


def effect_label(d: float) -> str:
    ad = abs(d)
    if np.isnan(ad):  return "n/d"
    if ad < 0.2:      return "trivijalan"
    if ad < 0.5:      return "mali"
    if ad < 0.8:      return "srednji"
    return "veliki"


def parse_condition(label: str) -> tuple[str, int]:
    """'htap_md1' -> ('htap', 1)"""
    parts = label.split("_md")
    if len(parts) == 2:
        return parts[0], int(parts[1])
    return label, 0


def load() -> pd.DataFrame:
    if not SUMMARY_CSV.exists():
        raise SystemExit(
            f"Nedostaje {SUMMARY_CSV.name}\n"
            "Pokrenite prvo: dotnet run --project HTAPBenchmark.Runner -- --experiment maxdop"
        )

    df = pd.read_csv(SUMMARY_CSV)
    df[["ConfigBase", "MaxDop"]] = df["Configuration"].apply(
        lambda s: pd.Series(parse_condition(s))
    )

    # Ista kontrola kvalitete kao u glavnoj analizi: runovi s <90% uspješnih OLTP
    # operacija označavaju nestabilno mjerno okruženje.
    before = len(df)
    df = df[df["OltpSuccessRate"] >= 0.90].copy()
    if before != len(df):
        print(f"  Isključeno {before - len(df)} runova (OLTP success rate < 90%).")

    return df


def compare(df: pd.DataFrame, label_a: str, label_b: str, metric: str,
            ratio: str, concurrency: int) -> dict | None:
    """Mann-Whitney U + Cohenov d za jedan par uvjeta."""
    sel = (df["OltpOlapRatio"] == ratio) & (df["ConcurrencyLevel"] == concurrency)
    a = df[sel & (df["Configuration"] == label_a)][metric].dropna().to_numpy()
    b = df[sel & (df["Configuration"] == label_b)][metric].dropna().to_numpy()

    if len(a) < 3 or len(b) < 3:
        return None

    u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    return {
        "Metrika": metric,
        "OltpOlapRatio": ratio,
        "ConcurrencyLevel": concurrency,
        "Uvjet_A": label_a,
        "Uvjet_B": label_b,
        "N_A": len(a),
        "N_B": len(b),
        "Median_A": round(float(np.median(a)), 2),
        "Median_B": round(float(np.median(b)), 2),
        "Omjer_B_A": round(float(np.median(b) / np.median(a)), 2) if np.median(a) else None,
        "U": float(u),
        "p": float(p),
        "CohenD": round(cohens_d(a, b), 3),
        "VelicinaEfekta": effect_label(cohens_d(a, b)),
    }


def run_tests(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    ratios = sorted(df["OltpOlapRatio"].unique())
    levels = sorted(df["ConcurrencyLevel"].unique())

    for ratio in ratios:
        for c in levels:
            # (1) KLJUČNO: isti MAXDOP, različita arhitektura.
            for dop in (1, 2):
                r = compare(df, f"im_md{dop}", f"htap_md{dop}",
                            "OltpThroughput", ratio, c)
                if r:
                    r["Pitanje"] = f"Arhitektura pri MAXDOP {dop}"
                    rows.append(r)

            # (2) Efekt samog MAXDOP-a unutar iste arhitekture.
            for cfg in ("im", "htap"):
                r = compare(df, f"{cfg}_md1", f"{cfg}_md2",
                            "OltpThroughput", ratio, c)
                if r:
                    r["Pitanje"] = f"MAXDOP unutar {cfg.upper()}"
                    rows.append(r)

    if not rows:
        raise SystemExit("Nema dovoljno podataka za usporedbe (potrebno >=3 runa po uvjetu).")

    out = pd.DataFrame(rows)
    # Bonferroni nad brojem provedenih testova.
    out["p_bonferroni"] = (out["p"] * len(out)).clip(upper=1.0)
    out["Znacajno"] = out["p_bonferroni"] < 0.05
    return out


def plot(df: pd.DataFrame) -> None:
    ratios = sorted(df["OltpOlapRatio"].unique())
    fig, axes = plt.subplots(1, len(ratios), figsize=(6 * len(ratios), 5), sharey=True)
    if len(ratios) == 1:
        axes = [axes]

    levels = sorted(df["ConcurrencyLevel"].unique())
    width = 0.2

    for ax, ratio in zip(axes, ratios):
        subset = df[df["OltpOlapRatio"] == ratio]
        x = np.arange(len(levels))

        for i, (cfg, dop) in enumerate([("im", 1), ("im", 2), ("htap", 1), ("htap", 2)]):
            label = f"{cfg}_md{dop}"
            means, errs = [], []
            for c in levels:
                vals = subset[(subset["Configuration"] == label) &
                              (subset["ConcurrencyLevel"] == c)]["OltpThroughput"]
                means.append(vals.mean() if len(vals) else 0)
                errs.append(vals.std() if len(vals) > 1 else 0)

            ax.bar(
                x + (i - 1.5) * width, means, width, yerr=errs, capsize=3,
                label=f"{cfg.upper()} MAXDOP {dop}",
                color=COLORS[cfg],
                alpha=1.0 if dop == 1 else 0.55,
                edgecolor="black", linewidth=0.6,
            )

        ax.set_xticks(x)
        ax.set_xticklabels([f"C={c}" for c in levels])
        ax.set_title(f"Omjer {ratio.replace('_', '%/')}%")
        ax.grid(axis="y", alpha=0.3, linestyle="--")

    axes[0].set_ylabel("OLTP propusnost (ops/s)")
    axes[0].legend(frameon=True, fontsize=9)
    fig.suptitle(
        "Kontrola stepena paralelizma: OLTP propusnost pri izjednačenom MAXDOP-u\n"
        "Puna boja = MAXDOP 1, prozirna = MAXDOP 2",
        fontsize=13, fontweight="bold",
    )
    fig.tight_layout()

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / "16_maxdop_control.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Figura: {path.relative_to(ROOT)}")


def write_report(tests: pd.DataFrame) -> None:
    lines: list[str] = []
    add = lines.append

    add("=" * 78)
    add("HTAPBenchmark: kontrola stepena paralelizma (MAXDOP) u usporedbi HTAP/IM")
    add("=" * 78)
    add("")
    add("PITANJE: koliko izmjerenog jaza u OLTP propusnosti između HTAP i IM potiče")
    add("od dual-store arhitekture, a koliko od razlike u stepenu paralelizma")
    add("analitičkih upita (MAXDOP 2 naspram MAXDOP 1)?")
    add("")

    add("-" * 78)
    add("1. ARHITEKTURA PRI IZJEDNAČENOM MAXDOP-u  (im_mdN vs htap_mdN)")
    add("-" * 78)
    add("   Ovo je usporedba koja NEMA confounding varijablu paralelizma.")
    add("")
    key = tests[tests["Pitanje"].str.startswith("Arhitektura")]
    for _, r in key.iterrows():
        sig = "ZNAČAJNO" if r["Znacajno"] else "n.z."
        add(f"   {r['OltpOlapRatio']} C={r['ConcurrencyLevel']:<3} {r['Pitanje']:<26} "
            f"IM={r['Median_A']:9.1f}  HTAP={r['Median_B']:9.1f}  "
            f"faktor={r['Omjer_B_A']:5.2f}x  d={r['CohenD']:7.3f} "
            f"({r['VelicinaEfekta']})  p={r['p_bonferroni']:.2e}  {sig}")

    add("")
    add("-" * 78)
    add("2. EFEKT SAMOG MAXDOP-a UNUTAR ISTE ARHITEKTURE  (cfg_md1 vs cfg_md2)")
    add("-" * 78)
    add("   Kvantificira koliki dio jaza je pripisiv paralelizmu, a ne arhitekturi.")
    add("")
    within = tests[tests["Pitanje"].str.startswith("MAXDOP")]
    for _, r in within.iterrows():
        sig = "ZNAČAJNO" if r["Znacajno"] else "n.z."
        add(f"   {r['OltpOlapRatio']} C={r['ConcurrencyLevel']:<3} {r['Pitanje']:<26} "
            f"MD1={r['Median_A']:9.1f}  MD2={r['Median_B']:9.1f}  "
            f"faktor={r['Omjer_B_A']:5.2f}x  d={r['CohenD']:7.3f} "
            f"({r['VelicinaEfekta']})  p={r['p_bonferroni']:.2e}  {sig}")

    add("")
    add("-" * 78)
    add("3. KAKO ČITATI REZULTAT")
    add("-" * 78)
    if not key.empty:
        md1 = key[key["Pitanje"] == "Arhitektura pri MAXDOP 1"]
        if not md1.empty:
            lo, hi = md1["Omjer_B_A"].min(), md1["Omjer_B_A"].max()
            add(f"   Pri izjednačenom MAXDOP 1, HTAP nadmašuje IM za faktor {lo:.2f}-{hi:.2f}x.")
            add("")
            add("   Ako je taj raspon blizu originalno izmjerenih 3,3-6,9x, confounding")
            add("   varijabla paralelizma je zanemariva i tvrdnja o dual-store arhitekturi")
            add("   stoji u punom obimu.")
            add("")
            add("   Ako je bitno manji, dio originalnog jaza pripisiv je paralelizmu i")
            add("   tvrdnju treba iskazati OVIM brojem, ne originalnim.")
    add("")
    add("   U oba slučaja rad prestaje nositi nekvantificirano ograničenje i umjesto")
    add("   njega iznosi izmjerenu vrijednost.")

    path = RESULTS_DIR / "maxdop_control_report.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Izvještaj: {path.relative_to(ROOT)}")


def main() -> None:
    print("=" * 78)
    print("07: Kontrola stepena paralelizma (MAXDOP)")
    print("=" * 78)

    df = load()
    print(f"  Učitano {len(df)} runova, uvjeti: {sorted(df['Configuration'].unique())}")

    tests = run_tests(df)
    out_csv = RESULTS_DIR / "maxdop_control_tests.csv"
    tests.to_csv(out_csv, index=False)
    print(f"  Testovi: {out_csv.relative_to(ROOT)}")

    plot(df)
    write_report(tests)

    print("\nGotovo.")


if __name__ == "__main__":
    main()
