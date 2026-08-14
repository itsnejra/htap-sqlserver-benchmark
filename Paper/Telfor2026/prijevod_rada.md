# Prijevod Telfor rada na bosanski

Radna verzija za čitanje — **nije** za slanje. Rad se šalje na engleskom
(`telfor2026.tex`). Ovo služi samo da vidiš šta tekst zapravo tvrdi.

**Crveno** = mjesta koja u radu stoje kao `\todonum{}` i čekaju brojke.

---

## Naslov

**Ubrzanje analitike kao optimizacija transakcija: dokazi iz dual-store HTAP
konfiguracije u SQL Serveru 2022**

Nejra Smajlović, Denis Čeke — Politehnički fakultet, Univerzitet u Zenici

---

## Sažetak

Hibridna transakcijsko-analitička obrada (HTAP) obično se vrednuje kao
kompromis: analitička propusnost se plaća gubitkom transakcijske. Mi
izvještavamo o kontroliranom mjerenju u kojem vrijedi suprotno.

Dvije konfiguracije Microsoft SQL Servera 2022 dijele identičan memorijsko-
optimizirani (Hekaton) transakcijski sloj i razlikuju se samo po tome gdje se
izvršavaju analitički upiti — nad samim memorijsko-optimiziranim tabelama, ili
nad columnstore kopijom. Kroz puni faktorijalni dizajn (3 omjera opterećenja ×
3 razine konkurentnosti × 30 runova) nad skupom StackOverflow2010 (~19,2
miliona zapisa), preusmjeravanje analitike na columnstore sloj povećava
**transakcijsku** propusnost 3,3× do 6,9× (p < 0,001, Cohenov d od 4,38 do
11,93), iako nije promijenjen nijedan transakcijski kod, indeks ni medij
pohrane.

Mehanizam je natjecanje za procesor: row-mode skeniranja nad memorijsko-
optimiziranim tabelama troše CPU cikluse koje bi inače koristio transakcijski
engine. Izoliramo confounding varijablu stepena paralelizma zasebnom
kontrolnom rukom i mjerimo mehanizam direktno kroz wait statistiku na razini
raspoređivača.

Praktična posljedica: u single-engine HTAP postavci, ubrzanje analitike **jeste**
transakcijska optimizacija i treba ga tako i budžetirati.

> ⚠️ **Ove dvije rečenice o kontrolnoj ruci i wait statistici tvrde nešto što
> još nije izmjereno.** Ovo je glavni razlog zašto rad trenutno nije za slanje.

---

## I. Uvod

Sistemi koji iz jedne baze opslužuju i transakcijska i analitička opterećenja
moraju pomiriti dva suprotna obrasca pristupa: kratke točkaste operacije uz
stroge zahtjeve konzistentnosti, i duga skeniranja koja agregiraju milione
redova. HTAP paradigma to rješava uklanjanjem ETL granice između OLTP sistema i
zasebnog skladišta.

Komercijalna rješenja pokrivaju širok raspon — od single-engine dual-format
pohrane u SAP HANA i Oracle Database In-Memory, do fizički odvojenih
dual-engine sistema kao što su TiDB i Google F1 Lightning.

Literatura dosljedno postavlja izbor između tih dizajna kao kompromis u
**izolaciji**: odvajanje analitičkog engina štiti transakcijske performanse, po
cijenu replikacije i sinhronizacije. Ono što taj okvir ostavlja neizrečenim
jeste **koliko velika** je ta zaštita — i posebno, može li biti dovoljno velika
da odvajanje bude neto dobitak za samu transakcijsku stranu, nezavisno od bilo
kakve analitičke koristi.

Ovaj rad mjeri upravo tu veličinu. Uspoređujemo dvije konfiguracije SQL Servera
2022 koje dijele identičan Hekaton transakcijski sloj — iste tabele, isti hash
indeksi, iste nativno kompajlirane procedure, ista postavka durabilnosti, isti
podaci — a razlikuju se u samo jednom pogledu: čitaju li analitički upiti
memorijsko-optimizirane tabele direktno, ili columnstore kopiju istih podataka.

Budući da je transakcijska putanja identična do bajta, svaka razlika u OLTP
propusnosti pripisuje se **smještaju analitičkog opterećenja**, a ne
transakcijskom inženjeringu.

Ta razlika ispada velika: 3,3× do 6,9× u OLTP propusnosti pri transakcijski
dominantnom opterećenju, i raste s konkurentnošću.

---

## II. Teorijska osnova i dosadašnja istraživanja

