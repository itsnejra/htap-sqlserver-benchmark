# HTAPBenchmark
## Evaluacija performansi hibridne transakcijsko-analiticke obrade (HTAP) u Microsoft SQL Serveru 2022

Projekat iz Optimizacija baza podataka -- Komparativna analiza cetiri konfiguracijske strategije pohrane nad skupom podataka StackOverflow2010

UPOZORENJE: Puni benchmark (1.080 runova) traje priblizno 21 sat. Ako zelite samo provjeriti ispravnost postavljanja, pokrenite kratki test opisan odmah ispod.

---

## Brzi test -- provjera ispravnosti postavljanja

Prije pokretanja punog benchmarka preporucuje se pokrenuti kratki test koji provjerava ispravnost svih komponenti (SQL Server veza, stored procedure, .NET aplikacija, CSV izlaz):

```bash
cd HTAPBenchmark
dotnet run --project BenchmarkApp/HTAPBenchmark.Runner -c Release -- --dry-run
```

Kratki test pokrece 36 runova (1 run po kombinaciji, warmup=2s, mjerenje=5s) i zavrsava za priblizno 7 minuta. Ako se zavrsava bez gresaka i generise Results/summary.csv s 36 redova, okruzenje je ispravno postavljeno.

---

## Sadrzaj

