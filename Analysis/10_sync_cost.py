#!/usr/bin/env python3
"""
08_sync_cost.py — cijena sinhronizacije dual-store slojeva.

SVRHA
    U glavnom eksperimentu HTAP konfiguracija fizički odvaja OLTP i analitički
    sloj, ali tokom mjerenja ne radi nikakav mehanizam sinhronizacije. Izmjerene
    prednosti stoga predstavljaju GORNJU GRANICU ostvarivu uz nultu cijenu
    propagacije. Ova skripta obrađuje eksperiment u kojem sinhronizacija radi na
    više intervala i pretvara to ograničenje u izmjerenu krivulju kompromisa
    između svježine analitičkih podataka i OLTP propusnosti.

ULAZ
    Results/summary_arm_sync*.csv   (propusnost i latencija po intervalu)
    Results/sync_cycles_*s.csv      (trajanje ciklusa, propagirani redovi, kašnjenje)

    Generiše se po jednom pokretanju za svaki interval, SVE U ISTOJ SESIJI:
        dotnet run --project HTAPBenchmark.Runner -- --sync 0
        dotnet run --project HTAPBenchmark.Runner -- --sync 1
        dotnet run --project HTAPBenchmark.Runner -- --sync 5
        dotnet run --project HTAPBenchmark.Runner -- --sync 30

    Interval 0 je kontrolna ruka i mora biti izmjeren u istoj sesiji kao ostali;
    inače se cijena sinhronizacije ne može odvojiti od razlike među sesijama.

IZLAZ
    Results/sync_cost_report.txt
    Results/sync_cost_summary.csv
    Results/figures/15_sync_cost_tradeoff.png
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

SUMMARY_GLOB = "summary_arm_sync*.csv"
CYCLES_GLOB  = "sync_cycles_*s.csv"

HTAP_COLOR = "#2E86AB"


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return float("nan")
    pooled = np.sqrt(((n1 - 1) * np.var(a, ddof=1) + (n2 - 1) * np.var(b, ddof=1)) / (n1 + n2 - 2))
    return float("nan") if pooled == 0 else (np.mean(a) - np.mean(b)) / pooled


def parse_interval(label: str) -> int:
    """'htap@sync5' -> 5; 'htap@sync0' -> 0; 'htap' -> 0"""
    return int(label.split("@sync")[1]) if "@sync" in label else 0


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_files = sorted(RESULTS_DIR.glob(SUMMARY_GLOB))
    if not summary_files:
        raise SystemExit(
            f"Nema nijedne datoteke {SUMMARY_GLOB} u Results/\n"
            "Pokrenite mjerenje za svaki interval u istoj sesiji, npr.:\n"
            "  dotnet run --project HTAPBenchmark.Runner -- --sync 0\n"
            "  dotnet run --project HTAPBenchmark.Runner -- --sync 5"
        )

    print(f"  Ulazne datoteke: {', '.join(f.name for f in summary_files)}")
    df = pd.concat([pd.read_csv(f) for f in summary_files], ignore_index=True)
    df["SyncInterval"] = df["Configuration"].map(parse_interval)

    before = len(df)
    df = df[df["OltpSuccessRate"] >= 0.90].copy()
    if before != len(df):
        print(f"  Isključeno {before - len(df)} runova (OLTP success rate < 90%).")

    cycle_files = sorted(RESULTS_DIR.glob(CYCLES_GLOB))
    cycles = (pd.concat([pd.read_csv(f) for f in cycle_files], ignore_index=True)
              if cycle_files else pd.DataFrame())
    return df, cycles


def build_summary(df: pd.DataFrame, cycles: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ratio in sorted(df["OltpOlapRatio"].unique()):
        baseline = df[(df["OltpOlapRatio"] == ratio) & (df["SyncInterval"] == 0)]["OltpThroughput"]

        for interval in sorted(df["SyncInterval"].unique()):
            sel = df[(df["OltpOlapRatio"] == ratio) & (df["SyncInterval"] == interval)]
            if sel.empty:
                continue

            tput = sel["OltpThroughput"]
            row = {
                "OltpOlapRatio": ratio,
                "SyncIntervalSeconds": interval,
                "N": len(sel),
                "OltpThroughput_median": round(float(tput.median()), 2),
                "OltpThroughput_mean": round(float(tput.mean()), 2),
                "OltpThroughput_sd": round(float(tput.std()), 2),
                "OlapLatencyP50_median": round(float(sel["OlapLatencyP50"].median()), 1),
            }

            # Trošak u odnosu na uvjet bez sinhronizacije.
            if len(baseline) >= 3 and interval > 0 and len(tput) >= 3:
                loss = (1 - tput.median() / baseline.median()) * 100
                _, p = stats.mannwhitneyu(baseline, tput, alternative="two-sided")
                row["PropusnostGubitakPct"] = round(float(loss), 2)
                row["p_vs_bez_sync"] = float(p)
                row["CohenD_vs_bez_sync"] = round(cohens_d(baseline.to_numpy(), tput.to_numpy()), 3)
            else:
                row["PropusnostGubitakPct"] = 0.0 if interval == 0 else None
                row["p_vs_bez_sync"] = None
                row["CohenD_vs_bez_sync"] = None

            # Metrike svježine iz ciklusa sinhronizacije.
            if not cycles.empty and interval > 0:
                cyc = cycles[
                    (cycles["OltpOlapRatio"] == ratio)
                    & (cycles["SyncIntervalSeconds"] == interval)
                    & (cycles["Success"] == 1)
                ]
                if not cyc.empty:
                    lag = cyc[cyc["AvgFreshnessLagMs"] >= 0]["AvgFreshnessLagMs"]
                    row["CiklusTrajanjeMs_median"] = round(float(cyc["DurationMs"].median()), 1)
                    row["RedovaPoCiklusu_median"] = round(
                        float((cyc["VotesPropagated"] + cyc["CommentsPropagated"]).median()), 1)
                    row["SvjezinaLagMs_median"] = round(float(lag.median()), 1) if len(lag) else None
                    row["SvjezinaLagMs_p95"] = round(float(lag.quantile(0.95)), 1) if len(lag) else None

            rows.append(row)

    return pd.DataFrame(rows)


def plot(summary: pd.DataFrame) -> None:
    ratios = sorted(summary["OltpOlapRatio"].unique())
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Lijevo: propusnost kao funkcija intervala.
    ax = axes[0]
    for ratio in ratios:
        sub = summary[summary["OltpOlapRatio"] == ratio].sort_values("SyncIntervalSeconds")
        # Interval 0 (bez sinhronizacije) crta se kao referentna linija, ne kao tačka
        # na logaritamskoj osi — nula na njoj ne postoji.
        with_sync = sub[sub["SyncIntervalSeconds"] > 0]
        no_sync   = sub[sub["SyncIntervalSeconds"] == 0]

        line, = ax.plot(with_sync["SyncIntervalSeconds"], with_sync["OltpThroughput_median"],
                        marker="o", linewidth=2, label=f"{ratio.replace('_', '%/')}%")
        if not no_sync.empty:
            ax.axhline(no_sync["OltpThroughput_median"].iloc[0],
                       color=line.get_color(), linestyle=":", linewidth=1.5, alpha=0.8)

    ax.set_xscale("log")
    ax.set_xlabel("Interval sinhronizacije (s, log skala)")
    ax.set_ylabel("OLTP propusnost (medijan, ops/s)")
    ax.set_title("Cijena sinhronizacije\n(tačkasto = bez sinhronizacije)", fontweight="bold")
    ax.grid(alpha=0.3, linestyle="--")
    ax.legend(title="Omjer opterećenja")

    # Desno: kompromis svježina/propusnost.
    ax = axes[1]
    plotted = False
    for ratio in ratios:
        sub = summary[
            (summary["OltpOlapRatio"] == ratio)
            & (summary["SyncIntervalSeconds"] > 0)
            & summary.get("SvjezinaLagMs_median", pd.Series(dtype=float)).notna()
        ].sort_values("SyncIntervalSeconds")

        if sub.empty:
            continue
        plotted = True

        ax.plot(sub["SvjezinaLagMs_median"] / 1000.0, sub["OltpThroughput_median"],
                marker="s", linewidth=2, label=f"{ratio.replace('_', '%/')}%")
        for _, r in sub.iterrows():
            ax.annotate(f"{int(r['SyncIntervalSeconds'])}s",
                        (r["SvjezinaLagMs_median"] / 1000.0, r["OltpThroughput_median"]),
                        textcoords="offset points", xytext=(6, 6), fontsize=9)

    if plotted:
        ax.set_xlabel("Kašnjenje svježine analitičkih podataka (s, medijan)")
        ax.set_ylabel("OLTP propusnost (medijan, ops/s)")
        ax.set_title("Kompromis: svježina naspram propusnosti", fontweight="bold")
        ax.grid(alpha=0.3, linestyle="--")
        ax.legend(title="Omjer opterećenja")
    else:
        ax.text(0.5, 0.5, "Nema podataka o svježini\n(sync_cycles.csv prazan)",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()

    fig.suptitle("Dual-store sinhronizacija htap.* → cs.*", fontsize=13, fontweight="bold")
    fig.tight_layout()

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / "15_sync_cost_tradeoff.png"
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  Figura: {path.relative_to(ROOT)}")


def write_report(summary: pd.DataFrame, cycles: pd.DataFrame) -> None:
    lines: list[str] = []
    add = lines.append

    add("=" * 78)
    add("HTAPBenchmark: cijena sinhronizacije dual-store slojeva")
    add("=" * 78)
    add("")
    add("PITANJE: koliko OLTP propusnosti dual-store konfiguracija gubi kada")
    add("analitički sloj mora ostati svjež, umjesto da čita statičan snapshot?")
    add("")
    add("Mehanizam: periodična batch propagacija htap.* -> cs.* po rasponu")
    add("identifikatora (seek po hash indeksu, bez skeniranja tablice).")
    add("")

    add("-" * 78)
    add("1. PROPUSNOST PO INTERVALU SINHRONIZACIJE")
    add("-" * 78)
    for ratio in sorted(summary["OltpOlapRatio"].unique()):
        add(f"\n  Omjer {ratio}:")
        for _, r in summary[summary["OltpOlapRatio"] == ratio].sort_values("SyncIntervalSeconds").iterrows():
            interval = int(r["SyncIntervalSeconds"])
            name = "bez sinhronizacije" if interval == 0 else f"svakih {interval:>2} s"
            loss = r.get("PropusnostGubitakPct")
            loss_txt = "     —" if loss is None else f"{loss:6.2f}%"
            add(f"    {name:<20} propusnost={r['OltpThroughput_median']:9.1f} ops/s   "
                f"gubitak={loss_txt}   OLAP P50={r['OlapLatencyP50_median']:8.1f} ms  (N={int(r['N'])})")

    if "SvjezinaLagMs_median" in summary.columns:
        add("")
        add("-" * 78)
        add("2. SVJEŽINA ANALITIČKIH PODATAKA")
        add("-" * 78)
        add("   Kašnjenje = vrijeme od nastanka reda u OLTP sloju do vidljivosti u")
        add("   analitičkom sloju. Rezolucija mjerenja je 1 s (kolona DATETIME2(0)).")
        for ratio in sorted(summary["OltpOlapRatio"].unique()):
            rows = summary[(summary["OltpOlapRatio"] == ratio) & (summary["SyncIntervalSeconds"] > 0)]
            if rows.empty:
                continue
            add(f"\n  Omjer {ratio}:")
            for _, r in rows.sort_values("SyncIntervalSeconds").iterrows():
                lag = r.get("SvjezinaLagMs_median")
                if lag is None or pd.isna(lag):
                    continue
                add(f"    interval {int(r['SyncIntervalSeconds']):>2} s → kašnjenje medijan="
                    f"{lag/1000:5.2f} s, P95={r.get('SvjezinaLagMs_p95', float('nan'))/1000:5.2f} s   "
                    f"(ciklus={r.get('CiklusTrajanjeMs_median', float('nan')):7.1f} ms, "
                    f"{r.get('RedovaPoCiklusu_median', float('nan')):8.1f} redova)")

    add("")
    add("-" * 78)
    add("3. ŠTA OVO MIJENJA U RADU")
    add("-" * 78)
    add("   Bez ovog eksperimenta tvrdnja o prednosti dual-store pristupa vrijedi samo")
    add("   uz nultu cijenu sinhronizacije i mora se iskazati kao gornja granica.")
    add("   S njim se prednost iskazuje kao funkcija tražene svježine podataka, što je")
    add("   oblik u kojem je upotrebljiva za projektovanje stvarnog sistema.")

    if not cycles.empty:
        failed = int((cycles["Success"] == 0).sum())
        if failed:
            add("")
            add(f"   UPOZORENJE: {failed} ciklusa sinhronizacije nije uspjelo. Provjerite")
            add("   Results/sync_cycles.csv prije interpretacije rezultata.")

    path = RESULTS_DIR / "sync_cost_report.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Izvještaj: {path.relative_to(ROOT)}")


def main() -> None:
    print("=" * 78)
    print("10: Cijena sinhronizacije dual-store slojeva")
    print("=" * 78)

    df, cycles = load()
    print(f"  Učitano {len(df)} runova, intervali: {sorted(df['SyncInterval'].unique())}")

    summary = build_summary(df, cycles)
    out_csv = RESULTS_DIR / "sync_cost_summary.csv"
    summary.to_csv(out_csv, index=False)
    print(f"  Tabela: {out_csv.relative_to(ROOT)}")

    plot(summary)
    write_report(summary, cycles)

    print("\nGotovo.")


if __name__ == "__main__":
    main()