### A. Modeli izvršavanja

**Hekaton** je redizajnirani OLTP engine s optimističnom viševerzijskom
kontrolom konkurentnosti, lock-free strukturama koje u cijelosti zaobilaze
buffer pool, i nativno kompajliranim procedurama; originalni rad navodi
ubrzanja 10–30× za točkaste operacije. Nije, međutim, građen za skeniranja:
hash indeksi ne služe efikasno rasponskom pristupu, a engine ne podržava
batch-mode izvršavanje.

**Columnstore indeksi** pohranjuju vrijednosti stupca zajedno u kompresiranim
segmentima i obrađuje ih batch-mode executor koji radi nad ~1000 redova
odjednom koristeći vektorizirane instrukcije, uz ubrzanja 10–100× za tipične
skladišne upite.

Dva dizajna su arhitekturalno nespojiva u jednom smjeru: **MVCC version chains
se ne mogu održavati nad nepromjenjivim kompresiranim segmentima.** Ta
nespojivost je ono što analitičke upite u memorijsko-optimiziranoj shemi tjera
u row-mode, i ona je izvor efekta koji mjerimo.

### B. Interferencija i izolacija

Song i drugi tvrde da je sposobnost održavanja stabilnih transakcijskih
performansi pod analitičkim opterećenjem smislenija mjera HTAP sistema od vršne
propusnosti. Zhao i drugi performansnu izolaciju postavljaju kao organizacijski
princip HTAP evaluacije. Wu i drugi empirijski potvrđuju da dodavanje
analitičkih klijenata degradira OLTP propusnost, i da se degradacija pojačava s
konkurentnošću.

**Ono što u tom korpusu nedostaje** jeste mjerenje koje drži transakcijski
engine fiksnim i mijenja samo smještaj analitike. Postojeće usporedbe
istovremeno mijenjaju medij pohrane, durabilnost, engine i model izvršavanja
upita, pa se član interferencije ne može odvojiti od arhitekturalnih članova.
Usporedba u ovom radu dizajnirana je da ga izoluje.

---

## III. Eksperimentalni dizajn

### A. Kontrolirana usporedba

Četiri konfiguracije pohrane implementirane su kao zasebne sheme u jednoj
instanci SQL Servera 2022 nad identičnim podacima. Dvije od njih čine usporedbu
analiziranu u ovom radu; disk-zasnovana i columnstore-only konfiguracija ostaju
kao kontekst, ali nisu predmet usporedbe jer se od druge dvije razlikuju i po
mediju pohrane i po durabilnosti, a ne samo po smještaju analitike.

**Tabela I — Kontrolirana usporedba:**

| | IM | HTAP |
|---|---|---|
| OLTP pohrana | Hekaton (RAM) | Hekaton (RAM) |
| OLTP indeksi | hash + range | hash + range |
| OLTP procedure | nativno kompajlirane | nativno kompajlirane |
| Durabilnost | `SCHEMA_ONLY` | `SCHEMA_ONLY` |
| **OLAP cilj** | **iste tabele** | **columnstore kopija** |
| **OLAP izvršavanje** | **row-mode** | **batch-mode** |

Sve iznad crte je identično. To je ono što usporedbu čini tumačivom:
transakcijski sloj nije tek sličan nego je isti dizajn, pa se razlika u OLTP
propusnosti ne može objasniti transakcijskim inženjeringom, rezidentnošću u
memoriji, ni durabilnošću.

### B. Opterećenje i skup podataka

Mjerenja koriste StackOverflow2010 dump (~19,2 miliona redova kroz Posts,
Users, Votes, Comments i Badges), odabran umjesto sintetičkih alternativa jer
nosi Pareto distribuciju korisničke aktivnosti karakterističnu za web
aplikacije, koju TPC generatori ne reproduciraju.

Transakcijsko opterećenje čini šest pohranjenih procedura s težinom na
upisima (35% unos glasa, 25% ažuriranje score-a, 15% unos komentara, 25%
čitanja). Analitičko opterećenje čini pet agregacijskih upita biranih uniformno
nasumično, svi s punim skeniranjima uz grupiranje, spajanja ili CTE-ove.

### C. Dizajn i okruženje

Puni faktorijalni dizajn: 3 omjera opterećenja (80/20, 50/50, 20/80) × 3 razine
konkurentnosti (C ∈ {4, 16, 32}) × 30 runova po ćeliji, za svaku konfiguraciju.
Svaki run ima 10 s warmup faze koja se odbacuje, pa 60 s mjerne faze. Runovi s
uspješnošću OLTP operacija ispod 90% tretirani su kao nestabilno mjerno
okruženje i isključeni (0,93% runova); ostaje 1.070 validnih runova.

