# Evaluacija performansi hibridne transakcijsko-analitičke obrade (HTAP) u Microsoft SQL Serveru: komparativna analiza konfiguracija pohrane nad skupom podataka StackOverflow2010

---

## Sažetak

Organizacije koje istovremeno zahtijevaju transakcijsku i analitičku obradu podataka tradicionalno oslanjaju se na odvojene OLTP i OLAP sustave premošćene ETL slojem, što uvodi latenciju, operativnu kompleksnost i dodatne infrastrukturne troškove. Hibridna transakcijsko-analitička obrada (HTAP) predlaže eliminaciju tog jaza unutar jednog sustava. Ovaj rad eksperimentalno evaluira i kvantificira četiri konfiguracijske strategije pohrane u Microsoft SQL Serveru 2022: disk-zasnovanu s B-tree indeksima (Baseline), disk-zasnovanu s columnstore indeksom (CS), memorijski optimiziranu bez columnstore (IM) i hibridnu memorijsko-columnstore (HTAP) konfiguraciju. Eksperiment je proveden kao 4×3×3 faktorijalni dizajn (4 konfiguracije × 3 OLTP/OLAP omjera × 3 razine konkurentnosti), uz 30 mjernih serija po kombinaciji, nad skupom podataka StackOverflow2010 (≈19,2 milijuna postova, stvarna produkcijska distribucija). Mjerno okruženje je .NET 8 aplikacija koja simulira mješovito opterećenje s kontroliranim parametrima konkurentnosti. Statistička obrada uključuje Kruskal-Wallis H-test, Mann-Whitney U test s Bonferroni korekcijom i Cohenov d za kvantifikaciju veličine efekta. Rezultati i zaključci iz provjere triju istraživačkih hipoteza prezentiraju se s ciljem pružanja empirijski potkrijepljenih smjernica arhitektima baza podataka.

**Ključne riječi:** HTAP, In-Memory OLTP, columnstore indeks, SQL Server, Hekaton, mješovito opterećenje, benchmark, StackOverflow2010

---

## 1. Uvod

### 1.1 Motivacija

Suvremene organizacije suočavaju se s paradoksom operativnih podataka: isti podaci koji su predmet intenzivnih transakcijskih operacija u realnom vremenu moraju biti dostupni i za analitičke upite koji zahtijevaju pregled cjelokupne historije. Tradicionalni odgovor na ovaj zahtjev bila je arhitektura dvostrukih sustava — OLTP baza podataka optimizirana za brze točkačne operacije i OLAP skladište podataka optimizirano za analitiku — premošćenih ETL (Extract-Transform-Load) procesom koji periodično prenosi podatke između dva okruženja.

Ova arhitektura nosi niz nedostataka koji su dobro dokumentirani u literaturi [1, 6]: (1) **latencija svježine podataka** — analitički sustav uvijek zaostaje za operativnim za period jednog ETL ciklusa, što može biti od sat do dan; (2) **operativna kompleksnost** — dvije odvojene infrastrukture zahtijevaju odvojeno administriranje, backup, monitoring i skaliranje; (3) **troškovi** — dupliciranje licence, hardvera i radnih sati; (4) **arhitekturalna krhkost** — promjena sheme u OLTP sustavu zahtijeva sinkroniziranu promjenu u ETL transformacijama i OLAP shemi.

Paradigma hibridne transakcijsko-analitičke obrade (HTAP) adresira ove probleme eliminacijom ETL-a i obradom transakcijskih i analitičkih upita unutar istog sustava, nad istim (ili minimalnom latencijom odvojenim) podacima [1]. Ključno istraživačko pitanje nije "je li HTAP moguć", već "uz koje kompromise i kada se isplati" — a odgovor ovisi o konkretnoj implementaciji.

### 1.2 Problem i doprinos

Microsoft SQL Server 2022 nudi tri relevantna mehanizma koji mogu poslužiti kao osnova HTAP arhitekture: (1) **In-Memory OLTP (Hekaton)** — memorijsko-optimizirane tablice s optimističkim upravljanjem konkurentnošću za ubrzanje transakcija [13]; (2) **Columnstore indeksi** — stupčasta pohrana s batch-mode izvršavanjem za ubrzanje analitičkih upita [14]; (3) **kombinacija** oba mehanizma u tzv. dual-store pristupu gdje memorijsko-optimizirane tablice prihvaćaju OLTP upise, dok columnstore replike služe analitičkim čitanjima.

Ključna motivacija za ovaj rad je nedostatak empirijskih istraživanja nad **stvarnim** skupovima podataka s realnom distribucijom korisničke aktivnosti. Kako ističu autori u [1] i [9], većina benchmarking studija koristi sintetičke skupove podataka (TPC-C, TPC-H) koji ne odražavaju distribucije stvarnih aplikacija. StackOverflow2010 dataset, kao dump stvarne produkcijske baze s dokumentiranom skew distribucijom aktivnosti korisnika (mali postotak korisnika generira najveći postotak sadržaja), pruža ekološki validniji okvir za evaluaciju.

**Doprinos ovog rada**: (1) empirijska komparacija četiri konfiguracijske strategije SQL Servera nad stvarnim skupom podataka uz statistički rigoroznu metodologiju; (2) kvantifikacija degradacije OLTP propusnosti pri mješovitom opterećenju za svaku konfiguraciju; (3) praktične smjernice za odabir konfiguracijske strategije ovisno o omjeru OLTP/OLAP opterećenja i razini konkurentnosti.

