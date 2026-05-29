# POLITEHNIČKI FAKULTET  
## Sveučilište u Zenici

&nbsp;

&nbsp;

&nbsp;

# EVALUACIJA PERFORMANSI HIBRIDNE TRANSAKCIJSKO-ANALITIČKE OBRADE (HTAP) U MICROSOFT SQL SERVERU

## Komparativna analiza četiri konfiguracijske strategije pohrane nad skupom podataka StackOverflow2010

&nbsp;

### Projektni zadatak iz predmeta Optimizacija baza podataka

&nbsp;

&nbsp;

&nbsp;

| | |
|---|---|
| **Student:** | Nejra Smajlović |
| **Predmet:** | Optimizacija baza podataka |
| **Profesor:** | V. prof. dr. Denis Čeke |
| **Datum predaje:** | Maj 2026. |

&nbsp;

&nbsp;

---

*Zenica, 2026.*

---

&nbsp;

---

## SADRŽAJ

1. [Uvod](#1-uvod)
   - 1.1 [Motivacija i cilj istraživanja](#11-motivacija-i-cilj-istraživanja)
   - 1.2 [Doprinos rada](#12-doprinos-rada)
   - 1.3 [Hipoteze istraživanja](#13-hipoteze-istraživanja)
   - 1.4 [Struktura rada](#14-struktura-rada)
2. [Pregled dosadašnjih istraživanja](#2-pregled-dosadašnjih-istraživanja)
   - 2.1 [HTAP paradigma i arhitekturalni pristupi](#21-htap-paradigma-i-arhitekturalni-pristupi)
   - 2.2 [Komercijalne HTAP implementacije](#22-komercijalne-htap-implementacije)
   - 2.3 [In-Memory OLTP (Hekaton) u SQL Serveru](#23-in-memory-oltp-hekaton-u-sql-serveru)
   - 2.4 [Columnstore indeksi i batch-mode izvršavanje](#24-columnstore-indeksi-i-batch-mode-izvršavanje)
   - 2.5 [HTAP benchmarking — metode i alati](#25-htap-benchmarking--metode-i-alati)
   - 2.6 [Istraživačka praznina](#26-istraživačka-praznina)
3. [Metodologija istraživanja](#3-metodologija-istraživanja)
   - 3.1 [Eksperimentalni dizajn](#31-eksperimentalni-dizajn)
   - 3.2 [Konfiguracijske strategije](#32-konfiguracijske-strategije)
   - 3.3 [Radna opterećenja](#33-radna-opterećenja)
   - 3.4 [Mjerno okruženje i implementacija](#34-mjerno-okruženje-i-implementacija)
   - 3.5 [Statistička metodologija](#35-statistička-metodologija)
4. [Eksperimentalno okruženje](#4-eksperimentalno-okruženje)
   - 4.1 [Hardverska i softverska konfiguracija](#41-hardverska-i-softverska-konfiguracija)
   - 4.2 [Skup podataka — StackOverflow2010](#42-skup-podataka--stackoverflow2010)
   - 4.3 [Priprema podataka i kontekst učitavanja](#43-priprema-podataka-i-kontekst-učitavanja)
   - 4.4 [Tehnički izazovi i rješenja](#44-tehnički-izazovi-i-rješenja)
5. [Rezultati](#5-rezultati)
   - 5.1 [Deskriptivna statistika](#51-deskriptivna-statistika)
   - 5.2 [Rezultati statističkih testova](#52-rezultati-statističkih-testova)
   - 5.3 [Provjera hipoteza](#53-provjera-hipoteza)
6. [Diskusija](#6-diskusija)
   - 6.1 [OLTP performanse — memorija nasuprot disku](#61-oltp-performanse--memorija-nasuprot-disku)
   - 6.2 [OLAP performanse — prednost columnstore arhitekture](#62-olap-performanse--prednost-columnstore-arhitekture)
   - 6.3 [Degradacija pri mješovitom opterećenju](#63-degradacija-pri-mješovitom-opterećenju)
   - 6.4 [Utjecaj arhitekture na rezultate](#64-utjecaj-arhitekture-na-rezultate)
   - 6.5 [Usporedba s literaturom](#65-usporedba-s-literaturom)
   - 6.6 [Praktične preporuke](#66-praktične-preporuke)
   - 6.7 [Ograničenja istraživanja](#67-ograničenja-istraživanja)
7. [Zaključak](#7-zaključak)

[Literatura](#literatura)

---

&nbsp;

## SAŽETAK

Organizacije koje istovremeno obrađuju transakcijske i analitičke upite suočavaju se s problemom arhitekturalne podjele na OLTP i OLAP sisteme, premošćene ETL procesom koji uvodi kašnjenje i operativnu složenost. Ovaj rad ispituje četiri konfiguracijske strategije pohrane u Microsoft SQL Serveru 2022: disk-zasnovanu s B-tree indeksima (**Baseline**), disk-zasnovanu s columnstore indeksom (**CS**), memorijski optimizovanu bez columnstore (**IM**) i hibridnu dual-store konfiguraciju (**HTAP**). Eksperiment je proveden kao puni faktorijalni dizajn 4×3×3 (4 konfiguracije × 3 OLTP/OLAP omjera × 3 razine konkurentnosti), s 30 serija po kombinaciji, nad skupom podataka StackOverflow2010 (~19,2 miliona zapisa). Za statističku obradu korišteni su Kruskal-Wallis H-test, Mann-Whitney U test s Bonferroni korekcijom i Cohenov *d*. Rezultati pokazuju da HTAP dual-store konfiguracija dominira u svim scenarijima: ostvaruje 3,3–6,9× veću OLTP propusnost od IM i 8,0× bolji OLAP od Baseline, uz najniže OLAP latencije (P50 = 924 ms pri 80/20 opterećenju).

**Ključne riječi:** HTAP, In-Memory OLTP, columnstore indeks, SQL Server 2022, Hekaton, benchmark, dual-store arhitektura

---

&nbsp;

## 1. UVOD

### 1.1 Motivacija i cilj istraživanja

Savremene organizacije zahtijevaju istovremenu transakcijsku i analitičku obradu podataka. Transakcijska obrada (OLTP) zahtijeva brze točkačne operacije s niskom latencijom i visokom konkurentnošću, dok analitička obrada (OLAP) zahtijeva efikasno skeniranje velikih skupova podataka s agregacijama [1], [15]. Ovi zahtjevi su dijametralno suprotni.

Tradicionalno rješenje bila je arhitektura dvostrukih sistema: odvojene OLTP i OLAP baze, premošćene ETL procesom. Ova arhitektura ima značajne nedostatke:
- **Kašnjenje podataka** — analitički sistem zaostaje za OLTP-om za period jednog ETL ciklusa (sat do dan)
- **Operativna složenost** — dvije odvojene infrastrukture zahtijevaju odvojeno administriranje
- **Troškovi** — dupliciranje licence, hardvera i radnih sati
- **Arhitekturalna krhkost** — promjena sheme zahtijeva sinhronizovanu promjenu u ETL-u

Paradigma hibridne transakcijsko-analitičke obrade (HTAP) eliminiše ETL sloj i obrađuje oba tipa upita unutar jednog sistema, nad istim ili minimalno zakašnjelim podacima [1]. Microsoft SQL Server 2022 nudi nekoliko mehanizama za podršku ovom pristupu, a njihova empirijska usporedba nedostaje u akademskoj literaturi.

Cilj ovog rada je eksperimentalno evaluirati i usporediti četiri konfiguracijske strategije SQL Servera nad stvarnim skupom podataka, uz statički rigoroznu metodologiju.

### 1.2 Doprinos rada

Doprinos ovog rada je trostran:
1. **Empirijska komparacija** četiri konfiguracijske strategije SQL Servera nad stvarnim skupom podataka (~19,2 miliona zapisa)
2. **Kvantifikacija degradacije** OLTP propusnosti pri mješovitom opterećenju za svaku konfiguraciju
3. **Praktične smjernice** za odabir konfiguracijske strategije ovisno o omjeru opterećenja i razini konkurentnosti

### 1.3 Hipoteze istraživanja

Na osnovu pregleda literature [1], [2], [3] formulisane su tri hipoteze:

**H1:** Disk-zasnovana konfiguracija s columnstore indeksom (CS) ostvaruje usporedivu OLAP latenciju s HTAP konfiguracijom pri niskim razinama konkurentnosti (C=4), dok razlika postaje statistički značajna pri visokim razinama (C=32).

*Obrazloženje:* Pri niskom broju korisnika, batch-mode executor CS konfiguracije može iskoristiti sve raspoložive CPU threadove. Pri visokoj konkurentnosti, HTAP s odvojenim memorijskim OLTP slojem pruža bolju izolaciju.

**H2:** Degradacija OLTP propusnosti uzrokovana istovremenim analitičkim upitima veća je u CS konfiguraciji nego u HTAP konfiguraciji.

*Obrazloženje:* U CS konfiguraciji analitički batch-mode scans dijele CPU i memoriju s OLTP operacijama na istim fizičkim tablicama. U HTAP dual-store pristupu, analitički upiti čitaju iz odvojenih columnstore tablica (cs.*), dok OLTP ostaje na memorijskim tablicama (htap.*).

**H3:** Pri transakcijsko intenzivnom opterećenju (80% OLTP / 20% OLAP) HTAP konfiguracija ne ostvaruje statistički značajno veću OLTP propusnost od čisto transakcijske konfiguracije (IM).

*Obrazloženje:* Obje konfiguracije koriste identične memorijsko-optimizovane tablice i nativno kompajlirane procedure za OLTP. Overhead dual-store pristupa trebao bi biti minimalan.

### 1.4 Struktura rada

Rad je organiziran prema IMRaD strukturi [15]. Poglavlje 2 daje pregled literature i identificira istraživačku prazninu. Poglavlje 3 opisuje metodologiju i eksperimentalni dizajn. Poglavlje 4 opisuje okruženje i skup podataka. Poglavlje 5 prezentira rezultate statističke analize. Poglavlje 6 diskutira nalaze i daje preporuke. Poglavlje 7 zaključuje rad.

---

&nbsp;

## 2. PREGLED DOSADAŠNJIH ISTRAŽIVANJA

### 2.1 HTAP paradigma i arhitekturalni pristupi

Pojam HTAP (Hybrid Transactional/Analytical Processing) popularizirali su Gartner analitičari 2014. godine. Sveobuhvatni pregled Zhang et al. [1] klasificira HTAP sisteme prema tri primarne arhitekturalne strategije:

- ***Single-engine* pristup** — jedan motor obrađuje oba tipa opterećenja (SAP HANA, HyPer). Eliminiše troškove replikacije, ali zahtijeva kompromis pri dizajnu internog motora.
- ***Dual-engine* pristup** — podaci se repliciraju između OLTP i OLAP motora (TiDB [11], Google F1 Lightning [12]). Bolja izolacija, ali uvodi mrežnu latenciju i overhead replikacije.
- ***In-place* pristup** — isti fizički zapis indeksiran je na dva načina (Oracle Dual Format, SQL Server dual-store). Kompromis između prethodna dva.

Ključni izazov svakog HTAP sistema je **performansna izolacija** — sposobnost garantiranja OLTP performansi bez obzira na analitičko opterećenje [6]. Prema Song et al. [6], degradacija OLTP propusnosti veća od 30% pod analitičkim opterećenjem smatra se neprihvatljivom u produkcijskim okruženjima.

### 2.2 Komercijalne HTAP implementacije

**SAP HANA** je pionirski HTAP sistem koji kombinuje red-store i column-store unutar jednog in-memory motora [15]. Koristi MVCC za izolaciju transakcija. Ograničenje je visoka cijena memorije potrebne za pohranu cjelokupnog skupa podataka.

**TiDB** [11] koristi dual-engine pristup: TiKV (row-store za OLTP) i TiFlash (column-store za OLAP), spojene Raft konsenzus protokolom. Asinkrona replikacija uvodi kašnjenje konzistentnosti tipično ispod sekunde. TiDB-ov pristup direktno je inspirisao dual-store arhitekturu ispitivanu u ovom radu.

**Google F1 Lightning** [12] implementira Delta-Store arhitekturu — svježi podaci čuvaju se u row formatu i kompaktiraju se u column format u pozadini.

**Microsoft SQL Server 2022** implementira in-process dual-store koji eliminiše mrežnu komunikaciju između komponenti. Za razliku od TiDB-a koji koristi fizički odvojene procese, SQL Server-ov Hekaton engine i columnstore indeksi dijele isti procesni prostor.

### 2.3 In-Memory OLTP (Hekaton) u SQL Serveru

Hekaton engine, opisan u radu Diaconu et al. [13], zasnovan je na tri ključne inovacije:

1. **Optimistično upravljanje konkurentnošću bez brava (latch-free)** — zasnovano na MVCC-u; eliminiše bottleneck globalnog zaključavanja koji ograničava skalabilnost tradicionalnih sistema
2. **Memorijsko-optimizovane strukture podataka** — hash i range indeksi bez buffer pool-a; eliminiše I/O overhead i CPU cikluse za upravljanje stranicama
3. **Nativno kompajlirane pohranjene procedure** — prevode se u strojni kod pri kreiranju, eliminišući interpretativni overhead T-SQL izvršavanja

Izvorni rad [13] izvještava o ubrzanjima od 5 do 70 puta za točkačne OLTP upite. Hekaton je, međutim, suboptimalan za analitičke upite — hash indeksi nisu optimizovani za raspone i nema batch-mode izvršavanja. Važno ograničenje za ovaj rad: **SQL Server 2022 RTM ne podržava NONCLUSTERED COLUMNSTORE indeks na memorijsko-optimizovanim tablicama**. Zbog toga je korišten dual-store pristup.

### 2.4 Columnstore indeksi i batch-mode izvršavanje

Columnstore indeksi [14] pohranjuju podatke stupčasto — sve vrijednosti jednog stupca pohranjuju se zajedno u kompresovanim segmentima. To ima dvije ključne prednosti:

- **Kompresija** — faktor 5–10×, što drastično smanjuje I/O pri skeniranju
- **Batch-mode executor** — obrađuje 900+ redova istovremeno koristeći SIMD CPU instrukcije [14]; ubrzanja od 10–100× za agregacijske upite

Relevantno ograničenje pri visokim razinama konkurentnosti: s 6+ istovremenih batch-mode upita dolazi do saturacije CPU threadova i čekanja na dodjelu memorijskog prostora (RESOURCE_SEMAPHORE wait type). Ovaj problem riješen je dodavanjem OPTION(MAXDOP 2) u sve analitičke procedure.

### 2.5 HTAP benchmarking — metode i alati

**HyBench** [2] je benchmark dizajniran specifično za HTAP sisteme, koji uz TPC-C transakcije uključuje analitičke upite relevantne za finansijske primjene.

Wu et al. [3] proširuju pristup na finansijske scenarije s naglaskom na izolaciju radnog opterećenja. Ključna studija Zhao et al. [9] naglašava da je **performansna izolacija** najvažnija mjera kvalitete HTAP implementacije — ispred peak propusnosti. Autori predlažu mjeru degradacije (omjer propusnosti pri čistom OLTP nasuprot mješovitom) kao primarnu metriku, što je direktno implementirano u provjeri hipoteze H2.

Novija istraživanja proširuju benchmarking na specijalizirane arhitekture: PUSHtap [4] istražuje PIM (Processing-In-Memory) pristup, SynchroStore [10] cost-based kompakciju, veDB-HTAP [7] integrisanu arhitekturu. Zajednički zaključak: optimalna konfiguracija ovisi o omjeru opterećenja i razini konkurentnosti.

### 2.6 Istraživačka praznina

Pregledom literature identificirane su sljedeće praznine:

- Benchmarking studije [2], [3], [9] uglavnom koriste **sintetičke skupove podataka** (TPC-C, TPC-H) koji ne odražavaju asimetriju stvarnih aplikacija
- Evaluacije SQL Server-ovih specifičnih mehanizama (Hekaton + columnstore) u HTAP kontekstu su **rijetke** u akademskoj literaturi
- Ne postoje studije koje istovremeno evaluiraju sve tri razine konkurentnosti i tri omjera opterećenja uz statistički rigoroznu analizu

---

&nbsp;

## 3. METODOLOGIJA ISTRAŽIVANJA

### 3.1 Eksperimentalni dizajn

Istraživanje je provedeno kao **4×3×3 puni faktorijalni dizajn** s 30 ponavljanja po kombinaciji:

```
4 konfiguracije × 3 OLTP/OLAP omjera × 3 razine konkurentnosti × 30 runova
= 1.080 ukupnih mjernih serija
```

Puni faktorijalni dizajn odabran je jer omogućava procjenu interakcijskih efekata između faktora, posebno interakcije konfiguracija × razina konkurentnosti (relevantno za H1). Broj od 30 ponavljanja osigurava dovoljnu statističku snagu za neparametarsku analizu čak i pri izrazito asimetričnim distribucijama [2].

**Nezavisne varijable:**
- Konfiguracija pohrane: {Baseline, CS, IM, HTAP}
- OLTP/OLAP omjer radnog opterećenja: {80/20, 50/50, 20/80}
- Razina konkurentnosti (broj paralelnih radnih threadova): {C=4, C=16, C=32}

**Zavisne varijable:**
- OLTP propusnost (ops/s)
- OLAP propusnost (q/s)
- OLTP latencija: P50, P95, P99 (ms)
- OLAP latencija: P50, P95, P99 (ms)
- Stopa uspješnosti operacija (%)

**Kontrolirane varijable:** identična hardverska konfiguracija, identičan broj redova u svim shemama, warmup faza 10 s, mjerna faza 60 s po runu.

### 3.2 Konfiguracijske strategije

#### Baseline — disk-zasnovane tablice s B-tree indeksima

Standardna SQL Server konfiguracija s row-store tablicama pohranjenima na disku. Svaka tablica ima clustered B-tree indeks na primarnom ključu. OLTP i OLAP operacije koriste row-mode executor bez prednosti batch-mode obrade. Ova konfiguracija predstavlja **kontrolnu grupu** — polaznu tačku za usporedbu svih ostalih.

#### CS — disk-zasnovane tablice s nonclustered columnstore indeksom

Identična fizička shema kao Baseline, s dodatkom NONCLUSTERED COLUMNSTORE indeksa na svakoj tablici (covering columnstore). SQL Server automatski bira columnstore skeniranje i batch-mode execution plan za analitičke upite, što donosi ubrzanje 10–100× [14]. Problem saturacije CPU-a pri C=32 riješen je dodavanjem OPTION(MAXDOP 2).

#### IM — memorijsko-optimizovane tablice (Hekaton)

Sve tablice su memorijsko-optimizovane (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_ONLY). Koriste se hash indeksi za točkačne OLTP operacije i nonclustered range indeksi za rasponske upite. Sve OLTP procedure nativno su kompajlirane (NATIVE_COMPILATION). Analitički upiti rade u row-mode jer Hekaton ne podržava batch-mode. Dodan je OPTION(MAXDOP 1) za analitičke procedure zbog CXSYNC_PORT čekanja pri paralelnim planovima.

#### HTAP — dual-store hibridna konfiguracija

HTAP implementacija koristi dual-store arhitekturalni obrazac srodan TiDB/TiFlash pristupu [11]:
- **OLTP pisanja i točkačna čitanja** → memorijsko-optimizovane tablice (htap.*)
- **Analitički upiti** → columnstore tablice (cs.*)

Ovo odvajanje osigurava da analitički batch-mode scans ne ometaju OLTP operacije. Implementacijsko ograničenje: postoji konzistentnosna razlika između htap.* i cs.* — analitika ne vidi upravo unesene OLTP zapise dok se ne sinhroniziraju s cs.* kopijom. U kontekstu benchmarka ovo ne utiče na mjerene metrike.

### 3.3 Radna opterećenja

#### OLTP radni tok

Šest OLTP operacija bira se nasumično s fiksnom distribucijom koja odražava tipično opterećenje web aplikacije (65% čitanja, 35% pisanja):

| Procedura | Tip | Udio |
|-----------|-----|------|
| usp_GetPostById | SELECT točkačno | ~25% |
| usp_GetUserById | SELECT točkačno | ~20% |
| usp_GetRecentUserPosts | SELECT rasponski | ~20% |
| usp_InsertVote | INSERT | ~15% |
| usp_InsertComment | INSERT | ~10% |
| usp_UpdatePostScore | UPDATE | ~10% |

Svaki OLTP worker drži persistentnu konekciju i izvršava operacije sekvencijalno bez pauza, simulirajući intenzivno opterećenje aplikacijskog sloja.

#### OLAP radni tok

Pet analitičkih upita biraju se nasumično. Svi su agregacijske prirode bez parametara koji bi ograničili skenirani skup (full-scan queries):

| Upit | Opis | Ključne operacije |
|------|------|------------------|
| Q1 MonthlyActivity | Aktivnost po godini, mjesecu i tipu posta | GROUP BY, COUNT, AVG, SUM |
| Q2 UserEngagement | Angažiranost korisnika | JOIN, GROUP BY, agregacija |
| Q3 TagAnalysis | Popularnost tagova po periodu | JOIN, SUBSTRING, GROUP BY |
| Q4 TimeToAnswer | Prosječno vrijeme odgovora | Self-JOIN, DATEDIFF, GROUP BY |
| Q5 TopContributors | Rangiranje korisnika po utjecaju | CTE, GROUP BY, ORDER BY |

### 3.4 Mjerno okruženje i implementacija

Za razvoj benchmark aplikacije korišten je **.NET 8** sa async/await modelom za istovremeno izvršavanje OLTP i OLAP workera. Aplikacija se spaja na SQL Server i izvršava SQL upite direktno, mjereći vrijeme izvršavanja svakog upita. Za izvršavanje SQL skripti i administraciju baze podataka korišten je **SQL Server Management Studio (SSMS) 20.x**.

Arhitektura aplikacije:
- **BenchmarkOrchestrator** — koordinira slijed konfiguracija, omjera i razina konkurentnosti; implementira resume logiku
- **WorkloadExecutor** — kreira OLTP i OLAP workere, koordinira warmup i mjerne faze
- **ResultsWriter** — atomarno upisuje rezultate u CSV datoteke
- **Dapper** micro-ORM — parametrizirani SQL upiti bez refleksivnog overhead-a

Svaki run prolazi kroz warmup (10 s, rezultati se odbacuju) i mjernu fazu (60 s). OLTP latencija mjeri se za svaku individualnu operaciju korištenjem Stopwatch.Elapsed. OLAP latencija mjeri se za svaki cijeli upit od slanja do primanja prvog paketa rezultata.

### 3.5 Statistička metodologija

#### Razlog za neparametarsku statistiku

Distribucije latencija u benchmarking eksperimentima tipično su desno-asimetrične s izraženim repovima, zbog garbage collection pauza i context switch-eva OS-a. Shapiro-Wilk testom normalnosti potvrđeno je statistički značajno odstupanje od normalne distribucije (p < 0,001). Zbog toga su primijenjeni neparametarski testovi koji ne pretpostavljaju distribuciju podataka.

#### Kruskal-Wallis H-test

Kruskal-Wallis H-test (neparametarska alternativa jednosmjernoj ANOVA-i) testira da li sve četiri konfiguracije dolaze iz iste distribucije. Test se primjenjuje za svaku kombinaciju mjerne metrike i razine konkurentnosti (6 metrika × 3 razine = 18 testova). Razina značajnosti: α = 0,05.

#### Mann-Whitney U test s Bonferroni korekcijom

Za parne usporedbe između konfiguracija korišten je Mann-Whitney U test. Budući da se testira C(4,2) = 6 parova, primjenjuje se Bonferroni korekcija: α/6 ≈ 0,0083.

#### Cohen's d — veličina efekta

Cohenov *d* kvantificira veličinu efekta kao razliku sredina podijeljenu skupnom standardnom devijacijom. Interpretacija: |d| < 0,2 trivijalan, 0,2–0,5 mali, 0,5–0,8 srednji, > 0,8 veliki efekt. U kontekstu benchmarkinga, veličina efekta > 0,8 indicira razliku praktično relevantnu za arhitekturalne odluke.

---

&nbsp;

## 4. EKSPERIMENTALNO OKRUŽENJE

### 4.1 Hardverska i softverska konfiguracija

Svi eksperimenti provedeni su na istoj konfiguraciji bez izmjena između mjernih sesija:

| Komponenta | Specifikacija |
|-----------|--------------|
| RAM | 32 GB DDR4 |
| Pohrana (baseline, cs) | HDD |
| Pohrana (im, htap OLTP sloj) | RAM (memorijsko-optimizovane tablice) |
| Operativni sistem | Windows 11 |
| Baza podataka | Microsoft SQL Server 2022 Developer Edition (16.x) |
| .NET runtime | .NET 8.0 |
| Python | 3.11 |
| Mjerna aplikacija | HTAPBenchmark v1.0 (.NET 8, Dapper 2.x) |

Napomena: im.* i htap.* tablice koriste DURABILITY = SCHEMA_ONLY — podaci se ne čuvaju pri restartu SQL Servera. Ova konfiguracija odabrana je jer SCHEMA_ONLY tablice imaju manji overhead pisanja u transakcijski log, što je relevantno za reprezentativnost OLTP mjerenja.

### 4.2 Skup podataka — StackOverflow2010

StackOverflow2010 je javno dostupan dump produkcijske baze platforme Stack Overflow, koji obuhvata zapise od osnivanja 2008. do kraja 2010. godine. Ovaj skup podataka odabran je umjesto sintetičkih alternativa (TPC-C, TPC-H) jer odražava **stvarnu distribuciju korisničke aktivnosti** — asimetričnu Pareto distribuciju gdje mali postotak korisnika generiše najveći dio sadržaja [1].

| Tablica | Opis | Broj redova |
|---------|------|------------|
| Posts | Pitanja i odgovori | 3.729.195 |
| Users | Korisnički profili | 299.398 |
| Votes | Glasovi na postovima | 10.143.364 |
| Comments | Komentari na postove | 3.875.183 |
| Badges | Bedževi korisnika | 1.102.019 |
| **Ukupno po shemi** | | **≈ 19.149.159** |
| **Ukupno (4 sheme)** | | **≈ 76.596.636** |

Svaka od četiri konfiguracijske sheme sadrži identičan skup podataka. Podaci su učitani jednom u Baseline i CS sheme (disk-zasnovane), a zatim kopirani u IM i HTAP sheme (memorijsko-optimizovane). Na taj način je osigurana apsolutna konzistentnost između konfiguracija.

### 4.3 Priprema podataka i kontekst učitavanja

Prije svake mjerne sesije učitava se radni kontekst koji definiše skup entiteta s kojima će workeri operirati:
- **20.000 nasumičnih ID-ova postova** iz aktivne sheme
- **5.000 nasumičnih ID-ova korisnika** iz aktivne sheme
- **Maksimalni ID** glasova i komentara (za generisanje novih jedinstvenih ID-ova pri INSERT operacijama)

Nasumično uzorkovanje (ORDER BY NEWID()) osigurava realnu distribuciju pristupa podacima. Za memorijsko-optimizovane tablice korišten je OPTION(MAXDOP 1) u upitima za učitavanje konteksta kako bi se izbjeglo CXSYNC_PORT čekanje karakteristično za paralelne planove na Hekaton tablicama.

### 4.4 Tehnički izazovi i rješenja

Tokom implementacije benchmarka naišlo se na nekoliko tehničkih problema. Dokumentovani su jer su relevantni za razumijevanje valjanosti mjerenja.

**Problem MVCC version chain akumulacije:** Pri C=32 s 30 uzastopnih serija, brisanje svih ~3,7 miliona redova tablice Posts između kombinacija generisalo je ~7,4 miliona GC stavki po brisanju. Akumulacija je uzrokovala iscrpljenje memorije SQL Servera (OOM). **Rješenje:** umjesto brisanja svih redova, između svake serije briše se i ponovo učitava samo 20.000 aktivnih redova iz radnog konteksta — 185× manje GC posla.

**Problem TRUNCATE TABLE na memorijsko-optimizovanim tablicama:** SQL Server 2022 ne podržava TRUNCATE TABLE naredbu na ovim tablicama (Error 10794). Sve operacije čišćenja zamijenjene su selektivnim DELETE naredbama po ID-u.

**Problem nastavka od mjesta prekida:** Pri dugotrajnim benchmarkovima (> 10 sati), prekid je zahtijevao pouzdanu resume logiku. Implementovano je čitanje summary.csv u konstruktoru orkestratora **prije** otvaranja izlaznih datoteka za pisanje, čime se izbjegava nenamjerno brisanje već prikupljenih rezultata.

---

&nbsp;

## 5. REZULTATI

Od inicijalnih 1.080 planiranih serija, **10 (0,93%)** isključeno je iz analize zbog nestabilnosti mjernog okruženja (stopa uspješnosti OLTP operacija ispod 90%). Konačan uzorak broji 1.070 validnih mjerenja, s 28–30 serija po kombinaciji. Ovaj udio je unutar prihvatljivih granica za neparametarsku analizu [2].

### 5.1 Deskriptivna statistika

Vrijednosti u tablicama 1–3 prikazuju srednju vrijednost ± standardnu devijaciju. Visoka standardna devijacija u tablicama 1 i 2 odražava stvarnu varijabilnost između omjera opterećenja (80/20 ostvaruje bitno veću OLTP propusnost od 20/80), a ne mjernu nestabilnost.

**Tablica 1.** OLTP propusnost (ops/s) — srednja vrijednost ± standardna devijacija

| Konfiguracija | C=4 | C=16 | C=32 |
|:-------------|----:|-----:|-----:|
| Baseline | 1.204 ± 704 | 4.051 ± 3.692 | 2.432 ± 2.375 |
| CS | 1.254 ± 636 | 3.637 ± 3.293 | 2.477 ± 2.210 |
| IM | 2.007 ± 1.258 | 4.249 ± 2.923 | 4.726 ± 2.664 |
| **HTAP** | **6.783 ± 3.557** | **18.442 ± 14.867** | **21.920 ± 17.130** |

**Tablica 2.** OLAP propusnost (q/s) — srednja vrijednost ± standardna devijacija

| Konfiguracija | C=4 | C=16 | C=32 |
|:-------------|----:|-----:|-----:|
| Baseline | 0,27 ± 0,14 | 0,73 ± 0,24 | 0,85 ± 0,20 |
| CS | 0,79 ± 0,39 | 2,33 ± 0,70 | 2,80 ± 0,43 |
| IM | 2,52 ± 0,71 | 3,05 ± 0,54 | 3,13 ± 0,55 |
| **HTAP** | **2,65 ± 1,20** | **6,95 ± 2,27** | **6,84 ± 1,80** |

**Tablica 3.** OLAP latencija P50 (ms) po omjeru opterećenja

| Konfiguracija | 80/20 | 50/50 | 20/80 |
|:-------------|------:|------:|------:|
| Baseline | 3.128 ± 605 | 4.927 ± 1.965 | 7.351 ± 3.872 |
| CS | 1.665 ± 465 | 2.583 ± 790 | 3.710 ± 1.732 |
| IM | 1.048 ± 549 | 2.035 ± 1.119 | 2.281 ± 1.202 |
| **HTAP** | **924 ± 158** | **1.215 ± 453** | **1.530 ± 688** |

Iz Tablice 1 vidljivo je da HTAP ostvaruje dramatično veću OLTP propusnost — pri C=32 dostiže 21.920 ops/s, nasuprot 4.726 za IM, 2.477 za CS i 2.432 za Baseline. Tablica 2 pokazuje da HTAP ostvaruje 6,84 q/s pri C=32, što je poboljšanje faktora 8,0 u odnosu na Baseline. Tablica 3 potvrđuje da HTAP ima najniže OLAP latencije u svim scenarijima opterećenja.

### 5.2 Rezultati statističkih testova

**Tablica 4.** Kruskal-Wallis H-test — globalne razlike između konfiguracija (df = 3)

| Metrika | C=4 | C=16 | C=32 |
|---------|-----|------|------|
| OLTP propusnost | H=194,44; p<0,001 | H=66,79; p<0,001 | H=158,01; p<0,001 |
| OLAP propusnost | H=272,03; p<0,001 | H=303,17; p<0,001 | H=290,16; p<0,001 |
| OLTP latencija P50 | H=302,06; p<0,001 | H=297,82; p<0,001 | H=284,92; p<0,001 |
| OLAP latencija P50 | H=300,91; p<0,001 | H=228,87; p<0,001 | H=182,55; p<0,001 |

Svi Kruskal-Wallis testovi potvrđuju statistički značajne globalne razlike (p < 0,001) za sve metrike i sve razine konkurentnosti. Ovi rezultati opravdavaju provođenje parnih Mann-Whitney testova.

**Tablica 5.** Mann-Whitney U test s Bonferroni korekcijom — OLAP latencija P50, C=32

| Par | U | p (Bonf.) | Cohen's d | Efekt | Znač. |
|-----|---|-----------|-----------|-------|-------|
| Baseline vs CS | 6.219 | <0,001 | +1,254 | veliki | ✓ |
| Baseline vs IM | 6.775 | <0,001 | +1,665 | veliki | ✓ |
| Baseline vs HTAP | 7.620 | <0,001 | +2,086 | veliki | ✓ |
| CS vs IM | 5.342 | 0,001 | +0,679 | srednji | ✓ |
| CS vs HTAP | 6.613 | <0,001 | +1,614 | veliki | ✓ |
| IM vs HTAP | 6.449 | <0,001 | +1,564 | veliki | ✓ |

*Pozitivan predznak Cohenovog d označava da prva konfiguracija ima veću (lošiju) latenciju.*

Sve parne usporedbe statistički su značajne. Parovi CS vs IM i IM vs HTAP pokazuju srednji, odnosno veliki efekt, što potvrđuje praktičnu relevantnost razlika.

### 5.3 Provjera hipoteza

#### Hipoteza H1 — CS vs HTAP OLAP latencija

**Tablica 6.** Provjera H1: CS vs HTAP OLAP latencija P50

| C | CS P50 (ms) | HTAP P50 (ms) | Razlika | Cohen's d | Zaključak |
|---|----------:|-------------:|--------:|----------:|-----------|
| 4 | 1.850 | 825 | −55% | 6,14 | odbačena* |
| 32 | 3.620 | 1.813 | −50% | 6,52 | potvrđena |

**H1 je djelimično potvrđena.** HTAP ostvaruje statistički značajno nižu OLAP latenciju od CS i pri niskoj konkurentnosti (d = 6,14), što hipoteza nije pretpostavljala. Apsolutna razlika raste s konkurentnošću: Δ = 1.025 ms pri C=4 → Δ = 1.807 ms pri C=32. Prednost HTAP-a nije samo posljedica CPU saturacije pri visokom C — temelji se na fundamentalnoj arhitekturalnoj razlici između in-memory i disk-zasnovane pohrane.

#### Hipoteza H2 — Degradacija OLTP propusnosti

**Tablica 7.** Provjera H2: Degradacija OLTP propusnosti (80/20 → 50/50)

| Konfiguracija | Degradacija (%) | SD (%) | Cohen's d | Zaključak |
|:-------------|---------------:|-------:|----------:|-----------|
| CS | 67,4 | 2,8 | 2,315 | potvrđena |
| HTAP | 55,9 | 6,3 | — | — |

**H2 je potvrđena.** CS bilježi degradaciju od 67,4%, HTAP 55,9% (p < 0,001, d = 2,315). Dual-store HTAP arhitektura efikasnije izolira OLTP od analitičkog opterećenja, što potvrđuje teorijsku pretpostavku o prednostima fizičkog odvajanja OLTP i OLAP sloja pohrane.

#### Hipoteza H3 — HTAP vs IM OLTP propusnost

**Tablica 8.** Provjera H3: HTAP vs IM OLTP propusnost pri 80/20

| C | IM (ops/s) | HTAP (ops/s) | Omjer | Cohen's d | Zaključak |
|---|----------:|------------:|------:|----------:|-----------|
| 4 | 3.027 | 10.083 | 3,3× | −4,38 | odbačena |
| 16 | 7.726 | 35.914 | 4,6× | −8,29 | odbačena |
| 32 | 6.325 | 43.751 | 6,9× | −11,93 | odbačena |

**H3 je odbačena na svim razinama konkurentnosti.** HTAP ostvaruje 3,3–6,9× veću OLTP propusnost od IM, a razlika raste s konkurentnošću. Ovi rezultati proturječe polaznoj pretpostavci da konfiguracije dijele isti OLTP engine.

---

&nbsp;

## 6. DISKUSIJA

### 6.1 OLTP performanse — memorija nasuprot disku

Razlika između HTAP i Baseline pri C=32 iznosi faktor 9,0 (21.920 vs 2.432 ops/s). Ovo je konzistentno s originalnim Hekaton radom [13] koji izvještava o ubrzanjima od 5–70×. Iznenađujući nalaz je da IM ostvaruje značajno manje OLTP propusnosti od HTAP (4.726 vs 21.920 ops/s) unatoč tome što oba koriste isti Hekaton engine i iste nativno kompajlirane procedure.

Jedno moguće objašnjenje je interakcija između OLAP i OLTP workera. U IM konfiguraciji, OLAP upiti moraju skenirati sve ~3,7 miliona redova bez prednosti columnstore organizacije, što troši znatno više CPU resursa po upitu. Ta CPU saturacija direktno kompetira s OLTP workerima. U HTAP konfiguraciji, columnstore ubrzava OLAP upite 7–8×, oslobađajući CPU kapacitet za OLTP operacije. Dakle, **columnstore ubrzanje OLAP-a indirektno poboljšava i OLTP propusnost** u mješovitom opterećenju.

### 6.2 OLAP performanse — prednost columnstore arhitekture

Rezultati potvrđuju prednost columnstore pohrane: HTAP (6,84 q/s pri C=32) i CS (2,80 q/s) značajno nadmašuju Baseline (0,85 q/s) i IM (3,13 q/s).

Zanimljiv nalaz je da IM (3,13 q/s) nadmašuje CS (2,80 q/s) u OLAP propusnosti pri C=32, unatoč tome što CS ima columnstore indekse. Objašnjenje leži u kontenciji za memorijskim resursima: pri C=32 s 6+ simultanih batch-mode upita, čekanje na dodjelu memorijskog prostora (RESOURCE_SEMAPHORE) povećava ukupno vrijeme izvršavanja više nego što ga batch-mode skraćuje. IM konfiguracija, s podacima u RAM-u i bez batch-mode overhead-a, može biti efikasnija pri ovoj specifičnoj razini. Ovaj nalaz konzistentan je s Zeng et al. [8] koji naglašavaju da upravljanje memorijom postaje dominantni faktor performansi pri visokim razinama konkurentnosti.

### 6.3 Degradacija pri mješovitom opterećenju

Razlika u degradaciji (67,4% CS vs 55,9% HTAP) može izgledati skromno u postocima. U apsolutnim brojevima pri C=32, međutim, to znači razliku između gubitka 2/3 i 1/2 ukupnog OLTP kapaciteta — što je kritično u scenarijima s garantiranom razinom usluge.

Mehanizam koji stoji iza razlike je jasan: u CS konfiguraciji, analitički batch-mode scans i OLTP operacije dijele iste fizičke tablice, buffer pool i CPU threadove. U HTAP dual-store pristupu, analitički upiti idu na cs.* tablice, dok OLTP operacije koriste htap.* memorijsko-optimizovane tablice koje ne koriste buffer pool uopće. Fizička izolacija između OLTP i OLAP sloja je znatno veća.

### 6.4 Utjecaj arhitekture na rezultate

Sve četiri konfiguracije dijele iste CPU resurse, istu instancu SQL Servera i isti OS. Performansna izolacija ovisi isključivo o SQL Server-ovim internim mehanizmima raspoređivanja resursa, a ne o fizičkom odvajanju kao kod distribuiranih sistema poput TiDB-a [11].

Jednočvorna arhitektura benchmarka je i prednost i ograničenje. Prednost: eliminira mrežnu latenciju i varijabilnost, mjere se čiste performansne karakteristike. Ograničenje: ne odražava distribuirana produkcijska okruženja.

Disk I/O kao arhitekturalni bottleneck posebno je relevantan za Baseline i CS konfiguracije koje čitaju s HDD-a. Razlika između HDD i RAM brzine (~100 MB/s nasuprot ~40 GB/s) objašnjava dio prednosti HTAP nad CS pri OLAP upitima. Zamjena HDD-a SSD-om bi smanjila ovu razliku, ali ne bi promijenila fundamentalne zaključke.

### 6.5 Usporedba s literaturom

Zhao et al. [9] zaključuju da je performansna izolacija kritičnija metrika od peak propusnosti — ovaj rad to potvrđuje kroz H2. Wu et al. [3] pronalaze slične obrasce degradacije (50–70%) za disk-zasnovane sisteme, što je konzistentno s nalazima za CS konfiguraciju. Zhang et al. [1] navode da dual-engine sistemi imaju bolju izolaciju, ali plaćaju mrežnu latenciju — SQL Server-ov in-process dual-store potvrđuje ovo empirijski.

Neočekivani nalaz odbacivanja H3 (HTAP 3,3–6,9× bolji od IM) nije direktno potkrijepljen dosadašnjom literaturom. Jedan od zaključaka ovog rada je upravo to da columnstore ubrzanje OLAP-a ima pozitivan indirektan utjecaj na OLTP propusnost pri mješovitom opterećenju.

### 6.6 Praktične preporuke

Na osnovu empirijskih nalaza, formulisane su sljedeće smjernice za odabir konfiguracijske strategije u SQL Serveru 2022:

| Scenario | Preporučena konfiguracija | Empirijska osnova |
|:---------|:--------------------------|:------------------|
| >80% OLTP, <20% OLAP | **HTAP** | 3,3–6,9× veća OLTP propusnost; OLAP P50 = 924 ms |
| 50–80% OLTP, 20–50% OLAP | **HTAP** | Najniža OLTP degradacija (55,9%) i OLAP latencija |
| <50% OLTP, >50% OLAP | **HTAP** | OLAP P50 = 1.530 ms vs 3.710 ms za CS |
| Samo OLAP, bez transakcija | **CS** | Bez RAM overhead-a; 7× bolja OLAP propusnost vs Baseline |
| RAM ograničen ili SQL Express | **CS** | Express ne podržava In-Memory OLTP |

Ključni zaključak: **HTAP nije optimalan samo za mješovita opterećenja** — dominira i pri OLTP-intenzivnim scenarijima (80/20), čineći IM konfiguraciju redundantnom osim pri ekstremnim RAM ograničenjima.

### 6.7 Ograničenja istraživanja

**Jednočvorna konfiguracija.** Benchmark je proveden na jednoj instanci SQL Servera. Distribuirani HTAP sistemi (TiDB, SingleStore) mogu pokazivati drugačija skalabilna svojstva, a mrežna latencija može promijeniti relativne prednosti konfiguracija.

**Pohrana na HDD-u.** Zamjena HDD-a SSD-om ili NVMe-om bi smanjila prednost memorijsko-optimizovanih tablica za I/O-intenzivne upite. Rezultati su konzervativniji za SSD okruženja.

**Vremenski okvir skupa podataka.** StackOverflow2010 dump iz 2010. može imati drugačije distribucije od modernijeg skupa podataka.

**Konzistentnosna razlika.** Dual-store HTAP pristup ne garantira konzistentnost između htap.* i cs.* u realnom vremenu. U produkcijskim scenarijima s analitikom nad svježe unesenim podacima, ova razlika mora biti razmotrena.

---

&nbsp;

## 7. ZAKLJUČAK

Ovaj rad eksperimentalno je evaluirao četiri konfiguracijske strategije pohrane u Microsoft SQL Serveru 2022 kroz 1.070 validnih mjernih serija (od planiranih 1.080) nad skupom podataka StackOverflow2010. Korištenjem faktorijalnog dizajna 4×3×3 i neparametarskih statističkih metoda, testirane su tri istraživačke hipoteze.

**Hipoteza H1 je djelimično potvrđena.** HTAP ostvaruje statistički značajno nižu OLAP latenciju od CS ne samo pri visokoj (C=32, d = 6,52), nego i pri niskoj konkurentnosti (C=4, d = 6,14). Apsolutna razlika raste s konkurentnošću.

**Hipoteza H2 je potvrđena.** CS konfiguracija degradira OLTP propusnost za 67,4% pri mješovitom opterećenju, HTAP za 55,9% (p < 0,001, d = 2,315). Dual-store arhitektura efikasnije izolira OLTP od OLAP opterećenja.

**Hipoteza H3 je odbačena** na svim razinama konkurentnosti. HTAP ostvaruje 3,3–6,9× veću OLTP propusnost od IM, a razlika raste s konkurentnošću (d = −4,38 do −11,93).

Primarni doprinos rada je empirijska validacija HTAP paradigme u SQL Server kontekstu nad stvarnim skupom podataka, što eliminiše ograničenja sintetičkih benchmarkova identifikovana u literaturi [1], [9]. HTAP dual-store konfiguracija superiorna je u svim ispitanim scenarijima opterećenja i preporučena je za organizacije koje koriste SQL Server 2022 Developer ili Enterprise Edition uz ~8–12 GB RAM-a za memorijsko-optimizovane tablice.

Organizacije koje koriste IM konfiguraciju trebaju razmotriti migraciju na HTAP dual-store pristup koji garantuje 3–7× bolje OLTP performanse. Organizacije koje koriste CS konfiguraciju trebaju biti svjesne da mješovito opterećenje uzrokuje degradaciju od 2/3 OLTP kapaciteta.

**Smjernice za buduća istraživanja:**
- Evaluacija na distribuiranim HTAP sistemima (TiDB, SingleStore, CockroachDB)
- Istraživanje utjecaja veličine skupa podataka korištenjem novijih Stack Overflow dumpova
- Evaluacija energetske efikasnosti različitih konfiguracija
- Istraživanje automatskog tuninga — može li SQL Server dinamički birati optimalnu konfiguraciju ovisno o omjeru opterećenja

---

&nbsp;

## LITERATURA

[1] C. Zhang, J. Zhou, H. Chen, Z. Wang, and T. Li, "HTAP databases: A survey," *IEEE Trans. Knowl. Data Eng.*, 2024. [Online]. Available: https://arxiv.org/abs/2404.15670

[2] C. Zhang, G. Li, and T. Lv, "HyBench: A new benchmark for HTAP databases," *Proc. VLDB Endow.*, vol. 17, no. 5, pp. 939–951, 2024. doi: 10.14778/3641204.3641206

[3] Y. Wu et al., "HTAP benchmark in financial scenarios," *Security and Safety*, vol. 4, 2025. doi: 10.1051/sands/2025010

[4] P. Zhao et al., "PUSHtap: PIM-based in-memory HTAP with unified data storage format," in *Proc. 30th ACM ASPLOS*, 2025. [Online]. Available: https://arxiv.org/abs/2508.02309

[5] H. Xiu et al., "Query performance explanation through large language model for HTAP systems," arXiv preprint arXiv:2412.01709, 2024.

[6] H. Song, Z. Zhao, X. Ding, and R. Chen, "A survey on hybrid transactional and analytical processing," *VLDB J.*, 2024. doi: 10.1007/s00778-024-00858-x

[7] C. Zhan et al., "veDB-HTAP: A highly integrated, efficient and adaptive HTAP system," *Proc. VLDB Endow.*, 2025. doi: 10.14778/3750601.3750614

[8] X. Zeng, M. Abebe, J. Waudby, and A. Pavlo, "An empirical evaluation of columnar storage formats," *Proc. VLDB Endow.*, vol. 17, no. 2, pp. 148–161, 2023. doi: 10.14778/3626292.3626298

[9] Y. Zhao, J. Chen, Y. Wang, and X. Shi, "Benchmarking HTAP databases for performance isolation and real-time analytics," *Inf. Syst.*, 2023. doi: 10.1016/j.is.2023.102195

[10] Y. Zhang et al., "SynchroStore: A cost-based fine-grained incremental compaction for hybrid workloads," arXiv preprint arXiv:2503.18688, 2025.

[11] D. Huang et al., "TiDB: A Raft-based HTAP database," *Proc. VLDB Endow.*, vol. 13, no. 12, pp. 3072–3084, 2020. doi: 10.14778/3415478.3415535

[12] J. Yang et al., "F1 Lightning: HTAP as a service," *Proc. VLDB Endow.*, vol. 13, no. 12, pp. 3313–3326, 2020. doi: 10.14778/3415478.3415539

[13] C. Diaconu et al., "Hekaton: SQL Server's memory-optimized OLTP engine," in *Proc. ACM SIGMOD*, New York: ACM, 2013, pp. 1243–1254. doi: 10.1145/2463676.2463710

[14] P.-Å. Larson et al., "Enhancements to SQL Server column stores," in *Proc. ACM SIGMOD*, New York: ACM, 2013, pp. 1159–1170. doi: 10.1145/2463676.2463708

[15] F. Özcan, Y. Tian, and P. Tözün, "Hybrid transactional/analytical processing: A survey," in *Proc. ACM SIGMOD*, Chicago: ACM, 2017, pp. 1771–1775. doi: 10.1145/3035918.3054784

---