Pokretač je .NET 8 aplikacija s asinhronim OLTP i OLAP radnim nitima preko
odvojenih veza. Hardver: Intel Core i9-14900HX (24 jezgra / 32 niti), 32 GB
DDR5, NVMe SSD, Windows 11, SQL Server 2022 Developer Edition.

Distribucije latencije potvrđene su kao nenormalne (Shapiro-Wilk, p < 0,001),
pa analiza koristi Kruskal-Wallis H test za globalne razlike i Mann-Whitney U
test s Bonferroni korekcijom (α′ ≈ 0,0083) za parne usporedbe, uz Cohenov d za
veličinu efekta. Log-linearni OLS model dopunjuje ih doprinosima faktora.

---

## IV. Rezultati

### A. Transakcijska propusnost

**Slika 1** prikazuje medijalnu OLTP propusnost za dvije ruke pri transakcijski
dominantnom omjeru. Preusmjeravanje analitike na columnstore kopiju podiže
transakcijsku propusnost **3,3× pri C = 4, 4,6× pri C = 16 i 6,9× pri C = 32**.
Sve parne razlike značajne su na p < 0,001 nakon Bonferroni korekcije, uz
veličine efekta od d = 4,38 do d = 11,93 — red veličine iznad konvencionalnog
praga za veliki efekt.

Da se jaz **širi** s konkurentnošću potpis je efekta natjecanja, a ne fiksnog
overheada. Konstantan trošak po analitičkom upitu davao bi konstantan omjer;
sukob oko dijeljenog resursa daje omjer koji raste kako se resurs zasićuje.

### B. Transakcijska latencija

Isti efekt pojavljuje se u repnoj latenciji (**Slika 3**). Pri C = 32 medijalna
P95 latencija transakcijskih operacija je **16,8 ms** kad analitika radi nad
memorijsko-optimiziranim tabelama, naspram **2,1 ms** kad je preusmjerena —
transakcije se ne samo rjeđe završavaju, nego su i pojedinačno usporene. To
razlikuje natjecanje za resurse od efekata čekanja u redu na strani drajvera.

### C. Gdje se dešava analitički preokret

**Slika 2** locira efekt. Pri C = 4 row-mode ruka je zapravo **brža** analitički
(medijalni P50 od 641 ms naspram 832 ms): sa svim podacima u RAM-u i malim
natjecanjem za procesore, row-mode skeniranje je sasvim dovoljno. Poredak se
obrće kako konkurentnost raste — 2126 ms naspram 1045 ms pri C = 16, i 3292 ms
naspram 1768 ms pri C = 32.

**Tačka preokreta poklapa se s tačkom u kojoj se transakcijska propusnost
razilazi**, što je centralno zapažanje ovog rada: analitičko i transakcijsko
opterećenje degradiraju **zajedno**, jer degradiraju iz istog razloga. Row-mode
skeniranje ~3,7 miliona redova zahtijeva znatno više procesorskih ciklusa po
redu nego vektorizirano batch-mode izvršavanje nad kompresiranim segmentima; ti
ciklusi se uzimaju od istih raspoređivača koje treba transakcijski engine.

### D. Izolacija confounding varijable paralelizma

Analitičke procedure u row-mode ruci koriste `MAXDOP 1`, što je nužno da se
izbjegnu `CXSYNC_PORT` zastoji na memorijsko-optimiziranim tabelama, dok
preusmjerena ruka koristi `MAXDOP 2`. Ta asimetrija je confounding varijabla:
dio izmjerenog jaza mogao bi odražavati stepen paralelizma, a ne arhitekturu.

Zato smo dodali dvije kontrolne ruke koje ga izjednačavaju — row-mode analitika
na `MAXDOP 2`, i preusmjerena analitika na `MAXDOP 1` — i ponovili usporedbu u
oba smjera. Uz paralelizam izjednačen na DOP = 2, omjer propusnosti je
🔴 **[brojka]**; izjednačen na DOP = 1, iznosi 🔴 **[brojka]**, naspram
🔴 **[3,3–6,9]** u nekontroliranoj usporedbi. Asimetrija paralelizma stoga
objašnjava 🔴 **[X]**× izvornog jaza, ostavljajući 🔴 **[Y]**× pripisivo
smještaju analitike.