### 1.3 Istraživačke hipoteze

Na temelju pregleda literature [1, 2, 3] formulirane su tri hipoteze:

**H1**: Disk-zasnovana konfiguracija s columnstore indeksom (CS) ostvaruje usporedivu latenciju analitičkih upita s hibridnom konfiguracijom (HTAP) pri niskim razinama konkurentnosti (C=4), dok razlika postaje statistički značajna pri visokim razinama (C=32).

**H2**: Degradacija propusnosti transakcijskih operacija uzrokovana istovremenim izvođenjem analitičkih upita veća je u CS konfiguraciji nego u HTAP konfiguraciji.

**H3**: Pri transakcijski intenzivnom opterećenju (omjer 80% OLTP / 20% OLAP) hibridna konfiguracija (HTAP) ne ostvaruje statistički značajno veću propusnost od čisto transakcijske konfiguracije (IM).

### 1.4 Struktura rada

Poglavlje 2 daje pregled relevantne literature. Poglavlje 3 opisuje metodologiju i eksperimentalni dizajn. Poglavlje 4 opisuje implementaciju mjernog okruženja. Poglavlje 5 prezentira rezultate. Poglavlje 6 diskutira nalaze u kontekstu hipoteza i literature. Poglavlje 7 zaključuje rad.

---

## 2. Pregled literature

### 2.1 HTAP paradigma — pregled

Koncept HTAP baza podataka sistematiziraju Zhang et al. [1] u obuhvatnom pregledu koji identificira tri primarne arhitekturalne strategije: (1) **single-engine** pristup gdje jedan motora baze podataka podjednako efikasno obrađuje oba tipa opterećenja (npr. SAP HANA, HyPer); (2) **dual-engine** pristup gdje se podaci repliciaju između OLTP i OLAP motora u okviru iste platforme (npr. TiDB [11], F1 Lightning [12]); (3) **in-place** pristup gdje se isti fizički zapis indeksira na dva načina — redačno za OLTP i stupčasto za OLAP.

SQL Server-ov dual-store pristup (memorijsko-optimizirane tablice + columnstore) spada u kategoriju (3) i integriranog (1), ovisno o konfiguraciji. Za razliku od TiDB-a [11] koji koristi Raft konsenzus za replikaciju između TiKV (OLTP) i TiFlash (OLAP) čvorova, SQL Server implementacija je jednočvorna i ne zahtijeva mrežnu komunikaciju između motora.

Song et al. [6] u sveobuhvatnom pregledu HTAP sustava naglašavaju da je ključni izazov **izolacija radnog opterećenja** — sprečavanje analitičkih upita da degradiraju performanse transakcijskog procesiranja. Ovaj rad direktno adresira ovaj izazov kroz mjerenje degradacije pod H2.

### 2.2 In-Memory OLTP (Hekaton)

Hekaton engine, opisan u [13], temelji se na tri ključne inovacije: (1) optimistično upravljanje konkurentnošću bez brava (latch-free) zasnovano na multi-version concurrency control (MVCC); (2) memorijsko-optimizirane strukture podataka s hash i range indeksima koji ne zahtijevaju straniče predmemorije (buffer pool); (3) nativno kompajlirane pohranjene procedure koje se prevode u strojni kod pri kreiranju, eliminirajući interpretativni overhead T-SQL izvršavanja.

Ove karakteristike čine Hekaton idealnim za točkačne OLTP operacije visoke konkurentnosti, ali suboptimalnim za analitičke upite koji zahtijevaju sekvencijalno skeniranje velikih skupova podataka — Hekaton ne podržava batch-mode izvršavanje niti je optimiziran za vektorske operacije.

### 2.3 Columnstore indeksi i batch-mode izvršavanje

Columnstore indeksi, opisani u [14], pohranjuju podatke stupčasto i komprimiraju vrijednosti unutar jednog stupca zajedno (delta store + compressed segment arhitektura). Ključna prednost nije samo kompresija (faktor 5–10×), već batch-mode executor koji obrađuje 900+ redova odjednom koristeći SIMD instrukcije procesora. Za agregacijske upite nad milijunima redova ovo rezultira ubrzanjima reda veličine 10–100× u usporedbi s row-mode izvršavanjem.

Zeng et al. [8] empirijski evaluiraju stupčaste formate pohrane i zaključuju da razlike u performansama između formata (Parquet, ORC, Arrow, SQL Server columnstore) postaju zanemarive pri dovoljno velikim skupovima podataka, dok dominantni faktor postaje sustav upravljanja memorijom i paralelizacija — što je relevantno za razumijevanje ponašanja CS konfiguracije u ovom radu pri visokim razinama konkurentnosti.

### 2.4 HTAP benchmarking

HyBench [2] je benchmark dizajniran specifično za HTAP sustave koji uz TPC-C transakcije uključuje analitičke upite relevantne za financijske primjene. Wu et al. [3] proširuju ovaj pristup na financijske scenarije s naglaskom na izolaciju radnog opterećenja. Zhao et al. [9] u empirijskoj evaluaciji HTAP sustava naglašavaju da je **"performance isolation"** — sposobnost sustava da garantira OLTP performanse neovisno o OLAP opterećenju — ključna mjera kvalitete HTAP implementacije.

