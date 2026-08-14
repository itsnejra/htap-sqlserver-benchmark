# Telfor 2026 — "Analytical Acceleration as an OLTP Optimization"

Rad od 4 stranice izveden iz projekta HTAPBenchmark. Teza: u single-engine HTAP
postavci, ubrzanje analitike je **transakcijska** optimizacija — jer analitička
skeniranja zauzimaju procesore koje bi inače koristio transakcijski engine.

Teza se dokazuje **dvjema nezavisnim polugama** nad istom konfiguracijom, uz
transakcijski sloj držan fiksnim:

| Poluga | Šta se mijenja | Dobitak u OLTP propusnosti |
|---|---|---|
| **Paralelizam** | jedan query hint (`MAXDOP 1` → `2`) | **1,21× / 2,45× / 3,61×** |
| **Smještaj** | analitika ide na columnstore kopiju | **2,76× / 1,90× / 1,92×** |

(vrijednosti za C = 4 / 16 / 32, omjer opterećenja 80/20)

Poluga paralelizma je metodološki čišća: mijenja se **jedan broj u jednom
hintu**, dok su shema, medij pohrane i model izvršavanja identični.

## Sadržaj

| Fajl | Opis |
|---|---|
| `telfor2026.tex` | Rad (IEEEtran conference, 4 str., engleski) |
| `prijevod_rada.md` | Prijevod na bosanski — samo za čitanje, ne šalje se |
| `make_figures.py` | Generira 3 figure iz `Results/` |
| `figures/` | Izlaz (PDF za LaTeX, PNG za pregled) |

## Status

**Sve brojke u radu su izmjerene.** Jedini preostali `\todonum{}` markeri su
e-mail adrese autora.

```bash
# Broji samo stvarne oznake u tekstu (ne komentar ni definiciju makroa):
grep -o '\\todonum{[^}]*}' Paper/Telfor2026/telfor2026.tex | wc -l   # trenutno 2
```

### Prijevod u citljiv format

`prijevod_rada.md` se cita i takav, ali za PDF ili Word:

```bash
cd Paper/Telfor2026
pandoc prijevod_rada.md -o prijevod_rada.docx --toc --toc-depth=2
```

Za PDF preko `pdflatex` prvo treba zamijeniti znakove koje taj engine nema
(emoji, `×`, `→`, `∈`) ili koristiti `--pdf-engine=xelatex` uz font koji ih
pokriva. Oba izlaza su generisana i nisu u git-u.

## Kako se rad kompajlira

Figure 1 i 3 traže podatke kontrolne ruke `im@d2`, koji **nisu u repou** (nastaju
lokalnim mjerenjem). Zato se prvo generišu figure, pa tek onda kompajlira:

```bash
python Paper/Telfor2026/make_figures.py
cd Paper/Telfor2026
pdflatex telfor2026 && pdflatex telfor2026
```

Ako `make_figures.py` ispiše `preskacem fig1_two_levers` ili
`preskacem fig3_cpu_evidence`, nedostaje `Results/summary_arm_d2.csv` i rad se
neće kompajlirati do kraja. Vidi niže kako se ta ruka mjeri.

## Kontrolni eksperiment

### Kako je nastao

Prva verzija rada tvrdila je jaz od 3,3–6,9× između IM i HTAP konfiguracije. Ta
usporedba je, međutim, mijenjala **dvije stvari odjednom**: smještaj analitike
i stepen paralelizma (`MAXDOP 1` na IM zbog `CXSYNC_PORT` zastoja na Hekaton
tabelama, `MAXDOP 2` na HTAP).

Kontrolni eksperiment je razdvojio ta dva člana i pokazao da je pri C = 32
**oko dvije trećine prividne arhitekturalne prednosti bila razlika u
paralelizmu**. Uz to je oborio i jedan argument iz prve verzije: nekontrolirano
jaz raste s konkurentnošću (3,33 → 6,92), a kontrolirano je ravan
(2,76 → 1,90 → 1,92). Ono što skalira jeste paralelizam, ne arhitektura.

Taj nalaz je sada dio rada — sekcija IV-C i metodološko upozorenje u zaključku.

### Kako se pokreće

```sql
-- Jednom, kreira procedure kontrolnih ruku:
sqlcmd -S . -d HTAPBenchmark -i SQL/10_MaxDopControl.sql
```

```bash
# Ruka D2: IM analitika s MAXDOP 2 (izjednačeno s HTAP) — POTREBNA za rad
dotnet run --project BenchmarkApp/HTAPBenchmark.Runner -- --arm d2 --only IM

# Ruka D1: HTAP analitika s MAXDOP 1 — recipročni smjer, nije obavezna
dotnet run --project BenchmarkApp/HTAPBenchmark.Runner -- --arm d1 --only HTAP
```

