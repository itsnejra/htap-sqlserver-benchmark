"""
HTAPBenchmark: run_all.py
Pokreće sve analitičke skripte sekvencijalno nakon završenog benchmarka.

Automatski detektuje koji summary CSV koristiti:
  - Ako postoji summary_full_crud.csv  → koristi njega (novi full-CRUD benchmark)
  - Inače                              → koristi summary.csv (originalni benchmark)

Pokretanje:
  cd Analysis
  python run_all.py

Opcije:
  python run_all.py --input ../Results/summary_full_crud.csv   # eksplicitni path
  python run_all.py --skip-merge                               # preskoči 00_merge
  python run_all.py --skip-delete-bench                        # preskoči 06 (treba SQL Server)
"""

import sys
import os
import subprocess
import time
import shutil
import argparse
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ANALYSIS_DIR = Path(__file__).parent
RESULTS_DIR  = ANALYSIS_DIR.parent / "Results"

# ─── Detekcija input fajla ────────────────────────────────────────────────────

def detect_summary_csv(explicit_path: str | None) -> Path:
    if explicit_path:
        p = Path(explicit_path)
        if not p.exists():
            sys.exit(f"ERROR: Navedeni fajl ne postoji: {p}")
        return p

    full_crud = RESULTS_DIR / "summary_full_crud.csv"
    original  = RESULTS_DIR / "summary.csv"

    if full_crud.exists():
        print(f"  Detektovan full-CRUD benchmark: {full_crud.name}")
        return full_crud
    elif original.exists():
        print(f"  Koristi se originalni benchmark: {original.name}")
        return original
    else:
        sys.exit("ERROR: Nije pronađen ni summary.csv ni summary_full_crud.csv u Results/.\n"
                 "       Pokrenite benchmark aplikaciju prvo.")


# ─── Runner ──────────────────────────────────────────────────────────────────

def run_script(script: str, env: dict) -> bool:
    """Pokreni Python skriptu u Analysis/ folderu. Vraća True ako uspješno."""
    path = ANALYSIS_DIR / script
    if not path.exists():
        print(f"  [PRESKOČI] {script} — fajl ne postoji.")
        return True

    print(f"\n{'─'*60}")
    print(f"  Pokrećem: {script}")
    print(f"{'─'*60}")

    t0 = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(ANALYSIS_DIR),
        env={**os.environ, **env},
        text=True,
        encoding="utf-8",
    )
    elapsed = time.perf_counter() - t0

    if result.returncode != 0:
        print(f"\n  [GREŠKA] {script} završio s kodom {result.returncode}")
        return False

    print(f"\n  [OK] {script} — {elapsed:.1f}s")
    return True


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="HTAPBenchmark — pokretanje svih analiza")
    parser.add_argument("--input",          help="Eksplicitni path do summary CSV fajla")
    parser.add_argument("--skip-merge",     action="store_true", help="Preskoči 00_merge_results.py")
    parser.add_argument("--skip-delete-bench", action="store_true", help="Preskoči 06 (ne treba SQL Server)")
    args = parser.parse_args()

    print("=" * 60)
    print("HTAPBenchmark: Pokretanje svih analiza")
    print("=" * 60)

    summary_csv = detect_summary_csv(args.input)

    # Ako koristimo full_crud, kopiramo ga kao aktivan summary.csv da skripte
    # (koje imaju hardkodirane putanje) rade bez izmjena.
    active_summary = RESULTS_DIR / "summary.csv"
    backup_summary = RESULTS_DIR / "summary_original_backup.csv"

    using_full_crud = (summary_csv.name == "summary_full_crud.csv")
    if using_full_crud:
        if active_summary.exists() and not backup_summary.exists():
            shutil.copy2(active_summary, backup_summary)
            print(f"  Backup originalnog summary.csv → {backup_summary.name}")
        shutil.copy2(summary_csv, active_summary)
        print(f"  Aktivan summary.csv ← {summary_csv.name}")

    env = {}  # može se proširiti s env varijablama ako treba

    start_total = time.perf_counter()
    results = {}

    # ── 00: Merge (opcionalno) ─────────────────────────────────────────────
    if not args.skip_merge:
        results["00_merge_results.py"] = run_script("00_merge_results.py", env)
    else:
        print("\n  [PRESKOČI] 00_merge_results.py (--skip-merge)")

    # ── 01–05: Statistika, testovi, grafovi, per-op, regresija ────────────
    for script in [
        "01_descriptive_stats.py",
        "02_statistical_tests.py",
        "03_visualizations.py",
        "04_per_operation_stats.py",
        "05_regression_anova.py",
    ]:
        results[script] = run_script(script, env)
        if not results[script]:
            print(f"\n  UPOZORENJE: {script} nije uspio — nastavljam s ostalima.")

    # ── 06: DELETE + Complex UPDATE mini benchmark (treba SQL Server) ─────
    if not args.skip_delete_bench:
        results["06_delete_update_benchmark.py"] = run_script("06_delete_update_benchmark.py", env)
    else:
        print("\n  [PRESKOČI] 06_delete_update_benchmark.py (--skip-delete-bench)")

    # ── Sažetak ────────────────────────────────────────────────────────────
    total = time.perf_counter() - start_total
    ok    = sum(1 for v in results.values() if v)
    fail  = sum(1 for v in results.values() if not v)

    print(f"\n{'='*60}")
    print(f"  Završeno za {total:.0f}s  |  OK: {ok}  |  Greške: {fail}")
    for script, success in results.items():
        status = "✓" if success else "✗ GREŠKA"
        print(f"  {status}  {script}")
    print(f"{'='*60}")

    if fail == 0:
        print("\n  Svi rezultati osvježeni. Provjerite Results/ folder.")
    else:
        print("\n  Neki scriptovi nisu uspjeli. Pogledajte poruke greške iznad.")
        sys.exit(1)


if __name__ == "__main__":
    main()
