"""
HTAPBenchmark: 00_merge_results.py
Spaja rezultate iz više CSV fajlova u jedan summary.csv za analizu.

Ulazni fajlovi (iz BenchmarkApp/Results/):
  - summary.csv          → baseline (270) + cs (270) + im (parcijalno)
  - summary_im_htap.csv  → im (270, kompletno) + htap (parcijalno)
  - summary_htap.csv     → htap (270, kompletno) — generira se nakon HTAP benchmarka

Izlaz:
  - ../Results/summary.csv  (za analitičke skripte 01, 02, 03)
  - Izvještaj o kompletnosti podataka
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
from pathlib import Path

# ----------------------------------------------------------------
# Putanje
# ----------------------------------------------------------------
BENCH_RESULTS = Path(__file__).parent.parent / "BenchmarkApp" / "HTAPBenchmark.Runner" / "bin" / "Release" / "net8.0" / "Results"

OUTPUT_DIR = Path("../Results")
OUTPUT_CSV = OUTPUT_DIR / "summary.csv"

CONFIGS    = ["baseline", "cs", "im", "htap"]
RATIOS     = ["80_20", "50_50", "20_80"]
CONCURRENCIES = [4, 16, 32]
RUNS_PER_COMBO = 30


def load_config(path: Path, config: str) -> pd.DataFrame:
    """Učitaj redove za zadanu konfiguraciju iz CSV fajla."""
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    return df[df["Configuration"] == config].copy()


def check_completeness(df: pd.DataFrame, label: str) -> bool:
    """Ispiši izvještaj o kompletnosti i vrati True ako je sve kompletno."""
    expected = len(RATIOS) * len(CONCURRENCIES) * RUNS_PER_COMBO
    actual = len(df)
    complete = (actual == expected)
    status = "✓" if complete else f"✗ (nedostaje {expected - actual} runova)"
    print(f"  {label:20s}: {actual:4d}/{expected} {status}")

    if not complete and actual > 0:
        # Pokaži koje kombinacije su nepotpune
        combos = df.groupby(["OltpOlapRatio", "ConcurrencyLevel"])["RunNumber"].count()
        missing = combos[combos < RUNS_PER_COMBO]
        if len(missing) > 0:
            for idx, cnt in missing.items():
                print(f"    - {idx[0]}/C={idx[1]}: {cnt}/{RUNS_PER_COMBO} runova")
    return complete


def main():
    print("=" * 60)
    print("HTAPBenchmark: Spajanje rezultata")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------------------
    # Učitaj svaku konfiguraciju iz najboljeg dostupnog izvora
    # ----------------------------------------------------------------
    print("\nIzvorna datoteka → konfiguracija:")

    # BASELINE: iz summary.csv (270 runova)
    baseline = load_config(BENCH_RESULTS / "summary.csv", "baseline")
    print(f"\n  summary.csv:")
    check_completeness(baseline, "baseline")

    # CS: iz summary.csv (270 runova)
    cs = load_config(BENCH_RESULTS / "summary.csv", "cs")
    check_completeness(cs, "cs")

    # IM: preferira summary_im_htap.csv (kompletnih 270), inače summary.csv
    im_full = load_config(BENCH_RESULTS / "summary_im_htap.csv", "im")
    im_partial = load_config(BENCH_RESULTS / "summary.csv", "im")

    print(f"\n  summary_im_htap.csv:")
    if len(im_full) >= 270:
        im = im_full
        check_completeness(im, "im (full)")
    else:
        # Spoji: uzmi im iz summary_im_htap.csv + dopuni iz summary.csv
        combos_full = set(zip(im_full["OltpOlapRatio"], im_full["ConcurrencyLevel"]))
        extra = im_partial[~im_partial.apply(
            lambda r: (r["OltpOlapRatio"], r["ConcurrencyLevel"]) in combos_full, axis=1)]
        im = pd.concat([im_full, extra], ignore_index=True)
        check_completeness(im, "im (merged)")

    # HTAP: iz summary_htap.csv (trenutno se puni)
    htap = load_config(BENCH_RESULTS / "summary_htap.csv", "htap")
    print(f"\n  summary_htap.csv:")
    htap_complete = check_completeness(htap, "htap")

    # ----------------------------------------------------------------
    # Spoji sve
    # ----------------------------------------------------------------
    all_dfs = [df for df in [baseline, cs, im, htap] if len(df) > 0]
    if not all_dfs:
        print("\nNema podataka za spajanje!")
        return

    merged = pd.concat(all_dfs, ignore_index=True)

    # Filtriraj loše runove (success rate < 0.90 — prouzrokovani SQL Server nestabilnošću)
    bad_mask = (merged["OltpSuccessRate"].astype(float) < 0.90)
    bad_count = bad_mask.sum()
    if bad_count > 0:
        print(f"\n  Filtrirano {bad_count} runova s OltpSuccessRate < 0.90 (nestabilni runovi):")
        print(merged[bad_mask][["Configuration","OltpOlapRatio","ConcurrencyLevel","RunNumber","OltpSuccessRate"]].to_string(index=False))
        merged = merged[~bad_mask]

    print(f"\nUkupno redova za analizu: {len(merged)}")

    # Sortiraj konzistentno
    config_order = {c: i for i, c in enumerate(CONFIGS)}
    merged["_cfg_order"] = merged["Configuration"].map(config_order).fillna(99)
    merged = merged.sort_values(["_cfg_order", "OltpOlapRatio", "ConcurrencyLevel", "RunNumber"])
    merged = merged.drop(columns=["_cfg_order"])

    merged.to_csv(OUTPUT_CSV, index=False)
    print(f"Pohranjen: {OUTPUT_CSV}")

    # ----------------------------------------------------------------
    # Brzi pregled
    # ----------------------------------------------------------------
    print("\n" + "=" * 60)
    print("OLTP propusnost (Mean ops/s) — pregled po konfiguraciji i concurrency-u")
    print("=" * 60)
    pivot = merged.groupby(["Configuration", "ConcurrencyLevel"])["OltpThroughput"].mean().round(0)
    print(pivot.unstack("ConcurrencyLevel").to_string())

    print("\n" + "=" * 60)
    print("OLAP latencija P50 (Mean ms) — pregled po konfiguraciji i omjeru")
    print("=" * 60)
    pivot2 = merged.groupby(["Configuration", "OltpOlapRatio"])["OlapLatencyP50"].mean().round(0)
    print(pivot2.unstack("OltpOlapRatio").to_string())

    if not htap_complete:
        print(f"\n⚠️  HTAP nije kompletno ({len(htap)}/270 runova).")
        print("   Pokrenite HTAP benchmark i onda ponovo ovaj skript.")
    else:
        print("\n✓ Svi podaci su kompletni. Pokrenite 01_descriptive_stats.py i 02_statistical_tests.py")


if __name__ == "__main__":
    main()