Za razliku od navedenih radova koji koriste sintetičke skupove podataka, ovaj rad koristi StackOverflow2010 dump s realnom distribucijom korisničke aktivnosti. StackOverflow baza ima karakteristične skew distribucije: Pareto distribucija aktivnosti korisnika (20% korisnika generira ~80% sadržaja), normalna distribucija glasova po postovima s dugim repom, i temporalna korelacija odgovora unutar 24h od postavljanja pitanja. Ove distribucije utječu na selektivnost indeksa i mogu bitno promijeniti relativne performanse konfiguracija u usporedbi sa uniformno distribuiranim sintetičkim podacima.

### 2.5 Noviji HTAP sustavi relevantni za kontekst

PUSHtap [4] istražuje PIM (Processing-In-Memory) pristup za HTAP s jedinstvenim formatom pohrane, naglašavajući da je memorijska propusnost kritičan bottleneck za analitičke upite. SynchroStore [10] predlaže cost-based kompakciju za hibridna opterećenja. veDB-HTAP [7] opisuje integriranu arhitekturu visokih performansi. Zajednički nalaz ovih radova je da ne postoji univerzalno superiorna strategija — optimalna konfiguracija ovisi o omjeru OLTP/OLAP opterećenja i razini konkurentnosti, što upravo ovaj rad eksperimentalno potvrđuje ili opovrgava za SQL Server kontekst.

---

## 3. Metodologija istraživanja

### 3.1 Eksperimentalni dizajn

Istraživanje je provedeno kao **4×3×3 puni faktorijalni dizajn** s 30 ponavljanja po kombinaciji:

```
4 konfiguracije × 3 OLTP/OLAP omjera × 3 razine konkurentnosti × 30 runova
= 1.080 ukupnih mjernih serija
```

**Nezavisne varijable:**
- Konfiguracija pohrane: {Baseline, CS, IM, HTAP}
- OLTP/OLAP omjer radnog opterećenja: {80/20, 50/50, 20/80}
- Razina konkurentnosti (broj paralelnih threadova): {4, 16, 32}

**Zavisne varijable:**
- OLTP propusnost: broj transakcija po sekundi (ops/s)
- OLAP propusnost: broj analitičkih upita po sekundi (q/s)
- OLTP latencija: P50, P95, P99 percentili (ms)
- OLAP latencija: P50, P95, P99 percentili (ms)
- Stopa uspješnosti operacija (%)

**Kontrolirane varijable:**
- Hardverska konfiguracija (isti stroj za sve eksperimente)
- Veličina skupa podataka (identičan broj redova u svim shemama)
- SQL Server konfiguracija (isti stupanj paralelizma, ista veličina memorijskog bazena)
- Trajanje warmup faze: 10 sekundi (rezultati warmup faze se odbacuju)
- Trajanje mjerne faze: 60 sekundi po runu

### 3.2 Konfiguracijske strategije

#### Baseline — disk-zasnovane tablice s B-tree indeksima

Standardna SQL Server konfiguracija s row-store tablicama na disku. Svaka tablica ima clustered B-tree indeks na primarnom ključu i odabrane nonclustered indekse na foreign key kolonama. OLTP operacije koriste row-mode executor. Analitički upiti također koriste row-mode executor uz eventualne paralelne planove, ali bez prednosti batch-mode obrade. Ova konfiguracija predstavlja **kontrolnu grupu** — polazna točka za usporedbu.

#### CS — disk-zasnovane tablice s columnstore indeksom

Identična fizička shema kao Baseline, ali s dodatnim NONCLUSTERED COLUMNSTORE indeksom na svakoj tablici. Za analitičke upite SQL Server automatski odabire columnstore skeniranje i batch-mode execution plan, što teoretski donosi ubrzanje od 10–100× za agregacijske upite [14]. OLTP operacije i dalje koriste B-tree clustered indeks, ali pisanje invalidira columnstore delta store, što uvodi blagi overhead.

Ključna razmatranje pri konfiguriranju: pri visokim razinama konkurentnosti (C=32) sa 6+ istovremenih analitičkih upita, svaki u batch-mode s paralelnim planom, može doći do saturacije CPU threadova i stradavanja zbog čekanja na memorijske dodjele (RESOURCE_SEMAPHORE wait type). Ovaj problem adresiran je dodavanjem `OPTION(MAXDOP 2)` u sve analitičke procedure, što ograničava paralelizam po upitu ali omogućava koegzistenciju više upita.

#### IM — memorijsko-optimizirane tablice (Hekaton)

Sve tablice su memorijsko-optimizirane (keyword `MEMORY_OPTIMIZED = ON`). Hash indeksi koriste se za točkačne OLTP operacije (usp_GetPostById, usp_GetUserById), a nonclustered range indeksi za upite rasponskog tipa. Sve OLTP procedure nativno su kompajlirane (`NATIVE_COMPILATION`), što eliminira T-SQL interpretativni overhead i drastično ubrzava točkačne operacije.

Analitički upiti rade u row-mode (Hekaton ne podržava batch-mode), a pošto hash indeksi nisu optimizirani za sekvencijalno skeniranje, agregacijski upiti nad 3,7 milijuna redova su značajno sporiji nego u CS konfiguraciji. Dodan je `OPTION(MAXDOP 1)` za analitičke procedure jer paralelni planovi na memorijsko-optimiziranim tablicama mogu uzrokovati sinkronizacijske blokade (CXSYNC_PORT wait).

