# Telfor 2026 — "Analytical Acceleration as an OLTP Optimization"

Rad od 4 stranice izveden iz projekta HTAPBenchmark. Teza: u single-engine HTAP
postavci, ubrzanje analitike je **transakcijska** optimizacija — jer row-mode
skeniranje troši procesor koji bi inače koristio OLTP engine.

Dokazna osnova je kontrolirana usporedba **IM vs HTAP**: obje konfiguracije
dijele identičan Hekaton transakcijski sloj (iste tabele, isti hash indeksi,
iste nativno kompajlirane procedure, ista `SCHEMA_ONLY` durabilnost, isti
podaci) i razlikuju se **samo** po tome gdje se izvršava analitika. Ostale dvije
konfiguracije (Baseline, CS) služe kao kontekst i nisu predmet usporedbe, jer se
razlikuju i po mediju pohrane i po durabilnosti.

## Sadržaj

| Fajl | Opis |
|---|---|
| `telfor2026.tex` | Rad (IEEEtran conference, 4 str.) |
| `make_figures.py` | Generira 3 figure iz `Results/summary.csv` |
| `figures/` | PDF + PNG izlaz |

## Status brojki

Sve brojke u radu su izmjerene, **osim** onih označenih crvenim `\todonum{...}`
markerima — one čekaju MAXDOP kontrolni eksperiment i serversku instrumentaciju
opisane niže. Prije slanja rada u tekstu ne smije ostati nijedan `\todonum`:

```bash
grep -c todonum Paper/Telfor2026/telfor2026.tex   # mora biti 0
```

## Šta još treba izmjeriti

Rad tvrdi dvije stvari koje izvorni projekat nije mogao potkrijepiti. Obje se
rješavaju jednim dodatnim mjerenjem.

### 1. MAXDOP kontrolni eksperiment

**Problem:** IM analitika koristi `MAXDOP 1` (zbog `CXSYNC_PORT` čekanja na
Hekaton tabelama), a HTAP `MAXDOP 2`. Dio izmjerenog jaza od 3,3–6,9× može
poticati od stepena paralelizma, a ne od dual-store arhitekture. Recenzent
Telfora će to primijetiti — to je najranjivija tačka rada.

**Rješenje:** dvije dodatne ruke koje izjednačavaju paralelizam u oba smjera.
Ako jaz opstane u obje, MAXDOP nije uzrok i zaključak drži.

```sql
-- Jednom, u SSMS-u:
:r SQL/10_MaxDopControl.sql
```

```bash
# Ruka D2: IM analitika s MAXDOP 2 (izjednačeno s HTAP)
dotnet run --project BenchmarkApp/HTAPBenchmark.Runner -- --arm d2 --only IM

# Ruka D1: HTAP analitika s MAXDOP 1 (izjednačeno s IM)
dotnet run --project BenchmarkApp/HTAPBenchmark.Runner -- --arm d1 --only HTAP
```

Rezultati se pišu pod `Configuration` = `im@d2` odnosno `htap@d1`, u zasebne
fajlove `Results/summary_arm_d2.csv` i `Results/summary_arm_d1.csv`. Glavni
`summary.csv` ostaje netaknut (nastao je prije uvođenja kolona sa serverskim
brojačima, pa bi dopisivanje širih redova u njega proizvelo neispravan CSV).
`Analysis/06_maxdop_control.py` spaja sve fajlove automatski.

**Trajanje.** Puni set obje ruke je 2 × 3 omjera × 3 razine × 30 runova × 70 s
≈ **10,5 h**. Za rad to nije potrebno: H3 je formulirana za transakcijski
intenzivno opterećenje, pa je dovoljan omjer 80/20. Suzite `WorkloadRatios` u
`appsettings.json` na `[ "OLTP80_OLAP20" ]` → 180 runova ≈ **3,5 h**.

