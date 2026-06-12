#!/bin/bash
# =============================================================================
# HTAPBenchmark: run_setup.sh
# Inicijalizacijska skripta za db-init Docker kontejner.
# Podržava i MDF (attach) i BAK (restore) format StackOverflow2010 baze.
# =============================================================================

set -e

SERVER="${SQL_SERVER:-sqlserver}"
PASSWORD="${SA_PASSWORD:-HTAPBenchmark_2024!}"
SQLCMD="/opt/mssql-tools18/bin/sqlcmd"

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

# ─── 2. StackOverflow2010 — MDF attach ili BAK restore ───────────────────────
MDF_FILE=""
BAK_FILE=""

# Pretraži Backups folder za MDF i BAK fajlove
for f in /backups/*.mdf /backups/*.MDF; do
    [ -f "$f" ] && MDF_FILE="$f" && break
done
for f in /backups/*.bak /backups/*.BAK; do
    [ -f "$f" ] && BAK_FILE="$f" && break
done

if [ -n "$MDF_FILE" ]; then
    echo ""
    echo "=== Pronađen MDF fajl: ${MDF_FILE} ==="
    echo "    Kopiram u /var/opt/mssql/data/ ..."
    cp "$MDF_FILE" /var/opt/mssql/data/StackOverflow2010.mdf

    # Kopiraj LDF ako postoji (nije obavezno — ATTACH_REBUILD_LOG ga rekreira)
    LDF_FILE="${MDF_FILE%.mdf}_log.ldf"
    [ ! -f "$LDF_FILE" ] && LDF_FILE="${MDF_FILE%.MDF}_log.ldf"
    if [ -f "$LDF_FILE" ]; then
        echo "    Pronađen i LDF fajl — kopiram..."
        cp "$LDF_FILE" /var/opt/mssql/data/StackOverflow2010_log.ldf
    fi

    run_sql "Attach StackOverflow2010 iz MDF fajla" \
            "/init/01_attach_stackoverflow.sql"

elif [ -n "$BAK_FILE" ]; then
    echo ""
    echo "=== Pronađen BAK fajl: ${BAK_FILE} ==="
    run_sql "Restore StackOverflow2010 iz BAK fajla (može trajati 10-30 min)" \
            "/init/01_restore_stackoverflow.sql"

else
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  GREŠKA: Nije pronađen StackOverflow2010 fajl!              ║"
    echo "║                                                              ║"
    echo "║  Postavi jedan od ovih fajlova u HTAPBenchmark/Backups/:    ║"
    echo "║    StackOverflow2010.mdf   (MDF format — brži attach)       ║"
    echo "║    StackOverflow2010.bak   (BAK format — restore)           ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    exit 1
fi

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
