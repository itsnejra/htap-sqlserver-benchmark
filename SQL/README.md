# SQL Setup Scripts

Execute the scripts in the following order against the `HTAPBenchmark` database.

## Prerequisites

- Microsoft SQL Server 2022 (Developer or Enterprise Edition)
- StackOverflow2010 database restored on the same instance
- At least 32 GB RAM (in-memory tables require ~8–12 GB)

## Execution Order

| # | Script | Description |
|---|--------|-------------|
| 1 | `00_DatabaseSetup.sql` | Create database, filegroups (including `MEMORY_OPTIMIZED_DATA`) and schemas (`baseline`, `cs`, `im`, `htap`) |
| 2 | `01_Schema_Baseline.sql` | Baseline schema — disk-based tables with clustered B-tree indexes |
| 3 | `02_Schema_CS.sql` | Columnstore schema — disk-based tables with NONCLUSTERED COLUMNSTORE indexes |
| 4 | `03_Schema_IM.sql` | In-Memory schema — memory-optimized tables with hash and range indexes |
| 5 | `04_Schema_HTAP.sql` | HTAP schema — memory-optimized tables for OLTP (`htap.*`); reuses `cs.*` as OLAP layer |
| 6 | `05_LoadData.sql` | Load all data from StackOverflow2010 into all 4 schemas (~30–60 min) |
| 7 | `06_StoredProcs_OLTP.sql` | OLTP stored procedures for all schemas (natively compiled for `im` and `htap`) |
| 8 | `07_StoredProcs_OLAP.sql` | OLAP analytical queries (Q1–Q5) for all schemas |
| 9 | `07b_StoredProcs_OLAP_HTAP_DualStore.sql` | **Override** HTAP OLAP procedures to read from `cs.*` instead of `htap.*` — **must run after script 8** |
| 10 | `09_Fix_OLAP_MaxDop.sql` | Add `OPTION(MAXDOP 2)` hints to OLAP procedures to prevent CPU saturation at C=32 |

> **Important:** Script `08_ResultsSchema.sql` is optional — it creates a DB-side results logging table not used by the benchmark application (results are written to CSV files directly).

## After SQL Server Restart

`htap.*` and `im.*` tables use `DURABILITY = SCHEMA_ONLY` — all data is lost when SQL Server stops.  
Table schemas and indexes survive; only rows are lost.

Run `05b_LoadData_CS_HTAP_Only.sql` to restore data without reloading `baseline` and `cs` schemas:

```sql
-- Fast reload: only im.* and htap.* from cs.* source (~5-10 min)
-- cs.* is disk-based and survives restarts - used as the reload source
USE HTAPBenchmark;
-- (script truncates and refills im.* and htap.* from cs.* tables)
```

**Why cs.* survives**: `cs.*` tables are disk-based (no `MEMORY_OPTIMIZED`) so they persist across restarts. Only `im.*` and `htap.*` are affected by `SCHEMA_ONLY` durability.

| Table | Durability | Survives restart? |
|-------|-----------|-------------------|
| baseline.* | SCHEMA_AND_DATA (disk) | ✅ Yes |
| cs.* | SCHEMA_AND_DATA (disk) | ✅ Yes |
| im.* | SCHEMA_ONLY (memory) | ❌ No — rows lost |
| htap.* | SCHEMA_ONLY (memory) | ❌ No — rows lost |

## Schema Architecture

```
baseline.*  — disk-based B-tree (control group)
cs.*        — disk-based + NONCLUSTERED COLUMNSTORE (OLAP layer, also used by HTAP)
im.*        — memory-optimized, no columnstore (pure OLTP)
htap.*      — memory-optimized for OLTP  ┐  dual-store
cs.*        — columnstore for OLAP       ┘  HTAP pair
```