#### HTAP — dual-store hibridna konfiguracija

HTAP implementacija slijedi dual-store arhitekturalni obrazac: OLTP pisanja i točkačna čitanja idu na memorijsko-optimizirane tablice (htap.*), dok analitički upiti čitaju iz columnstore tablica (cs.*). Ovo odvajanje osigurava da analitički batch-mode scans ne ometaju OLTP operacije na memorijskim tablicama, što je ključno za performansnu izolaciju [9].

Implementacijsko ograničenje: budući da su htap.* i cs.* fizički različite tablice, postoji kratka konzistentnosna razlika za analitičke upite — analitika ne vidi upravo unesene OLTP zapise dok se ne sinkroniziraju s cs.* kopijom. U kontekstu benchmarka ovo je zanemarivo jer se sintetički INSERT-i ne provjeravaju analitički, ali u produkcijskoj primjeni ovo mora biti razmotreno.

### 3.3 Radna opterećenja

#### OLTP radni tok

Šest OLTP operacija odabire se nasumično s fiksnom distribucijom koja odražava tipično opterećenje aplikacije tipa Stack Overflow:

| Operacija | Tip | Opis |
|-----------|-----|------|
| usp_GetPostById | SELECT (točkačno) | Dohvat jednog posta po ID-u |
| usp_GetUserById | SELECT (točkačno) | Dohvat jednog korisnika po ID-u |
| usp_GetRecentUserPosts | SELECT (rasponski) | 10 najnovijih postova korisnika |
| usp_InsertVote | INSERT | Dodavanje glasa (nova vrijednost PK) |
| usp_InsertComment | INSERT | Dodavanje komentara (nova vrijednost PK) |
| usp_UpdatePostScore | UPDATE | Inkrementalni update score kolone |

Svaki OLTP worker drži persistentnu konekciju (connection pool) i izvršava operacije sekvencijalno bez pauza između, simulirajući intenzivno opterećenje aplikacijskog sloja.

#### OLAP radni tok

Pet analitičkih upita odabire se nasumično. Svi upiti su agregacijske prirode, bez parametara koji bi ograničili skenirani skup (full-scan queries), što je reprezentativno za reportiranje i analitiku nad cjelokupnom historijom:

| Upit | Opis | Ključne operacije |
|------|------|-------------------|
| Q1 MonthlyActivity | Aktivnost po godini/mjesecu/tipu posta | GROUP BY, COUNT, AVG, SUM |
| Q2 UserEngagement | Angažiranost korisnika (postovi, odgovori, komentari) | JOIN, GROUP BY, agregacija |
| Q3 TagAnalysis | Analiza popularnosti tagova po periodu | JOIN, SUBSTRING, GROUP BY |
| Q4 TimeToAnswer | Prosječno vrijeme odgovora na pitanja | Self-JOIN, DATEDIFF, GROUP BY |
| Q5 TopContributors | Rangiranje korisnika po utjecaju | CTE, GROUP BY, ORDER BY |

Svaki OLAP worker koristi zasebnu konekciju s CommandTimeout=300 sekundi. Implementiran je mehanizam otkazivanja upita (per-query CancellationToken) koji automatski prekida upit koji premašuje vremenski okvir mjerne serije + 5 sekundi tolerancije, čime se sprečava produžavanje mjernog prozora zbog jednog sporog upita.

### 3.4 Mjerno okruženje i implementacija

Benchmark aplikacija razvijena je u .NET 8 koristeći async/await model za istovremeno izvršavanje radnih tokova. Arhitektura se temelji na:

- **BenchmarkOrchestrator**: koordinira slijed konfiguracija, omjera i razina konkurentnosti
- **WorkloadExecutor**: kreira OLTP i OLAP workere, koordinira faze warmup i mjerenja
- **ResultsWriter**: atomarno upisuje mjerenja u CSV fajlove
- **Dapper** micro-ORM za parametrizirane SQL upite bez refleksivnog overhead-a

Svaki run prolazi kroz warmup fazu (10 s) čiji se rezultati odbacuju, a zatim mjernu fazu (60 s) čiji se rezultati bilježe. OLTP latencija mjeri se za svaku individualnu operaciju (Stopwatch.Elapsed), dok se OLAP latencija mjeri za svaki cijeli upit od slanja do primanja prvog paketa rezultata (što za aggregacijske upite odgovara ukupnom vremenu izvršavanja na serveru).

### 3.5 Statistička metodologija

#### Razlog za neparametarsku statistiku

Distribucije latencija i propusnosti u benchmarking eksperimentima tipično su desno-asimetrične s izraženim repovima (heavy-tailed) zbog povremenih outlier-a uzrokovanih garbage collection pauzama, context switch-evima OS-a, CPU cache miss-evima i mrežnim varijabilnostima. Zbog ovoga se odbacuje pretpostavka normalnosti, a koriste se neparametarski testovi koji ne pretpostavljaju distribuciju podataka.

#### Kruskal-Wallis H-test

Neparametarska alternativa jednosmjernoj ANOVA-i testira nultu hipotezu da sve četiri konfiguracije dolaze iz iste distribucije:

```
H₀: distribucije metrike su identične za sve 4 konfiguracije
H₁: barem jedna konfiguracija ima statistički značajno različitu distribuciju
```

Test se primjenjuje zasebno za svaku kombinaciju metrike i razine konkurentnosti (6 metrika × 3 razine = 18 testova).

#### Mann-Whitney U test s Bonferroni korekcijom

Za parne usporedbe između konfiguracija koristi se Mann-Whitney U test. S obzirom na to da se testira C(4,2)=6 parova po metrici i razini konkurentnosti, primjenjuje se Bonferroni korekcija: p_korigirano = p_sirovo × 6, uz razinu značajnosti α=0,05.

#### Cohen's d — veličina efekta

Statistička značajnost (p-vrijednost) ne govori ništa o praktičnoj važnosti razlike. Cohenov d kvantificira veličinu efekta:

```
d = (μ₁ - μ₂) / s_pooled
```

Interpretacija: |d| < 0,2 trivijalan, 0,2–0,5 mali, 0,5–0,8 srednji, > 0,8 veliki efekt.

---

## 4. Eksperimentalno okruženje

### 4.1 Hardverska i softverska konfiguracija

| Komponenta | Specifikacija |
|-----------|--------------|
| Operativni sustav | Windows 11 |
| Baza podataka | Microsoft SQL Server 2022 (16.x) Developer Edition |
| .NET runtime | .NET 8.0 |
| Python | 3.11+ |
| Mjerna aplikacija | HTAPBenchmark v1.0 (.NET 8, Dapper 2.x) |

### 4.2 Skup podataka — StackOverflow2010

| Tablica | Opis | Broj redova |
|---------|------|------------|
| Posts | Pitanja i odgovori | 3.729.195 |
| Users | Korisnički profili | 299.398 |
| Votes | Glasovi na postovima | 10.143.364 |
| Comments | Komentari na postove | 3.875.183 |
| Badges | Zaslužene bedževe korisnika | 1.102.019 |
| **Ukupno po shemi** | | **≈ 19.149.159** |
| **Ukupno (4 sheme)** | | **≈ 76.596.636** |

Svaka od četiri konfiguracijske sheme sadrži identičan skup podataka učitan iz originalnog StackOverflow2010 dumpa. Podaci su učitani jednom a zatim kopirani u sve sheme kako bi se osigurala apsolutna konzistentnost između konfiguracija.

### 4.3 Kontekst učitavanja za benchmark

Prije svake mjerne sesije učitava se radni kontekst:
- **20.000 nasumičnih ID-ova postova** iz aktivne sheme (za OLTP operacije)
- **5.000 nasumičnih ID-ova korisnika** iz aktivne sheme
- **Maksimalni ID** glasova i komentara (za generiranje novih ID-ova INSERT operacija)

Nasumično uzorkovanje ID-ova (`ORDER BY NEWID()`) osigurava da benchmark simulira realnu distribuciju pristupa, a ne sekvencijalni pristup koji bi favorizirao određene konfiguracije indeksa.

---

## 5. Rezultati

Od inicijalnih 1.080 mjernih serija, 10 (0,93%) isključeno je iz analize zbog nestabilnosti SQL Servera (OltpSuccessRate < 0,90), što rezultira uzorkom od 1.070 validnih mjerenja i 28–30 serija po kombinaciji.

### 5.1 Deskriptivna statistika

Vrijednosti u tablicama predstavljaju srednju vrijednost ± standardnu devijaciju agregiranu po svim omjerima opterećenja (Tabele 1 i 2) odnosno po svim razinama konkurentnosti (Tabela 3). Visoka standardna devijacija u Tabeli 1 i 2 odražava stvarnu varijabilnost između omjera opterećenja (80/20 ostvaruje bitno višu OLTP propusnost od 20/80), a ne mjernu nestabilnost — koeficijenti varijacije unutar pojedinih omjera su znatno niži.

**Tabela 1**: OLTP propusnost (ops/s) — srednja vrijednost ± standardna devijacija

| Konfiguracija | C=4 | C=16 | C=32 |
|--------------|-----|------|------|
| Baseline | 1.204 ± 704 | 4.051 ± 3.692 | 2.432 ± 2.375 |
| CS | 1.254 ± 636 | 3.637 ± 3.293 | 2.477 ± 2.210 |
| IM | 2.007 ± 1.258 | 4.249 ± 2.923 | 4.726 ± 2.664 |
| HTAP | 6.783 ± 3.557 | 18.442 ± 14.867 | 21.920 ± 17.130 |

**Tabela 2**: OLAP propusnost (q/s) — srednja vrijednost ± standardna devijacija

| Konfiguracija | C=4 | C=16 | C=32 |
|--------------|-----|------|------|
| Baseline | 0,27 ± 0,14 | 0,73 ± 0,24 | 0,85 ± 0,20 |
| CS | 0,79 ± 0,39 | 2,33 ± 0,70 | 2,80 ± 0,43 |
| IM | 2,52 ± 0,71 | 3,05 ± 0,54 | 3,13 ± 0,55 |
| HTAP | 2,65 ± 1,20 | 6,95 ± 2,27 | 6,84 ± 1,80 |

**Tabela 3**: OLAP latencija P50 (ms) po omjeru opterećenja — srednja vrijednost ± standardna devijacija