Ruke pišu u `Results/summary_arm_d2.csv` odnosno `summary_arm_d1.csv`, pod
oznakom `Configuration` = `im@d2` / `htap@d1`. Glavni `summary.csv` ostaje
netaknut.

**Trajanje.** Uz `WorkloadRatios` sužen na `[ "OLTP80_OLAP20" ]` u
`appsettings.json`: 90 runova po ruci ≈ 1,8 h.

### Status ruku

- **D2 — izmjereno i valjano.** 90/90 runova, sve iznad praga uspješnosti.
- **D1 — nije uspjelo.** Svih 90 runova ispod praga, medijan uspješnosti 0,000.
  Rad to navodi kao ograničenje (sekcija V). Vjerovatan uzrok: `htap.*` tabele
  su `SCHEMA_ONLY` i gube sadržaj pri restartu SQL Servera — provjeriti brojeve
  redova prije ponovnog pokretanja, i po potrebi učitati iz
  `SQL/05b_LoadData_CS_HTAP_Only.sql`.

## Serverska instrumentacija

Benchmark snima serverske brojače oko mjerne faze svakog runa (`CollectServerMetrics`,
uključeno po defaultu):

- **CPU po tipu radne niti** — radne veze nose `Application Name`
  (`HTAPBench-OLTP` / `HTAPBench-OLAP`), pa se `cpu_time` iz
  `sys.dm_exec_sessions` atribuira odvojeno.
- **`SOS_SCHEDULER_YIELD`** iz `sys.dm_os_wait_stats` — čekanje na dodjelu
  procesorskog kvantuma, direktan pokazatelj natjecanja za procesor.
- Uz njih: `CXPACKET`/`CXCONSUMER`, `CXSYNC_PORT`, `RESOURCE_SEMAPHORE`,
  `PAGEIOLATCH`, `WRITELOG`.

Snimanje ide preko zasebne monitor veze i traje red veličine milisekunde.
Namjerno **nije** korišten `sys.dm_exec_procedure_stats`: nativno kompajlirane
procedure ne prijavljuju statistiku bez `sp_xtp_control_proc_exec_stats`, čiji
bi overhead pao upravo u OLTP putanju koju mjerimo.

> Brojači su dostupni samo za ruku `im@d2`, jer je instrumentacija dodana nakon
> glavne kampanje. Rad to navodi kao ograničenje. Za brojke i u glavnom setu,
> trebalo bi ponoviti barem kombinaciju 80/20 × C = 32.

## Dijagnostika

Ako analiza ne vidi očekivane podatke:

```bash
python Analysis/07_diagnose_data.py
```

Ispisuje po fajlu: broj linija, broj kolona, raspodjelu po konfiguracijama i
raspodjelu stope uspješnosti, te poredi glavni set s verzijom u git-u.

> `Results/summary.csv` je u git-u (1.070 runova). Ako se lokalno pokvari — što
> se dešava ako se pokrene `--dry-run` nakon brisanja CSV-a — vraća se s
> `git checkout -- Results/summary.csv`, bez dodirivanja kontrolnih ruku.

## Prije slanja

- [ ] E-mail adrese autora (jedina preostala `\todonum{}` mjesta)
- [ ] Zamijeniti `\documentclass` linijom iz aktuelnog Telfor predloška
- [ ] Provjeriti limit od 4 stranice nakon zamjene predloška
- [ ] **Provjeriti bibliografiju** — nekoliko stavki u `Paper/refs.bib` nema
      venue ni stranice i nije potvrđeno da postoje u tom obliku. Citiranje
      nepostojećeg rada je ozbiljan prekršaj, ne formalnost.
- [ ] Razmotriti da li dodati rečenicu zašto SQL Server 2022, a ne noviji

## Alternativna tema

Iz istog projekta izvediva je i druga, nezavisna tema: *Quantifying Workload
Interference in Mixed OLTP/OLAP Configurations* — degradacija CS 67,4% vs HTAP
55,9% kroz puni faktorijalni dizajn. Ne preklapa se s ovim radom (druga
hipoteza, drugi par konfiguracija, druge figure).

> Ako se ta tema pokrene, ista MAXDOP pouka vrijedi i tamo: usporedba CS protiv
> HTAP dijeli isti `MAXDOP 2`, pa je u tom pogledu čista — ali provjeriti prije
> nego se brojke prijave.
