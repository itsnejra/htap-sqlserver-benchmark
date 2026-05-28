# HTAPBenchmark
## Evaluacija performansi hibridne transakcijsko-analitičke obrade (HTAP) u Microsoft SQL Serveru

> **Projekat iz Optimizacija baza podataka** — Komparativna analiza četiri konfiguracijske strategije pohrane nad skupom podataka StackOverflow2010

---

## Sadržaj

1. [Pregled projekta](#1-pregled-projekta)
2. [Preduvjeti](#2-preduvjeti)
3. [Struktura projekta](#3-struktura-projekta)
4. [Postavljanje okruženja](#4-postavljanje-okruženja)
5. [Pokretanje benchmarka](#5-pokretanje-benchmarka)
6. [Statistička analiza i vizualizacije](#6-statistička-analiza-i-vizualizacije)
   - [6b. Rezultati benchmarka](#6b-rezultati-benchmarka-sažetak)
7. [Eksperimentalni dizajn](#7-eksperimentalni-dizajn)
   - [7b. Skala podataka](#7b-skala-podataka)
8. [Konfiguracijske strategije](#8-konfiguracijske-strategije)
9. [Radna opterećenja](#9-radna-opterećenja)
10. [Izlazni fajlovi](#10-izlazni-fajlovi)
11. [Rješavanje problema](#11-rješavanje-problema)
12. [Poznata ograničenja](#12-poznata-ograničenja)
13. [Licenca i citat](#13-licenca-i-citat)

---

## 1. Pregled projekta

Ovaj projekat eksperimentalno evaluira četiri konfiguracijske strategije pohrane podataka u Microsoft SQL Serveru u kontekstu hibridne transakcijsko-analitičke obrade (HTAP), kroz mješovito opterećenje OLTP i OLAP operacija nad stvarnim skupom podataka StackOverflow2010 (19,2 M postova, 299 K korisnika, 10,1 M glasova).

### Istraživačke hipoteze

| | Hipoteza |
|-|----------|
| **H1** | Disk-zasnovana konfiguracija s columnstore indeksom (CS) ostvaruje usporedivu OLAP latenciju s hibridnom konfiguracijom (HTAP) pri niskim razinama konkurentnosti, ali razlika postaje statistički značajna pri visokim razinama |
| **H2** | Degradacija OLTP propusnosti uzrokovana istovremenim analitičkim upitima veća je u CS konfiguraciji nego u HTAP konfiguraciji |
| **H3** | Pri transakcijski intenzivnom opterećenju HTAP konfiguracija ne ostvaruje statistički značajno veću OLTP propusnost od čisto transakcijske konfiguracije (IM) |

---

## 2. Preduvjeti

### Softver

| Komponenta | Verzija | Napomena |
|-----------|---------|----------|
| Microsoft SQL Server | 2022 (16.x) | Developer ili Enterprise — Express **ne podržava** In-Memory OLTP |
| SQL Server Management Studio | 20.x+ | Za izvršavanje SQL skripti |
| .NET SDK | 8.0+ | Provjeri: `dotnet --version` |
| Python | 3.11+ | Provjeri: `python --version` |
| StackOverflow2010 dataset | — | Vidi sekciju 4.1 |

### Hardver (preporučeno)

| Komponenta | Minimum | Preporučeno |
|-----------|---------|-------------|
| RAM | 16 GB | 32 GB+ (In-Memory tablice koriste ~8–12 GB) |
| CPU jezgre | 4 | 8+ (benchmark testira do C=32 korisnika) |
| Slobodan disk | 50 GB | SSD za disk-zasnovane tablice |

### Hardver korišten u istraživanju

Benchmark je pokrenut na slijedećoj konfiguraciji:

| Komponenta | Vrijednost |
|-----------|-----------|
| RAM | 32 GB DDR4 |
| SQL Server | Developer Edition 2022 (16.0.x) |
| OS | Windows 11 |
| Disk (cs/baseline) | HDD |
| Storage (im/htap) | RAM (memory-optimized) |

**Procijenjeno trajanje punog benchmarka (1.080 runova):**

| Faza | Trajanje |
|------|---------|
| Inicijalno punjenje podataka (05_LoadData.sql) | ~40–60 min |
| Benchmark: Baseline + CS (540 runova) | ~7–8 h |
| Benchmark: IM + HTAP (540 runova) | ~5–7 h |
| **Ukupno** | **~13–16 h** |

> Trajanje varira ovisno o hardveru. Benchmark podržava nastavak od mjesta prekida (resume) — siguran je restartati.

---

## 3. Struktura projekta

```
HTAPBenchmark/
├── SQL/
│   ├── 00_DatabaseSetup.sql               # Kreiranje baze i filegroupa
│   ├── 01_Schema_Baseline.sql             # Baseline schema (B-tree)
│   ├── 02_Schema_CS.sql                   # CS schema (columnstore)
│   ├── 03_Schema_IM.sql                   # IM schema (memory-optimized)
│   ├── 04_Schema_HTAP.sql                 # HTAP schema (memory-optimized, dual-store)
│   ├── 05_LoadData.sql                    # Učitavanje podataka (~30-60 min)
│   ├── 06_StoredProcs_OLTP.sql            # 6 OLTP procedura × 4 sheme
│   ├── 07_StoredProcs_OLAP.sql            # 5 OLAP procedura × 3 sheme
│   ├── 07b_StoredProcs_OLAP_HTAP_DualStore.sql  # HTAP dual-store OLAP
│   └── 09_Fix_OLAP_MaxDop.sql             # MAXDOP optimizacija
│
├── BenchmarkApp/
│   └── HTAPBenchmark.sln
│       ├── HTAPBenchmark.Core/
│       │   ├── Models/           # BenchmarkConfig, MeasurementResult
│       │   ├── Services/         # BenchmarkOrchestrator, WorkloadExecutor, ResultsWriter
│       │   └── Queries/          # OltpQueries, OlapQueries
│       └── HTAPBenchmark.Runner/
│           ├── Program.cs
│           └── appsettings.json  # Konfiguracija (connection string, broj runova itd.)
│
├── Analysis/
│   ├── requirements.txt
│   ├── 00_merge_results.py       # → Results/summary.csv (spaja sirova mjerenja)
│   ├── 01_descriptive_stats.py   # → descriptive_summary.csv / .xlsx
│   ├── 02_statistical_tests.py   # → statistical_tests.csv, hypothesis_results.txt
│   └── 03_visualizations.py      # → figures/*.png (6 grafova)
│
└── Results/                      # Auto-generirani (ne editovati ručno)
    ├── measurements.csv
    ├── summary.csv
    ├── descriptive_summary.csv
    ├── descriptive_summary.xlsx
    ├── statistical_tests.csv
    ├── hypothesis_results.txt
    └── figures/
        ├── 01_oltp_latency_violin.png
        ├── 02_olap_latency_violin.png
        ├── 03_oltp_throughput_latency.png
        ├── 04_olap_throughput_latency.png
        ├── 05_oltp_degradation.png
        └── 06_latency_heatmap.png
```

---

## 4. Postavljanje okruženja

### 4.1 StackOverflow2010 dataset

Preuzimanje gotovog SQL Server backup-a (preporučeno):
- **Brent Ozar**: https://www.brentozar.com/archive/2015/10/how-to-download-the-stack-overflow-database-via-bittorrent/
- Odaberite verziju **2010** (~10 GB)
- Restore u SSMS: `Restore Database → StackOverflow2010`

### 4.2 SQL skripte — pokrenuti redom u SSMS

Otvoriti svaki fajl u SSMS i pokrenuti redom (`F5`):

```
1. 00_DatabaseSetup.sql          -- baza, filegroups, sheme
2. 01_Schema_Baseline.sql        -- disk B-tree tablice
3. 02_Schema_CS.sql              -- disk + columnstore tablice
4. 03_Schema_IM.sql              -- memory-optimized tablice (IM)
5. 04_Schema_HTAP.sql            -- memory-optimized tablice (HTAP/OLTP sloj)
6. 05_LoadData.sql               -- punjenje podataka (~30–60 min)
7. 06_StoredProcs_OLTP.sql       -- OLTP stored procedure (sve 4 sheme)
8. 07_StoredProcs_OLAP.sql       -- OLAP upiti Q1–Q5 (sve sheme)
9. 07b_StoredProcs_OLAP_HTAP_DualStore.sql  -- OVERRIDE: HTAP OLAP čita iz cs.*
10. 09_Fix_OLAP_MaxDop.sql       -- dodaje MAXDOP 2 svim OLAP procedurama
```

> ⚠️ **Važno**: Skript `07b` mora se pokrenuti **nakon** `07` — on prepisuje HTAP OLAP procedure da čitaju iz `cs.*` (columnstore) umjesto iz `htap.*` (memory-optimized). Redoslijed 9 → 10 je obavezan.

> ℹ️ **Opcionalno**: `08_ResultsSchema.sql` kreira tablicu za DB-side logging rezultata — benchmark aplikacija ovo ne koristi (rezultati idu u CSV), ali može biti korisno za ručno testiranje.
```

**Provjera učitanih podataka:**
```sql
USE HTAPBenchmark;
SELECT s.name AS Shema, t.name AS Tablica, SUM(p.rows) AS Redova
FROM sys.tables t
JOIN sys.schemas s ON t.schema_id = s.schema_id
JOIN sys.partitions p ON t.object_id = p.object_id
WHERE s.name IN ('baseline','cs','im','htap') AND p.index_id IN (0,1)
GROUP BY s.name, t.name
ORDER BY s.name, t.name;
-- Svih 20 tablica moraju imati iste brojeve redova:
-- Posts ≈ 3.729.195 | Users ≈ 299.398 | Votes ≈ 10.143.364
-- Comments ≈ 3.875.183 | Badges ≈ 1.102.019
```

### 4.3 Nakon restarta SQL Servera

`im.*` i `htap.*` tablice koriste `DURABILITY = SCHEMA_ONLY` — svi podaci se gube kada SQL Server stane. Sheme i indexi ostaju, ali redovi nestaju.

Nakon svakog restarta SQL Servera pokrenuti:

```
SQL/05b_LoadData_CS_HTAP_Only.sql
```

Ovaj skript puni samo `im.*` i `htap.*` tablice iz `cs.*` (koja je disk-zasnovana i preživljava restart). Traje ~5–10 minuta (samo 2 sheme umjesto 4).

> `baseline.*` i `cs.*` su disk-zasnovane — NE trebaju ponovnog punjenja.

### 4.4 .NET aplikacija

```bash
cd HTAPBenchmark
dotnet restore BenchmarkApp/HTAPBenchmark.sln
dotnet build BenchmarkApp/HTAPBenchmark.sln -c Release
```

> **Napomena**: Ako je SQL Server na drugoj adresi, editujte `ConnectionString` u  
> `BenchmarkApp/HTAPBenchmark.Runner/appsettings.json`

### 4.5 Python okruženje

```bash
cd HTAPBenchmark/Analysis
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

---

## 5. Pokretanje benchmarka

### Puni benchmark (preporučeno za istraživanje)

```bash
cd HTAPBenchmark
dotnet run --project BenchmarkApp/HTAPBenchmark.Runner -c Release
```

| Parametar | Vrijednost |
|-----------|-----------|
| Konfiguracije | 4 (Baseline, CS, IM, HTAP) |
| OLTP/OLAP omjeri | 3 (80/20, 50/50, 20/80) |
| Razine konkurentnosti | 3 (C=4, C=16, C=32) |
| Runova po kombinaciji | 30 |
| **Ukupno runova** | **1.080** |
| Warmup po runu | 10 s |
| Mjerenje po runu | 60 s |
| **Procijenjeno trajanje** | **~21 sat** |

### Kratki test (provjera ispravnosti)

```bash
dotnet run --project BenchmarkApp/HTAPBenchmark.Runner -c Release -- --dry-run
# 36 runova, ~7 minuta
```

### Opcije komandne linije

| Opcija | Opis |
|--------|------|
| `--dry-run` | Warmup=2s, mjerenje=5s, 1 run/kombinacija |
| `--quick` | Warmup=5s, mjerenje=30s, 3 runa/kombinacija |
| `--only cs,htap` | Filtrira samo navedene konfiguracije |

**Ctrl+C** → graceful prekid (završava tekući run, potom staje)

### Konfiguracija benchmarka (appsettings.json)

```json
{
  "BenchmarkConfig": {
    "ConnectionString": "Server=.;Database=HTAPBenchmark;Trusted_Connection=True;TrustServerCertificate=True;Max Pool Size=200;",
    "WarmupSeconds": 10,
    "MeasurementSeconds": 60,
    "RunsPerCombination": 30,
    "ConcurrencyLevels": [ 4, 16, 32 ],
    "Configurations": [ "Baseline", "CS", "IM", "HTAP" ],
    "WorkloadRatios": [ "OLTP80_OLAP20", "OLTP50_OLAP50", "OLTP20_OLAP80" ],
    "ResultsCsvPath": "Results/measurements.csv",
    "SummaryCsvPath": "Results/summary.csv"
  }
}
```

Ako SQL Server nije na lokalnom hostu, promijeniti `Server=.` u `Server=ImeServera` ili `Server=IP,1433`.

### Resume (nastavak nakon prekida)

Benchmark automatski nastavlja od zadnjeg završenog runa. Čita `Results/summary.csv` pri startu i preskače kombinacije koje su već završene. Bezbijedno je prekinuti (Ctrl+C) i ponovo pokrenuti.

---

## 6. Statistička analiza i vizualizacije

Pokrenuti **redom** iz `Analysis/` direktorija nakon završenog benchmarka:

```bash
cd HTAPBenchmark/Analysis

python 00_merge_results.py
# Spaja results/measurements.csv u summary.csv (agregira po runu)
# Izlaz: ../Results/summary.csv

python 01_descriptive_stats.py
# Deskriptivna statistika: mean, std, P50, P95 po kombinaciji
# Izlaz: ../Results/descriptive_summary.csv i .xlsx

python 02_statistical_tests.py
# Kruskal-Wallis, Mann-Whitney U + Bonferroni, Cohen's d
# Izlaz: ../Results/statistical_tests.csv, hypothesis_results.txt

python 03_visualizations.py
# 6 grafova: violin, throughput-latency, degradacija, heatmap
# Izlaz: ../Results/figures/*.png
```

### Generirani grafovi

| Fajl | Sadržaj | Koristi za |
|------|---------|------------|
| `01_oltp_latency_violin.png` | Violin distribucije OLTP latencije | Usporedba OLTP performansi |
| `02_olap_latency_violin.png` | Violin distribucije OLAP latencije | **H1** vizualizacija |
| `03_oltp_throughput_latency.png` | OLTP Throughput-Latency krivulje | Skalabilnost OLTP-a |
| `04_olap_throughput_latency.png` | OLAP Throughput-Latency krivulje | **H2** vizualizacija |
| `05_oltp_degradation.png` | Degradacija OLTP pri mješovitom opterećenju | **H2** vizualizacija |
| `06_latency_heatmap.png` | Heatmap svih 36 kombinacija | Opći pregled |

---

## 6b. Rezultati benchmarka (sažetak)

### OLTP propusnost po konfiguraciji (C=32, 80/20 workload)

| Konfiguracija | Median ops/s | Std | vs Baseline |
|--------------|-------------|-----|-------------|
| **Baseline** | 2.432 | ±2.375 | — |
| **CS** | 3.618 | ±2.681 | +49% |
| **IM** | 28.764 | ±13.260 | +11.8× |
| **HTAP** | 21.920 | ±17.130 | +9.0× |

### OLAP propusnost po konfiguraciji (C=32)

| Konfiguracija | Median q/s | vs Baseline |
|--------------|-----------|-------------|
| **Baseline** | 0.85 | — |
| **CS** | 6.10 | +7.2× |
| **IM** | 0.77 | −9% |
| **HTAP** | 6.84 | +8.0× |

### Zaključci hipoteza

| Hipoteza | Ishod | Cohen's d |
|---------|-------|-----------|
| **H1**: CS ≈ HTAP pri niskom C, razlika pri visokom C | ⚠️ DJELIMIČNO POTVRĐENA | d=+1.61 (C=32) |
| **H2**: CS degradira više od HTAP pri mješovitom opterećenju | ✅ POTVRĐENA | d=2.32 |
| **H3**: HTAP ≈ IM pri OLTP-intenzivnom opterećenju | ❌ ODBAČENA | d=−4.4 do −11.9 |

> Detalji u `Results/hypothesis_results.txt` i `Paper/rad_nacrt.md`.

---

## 7. Eksperimentalni dizajn

### Faktorijalni plan 4 × 3 × 3

```
4 konfiguracije  ×  3 OLTP/OLAP omjera  ×  3 razine konkurentnosti
     = 36 kombinacija × 30 runova = 1.080 mjerenja
```

### Statističke metode

| Test | Primjena |
|------|----------|
| **Kruskal-Wallis H** | Globalne razlike između 4 konfiguracije (neparametarski ANOVA) |
| **Mann-Whitney U** | Parne usporedbe s Bonferroni korekcijom (α = 0.05) |
| **Cohen's d** | Veličina efekta: trivijalan <0.2 / mali 0.2–0.5 / srednji 0.5–0.8 / veliki >0.8 |

### Mjerene metrike

| Metrika | CSV kolona | Jedinica |
|---------|-----------|---------|
| OLTP propusnost | `OltpThroughput` | ops/s |
| OLAP propusnost | `OlapThroughput` | q/s |
| OLTP latencija P50 | `OltpLatencyP50` | ms |
| OLTP latencija P95 | `OltpLatencyP95` | ms |
| OLAP latencija P50 | `OlapLatencyP50` | ms |
| OLAP latencija P95 | `OlapLatencyP95` | ms |

---

## 7b. Skala podataka

### StackOverflow2010 — veličine tablica

| Tablica | Redova | Napomena |
|---------|--------|---------|
| `Posts` | ~3.729.195 | Pitanja i odgovori |
| `Users` | ~299.398 | Korisnički profili |
| `Votes` | ~10.143.364 | Glasovi (up/down/close...) |
| `Comments` | ~3.875.183 | Komentari |
| `Badges` | ~1.102.019 | Badge dodjele |
| **Ukupno** | **~19.149.159** | **po shemi** |

### Ukupno redova u bazi (sve 4 sheme)

```
4 sheme × ~19.149.159 redova ≈ 76.600.000 redova ukupno
```

### Disk i memorija

| Shema | Pohrana | Veličina (approx) |
|-------|---------|-------------------|
| baseline | Disk (HDD/SSD) | ~15 GB |
| cs | Disk (HDD/SSD) | ~17 GB (columnstore je kompresovan) |
| im | RAM | ~8 GB |
| htap | RAM | ~8 GB |

---

## 8. Konfiguracijske strategije

| Konfiguracija | Pohrana | Indeksiranje | OLAP engine | Očekivano |
|--------------|---------|-------------|-------------|-----------|
| **Baseline** | Disk (row-store) | B-tree (clustered + nonclustered) | Row-mode | Visok OLTP, nizak OLAP |
| **CS** | Disk (row-store) | B-tree + NONCLUSTERED COLUMNSTORE | Batch-mode | Umjeren OLTP, visok OLAP |
| **IM** | Memorija (Hekaton) | Hash + Range (memory-optimized) | Row-mode | Visok OLTP, nizak OLAP |
| **HTAP** | OLTP→Memorija / OLAP→Disk+CS | Dual-store (IM za pisanje, CS za čitanje) | Batch-mode (OLAP) | Visok OLTP + visok OLAP |

---

## 9. Radna opterećenja

### OLTP operacije (6 tipova, nasumična selekcija)

| Procedura | Tip | Udio |
|-----------|-----|------|
| `usp_GetPostById` | SELECT (točkačno) | ~25% |
| `usp_GetUserById` | SELECT (točkačno) | ~20% |
| `usp_GetRecentUserPosts` | SELECT (raspon) | ~15% |
| `usp_InsertVote` | INSERT | ~20% |
| `usp_InsertComment` | INSERT | ~10% |
| `usp_UpdatePostScore` | UPDATE | ~10% |

### OLAP upiti (5 tipova, nasumična selekcija)

| Procedura | Opis | Vrsta operacije |
|-----------|------|-----------------|
| `usp_OLAP_Q1_MonthlyActivity` | Godišnja/m aktivnost | GROUP BY + agregacija |
| `usp_OLAP_Q2_UserEngagement` | Angažiranost korisnika | JOIN + GROUP BY |
| `usp_OLAP_Q3_TagAnalysis` | Analiza popularnosti tagova | JOIN + GROUP BY |
| `usp_OLAP_Q4_TimeToAnswer` | Prosječno vrijeme odgovora | Self-JOIN + agregacija |
| `usp_OLAP_Q5_TopContributors` | Top korisnici po utjecaju | CTE + GROUP BY |

---

## 10. Izlazni fajlovi

### summary.csv (1.080 redova za puni benchmark)

```
Configuration, OltpOlapRatio, ConcurrencyLevel, RunNumber,
OltpThroughput, OlapThroughput,
OltpLatencyP50, OltpLatencyP95, OltpLatencyP99,
OlapLatencyP50, OlapLatencyP95, OlapLatencyP99,
OltpSuccessRate, OlapSuccessRate
```

### measurements.csv (sirovа mjerenja, ~milijuni redova)

```
Configuration, OltpOlapRatio, ConcurrencyLevel, RunNumber,
OperationType, OperationName, StartTimestamp, LatencyMs,
Success, ErrorMessage
```

---

## 11. Rješavanje problema

### OLAP upiti blokirani >60s (CXSYNC_PORT wait)
**Uzrok**: Prekomjerna paralelizacija (batch-mode columnstore) pri visokoj konkurentnosti.  
**Rješenje**: Skript `09_Fix_OLAP_MaxDop.sql` dodaje `OPTION(MAXDOP 2)` svim OLAP procedurama.  
**Bitno**: Pokrenuti ovaj skript **obavezno** prije pokretanja benchmarka pri C=32.

---

### Timeout pri učitavanju konteksta (30s)
**Uzrok**: `SELECT TOP 20000 ORDER BY NEWID()` na 3.7M redova — predugo za default 30s timeout.  
**Rješenje**: Ispravljeno u kodu — `commandTimeout: 300` u `WorkloadExecutor.cs`.

---

### ORDER BY NEWID() stall na memory-optimized tablicama
**Uzrok**: Paralelni plan izvršavanja na Hekaton tablicama uzrokuje `CXSYNC_PORT` wait.  
**Rješenje**: Dodan `OPTION(MAXDOP 1)` u context-loading upite za `im` i `htap` sheme.

---

### OOM crash / SQL Server gasi se pri C=32 (IM ili HTAP konfiguracija)
**Uzrok**: MVCC version chain akumulacija — svaki DELETE na memory-optimized tablici kreira "ghost" verzije koje GC mora pročistiti. Brisanje svih 3.7M redova između kombinacija generira ~7.4M GC stavki po tranziciji, što pri C=32 preopterećuje in-memory GC.  
**Rješenje implementirano u kodu**:
- `TruncateAndReloadPostsAsync` briše i puni samo 20.000 aktivnih postova (ne sve 3.7M)
- Poziva se i između kombinacija I između svakog od 30 runova (da GC ne akumulira)
- Ukupno: 185× manje GC posla po kombinaciji

```
Simptom: SQL Server se gasi ili app crashi s OutOfMemoryException
         nakon 2–3 kombinacije pri C=32
Rješenje: Koristiti trenutnu verziju koda (problem riješen u WorkloadExecutor.cs)
```

---

### TRUNCATE TABLE nije podržan na memory-optimized tablicama (Error 10794)
**Uzrok**: SQL Server In-Memory OLTP ne podržava `TRUNCATE TABLE`.  
**Greška**: `Msg 10794, Level 16: The statement 'TRUNCATE TABLE' is not supported with memory optimized tables.`  
**Rješenje**: Koristiti `DELETE FROM tablica` ili selektivni delete po ID-u.

---

### Python ModuleNotFoundError
```bash
cd Analysis && pip install -r requirements.txt
```

---

### SQL Server: memory-optimized tablice se ne mogu kreirati
**Uzrok**: SQL Server Express ne podržava In-Memory OLTP.  
**Greška**: `CREATE TABLE ... WITH (MEMORY_OPTIMIZED = ON)` ne uspijeva.  
**Rješenje**: Koristiti Developer, Standard ili Enterprise Edition.

---

### Benchmark se ne nastavlja (resume) nakon prekida
**Uzrok**: `ResultsWriter` otvara fajlove za pisanje (truncate mode) prije nego što se provjeri koje kombinacije su već završene.  
**Rješenje**: Implementirano u `BenchmarkOrchestrator.cs` — `_resumeMap` se čita iz `summary.csv` u konstruktoru, PRIJE otvaranja `ResultsWriter`.  
Pokretati benchmark normalno — automatski nastavlja od gdje je stao.

---

---

## 12. Poznata ograničenja

### SQL Server 2022 RTM — nema inline columnstore na memory-optimized tablicama
SQL Server 2022 RTM **ne podržava** `NONCLUSTERED COLUMNSTORE INDEX` direktno na memory-optimized tablicama. Poruka greške:

```
Msg 12332: Columnstore indexes are not supported for memory optimized tables.
```

Zbog toga HTAP konfiguracija koristi **dual-store pristup**: `htap.*` za OLTP (in-memory), `cs.*` za OLAP (disk+columnstore). Ovo je namjeran dizajn koji odgovara komercijalnim HTAP implementacijama (TiDB/TiFlash, Oracle Dual-Format).

### SCHEMA_ONLY durability — gubitak podataka pri restartu
`im.*` i `htap.*` tablice koriste `DURABILITY = SCHEMA_ONLY` radi maksimalnih performansi. Ovo znači da **svi podaci nestaju** kada SQL Server stane. Pogledati sekciju 4.3 za upute o ponovnom punjenju.

### Benchmark trajanje
Puni benchmark (1.080 runova × 70s po runu) traje ~13–16 sati. Ne može se smanjiti bez kompromisa na statističku valjanost (min. 30 runova/kombinacija za neparametarsku analizu).

### Ograničenost na jedan server
Benchmark ne testira distribuirane konfiguracije. Sva 4 konfiguracijska pristupa rade na jednoj instanci SQL Servera, što eliminira mrežni utjecaj ali ne odražava produkcijska distribuirana okruženja.

### Workload je sintetički
OLTP i OLAP operacije su reprezentativne za HTAP scenarije, ali nisu direktno prenosivi na specifičnu domensku aplikaciju. Rezultati su indikativni za klasu opterećenja, ne za konkretan use-case.

---

## 13. Licenca i citat

Projekt je razvijen za akademske istraživačke svrhe.

Ako koristite ovaj benchmark u vlastitom istraživanju, citirajte:

```
Evaluacija HTAP performansi u Microsoft SQL Serveru 2022:
Komparativna analiza Baseline, Columnstore, In-Memory i Dual-Store konfiguracija
Fakultet — Optimizacija baza podataka, 2025.
```

---

*Projekt razvijen za potrebe magistarskog istraživanja — evaluacija HTAP paradigme u SQL Serveru*
