"""
make_figures.py — figure za Telfor 2026 rad.

ULAZ
----
  Results/summary.csv            glavni set (baseline, cs, im, htap)
  Results/summary_arm_d2.csv     IM s analitikom na MAXDOP 2
  Results/summary_arm_d1.csv     HTAP s analitikom na MAXDOP 1 (opciono)

Ruke su nužne za Sliku 1 i Sliku 3. Ako nedostaju, te se figure preskaču uz
upozorenje umjesto da skripta padne — ali rad se bez njih ne može kompajlirati.

Format je prilagođen IEEE dvokolonskom radu: širina jedne kolone (3,4 in),
serif font, 6-8 pt, bez naslova iznad slike (caption ide u LaTeX).

Pokretanje:
    python Paper/Telfor2026/make_figures.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
RESULTS = ROOT / "Results"
OUT = Path(__file__).resolve().parent / "figures"

COL_W = 3.4       # širina jedne IEEE kolone u inčima
CONCS = [4, 16, 32]
RATIO = "80_20"   # omjer na kojem je formulirana teza rada

C_ROW = "#8c8c8c"   # row-mode analitika, MAXDOP 1
C_PAR = "#d08c30"   # row-mode analitika, MAXDOP 2 (poluga paralelizma)
C_OFF = "#2b6cb0"   # preusmjerena analitika (poluga smještaja)

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 7.5,
    "axes.labelsize": 7.5,
    "legend.fontsize": 6.5,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.4,
    "axes.axisbelow": True,
})


def load() -> pd.DataFrame:
    """Spaja glavni set i sve izmjerene ruke; filtrira nestabilne runove."""
    frames = [pd.read_csv(RESULTS / "summary.csv")]
    for arm in sorted(RESULTS.glob("summary_arm_*.csv")):
        frames.append(pd.read_csv(arm))

    df = pd.concat(frames, ignore_index=True)
    df["Configuration"] = df["Configuration"].str.strip().str.lower()

    before = len(df)
    df = df[df["OltpSuccessRate"] >= 0.90]
    print(f"  {len(df)} od {before} runova iznad praga uspjesnosti")
    print(f"  konfiguracije: {', '.join(sorted(df['Configuration'].unique()))}")
    return df


def med(df: pd.DataFrame, cfg: str, col: str, conc: int, ratio: str | None = RATIO) -> float:
    sel = (df.Configuration == cfg) & (df.ConcurrencyLevel == conc)
    if ratio is not None:
        sel &= df.OltpOlapRatio == ratio
    vals = df.loc[sel, col]
    return float(vals.median()) if len(vals) else float("nan")


def med_q(df: pd.DataFrame, cfg: str, col: str, conc: int, q: float,
          ratio: str | None = RATIO) -> float:
    """Kvantil unutar iste celije kao med() — za interkvartilne intervale."""
    sel = (df.Configuration == cfg) & (df.ConcurrencyLevel == conc)
    if ratio is not None:
        sel &= df.OltpOlapRatio == ratio
    v = df.loc[sel, col]
    return float(v.quantile(q)) if len(v) else float("nan")


def save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf")
    fig.savefig(OUT / f"{name}.png", dpi=300)
    plt.close(fig)
    print(f"  {name}")


def fig_two_levers(df: pd.DataFrame) -> None:
    """
    Slika 1 — centralni rezultat: dvije nezavisne poluge nad istim mehanizmom.

    Lijeva i srednja traka razlikuju se SAMO po MAXDOP hintu analitičkih upita;
    shema, medij i model izvršavanja su identični. Desna traka mijenja smještaj
    analitike. Obje intervencije podižu transakcijsku propusnost bez ijedne
    izmjene u transakcijskom sloju.
    """
    if "im@d2" not in df.Configuration.values:
        print("  ! preskacem fig1_two_levers — nedostaje ruka im@d2")
        return

    arms = [("im", "IM, OLAP at MAXDOP 1", C_ROW),
            ("im@d2", "IM, OLAP at MAXDOP 2", C_PAR),
            ("htap", "OLAP offloaded to columnstore", C_OFF)]

    x = np.arange(len(CONCS))
    width = 0.26

    fig, ax = plt.subplots(figsize=(COL_W, 2.5))
    for k, (cfg, label, colour) in enumerate(arms):
        vals = [med(df, cfg, "OltpThroughput", c) for c in CONCS]
        # Intervali su interkvartilni raspon oko medijana, dosljedno s
        # neparametarskom analizom u radu; simetricna devijacija bi ovdje
        # sugerirala normalnost koju su testovi odbacili.
        lo = [med_q(df, cfg, "OltpThroughput", c, 0.25) for c in CONCS]
        hi = [med_q(df, cfg, "OltpThroughput", c, 0.75) for c in CONCS]
        err = np.array([[v - l for v, l in zip(vals, lo)],
                        [h - v for v, h in zip(vals, hi)]])
        bars = ax.bar(x + (k - 1) * width, vals, width, label=label,
                      color=colour, edgecolor="black", linewidth=0.4,
                      yerr=err, capsize=1.6,
                      error_kw={"elinewidth": 0.6, "capthick": 0.6})
        ax.bar_label(bars, fmt="%.0f", fontsize=5.5, padding=7, rotation=90)

    base = [med(df, "im", "OltpThroughput", c) for c in CONCS]
    top = [med(df, "htap", "OltpThroughput", c) for c in CONCS]
    ax.set_ylim(0, np.nanmax(top) * 1.52)

    ax.set_xticks(x, [f"C = {c}" for c in CONCS])
    ax.set_ylabel("OLTP throughput [ops/s]")
    ax.legend(loc="upper left", frameon=False)
    fig.tight_layout(pad=0.3)
    save(fig, "fig1_two_levers")
    _ = base


def fig_olap_crossover(df: pd.DataFrame) -> None:
    """
    Slika 2 — analitička latencija kroz konkurentnost, agregirano po omjerima.

    Row-mode je konkurentan u izolaciji (C=4) i zaostaje tek pod natjecanjem.
    Ista tačka u kojoj analitika zaostaje jest tačka u kojoj transakcije trpe.
    """
    fig, ax = plt.subplots(figsize=(COL_W, 2.2))

    series = [("im", "IM, row mode", C_ROW, "s", "--"),
              ("htap", "Offloaded, batch mode", C_OFF, "o", "-")]

    for cfg, label, colour, marker, ls in series:
        vals = [med(df, cfg, "OlapLatencyP50", c, ratio=None) for c in CONCS]
        ax.plot(CONCS, vals, lw=1.2, ms=3.5, label=label,
                color=colour, marker=marker, ls=ls)
        for c, v in zip(CONCS, vals):
            ax.annotate(f"{v:.0f}", (c, v), textcoords="offset points",
                        xytext=(0, 6), ha="center", fontsize=6)

    ax.set_xscale("log", base=2)
    ax.set_xticks(CONCS, [str(c) for c in CONCS])
    ax.set_xlabel("Concurrency level")
    ax.set_ylabel("OLAP latency P50 [ms]")
    ax.legend(loc="upper left", frameon=False)
    fig.tight_layout(pad=0.3)
    save(fig, "fig2_olap_crossover")


def fig_cpu_evidence(df: pd.DataFrame) -> None:
    """
    Slika 3 — mjereni mehanizam, iz serverskih brojača ruke im@d2.

    Lijeva os: udio ukupnog CPU vremena benchmarka koji troše analitičke niti.
    Desna os (log): SOS_SCHEDULER_YIELD — čekanje na dodjelu procesorskog
    kvantuma, direktan pokazatelj natjecanja za procesor.
    """
    if "im@d2" not in df.Configuration.values:
        print("  ! preskacem fig3_cpu_evidence — nedostaje ruka im@d2")
        return
    if "SchedulerYieldMs" not in df.columns:
        print("  ! preskacem fig3_cpu_evidence — nema kolona serverskih brojaca")
        return

    share = [med(df, "im@d2", "OlapCpuShare", c) * 100 for c in CONCS]
    yield_s = [med(df, "im@d2", "SchedulerYieldMs", c) / 1000 for c in CONCS]

    if not np.isfinite(share).any():
        print("  ! preskacem fig3_cpu_evidence — brojaci su prazni")
        return

    fig, ax = plt.subplots(figsize=(COL_W, 2.2))
    x = np.arange(len(CONCS))

    bars = ax.bar(x, share, 0.5, color=C_PAR, edgecolor="black", linewidth=0.4,
                  label="Analytical share of CPU time")
    ax.bar_label(bars, fmt="%.0f%%", fontsize=6, padding=1)
    ax.set_ylabel("Analytical share of CPU time [%]")
    ax.set_ylim(0, 118)
    ax.set_xticks(x, [f"C = {c}" for c in CONCS])

    ax2 = ax.twinx()
    ax2.plot(x, yield_s, color="#a02020", marker="o", ms=3.5, lw=1.3,
             label="SOS_SCHEDULER_YIELD")
    ax2.set_yscale("log")
    ax2.set_ylabel("Scheduler yield [s per 60 s run]", color="#a02020")
    ax2.tick_params(axis="y", colors="#a02020")
    ax2.grid(False)
    for xi, v in zip(x, yield_s):
        ax2.annotate(f"{v:.1f}", (xi, v), textcoords="offset points",
                     xytext=(6, -7), fontsize=6, color="#a02020")

    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", frameon=False)

    fig.tight_layout(pad=0.3)
    save(fig, "fig3_cpu_evidence")


def main() -> None:
    if not (RESULTS / "summary.csv").exists():
        raise SystemExit(f"Nedostaje {RESULTS / 'summary.csv'}.")

    print("Figure za Telfor rad:")
    df = load()
    fig_two_levers(df)
    fig_olap_crossover(df)
    fig_cpu_evidence(df)
    print(f"Izlaz: {OUT}")


if __name__ == "__main__":
    main()
