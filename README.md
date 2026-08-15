# HTAPBenchmark
## Evaluacija performansi hibridne transakcijsko-analitičke obrade (HTAP) u Microsoft SQL Serveru 2022

Projekat iz Optimizacija baza podataka — Komparativna analiza četiri konfiguracijske strategije pohrane nad skupom podataka StackOverflow2010

**Napomena:** Puni benchmark (1.080 runova) traje približno **21 sat**.
---

## Sadržaj

1. [Pregled projekta](#1-pregled-projekta)
2. [Preduvjeti i reproducibilnost](#2-preduvjeti-i-reproducibilnost)
3. [Struktura projekta](#3-struktura-projekta)
4. [Postavljanje okruženja](#4-postavljanje-okruženja)
5. [Pokretanje benchmarka](#5-pokretanje-benchmarka)
6. [Statistička analiza i vizualizacije](#6-statistička-analiza-i-vizualizacije)
7. [Rezultati benchmarka](#7-rezultati-benchmarka)
8. [Eksperimentalni dizajn](#8-eksperimentalni-dizajn)
9. [Konfiguracijske strategije](#9-konfiguracijske-strategije)
10. [Radna opterećenja](#10-radna-opterećenja)
11. [Izlazni fajlovi](#11-izlazni-fajlovi)
12. [Provjera skupa podataka](#12-provjera-skupa-podataka)
13. [Cijena sinhronizacije dual-store slojeva](#13-cijena-sinhronizacije-dual-store-slojeva)

---

## 1. Pregled projekta

Ovaj projekat eksperimentalno evaluira četiri konfiguracijske strategije pohrane podataka u Microsoft SQL Serveru 2022 kroz mješovito opterećenje OLTP i OLAP operacija nad skupom podataka StackOverflow2010 (približno 19,2 milijuna zapisa). Cilj je kvantificirati performansne razlike i statistički testirati tri hipoteze o HTAP obradi.

Puni benchmark obuhvata 1.080 mjerenja (4 konfiguracije × 3 omjera radnog opterećenja × 3 razine konkurentnosti × 30 runova) i traje približno 21 sat na referentnom hardveru (Intel Core i9-14900HX, 32 GB DDR5, 1 TB NVMe SSD). Trajanje može biti duže na sporijim mašinama.

### Istraživačke hipoteze

| | Hipoteza |
|-|----------|
| H1 | Disk-zasnovana konfiguracija s columnstore indeksom (CS) ostvaruje usporedivu OLAP latenciju s hibridnom konfiguracijom (HTAP) pri niskim razinama konkurentnosti, ali razlika postaje statistički značajna pri visokim razinama |
| H2 | Degradacija OLTP propusnosti uzrokovana istovremenim analitičkim upitima veća je u CS konfiguraciji nego u HTAP konfiguraciji |
| H3 | Pri transakcijski intenzivnom opterećenju HTAP konfiguracija ne ostvaruje statistički značajno veću OLTP propusnost od čisto transakcijske konfiguracije (IM) |

---

## 2. Preduvjeti i reproducibilnost

Projekat je dizajniran da bude reproducibilan na drugoj mašini koja zadovoljava navedene zahtjeve. Svi preduvjeti moraju biti ispunjeni prije prvog pokretanja.

### Operativni sistem

Projekat zahtijeva **Windows** (10 ili 11, 64-bit). Microsoft SQL Server In-Memory OLTP (Hekaton) i memory-optimized tablice dostupni su isključivo na Windows platformi u SQL Server 2022.

### Obavezni softver

| Komponenta | Preporučena verzija | Provjera instalacije |
|-----------|---------------------|----------------------|
| Microsoft SQL Server 2022 | 16.x, Developer ili Enterprise Edition | `SELECT @@VERSION` u SSMS |
| SQL Server Management Studio (SSMS) | 20.x ili noviji | SSMS > Help > About |
| .NET SDK | 8.0 ili noviji | `dotnet --version` |
| Python | 3.11 ili noviji | `python --version` |

**Napomena:** SQL Server **Express Edition nije podržana** jer ne uključuje In-Memory OLTP. Koristiti Developer Edition (besplatna za neproizvodnu upotrebu).

### Hardver (minimalni i referentni)

| Komponenta | Minimum | Referentni (korišten) |
|-----------|---------|------------------------|
| RAM | 16 GB | 32 GB DDR5 |
| CPU jezgre | 4 | 24 (Intel Core i9-14900HX) |
| Slobodan disk | 60 GB SSD | 1 TB NVMe SSD |
| OS | Windows 10 64-bit | Windows 11 Home |

**Napomena:** `im.*` i `htap.*` konfiguracije koriste memory-optimized tablice koje trebaju približno 8 GB RAM po shemi (~16 GB ukupno samo za SQL Server in-memory podatke). Na mašinama s manje od 16 GB RAM ove konfiguracije mogu uzrokovati OOM greške.

### Python paketi

Sve zavisnosti su navedene u `Analysis/requirements.txt`. Instalirati ih unutar virtualnog okruženja:

```bash
cd Analysis
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

| Paket | Minimalna verzija | Svrha |
|-------|-------------------|-------|
| pandas | 2.2.0 | Obrada CSV rezultata |
| numpy | 1.26.0 | Numeričke operacije |
| scipy | 1.13.0 | Statistički testovi (Kruskal-Wallis, Mann-Whitney U) |
| matplotlib | 3.9.0 | Generisanje grafova |
| seaborn | 0.13.2 | Violin grafovi i heatmap |
| openpyxl | 3.1.2 | Izvoz u .xlsx format |
| statsmodels | 0.14.0 | OLS regresija i ANOVA |
| pyodbc | 5.0.0 | Direktna SQL Server veza |

Provjera instalacije:

```bash
python -c "import pandas, numpy, scipy, matplotlib, seaborn, openpyxl, statsmodels, pyodbc; print('Sve zavisnosti instalirane')"
```

### .NET zavisnosti (automatski preuzete)

```bash
dotnet restore BenchmarkApp/HTAPBenchmark.sln
```

| NuGet paket | Svrha |
|-------------|-------|
| Microsoft.Data.SqlClient | SQL Server konekcija i query izvršavanje |
| Dapper | Lagani ORM za mapiranje rezultata |
| Microsoft.Extensions.Configuration | Učitavanje appsettings.json |
| Microsoft.Extensions.Configuration.EnvironmentVariables | Podrška za env varijable (override connection stringa) |

### Konfiguracija SQL Servera

Nakon instalacije SQL Servera preporučuje se podesiti maksimalnu količinu memorije:

```sql
-- Preporučeno: ostaviti ~4 GB OS-u, ostatak SQL Serveru
-- Primjer za 32 GB mašinu:
EXEC sp_configure 'max server memory (MB)', 28000;
RECONFIGURE;
```

SQL Server mora biti konfigurisan s Windows Authentication (`Trusted_Connection=True`). Za SQL Authentication izmijeniti `ConnectionString` u `BenchmarkApp/HTAPBenchmark.Runner/appsettings.json`.

---

## 3. Struktura projekta

```
HTAPBenchmark/
|
|-- SQL/                                      # SQL skripte za postavljanje okruženja
|   |-- 00_DatabaseSetup.sql                  # Kreiranje baze, filegroup-a i shema
|   |-- 01_Schema_Baseline.sql                # Baseline tablice: disk, B-tree indeksi
|   |-- 02_Schema_CS.sql                      # CS tablice: disk + NONCLUSTERED COLUMNSTORE
|   |-- 03_Schema_IM.sql                      # IM tablice: memory-optimized, Hekaton
|   |-- 04_Schema_HTAP.sql                    # HTAP tablice: memory-optimized OLTP sloj
|   |-- 05_LoadData.sql                       # Punjenje podataka iz StackOverflow2010 (~30-60 min)
|   |-- 05b_LoadData_CS_HTAP_Only.sql         # Obnova im.* i htap.* nakon restarta SQL Servera
|   |-- 06_StoredProcs_OLTP.sql               # OLTP procedure za sve 4 sheme (nativno kompajlirane za im/htap)
|   |-- 07_StoredProcs_OLAP.sql               # OLAP upiti Q1-Q5 za sve sheme
|   |-- 07b_StoredProcs_OLAP_HTAP_DualStore.sql  # Override: HTAP OLAP čita iz cs.* (pokrenuti NAKON 07)
|   |-- 08_ResultsSchema.sql                  # (Opcionalno) DB-side log tablica za mjerenja
|   |-- 09_Fix_OLAP_MaxDop.sql                # Dodaje OPTION(MAXDOP 2) OLAP procedurama (obavezno za C=32)
|   `-- README.md                             # Upute za SQL skripte (na engleskom)
|
|-- BenchmarkApp/                             # .NET 8 benchmark aplikacija
|   `-- HTAPBenchmark.sln
|       |-- HTAPBenchmark.Core/
|       |   |-- Models/
|       |   |   |-- BenchmarkConfig.cs        # Konfiguracija benchmarka (deserijalizira appsettings.json)
|       |   |   `-- MeasurementResult.cs      # Model jednog mjerenja (latencija, propusnost, success)
|       |   `-- Services/
|       |       |-- BenchmarkOrchestrator.cs  # Glavna petlja: iteracija kroz kombinacije, resume logika
|       |       |-- WorkloadExecutor.cs       # Paralelno izvršavanje OLTP/OLAP workloa-da, warmup, mjerenje
|       |       |-- ResultsWriter.cs          # Streaming zapis rezultata u CSV (measurements + summary)
|       |       |-- MetricsCalculator.cs      # Računanje P50/P95/P99 latencija i propusnosti
|       |       |-- OltpQueries.cs            # Definicija 6 OLTP operacija i njihovog distribucijskog udjela
|       |       `-- OlapQueries.cs            # Definicija 5 OLAP upita (Q1-Q5)
|       `-- HTAPBenchmark.Runner/
|           |-- Program.cs                    # Entry point: parsiranje argumenata, DI, pokretanje
|           `-- appsettings.json              # Konfiguracija: connection string, broj runova, concurrency, itd.
|
|-- Analysis/                                 # Python skripte za statističku analizu i vizualizacije
|   |-- requirements.txt                      # Sve Python zavisnosti (pip install -r requirements.txt)
|   |-- run_all.py                            # Pokreće sve analize sekvencijalno (00-06), s opcijama
|   |-- 00_merge_results.py                   # Spaja measurements.csv u agregirani summary.csv
|   |-- 01_descriptive_stats.py               # Deskriptivna statistika: mean, std, P50, P95 po kombinaciji
|   |-- 02_statistical_tests.py               # Kruskal-Wallis, Mann-Whitney U + Bonferroni, Cohen's d
|   |-- 03_visualizations.py                  # 6 grafova: violin, throughput-latency, degradacija, heatmap
|   |-- 04_per_operation_stats.py             # Per-operacijska statistika (avg/P50/P95/P99 po tipu operacije)
|   `-- 05_regression_anova.py                # OLS regresija i ANOVA analiza uticaja faktora
|
|-- Paper/                                    # LaTeX izvorni fajlovi akademskog rada
|   |-- rad.tex                               # Master fajl: preamble, naslovna strana, input poglavlja
|   |-- 00_sazetak.tex                        # Sažetak (BHS) i Abstract (EN)
|   |-- 01_uvod.tex                           # Uvod: motivacija, istraživačka pitanja, pregled rada
|   |-- 02_metodologija.tex                   # Metodologija: eksperimentalni dizajn, statistički testovi
|   |-- 03_sistem.tex                         # Opis sistema: četiri arhitekturalne strategije, dataset
|   |-- 04_eksperiment.tex                    # Opis eksperimenta: workload, metrike, implementacija
|   |-- 05_rezultati.tex                      # Rezultati i diskusija: hipoteze, tabele, grafovi
|   |-- 06_zakljucak.tex                      # Zaključak i smjernice za buduća istraživanja
|   |-- app_a_oltp.tex                        # Dodatak A: implementacija OLTP pohranjenih procedura
|   |-- app_b_olap.tex                        # Dodatak B: implementacija OLAP analitičkih upita
|   `-- refs.bib                              # BibTeX bibliografija (IEEE format)
|
`-- Results/                                  # Generirani izlazi benchmarka i analize (ne editovati ručno)
    |-- summary.csv                           # Agregirani rezultati po runu (1.080 redova za puni benchmark)
    |-- measurements.csv                      # Sirova mjerenja po operaciji (milioni redova)
    |-- descriptive_summary.csv / .xlsx       # Deskriptivna statistika po kombinaciji
    |-- statistical_tests.csv                 # Rezultati statističkih testova (p-vrijednosti, effect size)
    |-- hypothesis_results.txt                # Zaključci za H1, H2 i H3 u čitljivom formatu
    |-- per_operation_stats.csv / .xlsx       # P50/P95/P99 po tipu operacije i konfiguraciji
    |-- regression_oltp_throughput.csv        # OLS regresija: faktori koji utječu na OLTP propusnost
    |-- regression_olap_latency.csv           # OLS regresija: faktori koji utječu na OLAP latenciju
    |-- regression_report.txt                 # Sažetak regresijske analize u čitljivom formatu
    `-- figures/                              # Generirani grafovi (PNG, 6 fajlova)
        |-- 01_oltp_latency_violin.png
        |-- 02_olap_latency_violin.png
        |-- 03_oltp_throughput_latency.png
        |-- 04_olap_throughput_latency.png
        |-- 05_oltp_degradation.png
        `-- 06_latency_heatmap.png
```

---

## 4. Postavljanje okruženja

### 4.1 StackOverflow2010 dataset

- Preuzeti sa: https://www.brentozar.com/archive/2015/10/how-to-download-the-stack-overflow-database-via-bittorrent/
- Odabrati verziju **2010** (~10 GB download, ~25 GB nakon restore-a)
- Restore u SSMS: desni klik na Databases > Restore Database > From Device > odabrati `.bak` fajl

### 4.2 SQL skripte — pokrenuti redom u SSMS

Otvoriti svaki fajl u SSMS i pokrenuti redom (F5 ili Execute):

| # | Skripta | Šta radi |
|---|---------|----------|
| 1 | `00_DatabaseSetup.sql` | Kreira bazu `HTAPBenchmark`, filegroup-e (uključujući `MEMORY_OPTIMIZED_DATA`) i četiri sheme (`baseline`, `cs`, `im`, `htap`) |
| 2 | `01_Schema_Baseline.sql` | Kreira disk-zasnovane tablice s clustered B-tree indeksima — kontrolna grupa |
| 3 | `02_Schema_CS.sql` | Kreira disk-zasnovane tablice s dodatnim `NONCLUSTERED COLUMNSTORE` indeksima za batch-mode OLAP |
| 4 | `03_Schema_IM.sql` | Kreira memory-optimized tablice s hash i range indeksima; sve OLTP procedure nativno kompajlirane |
| 5 | `04_Schema_HTAP.sql` | Kreira memory-optimized tablice za OLTP sloj (`htap.*`); OLAP čita iz `cs.*` (dual-store) |
| 6 | `05_LoadData.sql` | Puni sve četiri sheme podacima iz StackOverflow2010 (~30–60 min, ~76M redova ukupno) |
| 7 | `06_StoredProcs_OLTP.sql` | Kreira 6 OLTP procedura za sve 4 sheme: INSERT glas, UPDATE skor, INSERT komentar, SELECT postovi/korisnik/ID (disk varijante s `CREATE OR ALTER`, memory varijante s `NATIVE_COMPILATION`) |
| 8 | `07_StoredProcs_OLAP.sql` | Kreira 5 OLAP upita (Q1–Q5) za sve sheme: agregatna analiza aktivnosti, angažiranosti, tagova, vremena odgovora i top korisnika |
| 9 | `07b_StoredProcs_OLAP_HTAP_DualStore.sql` | **Override:** prepisuje HTAP OLAP procedure da čitaju iz `cs.*` (columnstore) umjesto iz `htap.*` (memory). Mora se pokrenuti **nakon skripte 8** |
| 10 | `09_Fix_OLAP_MaxDop.sql` | Dodaje `OPTION(MAXDOP 2)` svim OLAP procedurama — sprječava `CXSYNC_PORT` čekanje pri C=32 s više istovremenih batch-mode skenova. **Obavezno pokrenuti prije benchmarka** |

**Opcionalno:** `08_ResultsSchema.sql` kreira tablicu za DB-side logging mjerenja — benchmark aplikacija to ne koristi (rezultati idu u CSV), ali može biti korisno za ručno testiranje pojedinih procedura.

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
```

Sve četiri sheme moraju imati identičan broj redova po tablici:

| Tablica | Očekivani broj redova |
|---------|----------------------|
| Badges | ~1.102.019 |
| Comments | ~3.875.183 |
| Posts | ~3.729.195 |
| Users | ~299.398 |
| Votes | ~10.143.364 |

Ako `im.*` ili `htap.*` pokazuju 0 redova, SQL Server je bio restartovan — pokrenuti `05b_LoadData_CS_HTAP_Only.sql`.

### 4.3 Nakon restarta SQL Servera

`im.*` i `htap.*` tablice koriste `DURABILITY = SCHEMA_ONLY` — svi podaci se gube kada SQL Server stane. Sheme i indeksi ostaju, ali redovi nestaju.

| Shema | Pohrana | Preživljava restart? |
|-------|---------|----------------------|
| baseline.* | Disk (B-tree) | Da |
| cs.* | Disk (columnstore) | Da |
| im.* | RAM (Hekaton, SCHEMA_ONLY) | Ne — redovi se brišu |
| htap.* | RAM (Hekaton, SCHEMA_ONLY) | Ne — redovi se brišu |

Nakon svakog restarta SQL Servera pokrenuti u SSMS:

```
SQL/05b_LoadData_CS_HTAP_Only.sql
```

Ova skripta puni samo `im.*` i `htap.*` tablice iz `cs.*` (koja je disk-zasnovana i preživljava restart). Traje ~5–10 minuta.

**Napomena o potpunosti podataka:** `05b` učitava `TOP 500.000` redova za `htap.Votes` i `htap.Comments` (umjesto punih ~10M i ~3,9M) kako bi se spriječile OOM greške Hekaton GC-a pri ponovnom punjenju. Ovo ne utječe na validnost mjerenja — skripta je namijenjena isključivo kao alat za oporavak od restarta. Puni benchmark je proveden nakon inicijalnog punjenja s `05_LoadData.sql`, s identičnim brojem redova u svim četirima shemama.

### 4.4 .NET aplikacija

```bash
dotnet restore BenchmarkApp/HTAPBenchmark.sln
dotnet build BenchmarkApp/HTAPBenchmark.sln -c Release
```

Ako je SQL Server na drugoj adresi, izmijeniti `ConnectionString` u `BenchmarkApp/HTAPBenchmark.Runner/appsettings.json`:

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

Za SQL Authentication (umjesto Windows Authentication):

```
Server=.;Database=HTAPBenchmark;User Id=korisnik;Password=lozinka;TrustServerCertificate=True;Max Pool Size=200;
```

### 4.5 Python okruženje

```bash
cd Analysis
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## 5. Pokretanje benchmarka

### Kratki test (provjera ispravnosti — pokrenuti prvi)

Ako `Results/summary.csv` već postoji (npr. iz kloniranog repoa), benchmark će sve kombinacije preskočiti jer smatra da su završene. Prije pokretanja obrisati oba CSV fajla:

```powershell
del Results\summary.csv
del Results\measurements.csv
```

Zatim pokrenuti kratki test:

```bash
dotnet run --project BenchmarkApp/HTAPBenchmark.Runner -c Release -- --dry-run
```

| Parametar | Vrijednost |
|-----------|-----------|
| Warmup | 2 s |
| Mjerenje | 5 s |
| Runova po kombinaciji | 1 |
| Ukupno runova | 36 |
| Trajanje | ~7–12 minuta |

Očekivani izlaz: `Results/summary.csv` s 36 redova, bez grešaka u konzoli.

### Puni benchmark (za istraživačke rezultate)

```bash
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
| Procijenjeno trajanje | ~21 sat |

### Opcije komandne linije

| Opcija | Opis |
|--------|------|
| `--dry-run` | Warmup=2s, mjerenje=5s, 1 run/kombinacija — ukupno 36 runova (~7–12 min) |
| `--quick` | Warmup=5s, mjerenje=30s, 3 runa/kombinacija — brza provjera rezultata |
| `--only cs,htap` | Filtrira samo navedene konfiguracije (korisno za parcijalno ponavljanje) |

Ctrl+C pokreće graceful prekid — završava tekući run i potom staje.

### Resume — nastavak nakon prekida

Benchmark automatski nastavlja od zadnjeg završenog runa. Pri startu čita `Results/summary.csv` i preskače sve kombinacije koje su već zabilježene. Sigurno je prekinuti (Ctrl+C) i ponovo pokrenuti — niti jedan završeni run neće se ponoviti.

---

## 6. Statistička analiza i vizualizacije

### Automatsko pokretanje svih analiza

Najjednostavniji način je `run_all.py` koji pokreće sve skripte sekvencijalno:

```bash
cd Analysis
venv\Scripts\activate
python run_all.py
```

Opcije:

| Opcija | Opis |
|--------|------|
| `--skip-merge` | Preskoči `00_merge_results.py` (ako je `summary.csv` već ažuran) |
| `--input PATH` | Eksplicitni path do summary CSV-a (default: `../Results/summary.csv`) |

### Ručno pokretanje pojedinih skripti

```bash
cd Analysis
venv\Scripts\activate

python 00_merge_results.py
# Spaja sirova mjerenja iz measurements.csv u agregirani summary.csv (jedan red po runu)
# Izlaz: ../Results/summary.csv

python 01_descriptive_stats.py
# Deskriptivna statistika po konfiguraciji i kombinaciji: mean, std, P50, P95, min, max
# Izlaz: ../Results/descriptive_summary.csv i .xlsx

python 02_statistical_tests.py
# Kruskal-Wallis H test (globalne razlike), Mann-Whitney U s Bonferroni korekcijom, Cohen's d
# Izlaz: ../Results/statistical_tests.csv, ../Results/hypothesis_results.txt

python 03_visualizations.py
# Generiše 6 grafova: violin distribucije, throughput-latency krivulje, degradacija, heatmap
# Izlaz: ../Results/figures/*.png

python 04_per_operation_stats.py
# Per-operacijska statistika: P50/P95/P99 latencija za svaki od 6 OLTP i 5 OLAP tipova
# Izlaz: ../Results/per_operation_stats.csv i .xlsx

python 05_regression_anova.py
# OLS regresija i ANOVA: kvantificira uticaj konfiguracije, omjera i konkurentnosti na metrike
# Izlaz: ../Results/regression_oltp_throughput.csv, regression_olap_latency.csv, regression_report.txt
```

### Generirani grafovi

| Fajl | Sadržaj | Hipoteza |
|------|---------|----------|
| `01_oltp_latency_violin.png` | Violin distribucije OLTP latencije po konfiguraciji | — |
| `02_olap_latency_violin.png` | Violin distribucije OLAP latencije po konfiguraciji | H1 |
| `03_oltp_throughput_latency.png` | OLTP propusnost vs. latencija po razini konkurentnosti | — |
| `04_olap_throughput_latency.png` | OLAP propusnost vs. latencija po razini konkurentnosti | H2 |
| `05_oltp_degradation.png` | Pad OLTP propusnosti pri povećanju udjela OLAP u workloadu | H2 |
| `06_latency_heatmap.png` | Heatmap latencija za svih 36 kombinacija | Opći pregled |

---

## 7. Rezultati benchmarka

### OLTP propusnost po konfiguraciji (C=32, omjer 80/20)

| Konfiguracija | Median ops/s | Std | vs Baseline |
|--------------|-------------|-----|-------------|
| Baseline | 2.432 | ±2.375 | — |
| CS | 3.618 | ±2.681 | +49% |
| IM | 28.764 | ±13.260 | +11,8× |
| HTAP | 21.920 | ±17.130 | +9,0× |

### OLAP propusnost po konfiguraciji (C=32)

| Konfiguracija | Median q/s | vs Baseline |
|--------------|-----------|-------------|
| Baseline | 0,85 | — |
| CS | 6,10 | +7,2× |
| IM | 0,77 | −9% |
| HTAP | 6,84 | +8,0× |

### Zaključci hipoteza

| Hipoteza | Ishod | Cohen's d |
|---------|-------|-----------|
| H1: CS ≈ HTAP pri niskom C, razlika pri visokom C | Djelimično potvrđena | d = +1,61 (C=32) |
| H2: CS degradira više od HTAP pri mješovitom opterećenju | Potvrđena | d = 2,32 |
| H3: HTAP ≈ IM pri OLTP-intenzivnom opterećenju | Odbačena | d = −4,4 do −11,9 |

Detalji u `Results/hypothesis_results.txt`.

---

## 8. Eksperimentalni dizajn

### Faktorijalni plan 4 × 3 × 3

```
4 konfiguracije  ×  3 OLTP/OLAP omjera  ×  3 razine konkurentnosti
     = 36 kombinacija × 30 runova = 1.080 mjerenja
```

### Statističke metode

| Test | Primjena |
|------|----------|
| Kruskal-Wallis H | Globalne razlike između 4 konfiguracije (neparametarski ANOVA) |
| Mann-Whitney U | Parne usporedbe s Bonferroni korekcijom (α = 0,05) |
| Cohen's d | Veličina efekta: trivijalan <0,2 / mali 0,2–0,5 / srednji 0,5–0,8 / veliki >0,8 |

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
| Posts | ~3.729.195 | Pitanja i odgovori |
| Users | ~299.398 | Korisnički profili |
| Votes | ~10.143.364 | Glasovi (up/down/close...) |
| Comments | ~3.875.183 | Komentari na postove |
| Badges | ~1.102.019 | Dodjele bedževa |
| **Ukupno po shemi** | **~19.149.159** | |
| **Ukupno (4 sheme)** | **~76.600.000** | |

### Disk i memorija

| Shema | Pohrana | Veličina (približno) |
|-------|---------|---------------------|
| baseline.* | Disk (HDD/SSD) | ~15 GB |
| cs.* | Disk (HDD/SSD) | ~17 GB (columnstore kompresija) |
| im.* | RAM | ~8 GB |
| htap.* | RAM | ~8 GB |

---

## 9. Konfiguracijske strategije

| Konfiguracija | Pohrana | Indeksiranje | OLAP engine | Očekivano ponašanje |
|--------------|---------|-------------|-------------|---------------------|
| Baseline | Disk (row-store) | B-tree (clustered + nonclustered) | Row-mode | Visok OLTP, nizak OLAP |
| CS | Disk (row-store) | B-tree + NONCLUSTERED COLUMNSTORE | Batch-mode | Umjeren OLTP, visok OLAP |
| IM | Memorija (Hekaton) | Hash + Range (memory-optimized) | Row-mode | Visok OLTP, nizak OLAP |
| HTAP | OLTP→Memorija / OLAP→Disk+CS | Dual-store (IM za pisanje, CS za čitanje) | Batch-mode (OLAP) | Visok OLTP + visok OLAP |

---

## 10. Radna opterećenja

### OLTP operacije (6 tipova, nasumična selekcija)

| Procedura | Tip | Udio |
|-----------|-----|------|
| `usp_InsertVote` | INSERT (2 tabele, atomarno) | 35% |
| `usp_UpdatePostScore` | UPDATE | 25% |
| `usp_InsertComment` | INSERT | 15% |
| `usp_GetRecentUserPosts` | SELECT (range scan, TOP 10) | 10% |
| `usp_GetPostById` | SELECT (točkačno, PK) | 10% |
| `usp_GetUserById` | SELECT (točkačno, PK) | 5% |

Write-heavy workload: 75% pisanja / 25% čitanja. Distribucija definirana u `OltpQueries.cs`.

### OLAP upiti (5 tipova, nasumična selekcija)

| Procedura | Opis | Vrsta operacije |
|-----------|------|-----------------|
| `usp_OLAP_Q1_MonthlyActivity` | Godišnja/månačna aktivnost po periodu | GROUP BY + agregacija |
| `usp_OLAP_Q2_UserEngagement` | Angažiranost korisnika (odgovori, komentari) | JOIN + GROUP BY |
| `usp_OLAP_Q3_TagAnalysis` | Analiza popularnosti tagova | JOIN + GROUP BY |
| `usp_OLAP_Q4_TimeToAnswer` | Prosječno vrijeme do prvog odgovora | Self-JOIN + agregacija |
| `usp_OLAP_Q5_TopContributors` | Top korisnici po ukupnom utjecaju | CTE + GROUP BY |

---

## 11. Izlazni fajlovi

### `Results/summary.csv` — agregirani rezultati (1 red po runu)

```
Configuration, OltpOlapRatio, ConcurrencyLevel, RunNumber,
OltpThroughput, OlapThroughput,
OltpLatencyP50, OltpLatencyP95, OltpLatencyP99,
OlapLatencyP50, OlapLatencyP95, OlapLatencyP99,
OltpSuccessRate, OlapSuccessRate
```

1.080 redova za puni benchmark, 36 redova za dry-run.

### `Results/measurements.csv` — sirova mjerenja (1 red po operaciji)

```
Configuration, OltpOlapRatio, ConcurrencyLevel, RunNumber,
OperationType, OperationName, StartTimestamp, LatencyMs,
Success, ErrorMessage
```

Milioni redova za puni benchmark — koristiti za per-operacijsku analizu (`04_per_operation_stats.py`).

---

## 12. Provjera skupa podataka

**Ovo je najvažniji korak prije svake mjerne sesije.**

`im.*` i `htap.*` tablice su `DURABILITY = SCHEMA_ONLY` i gube **sve** podatke pri
svakom restartu SQL Servera. Ako se `05b_LoadData_CS_HTAP_Only.sql` ne pokrene
nakon restarta, benchmark radi nad djelimično praznim tablicama i uredno proizvodi
rezultate — samo neuporedive s ostatkom eksperimenta. Manje redova znači kraće OLAP
skeniranje, pa i OLTP i OLAP izgledaju višestruko brži nego što jesu.

Takav run se ne prepozna po greškama nego tek po tome što su brojke sumnjivo dobre,
a do tada su potrošeni sati mjerenja.

### Automatska provjera

Benchmark aplikacija sama broji redove u aktivnoj shemi prije prvog runa i
**prekida** ako odstupaju više od 5 % od očekivanog:

```
PREKID: shema im nema očekivan broj redova.
    im.Posts        412.883 redova, očekivano  3.729.195 (11,1 % očekivanog)
  Za im.*/htap.* pokrenite SQL/05b_LoadData_CS_HTAP_Only.sql
```

Provjera se isključuje s `--skip-verify` ili `"VerifyDatasetBeforeRun": false` u
`appsettings.json`. Isključivati je samo svjesno — rezultati iz takvog runa nisu
usporedivi s ostatkom eksperimenta ako je shema bila nepotpuna.

### Ručna provjera svih shema

```bash
sqlcmd -S . -i SQL/12_VerifyDataIntegrity.sql
```

Ispisuje broj redova po tablici za sve četiri sheme uz status `OK` / `ODSTUPANJE` /
`PRAZNO`. Traje nekoliko sekundi.

| Tablica | Očekivano redova |
|---|---|
| Posts | 3.729.195 |
| Users | 299.398 |
| Votes | 10.143.364 |
| Comments | 3.875.183 |
| Badges | 1.102.019 |

Tolerancija je 5 % jer benchmark tokom rada dodaje glasove i komentare, a cleanup
ih briše po vodenom žigu.

---

## 13. Cijena sinhronizacije dual-store slojeva

Glavni eksperiment mjeri HTAP konfiguraciju **bez ijedne propagacije** podataka:
analitički sloj `cs.*` čita statičan snapshot, pa izolacija radnih tokova dolazi
besplatno. Produkcijski dual-store sistemi tu cijenu plaćaju stalno — TiDB Raft
replikacijom na TiFlash, F1 Lightning Changepumpom i kompakcijom. Izmjerene
prednosti HTAP-a su zato **gornja granica** ostvariva uz nultu cijenu sinhronizacije.

`SQL/11_DualStore_Sync.sql` implementira periodičnu batch propagaciju `htap.*` →
`cs.*` po rasponu identifikatora (seek po hash indeksu, bez skeniranja tablice —
delta-store model kao u F1 Lightningu). Mjerenjem pri više intervala prednost
prestaje biti gornja granica i postaje funkcija tražene svježine podataka.

```bash
sqlcmd -S . -i SQL/11_DualStore_Sync.sql

# SVE ČETIRI RUKE U ISTOJ SESIJI — inače se cijena sinhronizacije
# ne može odvojiti od razlike među mjernim sesijama
dotnet run --project BenchmarkApp/HTAPBenchmark.Runner -- --sync 0
dotnet run --project BenchmarkApp/HTAPBenchmark.Runner -- --sync 1
dotnet run --project BenchmarkApp/HTAPBenchmark.Runner -- --sync 5
dotnet run --project BenchmarkApp/HTAPBenchmark.Runner -- --sync 30

python Analysis/10_sync_cost.py
```

Ruke se označavaju kao `htap@sync0`, `htap@sync5` itd. i pišu u
`Results/summary_arm_sync*.csv`, pa se ne miješaju s glavnim setom.
`--sync 0` je kontrolna ruka i **mora** biti izmjerena u istoj sesiji kao ostale.

**Napomene:**

- Nakon svakog runa `htap.usp_SyncCleanupColumnstore` vraća `cs.*` u polazno stanje.
  Bez toga bi se izmjene akumulirale kroz runove, jer `TruncateAndReloadPostsAsync`
  učitava `htap.Posts` iz `cs.Posts`.
- Kašnjenje svježine mjeri se nad `Comments` redovima jer je `Votes.CreationDate`
  tipa `DATE`. Rezolucija je 1 s (`DATETIME2(0)`) — dovoljna za intervale reda
  sekunde, ali ne za sub-sekundne.
- Na kraju eksperimenta pokrenuti `EXEC htap.usp_SyncMaintenance;` — propagirani pa
  obrisani redovi ostavljaju delete bitmap i nekompresirane row groupe u columnstore
  indeksima.
