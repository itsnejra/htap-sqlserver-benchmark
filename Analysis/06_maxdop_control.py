"""
06_maxdop_control.py — analiza MAXDOP kontrolnog eksperimenta i serverskih brojača.

SVRHA
-----
Izvorni rad odbacuje H3 na osnovu jaza HTAP vs IM u OLTP propusnosti (3,3-6,9x),
ali taj jaz nosi dvije poznate slabosti:

  (1) MAXDOP asimetrija — IM analitika koristi MAXDOP 1, HTAP MAXDOP 2, pa dio
      izmjerene razlike može poticati od stepena paralelizma, a ne od dual-store
      arhitekture. Doprinos te asimetrije nije bio izoliran.

  (2) Mehanizam CPU saturacije bio je IZVEDEN iz modela izvršavanja upita
      (row-mode vs batch-mode), a ne mjeren.

Ova skripta rješava obje:

  (1) Uspoređuje HTAP vs IM pri izjednačenom paralelizmu, u obje ruke:
        DOP=2: htap        vs im@d2
        DOP=1: htap@d1     vs im
      i računa koliki dio izvornog jaza otpada na MAXDOP.

  (2) Analizira serverske brojače (CPU po tipu radne niti, SOS_SCHEDULER_YIELD)
      koje benchmark sada bilježi po runu, čime se CPU saturacija dokazuje
      direktnim mjerenjem.

ULAZ
----
  Results/summary.csv  — mora sadržavati i glavni set (htap, im) i kontrolne
                         ruke (im@d2, htap@d1), te kolone serverskih brojača.

IZLAZ
-----
  Results/maxdop_control.csv         — usporedbe po (ratio, concurrency)
  Results/maxdop_control_report.txt  — čitljiv izvještaj
  Results/figures/14_maxdop_control.png
  Results/figures/15_cpu_attribution.png

POKRETANJE
----------
  python Analysis/06_maxdop_control.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
SUMMARY = ROOT / "Results" / "summary.csv"
OUT_DIR = ROOT / "Results"
FIG_DIR = OUT_DIR / "figures"

# Parovi koje uspoređujemo: (naziv, HTAP ruka, IM ruka, stepen paralelizma)
PAIRS = [
    ("DOP=2 (izjednačeno)", "htap",     "im@d2", 2),
    ("DOP=1 (izjednačeno)", "htap@d1",  "im",    1),
    ("Izvorno (asimetrično)", "htap",   "im",    None),
]

SERVER_COLS = [
    "OltpCpuMs", "OlapCpuMs", "CpuUtilizationPct", "OlapCpuShare",
    "SchedulerYieldMs", "ParallelismWaitMs", "CxSyncPortMs",
    "ResourceSemaphoreMs", "PageIoLatchMs", "WriteLogMs",
]


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Cohenov d s pooled standardnom devijacijom (isti oblik kao u 02_statistical_tests.py)."""
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return float("nan")
    s_pooled = np.sqrt(((n1 - 1) * a.std(ddof=1) ** 2 + (n2 - 1) * b.std(ddof=1) ** 2) / (n1 + n2 - 2))
    return (a.mean() - b.mean()) / s_pooled if s_pooled > 0 else float("nan")


def effect_label(d: float) -> str:
    ad = abs(d)
    if np.isnan(d):
        return "n/a"
    if ad < 0.2:
        return "trivijalan"
    if ad < 0.5:
        return "mali"
    if ad < 0.8:
        return "srednji"
    return "veliki"


