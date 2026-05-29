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
   1.1 [Motivacija i kontekst istraživanja](#11-motivacija-i-kontekst-istraživanja)  
   1.2 [Problem istraživanja i doprinos](#12-problem-istraživanja-i-doprinos)  
   1.3 [Istraživačke hipoteze](#13-istraživačke-hipoteze)  
   1.4 [Struktura rada](#14-struktura-rada)

2. [Pregled dosadašnjih istraživanja](#2-pregled-dosadašnjih-istraživanja)  
   2.1 [HTAP paradigma — definicija i arhitekturalne strategije](#21-htap-paradigma--definicija-i-arhitekturalne-strategije)  
   2.2 [Komercijalne HTAP implementacije](#22-komercijalne-htap-implementacije)  
   2.3 [In-Memory OLTP (Hekaton) u SQL Serveru](#23-in-memory-oltp-hekaton-u-sql-serveru)  
   2.4 [Columnstore indeksi i batch-mode izvršavanje](#24-columnstore-indeksi-i-batch-mode-izvršavanje)  
   2.5 [HTAP benchmarking — metode i alati](#25-htap-benchmarking--metode-i-alati)  
   2.6 [Identifikacija istraživačke praznine](#26-identifikacija-istraživačke-praznine)

3. [Metodologija istraživanja](#3-metodologija-istraživanja)  
   3.1 [Eksperimentalni dizajn](#31-eksperimentalni-dizajn)  
   3.2 [Konfiguracijske strategije](#32-konfiguracijske-strategije)  
   3.3 [Radna opterećenja](#33-radna-opterećenja)  
   3.4 [Mjerno okruženje i implementacija](#34-mjerno-okruženje-i-implementacija)  
   3.5 [Statistička metodologija](#35-statistička-metodologija)

4. [Eksperimentalno okruženje](#4-eksperimentalno-okruženje)  
   4.1 [Hardverska i softverska konfiguracija](#41-hardverska-i-softverska-konfiguracija)  
   4.2 [Skup podataka — StackOverflow2010](#42-skup-podataka--stackoverflow2010)  
   4.3 [Priprema podataka i kontekst učitavanja](#43-priprema-podataka-i-kontekst-učitavanja)  
   4.4 [Tehnički izazovi i riješeni problemi](#44-tehnički-izazovi-i-riješeni-problemi)

5. [Rezultati](#5-rezultati)  
   5.1 [Deskriptivna statistika](#51-deskriptivna-statistika)  
   5.2 [Rezultati statističkih testova](#52-rezultati-statističkih-testova)  
   5.3 [Provjera hipoteza](#53-provjera-hipoteza)

6. [Diskusija](#6-diskusija)  
   6.1 [OLTP performanse — memorija nasuprot disku](#61-oltp-performanse--memorija-nasuprot-disku)  
   6.2 [OLAP performanse — prednost columnstore arhitekture](#62-olap-performanse--prednost-columnstore-arhitekture)  
   6.3 [Degradacija performansi pri mješovitom opterećenju (H2)](#63-degradacija-performansi-pri-mješovitom-opterećenju-h2)  
   6.4 [Utjecaj arhitekture sustava na rezultate](#64-utjecaj-arhitekture-sustava-na-rezultate)  
   6.5 [Usporedba s dosadašnjim istraživanjima](#65-usporedba-s-dosadašnjim-istraživanjima)  
   6.6 [Praktične preporuke za arhitekte baza podataka](#66-praktične-preporuke-za-arhitekte-baza-podataka)  
   6.7 [Ograničenja istraživanja](#67-ograničenja-istraživanja)

7. [Zaključak](#7-zaključak)

[Literatura](#literatura)

---

&nbsp;

## Sažetak

Organizacije koje istovremeno zahtijevaju transakcijsku i analitičku obradu podataka tradicionalno se oslanjaju na odvojene OLTP i OLAP sustave premošćene ETL slojem, što uvodi latenciju svježine podataka, operativnu kompleksnost i dodatne infrastrukturne troškove. Paradigma hibridne transakcijsko-analitičke obrade (HTAP) adresira ovaj problem eliminacijom ETL procesa i obradom oba tipa upita unutar istog sustava. Ovaj rad eksperimentalno evaluira i kvantificira četiri konfiguracijske strategije pohrane u Microsoft SQL Serveru 2022: disk-zasnovanu s B-tree indeksima (Baseline), disk-zasnovanu s columnstore indeksom (CS), memorijski optimiziranu bez columnstore (IM) i hibridnu dual-store konfiguraciju (HTAP). Eksperiment je proveden kao 4×3×3 puni faktorijalni dizajn (4 konfiguracije × 3 OLTP/OLAP omjera × 3 razine konkurentnosti), uz 30 mjernih serija po kombinaciji, nad skupom podataka StackOverflow2010 s oko 19,2 milijuna zapisa koji predstavljaju stvarnu produkcijsku distribuciju. Mjerno okruženje je .NET 8 aplikacija koja simulira mješovito opterećenje s kontroliranim parametrima konkurentnosti. Statistička obrada uključuje Kruskal-Wallis H-test, Mann-Whitney U test s Bonferroni korekcijom i Cohenov *d* za kvantifikaciju veličine efekta. Rezultati pokazuju da HTAP dual-store konfiguracija dominira u svim scenarijima opterećenja — ostvaruje 3,3 do 6,9 puta veću OLTP propusnost od IM konfiguracije i 8,0 puta veću OLAP propusnost od Baseline konfiguracije, uz najniže OLAP latencije (P50 = 924 ms pri omjeru 80/20). Sve tri istraživačke hipoteze statistički su testirane, a Kruskal-Wallis testovi potvrđuju globalne razlike (p < 0,001) između svih konfiguracija za sve mjerne metrike.

**Ključne riječi:** HTAP, In-Memory OLTP, columnstore indeks, SQL Server 2022, Hekaton, mješovito opterećenje, benchmark, StackOverflow2010, dual-store arhitektura

---

&nbsp;

## 1. Uvod

### 1.1 Motivacija i kontekst istraživanja

Suvremene organizacije suočavaju se s paradoksom operativnih podataka koji je dobro dokumentiran u literaturi [1], [6]: isti podaci koji su predmet intenzivnih transakcijskih operacija u realnom vremenu moraju biti dostupni i za analitičke upite koji zahtijevaju pregled cjelokupne historije. Transakcijska obrada (OLTP) i analitička obrada (OLAP) postavljaju dijametralno suprotne zahtjeve na arhitekturu sustava za upravljanje bazama podataka — OLTP zahtijeva brze točkačne operacije (INSERT, UPDATE, SELECT po primarnom ključu) s niskom latencijom i visokom konkurentnošću, dok OLAP zahtijeva učinkovito skeniranje velikih skupova podataka s agregacijama i složenim spojevima tablica [15].

Tradicionalni odgovor na ove suprotstavljene zahtjeve bila je arhitektura dvostrukih sustava: OLTP baza podataka optimizirana za transakcije i OLAP skladište podataka optimizirano za analitiku, premošćeni ETL (Extract-Transform-Load) procesom koji periodično prenosi podatke između dva okruženja [6]. Ova arhitektura, premda dominantna u industrijskoj primjeni, nosi niz nedostataka: (1) *latencija svježine podataka* — analitički sustav uvijek zaostaje za operativnim za period jednog ETL ciklusa, koji može trajati od sat do dan; (2) *operativna kompleksnost* — dvije odvojene infrastrukture zahtijevaju odvojeno administriranje, sigurnosno kopiranje, praćenje i skaliranje; (3) *troškovi* — dupliciranje licence, hardvera i radnih sati; (4) *arhitekturalna krhkost* — promjena sheme u OLTP sustavu zahtijeva sinkroniziranu promjenu u ETL transformacijama i OLAP shemi.

Paradigma hibridne transakcijsko-analitičke obrade (HTAP) adresira ove probleme eliminacijom ETL sloja i obradom transakcijskih i analitičkih upita unutar istog sustava, nad istim ili minimalno zakašnjelim podacima [1]. Ključno istraživačko pitanje nije "je li HTAP moguć", već "uz koje kompromise i kada se isplati" — a odgovor ovisi o konkretnoj implementaciji, vrsti opterećenja i razini konkurentnosti. Microsoft SQL Server 2022, kao jedan od vodećih komercijalnih sustava za upravljanje relacijskim bazama podataka, nudi više mehanizama koji se mogu konfigurirati za podršku HTAP scenarija, čime postaje relevantna platforma za istraživanje performansnih kompromisa ove paradigme.

### 1.2 Problem istraživanja i doprinos

Microsoft SQL Server 2022 nudi tri relevantna mehanizma koji mogu poslužiti kao osnova HTAP arhitekture: (1) *In-Memory OLTP (Hekaton)* — memorijsko-optimizirane tablice s optimističkim upravljanjem konkurentnošću za ubrzanje transakcija [13]; (2) *Columnstore indeksi* — stupčasta pohrana s batch-mode izvršavanjem za ubrzanje analitičkih upita [14]; (3) *kombinacija* oba mehanizma u tzv. dual-store pristupu, gdje memorijsko-optimizirane tablice prihvaćaju OLTP pisanja, a columnstore replike služe analitičkim čitanjima. Svaka od ovih kombinacija ima različita performansna obilježja, koja su tek djelomično opisana u dostupnoj literaturi.

Ključna motivacija za ovaj rad je nedostatak empirijskih istraživanja nad *stvarnim* skupovima podataka s realnom distribucijom korisničke aktivnosti. Kako ističu autori u [1] i [9], većina benchmarking studija koristi sintetičke skupove podataka (TPC-C, TPC-H) koji ne odražavaju distribucije stvarnih aplikacija. StackOverflow2010 dataset, kao dump stvarne produkcijske baze s dokumentiranom asimetričnom distribucijom aktivnosti korisnika (mali postotak korisnika generira najveći dio sadržaja), pruža ekološki validniji okvir za evaluaciju od sintetičkih benchmarkova.

Doprinos ovog rada trostran je: (1) empirijska komparacija četiri konfiguracijske strategije SQL Servera nad stvarnim skupom podataka uz statistički rigoroznu metodologiju; (2) kvantifikacija degradacije OLTP propusnosti pri mješovitom opterećenju za svaku konfiguraciju, što izravno adresira problem performansne izolacije identificiran u [9]; (3) praktične smjernice za odabir konfiguracijske strategije ovisno o omjeru OLTP/OLAP opterećenja i razini konkurentnosti.

### 1.3 Istraživačke hipoteze

Na temelju pregleda literature [1], [2], [3] i teorijskog razmatranja karakteristika ispitivanih konfiguracija, formulirane su tri istraživačke hipoteze:

**H1:** Disk-zasnovana konfiguracija s columnstore indeksom (CS) ostvaruje usporedivu latenciju analitičkih upita s hibridnom konfiguracijom (HTAP) pri niskim razinama konkurentnosti (C=4), dok razlika postaje statistički značajna pri visokim razinama (C=32).

*Obrazloženje:* Pri niskom broju istovremenih korisnika, batch-mode executor columnstore konfiguracije teorijski može iskoristiti sve raspoložive CPU threadove, čime razlika između CS i HTAP pristupa može biti zanemariva. Pri visokom broju istovremenih korisnika, HTAP arhitektura s odvojenim memorijskim OLTP slojem može pružati bolju izolaciju analitičkih upita.

**H2:** Degradacija propusnosti transakcijskih operacija uzrokovana istovremenim izvođenjem analitičkih upita veća je u CS konfiguraciji nego u HTAP konfiguraciji.

*Obrazloženje:* U CS konfiguraciji, analitički batch-mode scans dijele CPU i memorijski podsustav s OLTP operacijama na istim fizičkim tablicama. U HTAP dual-store arhitekturi, analitički upiti čitaju iz odvojenih columnstore tablica (cs.*), dok OLTP operacije ostaju na memorijsko-optimiziranim tablicama (htap.*), što teorijski minimizira međusobnu interferenciju.

**H3:** Pri transakcijski intenzivnom opterećenju (omjer 80% OLTP / 20% OLAP) hibridna konfiguracija (HTAP) ne ostvaruje statistički značajno veću OLTP propusnost od čisto transakcijske konfiguracije s memorijsko-optimiziranim tablicama (IM).

*Obrazloženje:* HTAP OLTP operacije usmjeravaju se na iste memorijsko-optimizirane tablice kao i IM konfiguracija, koristeći identične nativno kompajlirane procedure. Overhead održavanja dual-store konzistentnosti trebao bi biti minimalan, što sugerira statističku ekvivalentnost HTAP i IM pri OLTP-intenzivnom opterećenju.

### 1.4 Struktura rada

Rad je organiziran prema IMRaD strukturi preporučenoj za empirijska istraživačka rada [15]. Poglavlje 2 daje pregled relevantne literature i identificira istraživačku prazninu koju ovaj rad popunjava. Poglavlje 3 opisuje metodologiju, eksperimentalni dizajn, konfiguracijske strategije i statističke metode. Poglavlje 4 opisuje eksperimentalno okruženje, skup podataka i tehničke detalje implementacije. Poglavlje 5 prezentira rezultate deskriptivne i inferencijalnog statistike uz provjeru hipoteza. Poglavlje 6 diskutira nalaze u kontekstu hipoteza, arhitekturalne teorije i dosadašnje literature, te daje praktične preporuke. Poglavlje 7 zaključuje rad i predlaže smjernice za buduća istraživanja.

---

&nbsp;

## 2. Pregled dosadašnjih istraživanja

### 2.1 HTAP paradigma — definicija i arhitekturalne strategije

Pojam "hibridna transakcijsko-analitička obrada" (HTAP) popularizirali su Gartner analitičari 2014. godine, a sistematizirani teorijski okvir za razumijevanje i klasifikaciju HTAP sustava pruža sveobuhvatni pregled Zhang et al. [1] iz 2024. godine. Prema toj klasifikaciji, HTAP sustavi mogu se podijeliti prema tri primarne arhitekturalne strategije: (1) *single-engine* pristup, gdje jedan motor baze podataka podjednako efikasno obrađuje oba tipa opterećenja; (2) *dual-engine* pristup, gdje se podaci repliciraju između OLTP i OLAP motora unutar iste platforme; (3) *in-place* pristup, gdje se isti fizički zapis indeksira na dva načina — redno za OLTP i stupčasto za OLAP.

Svaki od navedenih pristupa ima karakteristična performansna obilježja i kompromise. Single-engine pristup, koji zastupaju sustavi kao što su SAP HANA i HyPer, eliminirani su troškovi replikacije i konzistentnosnih protokola, ali zahtijevaju kompromis pri dizajnu internog motora koji mora efikasno podržavati oba tipa pristupa podacima. Dual-engine pristup, koji zastupaju TiDB [11] i Google F1 Lightning [12], postiže bolju performansnu izolaciju korištenjem fizički odvojenih motora, ali uvodi latenciju replikacije i dodatnu mrežnu komunikaciju između komponenti. In-place pristup, koji zastupa Oracle Dual Format i SQL Server-ov dual-store, postiže kompromis između ova dva ekstrema eliminacijom mrežne komunikacije uz zadržavanje određene razine izolacije.

Pregled Song et al. [6] dodatno naglašava da je ključni izazov svakog HTAP sustava *performansna izolacija* — sposobnost sustava da garantira OLTP performanse neovisno o analitičkom opterećenju. Ova sposobnost izravno se mjeri kroz hipotezu H2 u ovom istraživanju. Prema istim autorima, degradacija OLTP propusnosti za više od 30% pod analitičkim opterećenjem smatra se neprihvatljivom u produkcijskim scenarijima, što pruža referentnu točku za interpretaciju rezultata u Poglavlju 5.

### 2.2 Komercijalne HTAP implementacije

Pregled komercijalnih HTAP implementacija neophodan je za kontekstualizaciju SQL Server-ovog pristupa i razumijevanje industrijskih trendova koji motiviraju ovo istraživanje.

**SAP HANA** je pionirski HTAP sustav koji je popularizirao pristup pohrane podataka isključivo u memoriji, kombinirajući red-store i column-store unutar jednog motora [15]. SAP HANA koristi MVCC (Multi-Version Concurrency Control) za izolaciju transakcija i verzioniranje podataka, pri čemu analitički upiti čitaju konzistentnu snimku podataka bez blokiranja transakcijskog procesiranja. Ograničenje ovog pristupa je visoka cijena memorije potrebne za pohranu cjelokupnog skupa podataka.

**TiDB** [11] implementira dual-engine pristup koristeći TiKV (row-store za OLTP) i TiFlash (column-store za OLAP) komponente spojene Raft konsenzus protokolom za replikaciju. Asinkrona replikacija iz TiKV u TiFlash uvodi konfigurabilno kašnjenje konzistentnosti (tipično ispod sekunde za produkcijska okruženja). TiDB-ov pristup direktno je inspirirao dual-store arhitekturu ispitivanu u ovom radu.

**Google F1 Lightning** [12] pruža HTAP kao servis za Google-ove interne aplikacije, koristeći Delta-Store arhitekturu gdje se svježi podaci čuvaju u row formatu, a kompaktiraju se u column format u pozadini. Ovaj pristup minimizira utjecaj analitičkih upita na transakcijsko procesiranje korištenjem odvojenih čitačkih replikata.

**Microsoft SQL Server 2022** implementira in-process dual-store pristup koji eliminira mrežnu komunikaciju između komponenti. Za razliku od TiDB-a koji koristi fizički odvojene procese, SQL Server-ov Hekaton engine i columnstore indeksi dijele isti procesni prostor, što eliminira latenciju replikacije, ali zahtijeva pažljivije upravljanje izolacijom opterećenja. Ovo je posebno relevantno pri visokim razinama konkurentnosti (C=32), gdje contentie za memorijskim resursima može biti izražena.

### 2.3 In-Memory OLTP (Hekaton) u SQL Serveru

Hekaton engine, detaljno opisan u izvornom radu Diaconu et al. [13] iz 2013. godine, temelji se na tri ključne arhitekturalne inovacije koje ga razlikuju od standardnog SQL Server row-store motora: (1) optimistično upravljanje konkurentnošću bez brava (latch-free) zasnovano na multi-version concurrency control (MVCC), što eliminira bottleneck globalne zaključavanja koji ograničava skalabilnost tradicionalnih sustava pri visokim razinama konkurentnosti; (2) memorijsko-optimizirane strukture podataka s hash i range indeksima koji ne zahtijevaju straničenje predmemorije (buffer pool), što eliminira I/O overhead i CPU cikluse za upravljanje stranicama; (3) nativno kompajlirane pohranjene procedure koje se prevode u strojni kod pri kreiranju, eliminirajući interpretativni overhead T-SQL izvršavanja koji kod standardnih procedura iznosi 10–15% ukupnog vremena izvršavanja [13].

Navedene karakteristike čine Hekaton idealnim za točkačne OLTP operacije visoke konkurentnosti — izvorni rad [13] izvještava o ubrzanjima od 5 do 70 puta za točkačne OLTP upite u usporedbi s disk-zasnovanim tablicama, ovisno o scenariju. Međutim, Hekaton je suboptimalan za analitičke upite koji zahtijevaju sekvencijalno skeniranje velikih skupova podataka iz dva razloga: (1) hash indeksi nisu optimizirani za raspone — skeniranje N redova zahtijeva N hash lookupa; (2) Hekaton ne podržava batch-mode izvršavanje niti je optimiziran za vektorske operacije, što znači da agregacijski upiti nad milijunima redova moraju procesirati svaki red pojedinačno.

Važno implementacijsko ograničenje relevantno za ovaj rad jest da SQL Server 2022 RTM ne podržava NONCLUSTERED COLUMNSTORE indeks na memorijsko-optimiziranim tablicama. Ovaj tehnički nedostatak, dokumentiran u SQL Server 2022 Books Online, zahtijevao je dual-store pristup u HTAP konfiguraciji, gdje su OLTP tablice memorijsko-optimizirane, a OLAP tablice odvojene disk-zasnovane columnstore tablice.

### 2.4 Columnstore indeksi i batch-mode izvršavanje

Columnstore indeksi, opisani u radu Larson et al. [14], pohranjuju podatke stupčasto — sve vrijednosti jednog stupca pohranjuju se zajedno u kompresiranim segmentima, umjesto standardnog rednog pohrana gdje su sve vrijednosti jednog reda pohranjene zajedno. Ova promjena fizičke organizacije podataka ima dalekosežne implikacije za analitičke upite. Kompresija unutar jednog stupca (sve vrijednosti iste domene pohranjene zajedno) tipično postiže faktor kompresije 5 do 10 puta, što drastično smanjuje I/O pri skeniranju. Za agregacijske upite koji trebaju samo mali broj stupaca od ukupnog broja (npr. SELECT SUM(score), AVG(viewcount) FROM Posts), columnstore organizacija dramatično smanjuje količinu podataka koja se mora pročitati s diska ili iz memorije.

Ključna prednost, međutim, nije sama kompresija, već *batch-mode executor* koji omogućuje obradu 900 ili više redova istovremeno koristeći SIMD (Single Instruction, Multiple Data) CPU instrukcije [14]. Za agregacijske upite nad milijunima redova, batch-mode procesiranje postiže ubrzanja od 10 do 100 puta u usporedbi s row-mode procesiranjem, gdje se svaki red obrađuje zasebno. Empirijska evaluacija Zeng et al. [8] potvrđuje da razlike u performansama između različitih stupčastih formata pohrane (Parquet, ORC, Arrow, SQL Server columnstore) postaju zanemarive pri dovoljno velikom skupu podataka, dok dominantni faktor postaje sustav upravljanja memorijom i stupanj paralelizacije.

Relevantno ograničenje columnstore indeksa za ovaj rad jest ponašanje pri visokim razinama konkurentnosti s više istovremenih batch-mode upita. Pri C=32 s 6 ili više simultanih analitičkih upita, svaki s paralelnim planom izvršavanja, dolazi do saturacije CPU threadova i čekanja na dodjelu memorije (RESOURCE_SEMAPHORE wait type). Ovaj problem adresiran je dodavanjem OPTION(MAXDOP 2) u sve analitičke procedure, što ograničava paralelizam po upitu, ali omogućava koegzistenciju više istovremenih analitičkih upita.

### 2.5 HTAP benchmarking — metode i alati

Evaluacija HTAP sustava metodološki je zahtjevnija od evaluacije čistih OLTP ili OLAP sustava, jer zahtijeva mjerenje performansi pod mješovitim opterećenjem i kvantifikaciju uzajamnog utjecaja transakcijskog i analitičkog procesiranja. HyBench [2] je benchmark dizajniran specifično za HTAP sustave koji uz TPC-C transakcije uključuje analitičke upite relevantne za financijske primjene. Wu et al. [3] proširuju ovaj pristup na financijske scenarije s naglaskom na izolaciju radnog opterećenja pod različitim razinama konkurentnosti.

Ključna metodološka studija Zhao et al. [9] u empirijskoj evaluaciji HTAP sustava naglašava da je *"performance isolation"* — sposobnost sustava da garantira OLTP performanse neovisno o OLAP opterećenju — najvažnija mjera kvalitete HTAP implementacije, ispred peak propusnosti. Autori predlažu mjeru degradacije (omjer propusnosti pri čistom OLTP nasuprot mješovitom opterećenju) kao primarnu metriku za evaluaciju HTAP sustava, što je direktno implementirano u metodologiji provjere hipoteze H2 u ovom radu.

Novija istraživanja proširuju benchmarking na specijalizirane hardverske arhitekture. PUSHtap [4] istražuje PIM (Processing-In-Memory) pristup za HTAP s jedinstvenim formatom pohrane, naglašavajući da je memorijska propusnost kritičan bottleneck za analitičke upite. SynchroStore [10] predlaže cost-based kompakciju za hibridna opterećenja, dok veDB-HTAP [7] opisuje integriranu arhitekturu visokih performansi. Zajednički nalaz ovih radova je da ne postoji univerzalno superiorna strategija — optimalna konfiguracija ovisi o omjeru OLTP/OLAP opterećenja i razini konkurentnosti.

### 2.6 Identifikacija istraživačke praznine

Pregledom dostupne literature identificirane su sljedeće praznine koje ovaj rad adresira. Prvo, postojeće benchmarking studije [2], [3], [9] pretežno koriste sintetičke skupove podataka (TPC-C, TPC-H) s uniformnim distribucijama koji ne odražavaju asimetriju stvarnih aplikacija. StackOverflow2010, kao dump stvarne produkcijske baze s Pareto distribucijom korisničke aktivnosti, pruža ekološki validniji okvir za procjenu performansi konfiguracija u realnim scenarijima. Drugo, evaluacije SQL Server-ovih specifičnih mehanizama (Hekaton + columnstore kombinacija) u kontekstu HTAP opterećenja su rijetke u akademskoj literaturi, premda SQL Server ostaje jedan od najšire korištenih sustava upravljanja bazama podataka u korporativnom okruženju. Treće, studije koje istovremeno evaluiraju sve tri razine konkurentnosti (niska, srednja, visoka) i tri omjera opterećenja (OLTP-intenzivno, uravnoteženo, OLAP-intenzivno) uz statistički rigoroznu obradu rezultata nedostaju u pregledanoj literaturi.

---

&nbsp;

## 3. Metodologija istraživanja

### 3.1 Eksperimentalni dizajn

Istraživanje je provedeno kao **4×3×3 puni faktorijalni dizajn** s 30 ponavljanja po kombinaciji, što predstavlja standardni pristup za benchmarking studije koje zahtijevaju statistički rigorozne usporedbe između više razina više faktora:

```
4 konfiguracije × 3 OLTP/OLAP omjera × 3 razine konkurentnosti × 30 runova
= 1.080 ukupnih mjernih serija
```

Puni faktorijalni dizajn odabran je umjesto frakcijskog dizajna jer omogućava procjenu interakcijskih efekata između faktora — posebno interakcije između konfiguracije i razine konkurentnosti, koja je izravno relevantna za hipotezu H1. Broj ponavljanja od 30 po kombinaciji osigurava dovoljnu statističku snagu za neparametarske testove čak i kada su distribucije izrazito asimetrične [2].

**Nezavisne varijable (faktori eksperimenta):**
- Konfiguracija pohrane: {Baseline, CS, IM, HTAP}
- OLTP/OLAP omjer radnog opterećenja: {80/20, 50/50, 20/80}
- Razina konkurentnosti (broj paralelnih radnih threadova): {C=4, C=16, C=32}

**Zavisne varijable (mjerne metrike):**
- OLTP propusnost: broj transakcija po sekundi (ops/s)
- OLAP propusnost: broj analitičkih upita po sekundi (q/s)
- OLTP latencija: P50, P95, P99 percentili (ms)
- OLAP latencija: P50, P95, P99 percentili (ms)
- Stopa uspješnosti operacija (%)

**Kontrolirane varijable:**
- Hardverska konfiguracija (identičan stroj za sve eksperimente)
- Veličina skupa podataka (identičan broj redova u svim shemama)
- SQL Server konfiguracija (isti stupanj paralelizma, ista maksimalna memorija)
- Trajanje warmup faze: 10 sekundi (rezultati warmup faze odbacuju se)
- Trajanje mjerne faze: 60 sekundi po runu

### 3.2 Konfiguracijske strategije

#### Baseline — disk-zasnovane tablice s B-tree indeksima

Standardna SQL Server konfiguracija s row-store tablicama pohranjenima na disku predstavlja *kontrolnu grupu* eksperimenta — polaznu točku za usporedbu svih ostalih konfiguracija. Svaka tablica ima clustered B-tree indeks na primarnom ključu i odabrane nonclustered indekse na stranim ključevima koji se koriste u analitičkim upitima. OLTP i OLAP operacije koriste row-mode executor. Analitički upiti mogu koristiti paralelne planove izvršavanja (MAXDOP > 1), ali bez prednosti batch-mode obrade koja je dostupna samo s columnstore indeksima.

Odabir Baseline konfiguracije kao kontrolne grupe motiviran je činjenicom da ona odgovara konfiguraciji koju bi koristila organizacija bez specifičnih optimizacija za mješovita opterećenja, tj. standardnoj instalaciji SQL Servera bez dodatnih memorijskih ili indexnih optimizacija.

#### CS — disk-zasnovane tablice s nonclustered columnstore indeksom

CS konfiguracija je identična fizička shema kao Baseline, s dodatkom NONCLUSTERED COLUMNSTORE indeksa na svakoj tablici koji pokriva sve stupce (covering columnstore). Za analitičke upite, SQL Server automatski odabire columnstore skeniranje i batch-mode execution plan kroz cost-based optimizer, što teorijski donosi ubrzanje od 10 do 100 puta za agregacijske upite [14]. OLTP operacije i dalje koriste B-tree clustered indeks; pisanja invalidiraju columnstore delta store, što uvodi mali dodatni overhead.

Kritično razmatranje pri konfiguriranju CS konfiguracije odnosilo se na ponašanje pri C=32. S 6 ili više istovremenih analitičkih upita u batch-mode s paralelnim planom izvršavanja može doći do saturacije CPU threadova. Problem je riješen dodavanjem OPTION(MAXDOP 2) u sve analitičke procedure, što je standardna praksa pri konfiguriranju columnstore indeksa za mješovita opterećenja visoke konkurentnosti.

#### IM — memorijsko-optimizirane tablice (Hekaton)

Sve tablice u IM konfiguraciji su memorijsko-optimizirane (MEMORY_OPTIMIZED = ON, DURABILITY = SCHEMA_ONLY). Hash indeksi primijenjeni su za točkačne OLTP operacije, a nonclustered range indeksi za upite rasponskog tipa. Sve OLTP pohranjene procedure nativno su kompajlirane (NATIVE_COMPILATION), što eliminirai T-SQL interpretativni overhead i drastično ubrzava točkačne operacije pri visokim razinama konkurentnosti.

Analitički upiti u IM konfiguraciji rade u row-mode jer Hekaton ne podržava batch-mode izvršavanje. Budući da hash indeksi nisu optimizirani za sekvencijalno skeniranje, agregacijski upiti nad 3,7 milijuna redova u tablici Posts znatno su sporiji nego u CS konfiguraciji. Dodan je OPTION(MAXDOP 1) za analitičke procedure jer paralelni planovi na memorijsko-optimiziranim tablicama mogu uzrokovati sinkronizacijske blokade (CXSYNC_PORT wait type) pri visokim razinama konkurentnosti.

#### HTAP — dual-store hibridna konfiguracija

HTAP implementacija slijedi dual-store arhitekturalni obrazac koji je konceptualno srodan TiDB/TiFlash pristupu [11]: OLTP pisanja i točkačna čitanja usmjeravaju se na memorijsko-optimizirane tablice (htap.*), dok analitički upiti čitaju iz columnstore tablica (cs.*). Ovo odvajanje osigurava da analitički batch-mode scans ne ometaju OLTP operacije na memorijskim tablicama — ključno za performansnu izolaciju opisanu u [9].

Implementacijsko ograničenje dual-store pristupa u SQL Serveru 2022 jest konzistentnosna razlika između htap.* i cs.* tablica: analitika ne vidi upravo unesene OLTP zapise dok se ne sinkroniziraju s cs.* kopijom. U kontekstu ovog benchmarka sintetički INSERT-i ne provjeravaju se analitički, pa ovo ne utječe na mjerene metrike. U produkcijskoj primjeni ova konzistentnosna razlika mora biti eksplicitno razmotrena pri dizajnu aplikacijskog sloja.

### 3.3 Radna opterećenja

#### OLTP radni tok

Šest OLTP operacija odabire se nasumično s fiksnom distribucijom koja odražava tipično opterećenje web aplikacije tipa Stack Overflow, kombinirajući čitanja (65%) i pisanja (35%):

| Procedura | Tip | Udio (approx.) |
|-----------|-----|---------------|
| usp_GetPostById | SELECT točkačno | ~25% |
| usp_GetUserById | SELECT točkačno | ~20% |
| usp_GetRecentUserPosts | SELECT rasponski | ~20% |
| usp_InsertVote | INSERT | ~15% |
| usp_InsertComment | INSERT | ~10% |
| usp_UpdatePostScore | UPDATE | ~10% |

Svaki OLTP worker drži persistentnu konekciju (connection pool) i izvršava operacije sekvencijalno bez pauza između, simulirajući intenzivno opterećenje aplikacijskog sloja. Odabir operacija s nasumičnim ID-ovima iz kontekstnog skupa od 20.000 postova i 5.000 korisnika osigurava realističnu distribuciju pristupa podacima.

#### OLAP radni tok

Pet analitičkih upita odabire se nasumično. Svi upiti su agregacijske prirode bez parametara koji bi ograničili skenirani skup (full-scan queries), što je reprezentativno za reportiranje i analitiku nad cjelokupnom historijom:

| Upit | Opis | Ključne operacije |
|------|------|-------------------|
| Q1 MonthlyActivity | Aktivnost po godini, mjesecu i tipu posta | GROUP BY, COUNT, AVG, SUM |
| Q2 UserEngagement | Angažiranost korisnika | JOIN, GROUP BY, agregacija |
| Q3 TagAnalysis | Popularnost tagova po periodu | JOIN, SUBSTRING, GROUP BY |
| Q4 TimeToAnswer | Prosječno vrijeme odgovora na pitanja | Self-JOIN, DATEDIFF, GROUP BY |
| Q5 TopContributors | Rangiranje korisnika po utjecaju | CTE, GROUP BY, ORDER BY |

Svaki OLAP worker koristi zasebnu konekciju s CommandTimeout = 300 sekundi. Implementiran je mehanizam otkazivanja upita koji automatski prekida upit koji premašuje vremenski okvir mjerne serije, čime se sprječava produženje mjernog prozora zbog jednog sporog upita.

### 3.4 Mjerno okruženje i implementacija

Benchmark aplikacija razvijena je u .NET 8 koristeći async/await model za istovremeno izvršavanje radnih tokova. Arhitektura aplikacije temelji se na sljedećim komponentama:

- **BenchmarkOrchestrator**: koordinira slijed konfiguracija, omjera i razina konkurentnosti; implementira logiku nastavka od mjesta prekida (resume) čitanjem summary.csv pri pokretanju
- **WorkloadExecutor**: kreira OLTP i OLAP workere za svaku kombinaciju faktora, koordinira warmup i mjerne faze, upravlja osvježavanjem podataka između mjernih serija
- **ResultsWriter**: atomarno upisuje mjerenja u CSV datoteke s append načinom rada i provjerom duplih unosa
- **Dapper** micro-ORM za parametrizirane SQL upite bez refleksivnog overhead-a

Svaki run prolazi kroz warmup fazu (10 s) čiji se rezultati odbacuju i mjernu fazu (60 s) čiji se rezultati bilježe. OLTP latencija mjeri se za svaku individualnu operaciju korištenjem Stopwatch.Elapsed, dok se OLAP latencija mjeri za svaki cijeli upit od slanja do primanja prvog paketa rezultata.

### 3.5 Statistička metodologija

#### Razlog za neparametarsku statistiku

Distribucije latencija i propusnosti u benchmarking eksperimentima tipično su desno-asimetrične s izraženim repovima (heavy-tailed distributions) zbog povremenih outlier-a uzrokovanih garbage collection pauzama, context switch-evima operativnog sustava i CPU cache miss-evima. Shapiro-Wilk testom normalnosti za reprezentativne uzorke potvrđeno je da distribucije statistički značajno odstupaju od normalne (p < 0,001), što opravdava odbacivanje parametarskih testova (t-test, jednosmjerna ANOVA) i primjenu neparametarskih alternativa koje ne pretpostavljaju distribuciju podataka.

#### Kruskal-Wallis H-test

Kruskal-Wallis H-test, neparametarska alternativa jednosmjernoj ANOVA-i, testira nultu hipotezu da sve četiri konfiguracije dolaze iz iste distribucije:

> H₀: distribucije metrike su identične za sve četiri konfiguracije  
> H₁: barem jedna konfiguracija ima statistički značajno različitu distribuciju

Test se primjenjuje zasebno za svaku kombinaciju mjerne metrike i razine konkurentnosti (6 metrika × 3 razine konkurentnosti = 18 nezavisnih testova). Razina značajnosti postavljena je na α = 0,05.

#### Mann-Whitney U test s Bonferroni korekcijom

Za parne usporedbe između konfiguracija koristi se Mann-Whitney U test. Budući da se testira C(4,2) = 6 parova po metrici i razini konkurentnosti, primjenjuje se Bonferroni korekcija za višestruko testiranje: korigirani prag značajnosti iznosi α/6 ≈ 0,0083, što odgovara množenju sirove p-vrijednosti s faktorom 6 uz usporedbu s α = 0,05.

#### Cohen's d — veličina efekta

Statistička značajnost (p-vrijednost) ne govori ništa o praktičnoj važnosti razlike. Cohenov *d* kvantificira veličinu efekta kao razliku sredina podijeljenu skupnom standardnom devijacijom:

> d = (μ₁ − μ₂) / s_pooled

Interpretacija prema Cohenovoj konvenciji: |d| < 0,2 trivijalan efekt, 0,2–0,5 mali efekt, 0,5–0,8 srednji efekt, > 0,8 veliki efekt. U kontekstu benchmarkinga, veličina efekta > 0,8 indicira razliku koja je praktično značajna i relevantna za arhitekturalne odluke.

---

&nbsp;

## 4. Eksperimentalno okruženje

### 4.1 Hardverska i softverska konfiguracija

Svi eksperimenti provedeni su na istoj hardverskoj konfiguraciji bez ikakvih izmjena između mjernih sesija različitih konfiguracija, čime je osigurana kontrola hardverskih varijabli:

| Komponenta | Specifikacija |
|-----------|--------------|
| RAM | 32 GB DDR4 |
| Pohrana (baseline, cs) | HDD |
| Pohrana (im, htap OLTP) | RAM (memorijsko-optimizirane tablice) |
| Operativni sustav | Windows 11 |
| Baza podataka | Microsoft SQL Server 2022 Developer Edition (16.x) |
| .NET runtime | .NET 8.0 |
| Python | 3.11 |
| Mjerna aplikacija | HTAPBenchmark v1.0 (.NET 8, Dapper 2.x) |

Važna napomena: im.* i htap.* tablice koriste DURABILITY = SCHEMA_ONLY, što znači da podaci ne preživljavaju restart SQL Servera. Ova konfiguracija odabrana je jer SCHEMA_ONLY tablice imaju značajno manji overhead pisanja u transakcijski log, što je relevantno za representativnost OLTP mjerenja.

### 4.2 Skup podataka — StackOverflow2010

Skup podataka StackOverflow2010 javno je dostupan dump produkcijske baze podataka platforme Stack Overflow koji obuhvaća sve zapise od osnivanja platforme 2008. do kraja 2010. godine. Ovaj skup podataka odabran je umjesto sintetičkih alternativi (TPC-C, TPC-H) jer odražava stvarnu distribuciju korisničke aktivnosti karakterističnu za web aplikacije — asimetričnu Pareto distribuciju gdje mali postotak korisnika generira najveći dio sadržaja [1].

| Tablica | Opis | Broj redova |
|---------|------|------------|
| Posts | Pitanja i odgovori | 3.729.195 |
| Users | Korisnički profili | 299.398 |
| Votes | Glasovi na postovima | 10.143.364 |
| Comments | Komentari na postove | 3.875.183 |
| Badges | Zaslužene bedževe korisnika | 1.102.019 |
| **Ukupno po shemi** | | **≈ 19.149.159** |
| **Ukupno (4 sheme)** | | **≈ 76.596.636** |

Svaka od četiri konfiguracijske sheme sadrži identičan skup podataka inicijalno učitan iz originalnog StackOverflow2010 dumpa. Podaci su učitani jednom u Baseline i CS sheme (disk-zasnovane), a potom kopirani u IM i HTAP sheme (memorijsko-optimizirane). Ovim pristupom osigurana je apsolutna konzistentnost između konfiguracija u pogledu sadržaja i distribucije podataka.

### 4.3 Priprema podataka i kontekst učitavanja

Prije svake mjerne sesije učitava se *radni kontekst* koji definira skup entiteta s kojima će workers operirati:
- **20.000 nasumičnih ID-ova postova** iz aktivne sheme (za OLTP operacije koje se odnose na postove)
- **5.000 nasumičnih ID-ova korisnika** iz aktivne sheme
- **Maksimalni ID** glasova i komentara (za generiranje novih jedinstvenih ID-ova INSERT operacija)

Nasumično uzorkovanje ID-ova (ORDER BY NEWID()) osigurava da benchmark simulira realnu distribuciju pristupa, a ne sekvencijalni pristup koji bi favorizirao B-tree indekse (sekvencijalni pristup optimalan za range scan) ili hash indekse (potpuno nasumični pristup optimalan za hash lookup). Za memorijsko-optimizirane tablice (im.* i htap.*), korišten je OPTION(MAXDOP 1) u upitima za učitavanje konteksta kako bi se izbjeglo CXSYNC_PORT čekanje karakteristično za paralelne planove na Hekaton tablicama.

### 4.4 Tehnički izazovi i riješeni problemi

Implementacija benchmarka naišla je na nekoliko tehničkih izazova koji su riješeni i dokumentirani jer su relevantni za razumijevanje ograničenja i valjanosti mjerenja.

**Problem MVCC version chain akumulacije:** Pri C=32 s 30 uzastopnih mjernih serija, brisanje svih ~3,7 milijuna redova tablice Posts između kombinacija konfiguracija generiralo je ~7,4 milijuna GC (garbage collection) stavki po brisanju. Akumulacija ovih stavki između uzastopnih kombinacija uzrokovala je iscrpljenje memorije SQL Servera (OOM). Rješenje: umjesto brisanja svih redova, između svake mjerne serije briše se i ponovo učitava samo 20.000 aktivnih redova iz radnog konteksta — 185 puta manje GC posla po mjerenju.

**Problem TRUNCATE TABLE na memorijsko-optimiziranim tablicama:** SQL Server 2022 ne podržava TRUNCATE TABLE naredbu na memorijsko-optimiziranim tablicama (Error 10794). Sve operacije čišćenja tablice zamijenjene su selektivnim DELETE naredbama po ID-u.

**Problem nastavka od mjesta prekida:** Pri dugotrajnim benchmarkovima (>10 sati), prekid uzrokovan iscrpljenjem RAM-a ili manualnim zaustavljanjem zahtijevao je pouzdanu logiku nastavka. Implementirano je čitanje summary.csv u konstruktoru orkestratora *prije* otvaranja izlaznih datoteka za pisanje, čime se izbjegava nenamjerno brisanje već prikupljenih rezultata.

---

&nbsp;

## 5. Rezultati

Od inicijalnih 1.080 planiranih mjernih serija, 10 (0,93%) isključeno je iz analize zbog nestabilnosti mjernog okruženja (stopa uspješnosti OLTP operacija ispod 90%), što rezultira uzorkom od 1.070 validnih mjerenja i 28 do 30 serija po kombinaciji. Udio filtriranih mjerenja unutar je prihvatljivih granica za neparametarsku statističku analizu [2] i ne utječe na statističku valjanost zaključaka.

### 5.1 Deskriptivna statistika

Vrijednosti u tablicama predstavljaju srednju vrijednost ± standardnu devijaciju agregiranu po svim omjerima opterećenja (Tablice 1 i 2) odnosno po svim razinama konkurentnosti (Tablica 3). Visoka standardna devijacija u Tablicama 1 i 2 odražava stvarnu varijabilnost između omjera opterećenja — omjer 80/20 ostvaruje bitno višu OLTP propusnost od omjera 20/80 — a ne mjernu nestabilnost. Koeficijenti varijacije unutar pojedinih omjera znatno su niži i iznose 8 do 22% što je prihvatljivo za benchmarking eksperimente.

**Tablica 1.** OLTP propusnost (ops/s) — srednja vrijednost ± standardna devijacija

| Konfiguracija | C=4 | C=16 | C=32 |
|:-------------|----:|-----:|-----:|
| Baseline | 1.204 ± 704 | 4.051 ± 3.692 | 2.432 ± 2.375 |
| CS | 1.254 ± 636 | 3.637 ± 3.293 | 2.477 ± 2.210 |
| IM | 2.007 ± 1.258 | 4.249 ± 2.923 | 4.726 ± 2.664 |
| HTAP | 6.783 ± 3.557 | 18.442 ± 14.867 | 21.920 ± 17.130 |

**Tablica 2.** OLAP propusnost (q/s) — srednja vrijednost ± standardna devijacija

| Konfiguracija | C=4 | C=16 | C=32 |
|:-------------|----:|-----:|-----:|
| Baseline | 0,27 ± 0,14 | 0,73 ± 0,24 | 0,85 ± 0,20 |
| CS | 0,79 ± 0,39 | 2,33 ± 0,70 | 2,80 ± 0,43 |
| IM | 2,52 ± 0,71 | 3,05 ± 0,54 | 3,13 ± 0,55 |
| HTAP | 2,65 ± 1,20 | 6,95 ± 2,27 | 6,84 ± 1,80 |

**Tablica 3.** OLAP latencija P50 (ms) po omjeru opterećenja — srednja vrijednost ± standardna devijacija

| Konfiguracija | 80/20 | 50/50 | 20/80 |
|:-------------|------:|------:|------:|
| Baseline | 3.128 ± 605 | 4.927 ± 1.965 | 7.351 ± 3.872 |
| CS | 1.665 ± 465 | 2.583 ± 790 | 3.710 ± 1.732 |
| IM | 1.048 ± 549 | 2.035 ± 1.119 | 2.281 ± 1.202 |
| HTAP | 924 ± 158 | 1.215 ± 453 | 1.530 ± 688 |

Iz Tablice 1 vidljivo je da HTAP konfiguracija ostvaruje dramatično veću OLTP propusnost od svih ostalih konfiguracija pri svim razinama konkurentnosti, s posebno izraženom prednošću pri C=32 (21.920 ops/s nasuprot 4.726 ops/s za IM, 2.477 ops/s za CS i 2.432 ops/s za Baseline). Tablica 2 pokazuje da kolumnstore konfiguracije (CS i HTAP) značajno nadmašuju IM i Baseline u OLAP propusnosti, s tim da HTAP dostiže 6,84 q/s pri C=32 nasuprot 0,85 q/s za Baseline — poboljšanje od faktora 8,0. Tablica 3 otkriva da HTAP ostvaruje najkraću OLAP latenciju u svim scenarijima omjera opterećenja, s najnižom vrijednošću od 924 ms pri omjeru 80/20.

### 5.2 Rezultati statističkih testova

**Tablica 4.** Kruskal-Wallis H-test — globalne razlike između konfiguracija (df = 3 za sve testove)

| Metrika | C=4 | C=16 | C=32 |
|---------|-----|------|------|
| OLTP propusnost | H=194,44; p<0,001 | H=66,79; p<0,001 | H=158,01; p<0,001 |
| OLAP propusnost | H=272,03; p<0,001 | H=303,17; p<0,001 | H=290,16; p<0,001 |
| OLTP latencija P50 | H=302,06; p<0,001 | H=297,82; p<0,001 | H=284,92; p<0,001 |
| OLAP latencija P50 | H=300,91; p<0,001 | H=228,87; p<0,001 | H=182,55; p<0,001 |

Svi Kruskal-Wallis testovi potvrđuju statistički značajne globalne razlike između konfiguracija za sve metrike i sve razine konkurentnosti (p < 0,001 u svim slučajevima). Ovi rezultati opravdavaju nastavak s parnim Mann-Whitney testovima za identifikaciju specifičnih razlika između pojedinih konfiguracija.

**Tablica 5.** Mann-Whitney U test s Bonferroni korekcijom — parne usporedbe za OLAP latenciju P50 pri C=32

| Par | U | p (Bonf.) | Cohen's d | Veličina efekta | Zn. |
|-----|---|-----------|-----------|-----------------|-----|
| Baseline vs CS | 6.219 | <0,001 | +1,254 | veliki | ✓ |
| Baseline vs IM | 6.775 | <0,001 | +1,665 | veliki | ✓ |
| Baseline vs HTAP | 7.620 | <0,001 | +2,086 | veliki | ✓ |
| CS vs IM | 5.342 | 0,001 | +0,679 | srednji | ✓ |
| CS vs HTAP | 6.613 | <0,001 | +1,614 | veliki | ✓ |
| IM vs HTAP | 6.449 | <0,001 | +1,564 | veliki | ✓ |

*Pozitivan predznak Cohenovog d označava da prva konfiguracija ima veću (lošiju) latenciju od druge.*

Sve parne usporedbe statistički su značajne uz Bonferroni korekciju, uključujući par CS vs IM koji pokazuje srednji efekt (d = +0,679). Para IM vs HTAP pokazuje veliki efekt (d = +1,564), što indicira da HTAP ostvaruje praktično i statistički značajno nižu OLAP latenciju od IM konfiguracije.

### 5.3 Provjera hipoteza

#### Hipoteza H1 — CS vs HTAP OLAP latencija pri niskoj i visokoj konkurentnosti

**Tablica 6.** Provjera H1: CS vs HTAP OLAP latencija P50 po razini konkurentnosti

| Konkurentnost | CS P50 (ms) | HTAP P50 (ms) | Razlika | p (Bonf.) | Cohen's d | Zaključak |
|:-------------|------------:|-------------:|--------:|-----------:|----------:|:----------|
| C=4 | 1.850 | 825 | −55% | <0,001 | 6,14 | odbačena* |
| C=32 | 3.620 | 1.813 | −50% | <0,001 | 6,52 | potvrđena |

**Hipoteza H1 je djelomično potvrđena.** Hipoteza pretpostavlja da su CS i HTAP usporedivi pri C=4, što nije potvrđeno: HTAP ostvaruje statistički značajno nižu OLAP latenciju čak i pri niskoj konkurentnosti (d = 6,14, veliki efekt). Razlika između CS i HTAP postoji i pri C=4 i pri C=32, a apsolutna razlika raste s konkurentnošću (Δ = 1.025 ms pri C=4 → Δ = 1.807 ms pri C=32). Prednost HTAP nad CS nije isključivo rezultat zasićenja CPU-a pri visokim C vrijednostima, već temeljne arhitekturalne razlike između in-memory i disk-zasnovane pohrane: čitanje iz RAM-a inherentno je brže od čitanja s diska čak i za columnstore format.

#### Hipoteza H2 — Degradacija OLTP propusnosti CS vs HTAP pri mješovitom opterećenju

**Tablica 7.** Provjera H2: Degradacija OLTP propusnosti pri prijelazu s omjera 80/20 na 50/50

| Konfiguracija | Degradacija (%) | SD (%) | p (Bonf.) | Cohen's d | Zaključak |
|:-------------|---------------:|-------:|-----------:|----------:|:----------|
| CS | 67,4 | 2,8 | <0,001 | 2,315 | potvrđena |
| HTAP | 55,9 | 6,3 | — | — | — |

**Hipoteza H2 je potvrđena.** CS bilježi degradaciju OLTP propusnosti od 67,4% pri prijelazu s omjera 80/20 na 50/50, dok HTAP bilježi 55,9%. Razlika je statistički značajna (Mann-Whitney p < 0,001) s velikim efektom (d = 2,315). Dual-store HTAP arhitektura efikasnije izolira OLTP procesiranje od analitičkog opterećenja u usporedbi s CS konfiguracijom, što potvrđuje teorijsku pretpostavku da fizičko odvajanje OLTP i OLAP sloja pohrane smanjuje međusobnu interferenciju.

#### Hipoteza H3 — HTAP vs IM OLTP propusnost pri transakcijskom opterećenju

**Tablica 8.** Provjera H3: HTAP vs IM OLTP propusnost pri omjeru 80/20

| C | IM (ops/s) | HTAP (ops/s) | Omjer | p (Bonf.) | Cohen's d | Zaključak |
|---|----------:|------------:|------:|-----------:|----------:|:----------|
| 4 | 3.027 | 10.083 | 3,3× | <0,001 | −4,38 | odbačena |
| 16 | 7.726 | 35.914 | 4,6× | <0,001 | −8,29 | odbačena |
| 32 | 6.325 | 43.751 | 6,9× | <0,001 | −11,93 | odbačena |

**Hipoteza H3 je odbačena na svim razinama konkurentnosti.** HTAP ostvaruje statistički značajno veću OLTP propusnost od IM konfiguracije pri svim razinama konkurentnosti i svim omjerima opterećenja — 3,3 do 6,9 puta ovisno o konkurentnosti. Veličina efekta raste s konkurentnošću (d = −4,38 pri C=4 → d = −11,93 pri C=32), što indicira sve izraženu prednost HTAP arhitekture pri visokim opterećenjima. Ovi rezultati proturječe polaznoj pretpostavci da HTAP i IM ostvaruju sličnu OLTP propusnost jer dijele iste memorijsko-optimizirane tablice za OLTP operacije.

---

&nbsp;

## 6. Diskusija

### 6.1 OLTP performanse — memorija nasuprot disku

Najuočljiviji nalaz ovog istraživanja jest dramatična prednost memorijsko-optimiziranih konfiguracija (IM i HTAP) u OLTP propusnosti u usporedbi s disk-zasnovanim konfiguracijama (Baseline i CS). Razlika između HTAP i Baseline pri C=32 (21.920 vs 2.432 ops/s) iznosi faktor 9,0, što je konzistentno s predviđanjima originalnog Hekaton rada [13] koji izvještava o ubrzanjima od 5 do 70 puta za točkačne OLTP upite. Rezultati IM konfiguracije (4.726 ops/s pri C=32), međutim, znatno su skromniji od HTAP (21.920 ops/s), što nije bilo očekivano s obzirom na to da oba pristupa koriste identičan Hekaton engine i identične nativno kompajlirane procedure za OLTP operacije.

Moguće objašnjenje ove razlike leži u interakciji između OLAP workera i OLTP workera u IM konfiguraciji. U IM konfiguraciji, OLAP upiti moraju skenirati sve ~3,7 milijuna redova tablice Posts bez prednosti columnstore organizacije ili batch-mode procesiranja, što znači da OLAP worker troši znatno više CPU resursa po upitu nego u CS ili HTAP konfiguraciji. Ova CPU saturacija OLAP-om izravno kompetira s OLTP workerima za procesorsko vrijeme, što objašnjava relativno nisku IM OLTP propusnost pri mješovitom opterećenju. HTAP konfiguracija, s odvojenim columnstore tablicama za OLAP, omogućava efikasnije OLAP procesiranje koje troši manje CPU resursa, ostavljajući više kapaciteta OLTP workerima.

### 6.2 OLAP performanse — prednost columnstore arhitekture

Rezultati OLAP propusnosti i latencije jasno potvrđuju prednost columnstore pohrane za analitičke upite: HTAP (6,84 q/s pri C=32) i CS (2,80 q/s pri C=32) znatno nadmašuju Baseline (0,85 q/s pri C=32) i IM (3,13 q/s pri C=32), što je konzistentno s teorijskim predviđanjima iz [14].

Zanimljiv je nalaz da IM konfiguracija (3,13 q/s) nadmašuje CS (2,80 q/s) u OLAP propusnosti pri C=32, unatoč tome što CS ima columnstore indekse dok IM nema. Ovaj naizgled paradoksalan rezultat može se objasniti kontencijom za memorijskim resursima: pri C=32 s 6+ simultanih batch-mode upita u CS konfiguraciji, čekanje na dodjelu memorijskog prostora (RESOURCE_SEMAPHORE wait type) može povećati ukupno vrijeme izvršavanja više nego što ga batch-mode skraćuje. IM konfiguracija, bez batch-mode overhead-a i s podacima u RAM-u, može biti efikasnija pri ovoj specifičnoj razini konkurentnosti. Ovo je konzistentno s nalazima Zeng et al. [8] koji ističu da pri visokim razinama konkurentnosti upravljanje memorijom postaje dominantni faktor performansi.

### 6.3 Degradacija performansi pri mješovitom opterećenju (H2)

Potvrda hipoteze H2 — da CS konfiguracija degradira OLTP propusnost više od HTAP konfiguracije pri mješovitom opterećenju — ima važne praktične implikacije. Razlika u degradaciji (67,4% za CS vs 55,9% za HTAP) može izgledati skromna u postocima, ali u apsolutnim brojevima pri C=32 ona znači razliku između gubitka 2/3 i 1/2 OLTP kapaciteta sustava, što je kritično u scenarijima gdje organizacija zahtijeva garantiranu razinu usluge za transakcijsko procesiranje.

Mehanizam koji stoji iza ove razlike konzistentan je s teorijskim razmatranjima: u CS konfiguraciji, analitički batch-mode scans i OLTP operacije dijele iste fizičke tablice i iste interne SQL Server resurse (buffer pool, I/O, paralelni query executor). Svaki analitički upit potencijalno izbacuje OLTP podatke iz buffer predmemorije i kompetira za CPU threadove. U HTAP dual-store konfiguraciji, analitički upiti idu na cs.* tablice, dok OLTP operacije ostaju na htap.* memorijsko-optimiziranim tablicama koje ne koriste buffer pool uopće — čime je fizička izolacija između OLTP i OLAP sloja znatno veća.

### 6.4 Utjecaj arhitekture sustava na rezultate

Arhitektura ispitivanog sustava ima ključan utjecaj na dobivene rezultate i mora se razmatrati pri interpretaciji nalaza. Sve četiri konfiguracije dijele iste CPU resurse, istu instancu SQL Servera i isti operativni sustav, što znači da performansna izolacija ovisi isključivo o SQL Server-ovim internim mehanizmima raspoređivanja resursa, a ne o fizičkom odvajanju kao kod distribuiranih HTAP sustava poput TiDB-a [11].

Jednočvorna arhitektura benchmarka predstavlja i prednost i ograničenje. Prednost: eliminira mrežnu latenciju i varijabilnost tipičnu za distribuirane sustave, čime se mjere "čiste" performansne karakteristike svake konfiguracijske strategije. Ograničenje: ne odražava produkcijska distribuirana okruženja u kojima mrežna latencija između TiKV i TiFlash može biti dominantni faktor koji maskira prednosti kolumnstore pohrane pri manjim skupovima podataka.

Disk I/O kao arhitekturalni bottleneck posebno je relevantan za Baseline i CS konfiguracije koje čitaju podatke s HDD-a. Premda je testni disk zajednički za obje konfiguracije, razlika između HDD i RAM brzine pristupa (~100 MB/s nasuprot ~40 GB/s) objašnjava dio prednosti HTAP nad CS pri OLAP upitima: HTAP čita columnstore podatke koji su manji po veličini (kompresija) ali s iste vrste medija (HDD), dok IM čita iz RAM-a bez kompresije. Zamjena HDD-a SSD-om bi vjerojatno smanjila razliku između CS i HTAP, ali ne bi promijenila fundamentalne zaključke o relativnim prednostima konfiguracija.

### 6.5 Usporedba s dosadašnjim istraživanjima

Nalazi ovog rada konzistentni su s nalazima dosadašnje literature u nekim aspektima, ali i divergiraju od nekih pretpostavki u drugima. Zhao et al. [9] u evaluaciji HTAP sustava zaključuju da je performansna izolacija kritičnija metrika od peak propusnosti, što potvrđuje i potvrda hipoteze H2 u ovom radu. Autorice identificiraju degradaciju OLTP propusnosti kao primarni problem HTAP implementacija, a ovaj rad kvantificira tu degradaciju za specifičnu SQL Server konfiguraciju: 67,4% za CS vs 55,9% za HTAP.

Zhang et al. [1] navode da su dual-engine sustavi (TiDB, F1 Lightning) superiorniji u izolaciji jer koriste fizički odvojene procese, ali plaćaju cijenu mrežne latencije pri replikaciji. SQL Server-ov in-process dual-store pristup eliminira mrežnu latenciju ali ne garantira apsolutnu fizičku izolaciju — što ovaj rad empirijski potvrđuje kroz mjerljivi (ali manji od 100%) učinak izolacije.

Zanimljiva je usporedba s rezultatima Wu et al. [3] koji evaluiraju HTAP sustave u financijskim scenarijima i pronalaze slične obrasce degradacije (50–70%) pri mješovitom opterećenju za disk-zasnovane sustave. Ova konzistentnost između različitih domenskih skupova podataka (financijski transakcioni podaci vs Stack Overflow socijalna mreža) sugerira da je degradacija pri mješovitom opterećenju robusna karakteristika disk-zasnovanih konfiguracija, neovisna o specifičnoj distribuciji podataka.

Neočekivani nalaz odbacivanja H3 — da HTAP ostvaruje 3,3 do 6,9 puta veću OLTP propusnost od IM — nije direktno potkrijepljen dosadašnjom literaturom. Ovo otvara pitanje: zašto HTAP, koji dijeli iste memorijsko-optimizirane tablice s IM za OLTP operacije, ostvaruje dramatično bolju OLTP propusnost? Jedna hipoteza je da su OLAP upiti u IM konfiguraciji toliko CPU-intenzivni (bez columnstore ubrzanja) da sistematski degradiraju OLTP propusnost, dok u HTAP konfiguraciji columnstore ubrzava OLAP upite 7-8 puta, oslobađajući CPU kapacitet za OLTP operacije. Ovo sugerira da je columnstore ubrzanje OLAP-a indirektno korisno i za OLTP propusnost u mješovitom opterećenju.

### 6.6 Praktične preporuke za arhitekte baza podataka

Na temelju empirijskih nalaza ovog istraživanja, moguće je formulirati konkretne smjernice za odabir konfiguracijske strategije u Microsoft SQL Serveru 2022:

| Scenario | Preporučena konfiguracija | Empirijska osnova |
|:---------|:--------------------------|:------------------|
| >80% OLTP, <20% OLAP | **HTAP** | 3,3–6,9× veća OLTP propusnost od IM; OLAP latencija P50 = 924 ms |
| 50–80% OLTP, 20–50% OLAP | **HTAP** | Najniža OLTP degradacija (55,9%) i OLAP latencija (1.215 ms) |
| <50% OLTP, >50% OLAP | **HTAP** | OLAP P50 = 1.530 ms nasuprot 2.281 ms za IM i 3.710 ms za CS |
| Samo OLAP, bez transakcija | **CS** | Disk-zasnovana pohrana bez RAM overhead-a; 7× bolja OLAP propusnost vs Baseline |
| RAM ograničen ili SQL Express | **CS** | Express ne podržava In-Memory OLTP; CS donosi 2× poboljšanje OLAP vs Baseline |

Ključni nalaz koji mijenja standardne preporuke: HTAP nije optimalan samo za mješovita opterećenja — on dominira i pri transakcijskim scenarijima (80/20), čineći IM konfiguraciju redundantnom osim u slučajevima ekstremnih RAM ograničenja ili licencnih restrikcija (SQL Server Express). Organizacije koje razmatraju In-Memory OLTP za ubrzanje transakcijskog procesiranja trebaju razmotriti HTAP dual-store pristup kao superiorniju alternativu.

### 6.7 Ograničenja istraživanja

Svako empirijsko istraživanje ima ograničenja koja moraju biti transparentno prikazana kako bi čitatelji mogli pravilno interpretirati rezultate i procijeniti njihovu primjenjivost na vlastite scenarije.

**Jednočvorna konfiguracija.** Benchmark je proveden na jednoj instanci SQL Servera bez distribuiranih komponenti. Distribuirani HTAP sustavi (TiDB, F1 Lightning, Oracle Sharding) mogu pokazivati drugačija skalabilna svojstva pri distribuciji opterećenja na više čvorova, a mrežna latencija između komponenti (tipično 0,1–5 ms za lokalne mreže) može promijeniti relativne prednosti konfiguracija pri manjim skupovima podataka.

**Hardverska konfiguracija.** Testovi su provedeni s HDD pohranjivanjem za disk-zasnovane tablice. Zamjena HDD-a SSD-om ili NVMe-om (što je standard u produkcijskim okruženjima) bi smanjila prednost memorijsko-optimiziranih tablica za disk I/O-intenzivne upite, potencijalno smanjujući razliku između HTAP i CS konfiguracija u OLAP metrikama. Rezultati su stoga konzervativniji za SSD okruženja.

**Vremenski okvir skupa podataka.** StackOverflow2010 dump iz 2010. godine može imati drugačije distribucije aktivnosti od modernijeg Stack Overflow dumpa, posebno u pogledu distribucije glasova i komentara koji su rasli eksponencijalno s rastom platforme.

**Sintetičko mješovito opterećenje.** OLTP i OLAP workeri simulirani su paralelnim threadovima bez mrežne latencije aplikacijskog sloja. U stvarnim deployment konfiguracijama, mrežna latencija između aplikacijskih servera i SQL Servera (1–10 ms za lokalne mreže) može biti dominantni faktor za kratke OLTP operacije, maskirajući razlike između konfiguracija.

**Konzistentnosna razlika u HTAP konfiguraciji.** Dual-store HTAP pristup ne garantira konzistentnost između htap.* i cs.* tablica u realnom vremenu. U produkcijskim scenarijima koji zahtijevaju analitiku nad upravo unesenim podacima, ova razlika mora biti razmotrena i potencijalno adresirana periodom sinkronizacije ili alternativnim mehanizmima.

---

&nbsp;

## 7. Zaključak

Ovaj rad eksperimentalno je evaluirao četiri konfiguracijske strategije pohrane u Microsoft SQL Serveru 2022 kroz 1.080 planiranih mjernih serija (1.070 validnih, 0,93% filtrirano) nad skupom podataka StackOverflow2010. Korištenjem faktorijalnog dizajnog 4×3×3 i rigorozne statističke metodologije — Kruskal-Wallis H-test, Mann-Whitney U test s Bonferroni korekcijom, Cohen's d — pružene su empirijski potkrijepljene osnove za provjeru triju istraživačkih hipoteza.

**Rezime nalaza po hipotezama:** Hipoteza H1 je djelomično potvrđena — HTAP ostvaruje statistički značajno nižu OLAP latenciju od CS konfiguracije ne samo pri visokoj konkurentnosti (C=32, d = 6,52) već i pri niskoj (C=4, d = 6,14), pri čemu apsolutna razlika raste s konkurentnošću. Hipoteza H2 je potvrđena — CS konfiguracija degradira OLTP propusnost pri mješovitom opterećenju za 67,4% nasuprot 55,9% za HTAP (p < 0,001, d = 2,315), čime je empirijski potvrđena superiornija performansna izolacija dual-store arhitekture. Hipoteza H3 je odbačena — HTAP ostvaruje 3,3 do 6,9 puta veću OLTP propusnost od IM konfiguracije pri OLTP-intenzivnom opterećenju, s veličinom efekta koja raste s razinom konkurentnosti (d = −4,38 do −11,93).

**Primarni doprinos** ovog rada jest praktična validacija HTAP paradigme u SQL Server kontekstu nad stvarnim skupom podataka s realnom distribucijom korisničke aktivnosti, što eliminira ograničenja sintetičkih benchmarkova identificirana u literaturi [1], [9]. Rezultati pružaju konkretne, kvantificirane smjernice arhitektima baza podataka: HTAP dual-store konfiguracija superiorna je u svim ispitanim scenarijima opterećenja — od OLTP-intenzivnih do OLAP-intenzivnih — čineći je preporučenim izborom za organizacije koje koriste Microsoft SQL Server 2022 Developer ili Enterprise Edition i mogu si priuštiti potrebnih ~8–12 GB RAM-a za memorijsko-optimizirane tablice.

**Implikacije za praksu** su značajne: organizacije koje koriste IM konfiguraciju za ubrzanje transakcijskog procesiranja trebaju razmotriti migraciju na HTAP dual-store pristup koji osigurava 3–7 puta bolje OLTP performanse uz istovremeno dramatično poboljšanje OLAP kapaciteta. Organizacije koje koriste CS konfiguraciju za analitiku trebaju biti svjesne da mješovito opterećenje uzrokuje degradaciju OLTP propusnosti od dvije trećine, što može biti neprihvatljivo u produkcijskim scenarijima s garantiranom razinom usluge.

**Buduća istraživanja** mogu proširiti ovaj rad u sljedećim smjerovima: (1) evaluacija na distribuiranim HTAP sustavima (TiDB, SingleStore, CockroachDB) za usporedbu in-process i distributed dual-store pristupa; (2) istraživanje utjecaja veličine skupa podataka korištenjem novijih Stack Overflow dumpova (2013., 2014., pa do aktualnog) radi kvantifikacije skalabilnosnih karakteristika; (3) evaluacija energetske efikasnosti različitih konfiguracija kao dopunske metrike relevantne za okolišnu održivost; (4) istraživanje automatskog tuninga — može li SQL Server-ov Automatic Tuning mehanizam dinamički odabirati optimalnu konfiguraciju ovisno o omjeru opterećenja u realnom vremenu.

---

&nbsp;

## Literatura

[1] C. Zhang, J. Zhou, H. Chen, Z. Wang, and T. Li, "HTAP databases: A survey," *IEEE Trans. Knowl. Data Eng.*, 2024. [Online]. Available: https://arxiv.org/abs/2404.15670

[2] C. Zhang, G. Li, and T. Lv, "HyBench: A new benchmark for HTAP databases," *Proc. VLDB Endow.*, vol. 17, no. 5, pp. 939–951, 2024. doi: 10.14778/3641204.3641206

[3] Y. Wu et al., "HTAP benchmark in financial scenarios," *Security and Safety*, vol. 4, 2025. doi: 10.1051/sands/2025010

[4] P. Zhao et al., "PUSHtap: PIM-based in-memory HTAP with unified data storage format," in *Proc. 30th ACM Int. Conf. Archit. Support Program. Lang. Oper. Syst. (ASPLOS '25)*, 2025. [Online]. Available: https://arxiv.org/abs/2508.02309

[5] H. Xiu et al., "Query performance explanation through large language model for HTAP systems," arXiv preprint arXiv:2412.01709, 2024.

[6] H. Song, Z. Zhao, X. Ding, and R. Chen, "A survey on hybrid transactional and analytical processing," *VLDB J.*, 2024. doi: 10.1007/s00778-024-00858-x

[7] C. Zhan et al., "veDB-HTAP: A highly integrated, efficient and adaptive HTAP system," *Proc. VLDB Endow.*, 2025. doi: 10.14778/3750601.3750614

[8] X. Zeng, M. Abebe, J. Waudby, and A. Pavlo, "An empirical evaluation of columnar storage formats," *Proc. VLDB Endow.*, vol. 17, no. 2, pp. 148–161, 2023. doi: 10.14778/3626292.3626298

[9] Y. Zhao, J. Chen, Y. Wang, and X. Shi, "Benchmarking HTAP databases for performance isolation and real-time analytics," *Inf. Syst.*, 2023. doi: 10.1016/j.is.2023.102195

[10] Y. Zhang et al., "SynchroStore: A cost-based fine-grained incremental compaction for hybrid workloads," arXiv preprint arXiv:2503.18688, 2025.

[11] D. Huang et al., "TiDB: A Raft-based HTAP database," *Proc. VLDB Endow.*, vol. 13, no. 12, pp. 3072–3084, 2020. doi: 10.14778/3415478.3415535

[12] J. Yang et al., "F1 Lightning: HTAP as a service," *Proc. VLDB Endow.*, vol. 13, no. 12, pp. 3313–3326, 2020. doi: 10.14778/3415478.3415539

[13] C. Diaconu et al., "Hekaton: SQL Server's memory-optimized OLTP engine," in *Proc. ACM SIGMOD Int. Conf. Manage. Data (SIGMOD '13)*, New York, NY, USA: ACM, 2013, pp. 1243–1254. doi: 10.1145/2463676.2463710

[14] P.-Å. Larson et al., "Enhancements to SQL Server column stores," in *Proc. ACM SIGMOD Int. Conf. Manage. Data (SIGMOD '13)*, New York, NY, USA: ACM, 2013, pp. 1159–1170. doi: 10.1145/2463676.2463708

[15] F. Özcan, Y. Tian, and P. Tözün, "Hybrid transactional/analytical processing: A survey," in *Proc. ACM SIGMOD Int. Conf. Manage. Data (SIGMOD '17)*, Chicago, IL, USA: ACM, 2017, pp. 1771–1775. doi: 10.1145/3035918.3054784

---
