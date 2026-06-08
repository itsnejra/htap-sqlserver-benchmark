"""
HTAPBenchmark: 06_delete_update_benchmark.py
Mini benchmark za DELETE i Complex UPDATE operacije

Mjeri avg/min/max/total za:
  - Simple DELETE    (usp_DeleteVote)
  - Complex DELETE   (usp_DeletePostVotes)
  - Complex UPDATE   (usp_UpdateUserReputation)

Za svaku od 4 konfiguracije (baseline, cs, im, htap).

Pokretanje:
  cd Analysis
  pip install pyodbc
  python 06_delete_update_benchmark.py
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")

import pyodbc
import time
import random
import csv
import statistics
from pathlib import Path
from datetime import date, datetime

# ─────────────────────────────────────────────────────
# KONFIGURACIJA
# ─────────────────────────────────────────────────────
CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=.;"
    "DATABASE=HTAPBenchmark;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

CONFIGS   = ["baseline", "cs", "im", "htap"]

# Broj iteracija po operaciji po konfiguraciji
N_DELETE_SIMPLE  = 500   # insert 500 glasova pa brisemo jedan po jedan
N_DELETE_COMPLEX = 100   # insert 100 grupica pa brisemo grupu odjednom
N_UPDATE_COMPLEX = 500   # ažuriramo reputaciju 500 nasumičnih korisnika

# Sintetički ID-ovi — dovoljno visoki da ne koliziju s pravim podacima
SYNTHETIC_VOTE_ID_START = 100_000_000

OUTPUT_CSV  = Path("../Results/delete_update_benchmark.csv")
OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────
# POMOĆNE FUNKCIJE
# ─────────────────────────────────────────────────────

def connect():
    for driver in ["ODBC Driver 17 for SQL Server",
                   "ODBC Driver 18 for SQL Server",
                   "SQL Server"]:
        try:
            cs = CONN_STR.replace("ODBC Driver 17 for SQL Server", driver)
            return pyodbc.connect(cs, autocommit=True)
        except pyodbc.Error:
            continue
    raise RuntimeError("Nije moguće spojiti na SQL Server. Provjeri connection string.")


def get_user_ids(conn, schema, n=1000):
    """Vraća listu UserId-ova iz sheme. Ako je prazna, vraća sintetičke ID-ove."""
    cur = conn.cursor()
    cur.execute(f"SELECT TOP {n} Id FROM {schema}.Users")
    rows = cur.fetchall()
    if rows:
        return [r[0] for r in rows]
    # Shema nema korisnika — vraćamo sintetičke ID-ove (1..n)
    print(f"  [{schema}] Users prazna — koristim sintetičke UserIds")
    return list(range(1, n + 1))


def ensure_test_users(conn, schema, n=100):
    """Insertuje test korisnike ako je Users tabela prazna (nema FK-a)."""
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {schema}.Users")
    if cur.fetchone()[0] > 0:
        return  # već ima korisnika
    print(f"  [{schema}] Insertujem {n} test korisnika...")
    base = 90_000_000
    for i in range(n):
        try:
            cur.execute(
                f"INSERT INTO {schema}.Users "
                f"(Id, DisplayName, Reputation, CreationDate, LastAccessDate, Views, UpVotes, DownVotes) "
                f"VALUES (?, ?, 1, '2010-01-01', '2010-01-01', 0, 0, 0)",
                base + i, f"TestUser{i}"
            )
        except Exception:
            pass


def measure_ms(func):
    """Mjeri trajanje jednog poziva u milisekundama."""
    t0 = time.perf_counter()
    func()
    return (time.perf_counter() - t0) * 1000.0


def stats(latencies):
    return {
        "N":       len(latencies),
        "avg_ms":  round(statistics.mean(latencies),   4),
        "min_ms":  round(min(latencies),               4),
        "max_ms":  round(max(latencies),               4),
        "total_ms":round(sum(latencies),               2),
        "p50_ms":  round(statistics.median(latencies), 4),
    }


# ─────────────────────────────────────────────────────
# BENCHMARK FUNKCIJE
# ─────────────────────────────────────────────────────

def bench_simple_delete(conn, schema):
    """
    Insertuje N_DELETE_SIMPLE glasova s visokim sintetičkim ID-ovima,
    pa mjeri brisanje svakog glasa pojedinačno (usp_DeleteVote).
    """
    print(f"  [{schema}] Simple DELETE — insertujem {N_DELETE_SIMPLE} test glasova...")
    cur = conn.cursor()

    # Nema FK-a na Votes — možemo koristiti sintetičke ID-ove
    cur.execute(f"SELECT TOP 1 Id FROM {schema}.Posts")
    row = cur.fetchone()
    post_id = row[0] if row else 1   # fallback na 1 ako je tabela prazna

    cur.execute(f"SELECT TOP 1 Id FROM {schema}.Users")
    row = cur.fetchone()
    user_id = row[0] if row else 1

    # Insertuj testne glasove
    base_id = SYNTHETIC_VOTE_ID_START + abs(hash(schema)) % 1_000_000
    vote_ids = []
    for i in range(N_DELETE_SIMPLE):
        vid = base_id + i
        try:
            cur.execute(
                f"INSERT INTO {schema}.Votes (Id, PostId, VoteTypeId, CreationDate, UserId) "
                f"VALUES (?, ?, 5, ?, ?)",
                vid, post_id, date.today(), user_id
            )
            vote_ids.append(vid)
        except pyodbc.IntegrityError:
            pass  # ID već postoji, preskoči

    if not vote_ids:
        print(f"  [{schema}] Nema insertovanih glasova — preskačem.")
        return None

    print(f"  [{schema}] Mjerim brisanje {len(vote_ids)} glasova...")
    latencies = []
    for vid in vote_ids:
        lat = measure_ms(lambda v=vid:
            cur.execute(f"EXEC {schema}.usp_DeleteVote @Id=?", v))
        latencies.append(lat)

    return stats(latencies)


def bench_complex_delete(conn, schema):
    """
    Insertuje N_DELETE_COMPLEX × 10 glasova u grupama (isti PostId+VoteTypeId=6),
    pa mjeri brisanje svake grupe (usp_DeletePostVotes).
    """
    print(f"  [{schema}] Complex DELETE — insertujem {N_DELETE_COMPLEX * 10} test glasova u grupama...")
    cur = conn.cursor()

    cur.execute(f"SELECT TOP {N_DELETE_COMPLEX} Id FROM {schema}.Posts")
    post_ids = [row[0] for row in cur.fetchall()]
    # Ako nema postova, koristimo sintetičke PostId-ove (nema FK-a)
    if not post_ids:
        post_ids = list(range(1, N_DELETE_COMPLEX + 1))

    cur.execute(f"SELECT TOP 1 Id FROM {schema}.Users")
    row = cur.fetchone()
    user_id = row[0] if row else 1

    base_id = SYNTHETIC_VOTE_ID_START + 2_000_000 + abs(hash(schema)) % 1_000_000
    counter = 0
    valid_post_ids = []

    for post_id in post_ids:
        inserted = 0
        for j in range(10):
            vid = base_id + counter
            counter += 1
            try:
                cur.execute(
                    f"INSERT INTO {schema}.Votes (Id, PostId, VoteTypeId, CreationDate, UserId) "
                    f"VALUES (?, ?, 6, ?, ?)",
                    vid, post_id, date.today(), user_id
                )
                inserted += 1
            except pyodbc.IntegrityError:
                pass
        if inserted > 0:
            valid_post_ids.append(post_id)

    if not valid_post_ids:
        print(f"  [{schema}] Nema podataka za Complex DELETE — preskačem.")
        return None

    print(f"  [{schema}] Mjerim Complex DELETE za {len(valid_post_ids)} postova...")
    latencies = []
    for post_id in valid_post_ids:
        lat = measure_ms(lambda p=post_id:
            cur.execute(f"EXEC {schema}.usp_DeletePostVotes @PostId=?, @VoteTypeId=6", p))
        latencies.append(lat)

    return stats(latencies)


def bench_complex_update(conn, schema):
    """
    Mjeri usp_UpdateUserReputation za N_UPDATE_COMPLEX nasumičnih korisnika.
    """
    print(f"  [{schema}] Complex UPDATE — dohvatam korisnike...")
    ensure_test_users(conn, schema, n=N_UPDATE_COMPLEX)
    user_ids = get_user_ids(conn, schema, N_UPDATE_COMPLEX)
    if not user_ids:
        return None

    cur = conn.cursor()
    print(f"  [{schema}] Mjerim usp_UpdateUserReputation za {len(user_ids)} korisnika...")
    latencies = []
    for uid in user_ids:
        lat = measure_ms(lambda u=uid:
            cur.execute(f"EXEC {schema}.usp_UpdateUserReputation @UserId=?", u))
        latencies.append(lat)

    return stats(latencies)


# ─────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("HTAPBenchmark: DELETE + Complex UPDATE mini benchmark")
    print("=" * 65)

    print("\nSpajanje na SQL Server...")
    conn = connect()
    print("Spojeno.\n")

    results = []

    for schema in CONFIGS:
        print(f"\n{'─'*50}")
        print(f" Konfiguracija: {schema.upper()}")
        print(f"{'─'*50}")

        # 1. Simple DELETE
        r = bench_simple_delete(conn, schema)
        if r:
            results.append({
                "Configuration": schema,
                "Operation":     "usp_DeleteVote",
                "Category":      "Simple DELETE",
                **r
            })
            print(f"  → avg={r['avg_ms']:.3f}ms  min={r['min_ms']:.3f}ms  "
                  f"max={r['max_ms']:.3f}ms  total={r['total_ms']:.1f}ms")

        # 2. Complex DELETE
        r = bench_complex_delete(conn, schema)
        if r:
            results.append({
                "Configuration": schema,
                "Operation":     "usp_DeletePostVotes",
                "Category":      "Complex DELETE",
                **r
            })
            print(f"  → avg={r['avg_ms']:.3f}ms  min={r['min_ms']:.3f}ms  "
                  f"max={r['max_ms']:.3f}ms  total={r['total_ms']:.1f}ms")

        # 3. Complex UPDATE
        r = bench_complex_update(conn, schema)
        if r:
            results.append({
                "Configuration": schema,
                "Operation":     "usp_UpdateUserReputation",
                "Category":      "Complex UPDATE",
                **r
            })
            print(f"  → avg={r['avg_ms']:.3f}ms  min={r['min_ms']:.3f}ms  "
                  f"max={r['max_ms']:.3f}ms  total={r['total_ms']:.1f}ms")

    conn.close()

    # ── Ispis sažetka ─────────────────────────────────
    print(f"\n{'='*65}")
    print("SAŽETAK — Prosječno vrijeme izvršavanja (ms)")
    print(f"{'='*65}")
    print(f"{'Kategorija':<22} {'Baseline':>10} {'CS':>10} {'IM':>10} {'HTAP':>10}")
    print("-" * 65)

    categories = ["Simple DELETE", "Complex DELETE", "Complex UPDATE"]
    for cat in categories:
        row_vals = {}
        for r in results:
            if r["Category"] == cat:
                row_vals[r["Configuration"]] = r["avg_ms"]
        line = f"{cat:<22}"
        for cfg in CONFIGS:
            v = row_vals.get(cfg)
            line += f" {v:>10.3f}" if v is not None else f" {'N/A':>10}"
        print(line)

    # ── Pohrana CSV ───────────────────────────────────
    if results:
        fieldnames = ["Configuration", "Operation", "Category",
                      "N", "avg_ms", "min_ms", "max_ms", "total_ms", "p50_ms"]
        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(results)
        print(f"\nRezultati pohranjeni: {OUTPUT_CSV}")
    else:
        print("\nNema rezultata za pohraniti.")

    print("\nZavršeno.")


if __name__ == "__main__":
    main()
