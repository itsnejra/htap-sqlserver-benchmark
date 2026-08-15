"""
07_diagnose_data.py — dijagnostika stanja mjernih fajlova.

Ispisuje sve što je potrebno da se utvrdi zašto analiza ne vidi očekivane
podatke: broj redova i kolona po fajlu, raspodjelu po konfiguracijama, i
raspodjelu stope uspješnosti OLTP operacija.

Ne mijenja nijedan fajl — samo čita i ispisuje.

Pokretanje:
    python Analysis/07_diagnose_data.py
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "Results"

# Očekivano stanje glavnog seta prema verziji u git-u.
EXPECTED_MAIN_ROWS = 1070
EXPECTED_CONFIGS = {"baseline", "cs", "im", "htap"}


def describe(path: Path) -> pd.DataFrame | None:
    print(f"\n{'=' * 70}\n{path.name}\n{'=' * 70}")

    if not path.exists():
        print("  NE POSTOJI")
        return None

    size_kb = path.stat().st_size / 1024
    print(f"  velicina: {size_kb:,.1f} KB")

    # Broj fizičkih linija — ako se ne poklapa s brojem parsiranih redova,
    # fajl ima neispravne redove (npr. redove sa više kolona nego header).
    with path.open(encoding="utf-8", errors="replace") as fh:
        line_count = sum(1 for _ in fh)
    print(f"  linija u fajlu: {line_count:,} (ocekivano redova: {line_count - 1:,})")

    try:
        df = pd.read_csv(path)
    except Exception as exc:
        print(f"  !! pandas NE MOZE procitati fajl: {type(exc).__name__}: {exc}")
        print("     -> fajl je neispravan; vjerovatno su dopisani redovi sire strukture")
        return None

    print(f"  parsirano redova: {len(df):,}")
    print(f"  kolona: {len(df.columns)}")

    if len(df) != line_count - 1:
        print(f"  !! NESLAGANJE: {line_count - 1:,} linija vs {len(df):,} parsiranih redova")

    if "Configuration" not in df.columns:
        print(f"  !! nema kolone Configuration; kolone su: {list(df.columns)[:8]}")
        return df

    print("\n  po konfiguraciji:")
    for cfg, n in df["Configuration"].str.strip().str.lower().value_counts().items():
        print(f"    {cfg:<12} {n:>6,}")

    if "OltpSuccessRate" in df.columns:
        sr = pd.to_numeric(df["OltpSuccessRate"], errors="coerce")
        ok = (sr >= 0.90).sum()
        bad = (sr < 0.90).sum()
        nan = sr.isna().sum()
        print(f"\n  uspjesnost OLTP: {ok:,} >= 90%   |   {bad:,} < 90%   |   {nan:,} neispravnih")
        if bad:
            print(f"    medijan kod odbacenih: {sr[sr < 0.90].median():.3f}")
            worst = df.loc[sr.idxmin()] if sr.notna().any() else None
            if worst is not None:
                print(f"    najgori run: {worst.get('Configuration')} "
                      f"{worst.get('OltpOlapRatio')} C={worst.get('ConcurrencyLevel')} "
                      f"run={worst.get('RunNumber')} -> {sr.min():.3f}")

    return df


def main() -> None:
    print("DIJAGNOSTIKA MJERNIH FAJLOVA")
    print(f"Folder: {RESULTS}")

    main_df = describe(RESULTS / "summary.csv")

    for arm in sorted(RESULTS.glob("summary_arm_*.csv")):
        describe(arm)

    print(f"\n{'=' * 70}\nZAKLJUCAK\n{'=' * 70}")

    if main_df is None:
        print("  summary.csv je neispravan ili nedostaje.")
        print("  Popravak: git checkout -- Results/summary.csv")
        return

    rows = len(main_df)
    configs = set(main_df["Configuration"].str.strip().str.lower().unique()) \
        if "Configuration" in main_df.columns else set()
    missing = EXPECTED_CONFIGS - configs

    if rows == EXPECTED_MAIN_ROWS and not missing:
        print(f"  summary.csv je ISPRAVAN ({rows:,} redova, sve konfiguracije).")
    else:
        print(f"  summary.csv ODSTUPA od verzije u git-u:")
        print(f"    redova:        {rows:,}  (ocekivano {EXPECTED_MAIN_ROWS:,})")
        if missing:
            print(f"    nedostaju:     {', '.join(sorted(missing))}")
        print()
        print("  Popravak (vraca fajl iz git-a, ne dira ruke kontrolnog eksperimenta):")
        print("    git checkout -- Results/summary.csv")


if __name__ == "__main__":
    main()