1. [Pregled projekta](#1-pregled-projekta)
2. [Preduvjeti i reproducibilnost](#2-preduvjeti-i-reproducibilnost)
3. [Struktura projekta](#3-struktura-projekta)
4. [Postavljanje okruzenja](#4-postavljanje-okruzenja)
5. [Pokretanje benchmarka](#5-pokretanje-benchmarka)
6. [Statisticka analiza i vizualizacije](#6-statisticka-analiza-i-vizualizacije)
7. [Rezultati benchmarka](#7-rezultati-benchmarka)
8. [Eksperimentalni dizajn](#8-eksperimentalni-dizajn)
9. [Konfiguracijske strategije](#9-konfiguracijske-strategije)
10. [Radna opterecenja](#10-radna-opterecenja)
11. [Izlazni fajlovi](#11-izlazni-fajlovi)
12. [Rjesavanje problema](#12-rjesavanje-problema)
13. [Poznata ogranicenja](#13-poznata-ogranicenja)

---

## 1. Pregled projekta

Ovaj projekat eksperimentalno evaluira cetiri konfiguracijske strategije pohrane podataka u Microsoft SQL Serveru 2022 kroz mjjesovito opterecenje OLTP i OLAP operacija nad skupom podataka StackOverflow2010 (priblizno 19,2 milijuna zapisa). Cilj je kvantificirati performansne razlike i statisticki testirati tri hipoteze o HTAP obradi.

Puni benchmark obuhvata 1.080 mjerenja (4 konfiguracije x 3 omjera radnog opterecenja x 3 razine konkurentnosti x 30 runova) i traje priblizno 21 sat na referentnom hardveru (Intel Core i9-14900HX, 32 GB DDR5, 1 TB NVMe SSD). Trajanje moze biti duze na sporijim masinama.

### Istrazivacke hipoteze

| | Hipoteza |
|-|----------|
| H1 | Disk-zasnovana konfiguracija s columnstore indeksom (CS) ostvaruje usporedivu OLAP latenciju s hibridnom konfiguracijom (HTAP) pri niskim razinama konkurentnosti, ali razlika postaje statisticki znacajna pri visokim razinama |
| H2 | Degradacija OLTP propusnosti uzrokovana istovremenim analitickim upitima veca je u CS konfiguraciji nego u HTAP konfiguraciji |
| H3 | Pri transakcijski intenzivnom opterecenju HTAP konfiguracija ne ostvaruje statisticki znacajno vecu OLTP propusnost od cisto transakcijske konfiguracije (IM) |

---

## 2. Preduvjeti i reproducibilnost

Projekat je dizajniran da bude reproducibilan na drugoj masini koja zadovoljava navedene zahtjeve. Svi preduvjeti moraju biti ispunjeni prije prvog pokretanja.

### Operativni sistem

Projekat zahtijeva **Windows** (10 ili 11, 64-bit). Microsoft SQL Server In-Memory OLTP (Hekaton) i memory-optimized tablice dostupni su iskljucivo na Windows platformi u SQL Server 2022.

### Obavezni softver

| Komponenta | Preporucena verzija | Provjera instalacije |
|-----------|---------------------|----------------------|
| Microsoft SQL Server 2022 | 16.x, Developer ili Enterprise Edition | `SELECT @@VERSION` u SSMS |
| SQL Server Management Studio (SSMS) | 20.x ili noviji | Otvoriti SSMS i provjeriti Help > About |
| .NET SDK | 8.0 ili noviji | `dotnet --version` |
| Python | 3.11 ili noviji | `python --version` |

Napomena: SQL Server Express Edition nije podrzana jer ne ukljucuje In-Memory OLTP. Koristiti Developer Edition (besplatna za neproizvodnu upotrebu).

### Hardver (minimalni i referentni)

| Komponenta | Minimum | Referentni (koristeni) |
|-----------|---------|------------------------|
| RAM | 16 GB | 32 GB DDR5 |
| CPU jezgre | 4 | 24 (Intel Core i9-14900HX) |
| Slobodan disk | 60 GB SSD | 1 TB NVMe SSD |
| OS | Windows 10 64-bit | Windows 11 Home |

Napomena: im.* i htap.* konfiguracije koriste memory-optimized tablice koje traze priblizno 8 GB RAM po shemi (ukupno oko 16 GB samo za SQL Server in-memory podatke). Na masinama s manje od 16 GB RAM ove konfiguracije mogu uzrokovati OOM greske.

### Python paketi

Sve zavisnosti su navedene u `Analysis/requirements.txt`. Instalirajte ih unutar virtualnog okruzenja:

```bash
cd Analysis
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Popis paketa s minimalnim verzijama:

| Paket | Minimalna verzija | Svrha |
|-------|-------------------|-------|
| pandas | 2.2.0 | Obrada CSV rezultata |
| numpy | 1.26.0 | Numericke operacije |
| scipy | 1.13.0 | Statisticki testovi (Kruskal-Wallis, Mann-Whitney U) |
| matplotlib | 3.9.0 | Generisanje grafova |
| seaborn | 0.13.2 | Violin grafovi i heatmap |
| openpyxl | 3.1.2 | Izvoz u .xlsx format |
| statsmodels | 0.14.0 | OLS regresija i ANOVA |
| pyodbc | 5.0.0 | Direktna SQL Server veza (06_delete_update_benchmark.py) |

### .NET zavisnosti (automatski preuzete)

```bash
dotnet restore BenchmarkApp/HTAPBenchmark.sln
```

Kljucne NuGet zavisnosti (definirane u .csproj fajlovima):

| Paket | Svrha |
|-------|-------|
| Microsoft.Data.SqlClient | SQL Server konekcija i query izvrsavanje |
| Dapper | Lagani ORM za mapiranje rezultata |
| Microsoft.Extensions.Configuration | Ucitavanje appsettings.json |

### Konfiguracija SQL Servera

Nakon instalacije SQL Servera preporucuje se podesiti maksimalnu kolicinu memorije kako bi ostalo dovoljno za OS i in-memory tablice:

```sql
-- Preporuceno: ostaviti priblizno 4 GB OS-u, ostatak SQL Serveru
-- Primjer za 32 GB masinu:
EXEC sp_configure 'max server memory (MB)', 28000;
RECONFIGURE;

-- Provjera trenutne konfiguracije
EXEC sp_configure 'max server memory (MB)';
```

SQL Server mora biti konfigurisan s Windows Authentication (Trusted_Connection=True). Ako koristite SQL Authentication, izmijeniti ConnectionString u `BenchmarkApp/HTAPBenchmark.Runner/appsettings.json`.

---

## 3. Struktura projekta

```
HTAPBenchmark/
|-- SQL/
|   |-- 00_DatabaseSetup.sql               # Kreiranje baze i filegroupa
|   |-- 01_Schema_Baseline.sql             # Baseline schema (B-tree)
|   |-- 02_Schema_CS.sql                   # CS schema (columnstore)
|   |-- 03_Schema_IM.sql                   # IM schema (memory-optimized)
|   |-- 04_Schema_HTAP.sql                 # HTAP schema (memory-optimized, dual-store)
|   |-- 05_LoadData.sql                    # Ucitavanje podataka (~30-60 min)
|   |-- 05b_LoadData_CS_HTAP_Only.sql      # Obnova IM/HTAP tablica nakon restarta
|   |-- 06_StoredProcs_OLTP.sql            # OLTP procedure: SELECT/INSERT/UPDATE x 4 sheme
|   |-- 07_StoredProcs_OLAP.sql            # OLAP upiti Q1-Q5 x sve sheme
|   |-- 07b_StoredProcs_OLAP_HTAP_DualStore.sql  # Override: HTAP OLAP cita iz cs.*
|   |-- 08_ResultsSchema.sql               # (Opcionalno) DB-side log tablica
|   |-- 09_Fix_OLAP_MaxDop.sql             # MAXDOP 2 za OLAP procedure (anti-CXSYNC)
|   |-- 10_StoredProcs_DELETE.sql          # DELETE procedure: Simple/Complex x 4 sheme
|   `-- 11_StoredProcs_ComplexUPDATE.sql   # Complex UPDATE: usp_UpdateUserReputation x 4 sheme
|
|-- BenchmarkApp/
|   `-- HTAPBenchmark.sln
|       |-- HTAPBenchmark.Core/
|       |   |-- Models/           # BenchmarkConfig, MeasurementResult
|       |   |-- Services/         # BenchmarkOrchestrator, WorkloadExecutor, ResultsWriter
|       |   `-- Queries/          # OltpQueries, OlapQueries
|       `-- HTAPBenchmark.Runner/
|           |-- Program.cs
|           `-- appsettings.json  # Konfiguracija (connection string, broj runova itd.)
|
|-- Analysis/
|   |-- requirements.txt                   # pip install -r requirements.txt
|   |-- 00_merge_results.py                # -> Results/summary.csv
|   |-- 01_descriptive_stats.py            # -> descriptive_summary.csv / .xlsx
|   |-- 02_statistical_tests.py            # -> statistical_tests.csv, hypothesis_results.txt
|   |-- 03_visualizations.py               # -> figures/*.png (6 grafova)
|   |-- 04_per_operation_stats.py          # -> per_operation_stats.csv / .xlsx
|   |-- 05_regression_anova.py             # -> regression_*.csv, anova_results.csv
|   `-- 06_delete_update_benchmark.py      # DELETE + Complex UPDATE mini benchmark
|
|-- Paper/
|   |-- rad.tex                            # LaTeX master fajl rada
|   |-- 00_sazetak.tex ... 06_zakljucak.tex  # Poglavlja rada
|   |-- app_a_oltp.tex, app_b_olap.tex    # Dodaci
|   `-- refs.bib                           # BibTeX bibliografija
|
`-- Results/                               # Generirani izlazi (ne editovati rucno)
    |-- summary.csv
    |-- descriptive_summary.csv / .xlsx
    |-- statistical_tests.csv
    |-- hypothesis_results.txt
    |-- per_operation_stats.csv / .xlsx
    |-- delete_update_benchmark.csv
    |-- anova_results.csv
    |-- regression_oltp_throughput.csv
    |-- regression_olap_latency.csv
    |-- regression_report.txt
    `-- figures/
        |-- 01_oltp_latency_violin.png
        |-- 02_olap_latency_violin.png
        |-- 03_oltp_throughput_latency.png
        |-- 04_olap_throughput_latency.png
        |-- 05_oltp_degradation.png
        `-- 06_latency_heatmap.png
```

---

## 4. Postavljanje okruzenja

### 4.1 StackOverflow2010 dataset

Preuzimanje gotovog SQL Server backup-a:

- Brent Ozar: https://www.brentozar.com/archive/2015/10/how-to-download-the-stack-overflow-database-via-bittorrent/
- Odabrati verziju **2010** (priblizno 10 GB download, priblizno 25 GB nakon restore-a)
- Restore u SSMS: desni klik na Databases > Restore Database > From Device > odabrati .bak fajl

### 4.2 SQL skripte -- pokrenuti redom u SSMS

Otvoriti svaki fajl u SSMS i pokrenuti redom (F5 ili Execute):

```
 1. 00_DatabaseSetup.sql                      -- baza, filegroups, sheme
 2. 01_Schema_Baseline.sql                    -- disk B-tree tablice
 3. 02_Schema_CS.sql                          -- disk + columnstore tablice
 4. 03_Schema_IM.sql                          -- memory-optimized tablice (IM)
 5. 04_Schema_HTAP.sql                        -- memory-optimized tablice (HTAP/OLTP sloj)
 6. 05_LoadData.sql                           -- punjenje podataka (~30-60 min)
 7. 06_StoredProcs_OLTP.sql                   -- OLTP procedure: SELECT/INSERT/UPDATE (sve 4 sheme)
 8. 07_StoredProcs_OLAP.sql                   -- OLAP upiti Q1-Q5 (sve sheme)
 9. 07b_StoredProcs_OLAP_HTAP_DualStore.sql   -- OVERRIDE: HTAP OLAP cita iz cs.*
10. 09_Fix_OLAP_MaxDop.sql                    -- dodaje MAXDOP 2 svim OLAP procedurama
11. 10_StoredProcs_DELETE.sql                 -- DELETE procedure: Simple/Complex (sve 4 sheme)
12. 11_StoredProcs_ComplexUPDATE.sql          -- Complex UPDATE: usp_UpdateUserReputation (sve 4 sheme)
```

Vazno: Skript 07b mora se pokrenuti NAKON 07 -- on prepisuje HTAP OLAP procedure da citaju iz cs.* (columnstore) umjesto iz htap.* (memory-optimized). Redoslijed je obavezan.

Opcionalno: 08_ResultsSchema.sql kreira tablicu za DB-side logging rezultata -- benchmark aplikacija ovo ne koristi (rezultati idu u CSV), ali moze biti korisno za rucno testiranje.

**Provjera ucitanih podataka:**

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
-- Posts priblizno 3.729.195 | Users priblizno 299.398 | Votes priblizno 10.143.364
-- Comments priblizno 3.875.183 | Badges priblizno 1.102.019
```

### 4.3 Nakon restarta SQL Servera

im.* i htap.* tablice koriste DURABILITY = SCHEMA_ONLY -- svi podaci se gube kada SQL Server stane. Sheme i indeksi ostaju, ali redovi nestaju.

Nakon svakog restarta SQL Servera pokrenuti:

```
SQL/05b_LoadData_CS_HTAP_Only.sql
```

Ovaj skript puni samo im.* i htap.* tablice iz cs.* (koja je disk-zasnovana i prezivljava restart). Traje priblizno 5-10 minuta (samo 2 sheme umjesto 4).

baseline.* i cs.* su disk-zasnovane -- ne trebaju ponovnog punjenja.

### 4.4 .NET aplikacija

```bash
cd HTAPBenchmark
dotnet restore BenchmarkApp/HTAPBenchmark.sln
dotnet build BenchmarkApp/HTAPBenchmark.sln -c Release
```

Ako je SQL Server na drugoj adresi (ne localhost), izmijeniti ConnectionString u:
`BenchmarkApp/HTAPBenchmark.Runner/appsettings.json`

```json
{
  "BenchmarkConfig": {
    "ConnectionString": "Server=ImeServera;Database=HTAPBenchmark;Trusted_Connection=True;TrustServerCertificate=True;Max Pool Size=200;",
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

Za SQL Authentication umjesto Windows Authentication:

```json
"ConnectionString": "Server=.;Database=HTAPBenchmark;User Id=korisnik;Password=lozinka;TrustServerCertificate=True;Max Pool Size=200;"
```

### 4.5 Python okruzenje

```bash
cd HTAPBenchmark/Analysis
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Provjera instalacije:

```bash
python -c "import pandas, numpy, scipy, matplotlib, seaborn, openpyxl, statsmodels, pyodbc; print('Sve zavisnosti instalirane')"
```

---

## 5. Pokretanje benchmarka

### Kratki test (provjera ispravnosti -- pokrenuti prvi)

```bash
cd HTAPBenchmark
dotnet run --project BenchmarkApp/HTAPBenchmark.Runner -c Release -- --dry-run
```

Parametri kratkog testa: warmup=2s, mjerenje=5s, 1 run po kombinaciji = 36 runova ukupno.
Ocekivano trajanje: priblizno 7 minuta.
Ocekivani izlaz: Results/summary.csv s 36 redova, bez gresaka u konzoli.

### Puni benchmark (za istrazivacke rezultate)

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
| Ukupno runova | 1.080 |
| Warmup po runu | 10 s |
| Mjerenje po runu | 60 s |
| Procijenjeno trajanje | priblizno 21 sat |

### Opcije komandne linije

| Opcija | Opis |
|--------|------|
| `--dry-run` | Warmup=2s, mjerenje=5s, 1 run/kombinacija -- 36 runova, ~7 min |
| `--quick` | Warmup=5s, mjerenje=30s, 3 runa/kombinacija |
| `--only cs,htap` | Filtrira samo navedene konfiguracije |

Ctrl+C pokrece graceful prekid -- zavrsava tekuci run i potom staje.

### Resume (nastavak nakon prekida)

Benchmark automatski nastavlja od zadnjeg zavrsenog runa. Cita Results/summary.csv pri startu i preskace kombinacije koje su vec zavrsene. Bezbjedno je prekinuti (Ctrl+C) i ponovo pokrenuti.

---

## 6. Statisticka analiza i vizualizacije

Pokrenuti redom iz Analysis/ direktorija nakon zavrsenog benchmarka:

```bash
cd HTAPBenchmark/Analysis
venv\Scripts\activate

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

python 04_per_operation_stats.py
# Per-operacijska statistika iz sirovih mjerenja (measurements.csv)
# avg/min/max/total/P50/P95/P99 za svaku od 9 kategorija x 4 konfiguracije
# Izlaz: ../Results/per_operation_stats.csv / .xlsx

python 05_regression_anova.py
# OLS regresija + ANOVA analiza
# Izlaz: ../Results/regression_*.csv, anova_results.csv, regression_report.txt

python 06_delete_update_benchmark.py
# Mini benchmark za DELETE (Simple/Complex) i Complex UPDATE operacije
# Zahtijeva: aktivnu SQL Server instancu s procedurama iz SQL/10 i SQL/11
# Izlaz: ../Results/delete_update_benchmark.csv
```

### Generirani grafovi

| Fajl | Sadrzaj |
|------|---------|
| 01_oltp_latency_violin.png | Violin distribucije OLTP latencije po konfiguraciji |
| 02_olap_latency_violin.png | Violin distribucije OLAP latencije (H1 vizualizacija) |
| 03_oltp_throughput_latency.png | OLTP Throughput-Latency krivulje |
| 04_olap_throughput_latency.png | OLAP Throughput-Latency krivulje (H2 vizualizacija) |
| 05_oltp_degradation.png | Degradacija OLTP pri mjjesovitom opterecenju (H2 vizualizacija) |
| 06_latency_heatmap.png | Heatmap svih 36 kombinacija -- opci pregled |

---

## 7. Rezultati benchmarka

### OLTP propusnost po konfiguraciji (C=32, 80/20 workload)

| Konfiguracija | Median ops/s | Std | vs Baseline |
|--------------|-------------|-----|-------------|
| Baseline | 2.432 | +/-2.375 | -- |
| CS | 3.618 | +/-2.681 | +49% |
| IM | 28.764 | +/-13.260 | +11.8x |
| HTAP | 21.920 | +/-17.130 | +9.0x |

### OLAP propusnost po konfiguraciji (C=32)

| Konfiguracija | Median q/s | vs Baseline |
|--------------|-----------|-------------|
| Baseline | 0.85 | -- |
| CS | 6.10 | +7.2x |
| IM | 0.77 | -9% |
| HTAP | 6.84 | +8.0x |

### Zakljucci hipoteza

| Hipoteza | Ishod | Cohen's d |
|---------|-------|-----------|
| H1: CS priblizno jednako HTAP pri niskom C, razlika pri visokom C | DJELIMICNO POTVRDJENA | d=+1.61 (C=32) |
| H2: CS degradira vise od HTAP pri mjjesovitom opterecenju | POTVRDJENA | d=2.32 |
| H3: HTAP priblizno jednako IM pri OLTP-intenzivnom opterecenju | ODBACENA | d=-4.4 do -11.9 |

Detalji u Results/hypothesis_results.txt.

---

## 8. Eksperimentalni dizajn

### Faktorijalni plan 4 x 3 x 3

```
4 konfiguracije  x  3 OLTP/OLAP omjera  x  3 razine konkurentnosti
     = 36 kombinacija x 30 runova = 1.080 mjerenja
```

### Statisticke metode

| Test | Primjena |
|------|----------|
| Kruskal-Wallis H | Globalne razlike izmedju 4 konfiguracije (neparametarski ANOVA) |
| Mann-Whitney U | Parne usporedbe s Bonferroni korekcijom (alfa = 0.05) |
| Cohen's d | Velicina efekta: trivijalan <0.2 / mali 0.2-0.5 / srednji 0.5-0.8 / veliki >0.8 |

### Mjerene metrike

| Metrika | CSV kolona | Jedinica |
|---------|-----------|---------|
| OLTP propusnost | OltpThroughput | ops/s |
| OLAP propusnost | OlapThroughput | q/s |
| OLTP latencija P50 | OltpLatencyP50 | ms |
| OLTP latencija P95 | OltpLatencyP95 | ms |
| OLAP latencija P50 | OlapLatencyP50 | ms |
| OLAP latencija P95 | OlapLatencyP95 | ms |

### Skup podataka StackOverflow2010

| Tablica | Redova | Napomena |
|---------|--------|---------|
| Posts | priblizno 3.729.195 | Pitanja i odgovori |
| Users | priblizno 299.398 | Korisnicki profili |
| Votes | priblizno 10.143.364 | Glasovi (up/down/close...) |
| Comments | priblizno 3.875.183 | Komentari |
| Badges | priblizno 1.102.019 | Badge dodjele |
| Ukupno po shemi | priblizno 19.149.159 | |
| Ukupno (4 sheme) | priblizno 76.600.000 | |

### Disk i memorija

| Shema | Pohrana | Velicina (priblizno) |
|-------|---------|---------------------|
| baseline | Disk (HDD/SSD) | ~15 GB |
| cs | Disk (HDD/SSD) | ~17 GB (columnstore kompresija) |
| im | RAM | ~8 GB |
| htap | RAM | ~8 GB |

---

## 9. Konfiguracijske strategije

| Konfiguracija | Pohrana | Indeksiranje | OLAP engine | Ocekivano ponasanje |
|--------------|---------|-------------|-------------|---------------------|
| Baseline | Disk (row-store) | B-tree (clustered + nonclustered) | Row-mode | Visok OLTP, nizak OLAP |
| CS | Disk (row-store) | B-tree + NONCLUSTERED COLUMNSTORE | Batch-mode | Umjeren OLTP, visok OLAP |
| IM | Memorija (Hekaton) | Hash + Range (memory-optimized) | Row-mode | Visok OLTP, nizak OLAP |
| HTAP | OLTP->Memorija / OLAP->Disk+CS | Dual-store (IM za pisanje, CS za citanje) | Batch-mode (OLAP) | Visok OLTP + visok OLAP |

---

## 10. Radna opterecenja

### OLTP operacije (6 tipova, nasumicna selekcija)

| Procedura | Tip | Udio |
|-----------|-----|------|
| usp_InsertVote | INSERT | 35% |
| usp_UpdatePostScore | UPDATE | 25% |
| usp_InsertComment | INSERT | 15% |
| usp_GetRecentUserPosts | SELECT (raspon) | 10% |
| usp_GetPostById | SELECT (tockacno) | 10% |
| usp_GetUserById | SELECT (tockacno) | 5% |

Write-heavy workload: 75% pisanja / 25% citanja.

### OLAP upiti (5 tipova, nasumicna selekcija)

| Procedura | Opis | Vrsta operacije |
|-----------|------|-----------------|
| usp_OLAP_Q1_MonthlyActivity | Godisnja/mjjesecna aktivnost | GROUP BY + agregacija |
| usp_OLAP_Q2_UserEngagement | Angaziranost korisnika | JOIN + GROUP BY |
| usp_OLAP_Q3_TagAnalysis | Analiza popularnosti tagova | JOIN + GROUP BY |
| usp_OLAP_Q4_TimeToAnswer | Prosjecno vrijeme odgovora | Self-JOIN + agregacija |
| usp_OLAP_Q5_TopContributors | Top korisnici po utjecaju | CTE + GROUP BY |

---

## 11. Izlazni fajlovi

### summary.csv (1.080 redova za puni benchmark, 36 za dry-run)

```
Configuration, OltpOlapRatio, ConcurrencyLevel, RunNumber,
OltpThroughput, OlapThroughput,
OltpLatencyP50, OltpLatencyP95, OltpLatencyP99,
OlapLatencyP50, OlapLatencyP95, OlapLatencyP99,
OltpSuccessRate, OlapSuccessRate
```

### measurements.csv (sirova mjerenja, milioni redova za puni benchmark)

```
Configuration, OltpOlapRatio, ConcurrencyLevel, RunNumber,
OperationType, OperationName, StartTimestamp, LatencyMs,
Success, ErrorMessage
```

---

## 12. Rjesavanje problema

### OLAP upiti blokirani >60s (CXSYNC_PORT wait)

Uzrok: Prekomjerna paralelizacija (batch-mode columnstore) pri visokoj konkurentnosti.
Rjesenje: Skript 09_Fix_OLAP_MaxDop.sql dodaje OPTION(MAXDOP 2) svim OLAP procedurama.
Obavezno pokrenuti ovaj skript PRIJE pokretanja benchmarka pri C=32.

---

### Timeout pri ucitavanju konteksta (30s)

Uzrok: SELECT TOP 20000 ORDER BY NEWID() na 3.7M redova -- predugo za default 30s timeout.
Rjesenje: Ispravljeno u kodu -- commandTimeout: 300 u WorkloadExecutor.cs.

---

### ORDER BY NEWID() stall na memory-optimized tablicama

Uzrok: Paralelni plan izvrsavanja na Hekaton tablicama uzrokuje CXSYNC_PORT wait.
Rjesenje: Dodan OPTION(MAXDOP 1) u context-loading upite za im i htap sheme.

---

### OOM crash / SQL Server se gasi pri C=32 (IM ili HTAP konfiguracija)

Uzrok: MVCC version chain akumulacija -- svaki DELETE na memory-optimized tablici kreira ghost verzije koje GC mora procistiti. Brisanje svih 3.7M redova izmedju kombinacija generira priblizno 7.4M GC stavki po tranziciji, sto pri C=32 preopterecuje in-memory GC.

Rjesenje implementirano u kodu:
- TruncateAndReloadPostsAsync brise i puni samo 20.000 aktivnih postova (ne sve 3.7M)
- Poziva se i izmedju kombinacija i izmedju svakog od 30 runova (da GC ne akumulira)
- Ukupno: 185x manje GC posla po kombinaciji

```
Simptom: SQL Server se gasi ili app crashi s OutOfMemoryException
         nakon 2-3 kombinacije pri C=32
Rjesenje: Koristiti trenutnu verziju koda (problem rijesen u WorkloadExecutor.cs)
```

---

### TRUNCATE TABLE nije podrzana na memory-optimized tablicama (Error 10794)

Uzrok: SQL Server In-Memory OLTP ne podrzava TRUNCATE TABLE.
Greska: Msg 10794, Level 16: The statement 'TRUNCATE TABLE' is not supported with memory optimized tables.
Rjesenje: Koristiti DELETE FROM tablica ili selektivni delete po ID-u.

---

### Python ModuleNotFoundError

```bash
cd Analysis
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

### SQL Server: memory-optimized tablice se ne mogu kreirati

Uzrok: SQL Server Express ne podrzava In-Memory OLTP.
Greska: CREATE TABLE ... WITH (MEMORY_OPTIMIZED = ON) ne uspijeva.
Rjesenje: Koristiti Developer, Standard ili Enterprise Edition.

---

### Benchmark se ne nastavlja (resume) nakon prekida

Uzrok: ResultsWriter otvara fajlove za pisanje (truncate mode) prije nego sto se provjeri koje kombinacije su vec zavrsene.
Rjesenje: Implementirano u BenchmarkOrchestrator.cs -- _resumeMap se cita iz summary.csv u konstruktoru, PRIJE otvaranja ResultsWriter.
Pokretati benchmark normalno -- automatski nastavlja od gdje je stao.

---

## 13. Poznata ogranicenja

### SQL Server 2022 RTM -- nema inline columnstore na memory-optimized tablicama

SQL Server 2022 RTM ne podrzava NONCLUSTERED COLUMNSTORE INDEX direktno na memory-optimized tablicama. Poruka greske:

```
Msg 12332: Columnstore indexes are not supported for memory optimized tables.
```

Zbog toga HTAP konfiguracija koristi dual-store pristup: htap.* za OLTP (in-memory), cs.* za OLAP (disk+columnstore). Ovo je namjeran dizajn koji odgovara komercijalnim HTAP implementacijama (TiDB/TiFlash, Oracle Dual-Format).

### SCHEMA_ONLY durability -- gubitak podataka pri restartu

im.* i htap.* tablice koriste DURABILITY = SCHEMA_ONLY radi maksimalnih performansi. Svi podaci nestaju kada SQL Server stane. Pogledati sekciju 4.3 za upute o ponovnom punjenju.

### Benchmark trajanje

Puni benchmark (1.080 runova x 70s po runu) traje priblizno 21 sat na referentnom hardveru. Trajanje na sporijim masinama moze biti znacajno duze. Statisticka valjanost zahtijeva minimum 30 runova po kombinaciji za neparametarsku analizu.

### Ograniczenost na jedan server

Benchmark ne testira distribuirane konfiguracije. Sva 4 konfiguracijska pristupa rade na jednoj instanci SQL Servera, sto eliminira mrezni utjecaj ali ne odrazava produkcijska distribuirana okruzenja.

### Workload je sinteticki

OLTP i OLAP operacije su reprezentativne za HTAP scenarije, ali nisu direktno prenosivi na specificnu domensku aplikaciju. Rezultati su indikativni za klasu opterecenja, ne za konkretan use-case.

### Platforma

Projekat je razvijen i testiran iskljucivo na Windows 11 s SQL Server 2022 Developer Edition. Memory-optimized tablice (Hekaton) nisu dostupne na Linux verziji SQL Servera (SQL Server on Linux ne podrzava In-Memory OLTP u verziji 2022).

---

*Projekat razvijen za potrebe akademskog istrazivanja -- evaluacija HTAP paradigme u SQL Serveru 2022*
*Optimizacija baza podataka, Politechnicki fakultet Zenica, juni 2026.*
