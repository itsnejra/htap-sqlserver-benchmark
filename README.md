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
7. [Eksperimentalni dizajn](#7-eksperimentalni-dizajn)
8. [Konfiguracijske strategije](#8-konfiguracijske-strategije)
9. [Radna opterećenja](#9-radna-opterećenja)
10. [Izlazni fajlovi](#10-izlazni-fajlovi)
11. [Rješavanje problema](#11-rješavanje-problema)

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
| RAM | 16 GB | 32 GB+ (In-Memory tablice koriste ~8 GB) |
| CPU jezgre | 4 | 8+ |
| Slobodan disk | 50 GB | SSD za disk-zasnovane tablice |

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

### 4.3 .NET aplikacija

```bash
cd HTAPBenchmark
dotnet restore BenchmarkApp/HTAPBenchmark.sln
dotnet build BenchmarkApp/HTAPBenchmark.sln -c Release
```

> **Napomena**: Ako je SQL Server na drugoj adresi, editujte `ConnectionString` u  
> `BenchmarkApp/HTAPBenchmark.Runner/appsettings.json`

### 4.4 Python okruženje

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

---

## 6. Statistička analiza i vizualizacije

Pokrenuti **redom** iz `Analysis/` direktorija nakon završenog benchmarka:

```bash
cd HTAPBenchmark/Analysis

python 01_descriptive_stats.py
# Izlaz: ../Results/descriptive_summary.csv i .xlsx

python 02_statistical_tests.py
# Izlaz: ../Results/statistical_tests.csv i hypothesis_results.txt

python 03_visualizations.py
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

### Timeout pri učitavanju konteksta
**Uzrok**: `SELECT TOP 20000 ORDER BY NEWID()` na 3.7M redova — predugo za default 30s timeout.  
**Rješenje**: Ispravljeno u kodu — `commandTimeout: 300`.

### ORDER BY NEWID() deadlock na memory-optimized tablicama
**Uzrok**: Paralelni plan izvršavanja na Hekaton tablicama uzrokuje CXSYNC_PORT.  
**Rješenje**: Ispravljeno — dodan `OPTION(MAXDOP 1)` u context-loading upitima.

### Python ModuleNotFoundError
```bash
cd Analysis && pip install -r requirements.txt
```

### SQL Server: memory-optimized tablice se ne mogu kreirati
**Uzrok**: SQL Server Express ne podržava In-Memory OLTP.  
**Rješenje**: Koristiti Developer, Standard ili Enterprise Edition.

---

*Projekt razvijen za potrebe magistarskog istraživanja — evaluacija HTAP paradigme u SQL Serveru*