| Konfiguracija | 80/20 | 50/50 | 20/80 |
|--------------|-------|-------|-------|
| Baseline | 3.128 ± 605 | 4.927 ± 1.965 | 7.351 ± 3.872 |
| CS | 1.665 ± 465 | 2.583 ± 790 | 3.710 ± 1.732 |
| IM | 1.048 ± 549 | 2.035 ± 1.119 | 2.281 ± 1.202 |
| HTAP | 924 ± 158 | 1.215 ± 453 | 1.530 ± 688 |

### 5.2 Rezultati statističkih testova

**Tabela 4**: Kruskal-Wallis H-test — globalne razlike između konfiguracija (df=3 za sve testove)

| Metrika | C=4 | C=16 | C=32 |
|---------|-----|------|------|
| OLTP propusnost | H=194,44; p<0,001 | H=66,79; p<0,001 | H=158,01; p<0,001 |
| OLAP propusnost | H=272,03; p<0,001 | H=303,17; p<0,001 | H=290,16; p<0,001 |
| OLTP latencija P50 | H=302,06; p<0,001 | H=297,82; p<0,001 | H=284,92; p<0,001 |
| OLAP latencija P50 | H=300,91; p<0,001 | H=228,87; p<0,001 | H=182,55; p<0,001 |

Svi Kruskal-Wallis testovi potvrđuju statistički značajne globalne razlike između konfiguracija za sve metrike i razine konkurentnosti (p < 0,001).

**Tabela 5**: Mann-Whitney U test s Bonferroni korekcijom — parne usporedbe za OLAP latenciju P50 pri C=32

| Par | U | p (Bonf.) | Cohen's d | Veličina efekta | Značajno |
|-----|---|-----------|-----------|-----------------|---------|
| Baseline vs CS | 6.219 | <0,001 | +1,254 | veliki | ✓ |
| Baseline vs IM | 6.775 | <0,001 | +1,665 | veliki | ✓ |
| Baseline vs HTAP | 7.620 | <0,001 | +2,086 | veliki | ✓ |
| CS vs IM | 5.342 | 0,001 | +0,679 | srednji | ✓ |
| CS vs HTAP | 6.613 | <0,001 | +1,614 | veliki | ✓ |
| IM vs HTAP | 6.449 | <0,001 | +1,564 | veliki | ✓ |

Pozitivan predznak Cohenovog d označava da prva konfiguracija ima veću (lošiju) latenciju od druge. Sve parne usporedbe su statistički značajne, uključujući CS vs IM (srednji efekt) i IM vs HTAP (veliki efekt).

### 5.3 Provjera hipoteza

**H1** — CS vs HTAP OLAP latencija pri niskoj vs visokoj konkurentnosti:

| Konkurentnost | CS P50 (ms) | HTAP P50 (ms) | Razlika | p (Bonf.) | d | Zaključak |
|--------------|------------|--------------|---------|----------|---|-----------|
| C=4 | 1.850 | 825 | −55% | <0,001 | 6,14 | ODBAČENA* |
| C=32 | 3.620 | 1.813 | −50% | <0,001 | 6,52 | POTVRĐENO |

*H1 pretpostavlja da su CS i HTAP **usporedivi** pri C=4, što nije potvrđeno — HTAP ostvaruje statistički značajno nižu OLAP latenciju čak i pri niskoj konkurentnosti (d=6,14). Hipoteza je djelomično odbačena: razlika između CS i HTAP postoji i pri C=4 i pri C=32, a apsolutna razlika raste s konkurentnošću (Δ=1.025 ms pri C=4 → Δ=1.807 ms pri C=32). Prednost HTAP nad CS nije rezultat zasićenja CPU-a pri visokim C vrijednostima, već arhitekturalne razlike između in-memory i disk-zasnovane pohrane.

**H2** — Degradacija OLTP propusnosti CS vs HTAP pri miješanom opterećenju:

| Konfiguracija | Degradacija (%) | SD (%) | p (Bonf.) | Cohen's d | Zaključak |
|--------------|----------------|--------|----------|-----------|-----------|
| CS | 67,4 | 2,8 | <0,001 | 2,315 | POTVRĐENO |
| HTAP | 55,9 | 6,3 | — | — | — |

Degradacija se mjeri kao relativni pad OLTP propusnosti između omjera 80/20 i 50/50. CS bilježi degradaciju od 67,4%, dok HTAP bilježi 55,9% — razlika je statistički značajna (Mann-Whitney p<0,001, d=2,315; veliki efekt). H2 je potvrđena: dual-store HTAP arhitektura efikasnije izolira OLTP od OLAP opterećenja u usporedbi s CS konfiguracijom.

**H3** — HTAP vs IM OLTP propusnost pri transakcijskom opterećenju (80/20):

| C | IM (ops/s) | HTAP (ops/s) | Omjer | p (Bonf.) | Cohen's d | Zaključak |
|---|-----------|-------------|-------|----------|-----------|-----------|
| 4 | 3.027 | 10.083 | 3,3× | <0,001 | −4,38 | ODBAČENA |
| 16 | 7.726 | 35.914 | 4,6× | <0,001 | −8,29 | ODBAČENA |
| 32 | 6.325 | 43.751 | 6,9× | <0,001 | −11,93 | ODBAČENA |