> Ako ruka D2 pokaže `CXSYNC_PORT` čekanje na Hekaton tabelama, to nije greška
> mjerenja nego rezultat: paralelizam nad memorijsko-optimiziranim tabelama ima
> vlastitu cijenu. Instrumentacija ga bilježi (`CxSyncPortMs`), pa se kvantificira
> umjesto da se izbjegava.

### 2. Serverska instrumentacija (dokaz mehanizma)

**Problem:** tvrdnja o CPU saturaciji bila je izvedena iz modela izvršavanja
upita, a ne mjerena.

**Rješenje:** benchmark sada snima serverske brojače oko mjerne faze svakog runa
(uključeno po defaultu, `CollectServerMetrics`):

- **CPU po tipu radne niti** — radne veze nose `Application Name`
  (`HTAPBench-OLTP` / `HTAPBench-OLAP`), pa se `cpu_time` iz
  `sys.dm_exec_sessions` atribuira odvojeno. Daje udio procesora koji analitika
  oduzima transakcijama.
- **`SOS_SCHEDULER_YIELD`** iz `sys.dm_os_wait_stats` — direktan indikator da je
  zadatak potrošio kvantum procesora i ustupio ga. Ovo je mjereni dokaz CPU
  pritiska.
- Uz njih: `CXPACKET`/`CXCONSUMER`, `CXSYNC_PORT`, `RESOURCE_SEMAPHORE`,
  `PAGEIOLATCH`, `WRITELOG`.

Snimanje ide preko zasebne monitor veze i traje red veličine milisekunde, pa ne
perturbira mjerenje. Namjerno **nije** korišten `sys.dm_exec_procedure_stats`:
nativno kompajlirane procedure ne prijavljuju statistiku bez
`sp_xtp_control_proc_exec_stats`, čije bi uključivanje unijelo overhead upravo u
OLTP putanju koju mjerimo.

> Serverski brojači se pišu kao nove kolone u summary CSV-u. Postojeći
> `summary.csv` iz glavnog eksperimenta nema te kolone; analiza to detektuje i
> preskače taj dio umjesto da padne. Da bi rad imao CPU brojke i za glavni set, taj set
> treba ponoviti — ili barem kombinaciju 80/20 × C=32 na kojoj počiva argument.

## Kompletan tok

```bash
# 1. Kontrolne procedure (jednom)
sqlcmd -S . -i SQL/10_MaxDopControl.sql

# 2. Kontrolne ruke
dotnet run --project BenchmarkApp/HTAPBenchmark.Runner -- --arm d2 --only IM
dotnet run --project BenchmarkApp/HTAPBenchmark.Runner -- --arm d1 --only HTAP

# 3. Analiza → Results/maxdop_control_report.txt
python Analysis/06_maxdop_control.py

# 4. Figure → Paper/Telfor2026/figures/
python Paper/Telfor2026/make_figures.py

# 5. Popuniti \todonum{} vrijednosti iz izvještaja i kompajlirati
cd Paper/Telfor2026
pdflatex telfor2026 && pdflatex telfor2026
```

## Prije slanja

- [ ] Zamijeniti `\documentclass` linijom iz aktuelnog Telfor predloška
- [ ] Provjeriti limit od 4 stranice nakon zamjene predloška
- [ ] `grep -c todonum telfor2026.tex` → 0
- [ ] Dopuniti bibliografiju punim podacima (neke stavke u `Paper/refs.bib` imaju
      nepotpune reference — provjeriti svaku prije slanja)
- [ ] E-mail adrese autora

## Alternativna tema

Iz istog projekta izvediva je i druga, nezavisna tema: *Quantifying Workload
Interference in Mixed OLTP/OLAP Configurations* — degradacija CS 67,4% vs HTAP
55,9% ($d = 2{,}315$) kroz puni faktorijalni dizajn. Ne preklapa se s ovim radom
(druga hipoteza, drugi par konfiguracija, druge figure), ali je deskriptivnija:
potvrđuje literaturu umjesto da je iznenađuje. Ovaj rad je jači izbor za
prihvatanje.
