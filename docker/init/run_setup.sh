#!/bin/bash
# =============================================================================
# HTAPBenchmark: run_setup.sh
# Inicijalizacijska skripta za db-init Docker kontejner.
# Restorira StackOverflow2010.bak, kreira HTAPBenchmark bazu i učitava podatke.
# =============================================================================

set -e

SERVER="${SQL_SERVER:-sqlserver}"
PASSWORD="${SA_PASSWORD:-HTAPBenchmark_2024!}"
SQLCMD="/opt/mssql-tools18/bin/sqlcmd"

# Stariji mssql-tools nema -No flag i sqlcmd je na drugom putu
if [ ! -f "$SQLCMD" ]; then
    SQLCMD="/opt/mssql-tools/bin/sqlcmd"
fi

run_sql() {
    local desc="$1"
    local script="$2"
    echo ""
    echo "=== ${desc} ==="
    "$SQLCMD" -S "$SERVER" -U sa -P "$PASSWORD" -i "$script" -b -No
}

# ─── 1. Čekaj SQL Server ──────────────────────────────────────────────────────
echo "=== Čekam SQL Server (${SERVER}) da bude spreman... ==="
MAX_TRIES=60
for i in $(seq 1 $MAX_TRIES); do
    if "$SQLCMD" -S "$SERVER" -U sa -P "$PASSWORD" -Q "SELECT 1" -b -No 2>/dev/null; then
        echo "SQL Server je spreman (pokušaj ${i})."
        break
    fi
    if [ "$i" -eq "$MAX_TRIES" ]; then
        echo "GREŠKA: SQL Server nije odgovorio nakon ${MAX_TRIES} pokušaja."
        exit 1
    fi
    echo "  Pokušaj ${i}/${MAX_TRIES} — čekam 5s..."
    sleep 5
done

# ─── 2. Restore StackOverflow2010 ────────────────────────────────────────────
if [ ! -f "/backups/StackOverflow2010.bak" ]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  GREŠKA: /backups/StackOverflow2010.bak nije pronađen!      ║"
    echo "║                                                              ║"
    echo "║  Preuzmi .bak fajl (~7-10 GB) i postavi ga u:               ║"
    echo "║    HTAPBenchmark/Backups/StackOverflow2010.bak               ║"
    echo "║                                                              ║"
    echo "║  Izvor: https://www.brentozar.com/archive/2015/10/           ║"
    echo "║         how-to-download-the-stack-overflow-database/         ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    exit 1
fi

run_sql "Restoriranje StackOverflow2010 (može trajati 10-30 min)" \
        "/init/01_restore_stackoverflow.sql"

# ─── 3. Kreiranje HTAPBenchmark baze ─────────────────────────────────────────
run_sql "Kreiranje HTAPBenchmark baze (Linux putanje)" \
        "/init/00_DatabaseSetup_docker.sql"

# ─── 4. Kreiranje shema ───────────────────────────────────────────────────────
for script in 01_Schema_Baseline.sql 02_Schema_CS.sql 03_Schema_IM.sql 04_Schema_HTAP.sql; do
    run_sql "Shema: ${script}" "/sql/${script}"
done

# ─── 5. Učitavanje podataka (najduži korak, 30-120 min) ──────────────────────
echo ""
echo "=== Učitavanje podataka iz StackOverflow2010 (30-120 min) ==="
"$SQLCMD" -S "$SERVER" -U sa -P "$PASSWORD" -i "/sql/05_LoadData.sql" -b -No -t 7200

# ─── 6. CS/HTAP columnstore + stored procedure + rezultatna shema ────────────
for script in \
    05b_LoadData_CS_HTAP_Only.sql \
    06_StoredProcs_OLTP.sql \
    07_StoredProcs_OLAP.sql \
    07b_StoredProcs_OLAP_HTAP_DualStore.sql \
    08_ResultsSchema.sql \
    09_Fix_OLAP_MaxDop.sql
do
    run_sql "${script}" "/sql/${script}"
done

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║        INICIJALIZACIJA BAZE ZAVRŠENA USPJEŠNO!               ║"
echo "║  HTAPBenchmark baza je sprema. Benchmark može početi.        ║"
echo "╚══════════════════════════════════════════════════════════════╝"