def load() -> pd.DataFrame:
    """
    Spaja glavni summary.csv i sve summary_arm_*.csv fajlove kontrolnih ruku.

    Ruke pišu u zasebne fajlove jer glavni summary.csv potiče iz vremena prije
    uvođenja kolona sa serverskim brojačima; concat popunjava nedostajuće kolone
    s NaN umjesto da se redovi razilaze.
    """
    if not SUMMARY.exists():
        raise SystemExit(f"Nedostaje {SUMMARY}. Pokrenite benchmark prije analize.")

    frames = [pd.read_csv(SUMMARY)]
    for arm_file in sorted(SUMMARY.parent.glob("summary_arm_*.csv")):
        frames.append(pd.read_csv(arm_file))
        print(f"  + {arm_file.name}")

    df = pd.concat(frames, ignore_index=True)
    df["Configuration"] = df["Configuration"].str.strip().str.lower()

    # Ista kontrola kvaliteta kao u glavnoj analizi: runovi ispod 90% uspješnosti
    # OLTP operacija tretiraju se kao nestabilno mjerno okruženje.
    before = len(df)
    df = df[df["OltpSuccessRate"] >= 0.90].copy()
    print(f"  Učitano {before} runova, zadržano {len(df)} (OltpSuccessRate >= 0.90).")

    present = sorted(df["Configuration"].unique())
    print(f"  Prisutne konfiguracije: {', '.join(present)}")

    missing = {arm for _, h, i, _ in PAIRS for arm in (h, i)} - set(present)
    if missing:
        print(f"  UPOZORENJE: nedostaju ruke {sorted(missing)} — te usporedbe se preskaču.")
        print("  Pokrenite: dotnet run -- --arm d2 --only IM   i   --arm d1 --only HTAP")

    return df


def compare_arms(df: pd.DataFrame) -> pd.DataFrame:
    """Mann-Whitney U + Cohenov d za HTAP vs IM po svakoj ruci i kombinaciji."""
    rows = []
    for label, htap_cfg, im_cfg, dop in PAIRS:
        for ratio in sorted(df["OltpOlapRatio"].unique()):
            for conc in sorted(df["ConcurrencyLevel"].unique()):
                sel = (df["OltpOlapRatio"] == ratio) & (df["ConcurrencyLevel"] == conc)
                h = df.loc[sel & (df["Configuration"] == htap_cfg), "OltpThroughput"].to_numpy()
                i = df.loc[sel & (df["Configuration"] == im_cfg), "OltpThroughput"].to_numpy()
                if len(h) < 3 or len(i) < 3:
                    continue

                u, p = stats.mannwhitneyu(h, i, alternative="two-sided")
                d = cohens_d(h, i)
                rows.append({
                    "Poredjenje": label,
                    "MaxDop": dop if dop is not None else "1 vs 2",
                    "HtapArm": htap_cfg,
                    "ImArm": im_cfg,
                    "OltpOlapRatio": ratio,
                    "ConcurrencyLevel": conc,
                    "N_htap": len(h),
                    "N_im": len(i),
                    "HtapMedian": float(np.median(h)),
                    "ImMedian": float(np.median(i)),
                    "Faktor": float(np.median(h) / np.median(i)) if np.median(i) > 0 else np.nan,
                    "U": float(u),
                    "p": float(p),
                    "CohensD": d,
                    "EffectSize": effect_label(d),
                })
    return pd.DataFrame(rows)


def maxdop_contribution(comp: pd.DataFrame) -> pd.DataFrame:
    """
    Koliki dio izvornog jaza otpada na MAXDOP asimetriju.

    Izvorni faktor = htap(DOP2) / im(DOP1)          <- miješa arhitekturu i paralelizam
    Kontrolni      = htap(DOP2) / im@d2(DOP2)       <- samo arhitektura
    Doprinos MAXDOP-a = izvorni / kontrolni
      = 1,0  -> paralelizam nije doprinio ništa, cijeli jaz je arhitektura
      > 1,0  -> dio jaza otpada na paralelizam
    """
    key = ["OltpOlapRatio", "ConcurrencyLevel"]
    orig = comp[comp["Poredjenje"] == "Izvorno (asimetrično)"].set_index(key)["Faktor"]
    ctrl2 = comp[comp["Poredjenje"] == "DOP=2 (izjednačeno)"].set_index(key)["Faktor"]
    ctrl1 = comp[comp["Poredjenje"] == "DOP=1 (izjednačeno)"].set_index(key)["Faktor"]

    out = pd.DataFrame({
        "FaktorIzvorni": orig,
        "FaktorDop2": ctrl2,
        "FaktorDop1": ctrl1,
    }).reset_index()
    out["MaxDopDoprinos_Dop2"] = out["FaktorIzvorni"] / out["FaktorDop2"]
    out["MaxDopDoprinos_Dop1"] = out["FaktorIzvorni"] / out["FaktorDop1"]
    return out