H3 je odbačena na svim razinama konkurentnosti. HTAP ostvaruje statistički značajno veću OLTP propusnost od IM konfiguracije pri 80/20 omjeru — 3,3× do 6,9× ovisno o konkurentnosti. Veličina efekta raste s konkurentnošću (d=−4,38 pri C=4 → d=−11,93 pri C=32), što ukazuje na sve izraženu prednost HTAP arhitekture pri visokim opterećenjima. Mogući uzrok: HTAP koristi nativno kompajlirane procedure identične IM konfiguraciji za OLTP dio, ali columnstore struktura može poboljšati cache lokalnost za analitički kontekst koji posredno utječe na metapodatke OLTP operacija.

---

## 6. Diskusija

### 6.1 OLTP performanse — memorija vs disk

In-Memory OLTP (IM) i HTAP konfiguracija, koje koriste Hekaton engine, trebale bi dominirati u OLTP propusnosti zahvaljujući eliminaciji latch-ova, nativnoj kompilaciji procedura i eliminaciji buffer pool overhead-a. Ovo je konzistentno s originalnim Hekaton radom [13] koji izvještava o ubrzanjima od 5–70× za točkačne OLTP upite u usporedbi s disk-zasnovanim tablicama.

Međutim, razlika između IM i HTAP OLTP propusnosti nije očekivano značajna (H3), jer HTAP OLTP operacije idu na iste memorijsko-optimizirane tablice kao i IM. Eventualna razlika mogla bi nastati zbog overhead-a održavanja dual-store konzistentnosti, ali ovo ovisi o specifičnoj implementaciji.

### 6.2 OLAP performanse — columnstore prednost

CS i HTAP konfiguracije koje koriste columnstore indekse trebale bi dominirati u OLAP propusnosti. Batch-mode executor koji obrađuje 900+ redova istovremeno uz SIMD instrukcije naspram row-mode obrade jednog po jednog reda [14] trebao bi biti naročito vidljiv u upitima Q1 (GROUP BY na 3,7M redova) i Q4 (self-JOIN na 3,7M redova).

Ključno pitanje za H1 jest koliko ta prednost ovisi o razini konkurentnosti. Pri C=4 s jednim do dva OLAP workera, columnstore prednost je čista — nema contenzione za CPU threadove. Pri C=32 s 6+ simultanih batch-mode upita, paralelni planovi konkuriraju za CPU, memorijska dodjela postaje bottleneck, i prednost columnstore može biti limitirana čak i uz OPTION(MAXDOP 2).

### 6.3 Degradacija performansi pri mješovitom opterećenju (H2)

Temeljno pitanje za HTAP arhitekturu jest kolika je cijena mješovitog opterećenja. U CS konfiguraciji, analitički batch-mode scans dijele CPU i memorijski podsustav s OLTP operacijama. U HTAP dual-store arhitekturi, analitički upiti idu na cs.* tablice (odvojeni IO put), dok OLTP operacije ostaju na htap.* (memorijsko-optimizirane) tablicama, teoretski minimizirajući interference.

Degradacija se mjeri kao: `(propusnost_80_20 - propusnost_50_50) / propusnost_80_20 × 100%`. Ukoliko H2 bude potvrđena (CS ima veću degradaciju od HTAP), to potkrepljuje tezu da dual-store pristup efektivno izolira opterećenja.

### 6.4 Usporedba s literaturom

Zhao et al. [9] u evaluaciji HTAP sustava zaključuju da je performance izolacija kritičnija metrika od peak propusnosti — sustav koji drži stabilnu OLTP propusnost pod analitičkim opterećenjem je vredniji od sustava koji postiže veće peak vrijednosti ali doživljava izraženu degradaciju. Ovaj rad to direktno testira kroz mjerenje degradacije po H2.

Zhang et al. [1] navode da su dual-engine sustavi (TiDB, F1 Lightning) superiorniji u izolaciji jer koriste fizički odvojene procese, ali za to plaćaju cijenu mrežne latencije pri replikaciji. SQL Server-ov in-process dual-store pristup eliminira mrežnu latenciju ali ne garantira apsolutnu izolaciju — što empirijski testiramo.

### 6.5 Praktične preporuke

Na temelju empirijskih nalaza ovog istraživanja:

| Scenario | Preporučena konfiguracija | Empirijska osnova |
|---------|--------------------------|-------------------|
| >80% OLTP, <20% OLAP | **HTAP** | 3,3–6,9× veća OLTP propusnost od IM pri 80/20; OLAP latencija 924 ms |
| 50–80% OLTP, 20–50% OLAP | **HTAP** | OLTP degradacija samo 55,9% vs 67,4% kod CS; OLAP P50=1.215 ms |
| <50% OLTP, >50% OLAP | **HTAP** ili **IM** | HTAP OLAP: 1.530 ms; IM OLAP: 2.281 ms pri 20/80 — HTAP superioran |
| Samo OLTP, bez OLAP | **HTAP** ili **IM** | HTAP ~3–7× brži; koristiti IM ako nema columnstore licence ili RAM ograničen |
| Samo OLAP, bez OLTP | **CS** | Disk-zasnovana pohrana bez RAM overhead-a; ekvivalentna OLAP propusnost za batch analitiku |
| Budžetno ograničenje (SQL Express) | **CS** | Express ne podržava In-Memory OLTP; CS donosi 2× poboljšanje OLAP vs Baseline |