> ⚠️ **Ovo mjerenje nije izvedeno.** Ruka d2 jeste (90/90 runova), ruka d1 nije.

### E. Direktan dokaz mehanizma

Objašnjenje putem natjecanja je tvrdnja o procesorima, i testiramo je direktno
umjesto da je izvodimo iz planova izvršavanja. Radne veze su označene tako da
se CPU vrijeme iz `sys.dm_exec_sessions` može atribuirati transakcijskim i
analitičkim nitima odvojeno, a `sys.dm_os_wait_stats` se uzorkuje kroz mjernu
fazu.

Pri C = 32, analitičke niti troše 🔴 **[Z]%** ukupnog CPU vremena benchmarka u
row-mode ruci naspram 🔴 **[W]%** kad su preusmjerene, a `SOS_SCHEDULER_YIELD`
— tip čekanja koji bilježi da je zadatak potrošio svoj procesorski kvantum i
ustupio ga — akumulira 🔴 **[V]** s naspram 🔴 **[U]** s po runu od 60 s.
Analitika u row-mode ruci, po direktnom mjerenju, oduzima procesorsko vrijeme
transakcijama.

> ⚠️ **Ni ovo mjerenje nije izvedeno** za glavni set.

### F. Regresijski model

Log-linearni OLS model nad svih 1.070 runova
(log(OltpThroughput) ~ Config + Ratio + log(Concurrency), R² = 0,881) daje
preusmjerenoj konfiguraciji koeficijent **+1,965** (p < 0,001) naspram
disk-zasnovane osnove, tj. e^1,965 ≈ **7,1×** propusnosti, naspram **+0,708**
za row-mode ruku. Koeficijent konkurentnosti je **+0,325** (p < 0,001), što je
konzistentno sa širenjem jaza.

---

## V. Prijetnje validnosti

**Nema troška sinhronizacije.** Preusmjerena ruka odvaja transakcijski i
analitički sloj, ali tokom mjerenja ne radi nikakav mehanizam sinhronizacije
(change capture, replikacija ili kompakcija), dok produkcijski dual-store
sistemi taj trošak plaćaju kontinuirano. Izmjerena prednost je stoga **gornja
granica**: kvantificira koliko interferencije uklanja fizička separacija, a ne
neto dobit potpuno konzistentnog dual-store sistema. Aplikacije uz to vide
analitiku nad podacima koji nisu svježi u realnom vremenu.

**Memorijski budžet.** Preusmjerena ruka drži podatke dvaput — jednom u Hekaton
sloju i jednom kao columnstore kopiju — što otprilike udvostručuje zahtjev za
RAM-om. Gdje je memorija ograničena, usporedba se ne primjenjuje.

**Durabilnost.** Obje ruke koriste `SCHEMA_ONLY`, čime se eliminiraju upisi u
transakcijski log. Apsolutna propusnost bila bi niža uz `SCHEMA_AND_DATA`.
Budući da je postavka identična u obje ruke, prijavljeni omjer time nije
pogođen, mada njegova produkcijska veličina može biti.

**Opseg.** Sva mjerenja potiču iz jedne instance, jednog skupa podataka i jedne
hardverske konfiguracije. Generalizacija na distribuirane HTAP sisteme, druge
skupove podataka ili novije verzije DBMS-a traži oprez.

---

## VI. Zaključak

Držeći Hekaton transakcijski sloj fiksnim i premještajući samo analitičko
opterećenje na columnstore kopiju, transakcijska propusnost raste 3,3× do 6,9×
— efekt koji raste s konkurentnošću i objašnjava se natjecanjem za procesor
koje smo izmjerili, a ne pretpostavili.

Praktično čitanje: u single-engine HTAP postavci, **trošak analitike nije
ograničen na analitiku**. Ubrzanje upita — kroz columnstore indekse, batch-mode
izvršavanje ili fizičko preusmjeravanje — vraća i transakcijski kapacitet, a ne
samo analitičku latenciju, pa ga treba vrednovati prema oba budžeta.

Slijede dva pravca. Prvo, trošak sinhronizacije koji ovaj dizajn namjerno
isključuje treba izmjeriti, kako bi se ovdje prijavljena gornja granica mogla
pretvoriti u neto brojku za konzistentan dual-store sistem. Drugo, efekt
predviđa da bi raspoređivač svjestan opterećenja mogao usmjeravati analitičke
upite na onaj sloj koji trenutno ima procesorskog prostora; da li takvo
usmjeravanje adaptivno vraća izmjereni jaz, otvoreno je pitanje.