def server_metrics_summary(df: pd.DataFrame) -> pd.DataFrame | None:
    """Agregat serverskih brojača — direktan dokaz CPU saturacije."""
    if not all(c in df.columns for c in SERVER_COLS):
        print("  UPOZORENJE: summary.csv nema kolone serverskih brojača.")
        print("  Ponovo pokrenite benchmark s CollectServerMetrics=true.")
        return None
    if df[SERVER_COLS].fillna(0).to_numpy().sum() == 0:
        print("  UPOZORENJE: serverski brojači su svi nula — mjerenje nije bilo aktivno.")
        return None

    agg = (df.groupby(["Configuration", "OltpOlapRatio", "ConcurrencyLevel"])[SERVER_COLS]
             .agg(["mean", "std"]))
    agg.columns = [f"{c}_{s}" for c, s in agg.columns]
    return agg.reset_index()


def plot_control(comp: pd.DataFrame) -> None:
    """Faktor HTAP/IM po ruci — vizualni test opstaje li jaz nakon izjednačavanja."""
    sub = comp[comp["OltpOlapRatio"] == "80_20"]
    if sub.empty:
        return

    concs = sorted(sub["ConcurrencyLevel"].unique())
    labels = [p[0] for p in PAIRS]
    width = 0.26
    x = np.arange(len(concs))

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    for k, label in enumerate(labels):
        vals = [sub.loc[(sub["Poredjenje"] == label) & (sub["ConcurrencyLevel"] == c), "Faktor"].mean()
                for c in concs]
        bars = ax.bar(x + (k - 1) * width, vals, width, label=label)
        ax.bar_label(bars, fmt="%.1f×", fontsize=8, padding=2)

    ax.axhline(1.0, color="grey", lw=0.8, ls="--")
    ax.set_xticks(x, [f"C = {c}" for c in concs])
    ax.set_ylabel("OLTP propusnost: HTAP / IM (medijani)")
    ax.set_title("Jaz HTAP vs IM prije i poslije izjednačavanja MAXDOP-a\n(omjer opterećenja 80/20)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / "14_maxdop_control.png", dpi=200)
    plt.close(fig)
    print(f"  Slika: {FIG_DIR / '14_maxdop_control.png'}")


def plot_cpu(df: pd.DataFrame) -> None:
    """Podjela CPU vremena na OLTP i OLAP niti — mjereni mehanizam."""
    if "OltpCpuMs" not in df.columns:
        return

    sub = df[(df["OltpOlapRatio"] == "80_20") & (df["ConcurrencyLevel"] == 32)]
    order = [c for c in ["baseline", "cs", "im", "im@d2", "htap", "htap@d1"]
             if c in sub["Configuration"].unique()]
    if not order:
        return

    oltp = [sub.loc[sub["Configuration"] == c, "OltpCpuMs"].mean() / 1000 for c in order]
    olap = [sub.loc[sub["Configuration"] == c, "OlapCpuMs"].mean() / 1000 for c in order]
    if not np.isfinite(oltp).any():
        return

    x = np.arange(len(order))
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    ax.bar(x, oltp, 0.6, label="OLTP niti")
    ax.bar(x, olap, 0.6, bottom=oltp, label="OLAP niti")
    ax.set_xticks(x, [c.upper() for c in order], fontsize=9)
    ax.set_ylabel("Procesorsko vrijeme po runu (s)")
    ax.set_title("Atribucija procesorskog vremena po tipu radne niti\n(80/20, C = 32, mjerna faza 60 s)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / "15_cpu_attribution.png", dpi=200)
    plt.close(fig)
    print(f"  Slika: {FIG_DIR / '15_cpu_attribution.png'}")


def write_report(comp: pd.DataFrame, contrib: pd.DataFrame, server: pd.DataFrame | None) -> None:
    lines = [
        "=" * 78,
        "MAXDOP KONTROLNI EKSPERIMENT + SERVERSKA INSTRUMENTACIJA",
        "=" * 78,
        "",
        "1. HTAP vs IM PRI IZJEDNAČENOM PARALELIZMU (OLTP propusnost)",
        "-" * 78,
    ]

    for label, *_ in PAIRS:
        sub = comp[comp["Poredjenje"] == label]
        if sub.empty:
            lines.append(f"  {label}: nema podataka (ruka nije izmjerena).")
            continue
        lines.append(f"  {label}:")
        for _, r in sub.iterrows():
            sig = "✓" if r["p"] < 0.05 else "✗"
            lines.append(
                f"    {r['OltpOlapRatio']:>5} C={int(r['ConcurrencyLevel']):>2}: "
                f"HTAP={r['HtapMedian']:>9.0f}  IM={r['ImMedian']:>9.0f}  "
                f"faktor={r['Faktor']:>5.2f}×  p={r['p']:.4f}  "
                f"d={r['CohensD']:+.2f} ({r['EffectSize']}) {sig}")
        lines.append("")

    lines += [
        "2. DOPRINOS MAXDOP ASIMETRIJE IZVORNOM JAZU",
        "-" * 78,
        "  Vrijednost 1,00 znači da paralelizam nije doprinio ništa i da je cijeli",
        "  jaz posljedica dual-store arhitekture. Vrijednosti > 1,00 kvantificiraju",
        "  koliki je dio izvornog jaza bio artefakt razlike u stepenu paralelizma.",
        "",
    ]
    if contrib.empty or contrib["MaxDopDoprinos_Dop2"].isna().all():
        lines.append("  Nema podataka — kontrolne ruke nisu izmjerene.")
    else:
        for _, r in contrib.iterrows():
            lines.append(
                f"    {r['OltpOlapRatio']:>5} C={int(r['ConcurrencyLevel']):>2}: "
                f"izvorno={r['FaktorIzvorni']:>5.2f}×  "
                f"DOP2={r['FaktorDop2']:>5.2f}×  DOP1={r['FaktorDop1']:>5.2f}×  "
                f"doprinos MAXDOP={r['MaxDopDoprinos_Dop2']:>5.2f}×")
    lines.append("")

    lines += [
        "3. SERVERSKI BROJAČI (direktno mjerenje CPU saturacije)",
        "-" * 78,
    ]
    if server is None:
        lines.append("  Nedostupno — pokrenite benchmark s CollectServerMetrics=true.")
    else:
        lines.append(f"  {'Config':<10} {'ratio':<6} {'C':>3} {'CPU%':>7} "
                     f"{'OLAP CPU udio':>14} {'SchedYield(s)':>14}")
        for _, r in server.iterrows():
            lines.append(
                f"  {r['Configuration']:<10} {r['OltpOlapRatio']:<6} "
                f"{int(r['ConcurrencyLevel']):>3} "
                f"{r['CpuUtilizationPct_mean']:>7.1f} "
                f"{r['OlapCpuShare_mean']:>14.3f} "
                f"{r['SchedulerYieldMs_mean'] / 1000:>14.1f}")
    lines.append("")

    path = OUT_DIR / "maxdop_control_report.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Izvještaj: {path}")


def main() -> None:
    print("MAXDOP kontrolni eksperiment — analiza")
    df = load()

    comp = compare_arms(df)
    comp.to_csv(OUT_DIR / "maxdop_control.csv", index=False)
    print(f"  Usporedbe: {OUT_DIR / 'maxdop_control.csv'} ({len(comp)} redova)")

    contrib = maxdop_contribution(comp) if not comp.empty else pd.DataFrame()
    server = server_metrics_summary(df)
    if server is not None:
        server.to_csv(OUT_DIR / "server_metrics_summary.csv", index=False)
        print(f"  Serverski brojači: {OUT_DIR / 'server_metrics_summary.csv'}")

    if not comp.empty:
        plot_control(comp)
    plot_cpu(df)
    write_report(comp, contrib, server)
    print("Gotovo.")


if __name__ == "__main__":
    main()