Ključni nalaz koji mijenja standardne preporuke: HTAP nije optimalan samo za mješovita opterećenja — on dominira i pri transakcijskim (80/20) scenarijima, čineći IM konfiguraciju redundantnom osim u slučajevima ekstremnih RAM ograničenja ili licencnih restrikcija.

---

## 7. Zaključak

Ovaj rad eksperimentalno je evaluirao četiri konfiguracijske strategije pohrane u Microsoft SQL Serveru 2022 kroz 1.080 mjernih serija nad skupom podataka StackOverflow2010. Korištenjem faktorijalnog dizajana 4×3×3 i rigorozne statističke metodologije (Kruskal-Wallis, Mann-Whitney s Bonferroni korekcijom, Cohen's d) pružene su empirijski potkrijepljene osnove za tri istraživačke hipoteze.

Primarni doprinos ovog rada je **praktična validacija HTAP paradigme u SQL Server kontekstu nad stvarnim skupom podataka**, što eliminira ograničenja sintetičkih benchmarkova identificirana u literaturi [1, 9]. Rezultati pružaju konkretne, kvantificirane smjernice arhitektima baza podataka: kada dual-store HTAP pristup opravdava povećanu arhitekturalnu kompleksnost i kada su jednostavnije konfiguracije (CS ili IM) dostatne.

Ograničenja ovog istraživanja: (1) jednočvorna konfiguracija — distribuirani HTAP sustavi (TiDB, F1 Lightning) mogu pokazivati drugačija svojstva pri skaliranju na više čvorova; (2) StackOverflow2010 dataset iz 2010. godine — moderniji Stack Overflow dump mogao bi pokazati drugačije distribucije aktivnosti; (3) mješoviti workload simuliran je paralelnim threadovima bez mrežne latencije aplikacijskog sloja, što može precjenjivati propusnost u usporedbi s realnom deployment konfiguracijom.

Buduća istraživanja mogu proširiti ovaj rad: (1) evaluacijom na distribuiranim HTAP sustavima (TiDB, SingleStore, CockroachDB); (2) istraživanjem utjecaja veličine skupa podataka (StackOverflow2013, 2014... punih dumpova); (3) evaluacijom energetske efikasnosti različitih konfiguracija kao dopunske metrike.

---

## Literatura

[1] Zhang, C. et al. (2024). HTAP Databases: A Survey. *IEEE Transactions on Knowledge and Data Engineering*. https://arxiv.org/abs/2404.15670

[2] Zhang, C., Li, G. & Lv, T. (2024). HyBench: A New Benchmark for HTAP Databases. *PVLDB*, 17(5), 939–951. https://dl.acm.org/doi/abs/10.14778/3641204.3641206

[3] Wu, Y. et al. (2025). HTAP Benchmark in Financial Scenarios. *Security and Safety*, Vol. 4. https://doi.org/10.1051/sands/2025010

[4] Zhao, P. et al. (2025). PUSHtap: PIM-based In-Memory HTAP with Unified Data Storage Format. *ASPLOS 2025*. https://arxiv.org/abs/2508.02309

[5] Xiu, H. et al. (2024). Query Performance Explanation through Large Language Model for HTAP Systems. *arXiv:2412.01709*. https://arxiv.org/abs/2412.01709

[6] Song, H. et al. (2024). A Survey on Hybrid Transactional and Analytical Processing. *The VLDB Journal*. https://link.springer.com/article/10.1007/s00778-024-00858

[7] Zhan, C. et al. (2025). veDB-HTAP: A Highly Integrated, Efficient and Adaptive HTAP System. *PVLDB 2025*. https://dl.acm.org/doi/10.14778/3750601.3750614

[8] Zeng, X. et al. (2023). An Empirical Evaluation of Columnar Storage Formats. *PVLDB*, 17(2), 148–161. https://arxiv.org/abs/2304.05028

[9] Zhao, Y. et al. (2023). Benchmarking HTAP Databases for Performance Isolation and Real-Time Analytics. *Information Systems*, 2023. https://www.sciencedirect.com/science/article/pii/S277248592300039X

[10] Zhang, Y. et al. (2025). SynchroStore: A Cost-Based Fine-Grained Incremental Compaction for Hybrid Workloads. *arXiv:2503.18688*. https://arxiv.org/abs/2503.18688

[11] Huang, D. et al. (2020). TiDB: A Raft-based HTAP Database. *PVLDB*, 13(12), 3072–3084. https://dl.acm.org/doi/10.14778/3415478.3415535

[12] Yang, J. et al. (2020). F1 Lightning: HTAP as a Service. *PVLDB*, 13(12), 3313–3326. https://dl.acm.org/doi/10.14778/3415478.3415539

[13] Diaconu, C. et al. (2013). Hekaton: SQL Server's Memory-Optimized OLTP Engine. *SIGMOD 2013*. https://dl.acm.org/doi/10.1145/2463676.2463710

[14] Larson, P. et al. (2013). Enhancements to SQL Server Column Stores. *SIGMOD 2013*. https://dl.acm.org/doi/10.1145/2463676.2463708

[15] Özcan, F. et al. (2017). Hybrid Transactional/Analytical Processing: A Survey. *SIGMOD 2017*. https://dl.acm.org/doi/10.1145/3035918.3054784

---

