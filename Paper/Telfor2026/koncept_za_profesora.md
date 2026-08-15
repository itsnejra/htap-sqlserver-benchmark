---
title: "Prijedlog rada za konferenciju TELFOR 2026"
subtitle: "Ubrzanje analitike kao optimizacija transakcijske obrade u Microsoft SQL Serveru 2022"
author: "Nejra Smajlović · Politehnički fakultet, Univerzitet u Zenici"
date: "August 2026"
lang: bs
geometry: margin=2.3cm
fontsize: 11pt
colorlinks: true
linkcolor: black
urlcolor: blue
---

> **Sažetak prijedloga.** Predlažem rad od četiri stranice za konferenciju
> TELFOR 2026, izveden iz eksperimentalnog istraživanja provedenog u okviru
> predmeta Optimizacija baza podataka. Rad iznosi nalaz koji je suprotan
> uvriježenom shvatanju u literaturi o HTAP sistemima, potkrijepljen s 1.070
> mjernih serija i dvjema nezavisnim eksperimentalnim intervencijama. Cjelokupan
> izvorni kod, SQL skripte i sirovi rezultati javno su dostupni.

# 1. Predložena tema

**Radni naslov (engleski):**
*Analytical Acceleration as an OLTP Optimization: Two Independent Levers on the
Same Mechanism in SQL Server 2022*

**Naslov (bosanski):**
*Ubrzanje analitike kao optimizacija transakcijske obrade: dvije nezavisne
poluge nad istim mehanizmom u SQL Serveru 2022*

| | |
|---|---|
| **Konferencija** | TELFOR 2026 |
| **Format** | 4 stranice, IEEE dvokolonski |
| **Jezik** | engleski |
| **Predloženi autori** | N. Smajlović, D. Čeke |
| **Status** | rad napisan, kompajliran, sve brojke izmjerene |

# 2. Teza

> **U sistemu u kojem transakcijska i analitička obrada dijele isti procesorski
> resurs, ubrzanje analitičkih upita nije samo analitička nego i transakcijska
> optimizacija.**

Obrazloženje je jednostavno, ali u literaturi nije kvantificirano. Analitički
upit koji se izvršava tri sekunde zauzima procesor tri sekunde. Isti upit
ubrzan na jednu sekundu oslobađa dvije sekunde procesorskog vremena — a to
vrijeme preuzimaju transakcijske niti koje su na iste procesore čekale.

Posljedica je da svaka mjera koja skraćuje analitičko skeniranje — columnstore
indeks, batch-mode izvršavanje, veći stepen paralelizma, fizičko preusmjeravanje
— donosi i transakcijski kapacitet, iako se u praksi vrednuje isključivo kao
analitička investicija.

# 3. Zašto je tema vrijedna objavljivanja

## 3.1 Suprotstavlja se uvriježenom okviru

Literatura o HTAP sistemima dosljedno postavlja odnos dvaju opterećenja kao
**kompromis**: bolja analitika se plaća transakcijskim performansama, a
odvajanje analitičkog sloja štiti transakcije po cijenu replikacije i
sinhronizacije. Ubrzanje analitike se pritom tretira kao korist za analitiku,
plaćena negdje drugdje.

Naš rad pokazuje da je taj obračun nepotpun: dio troška se **vraća** kroz
transakcijski kapacitet, i taj povrat je mjerljiv i velik.

## 3.2 Popunjava konkretnu prazninu

Postojeće usporedbe HTAP sistema nužno mijenjaju više faktora odjednom — medij
pohrane, durabilnost, engine i model izvršavanja upita — pa se član
interferencije ne može odvojiti od arhitekturalnih članova. Naš prvi
eksperiment mijenja **jedan query hint i ništa drugo**, čime taj član izoluje.

## 3.3 Nezavisna evaluacija komercijalnog sistema

Kombinaciju Hekaton in-memory engine-a i columnstore indeksa u SQL Serveru
opisali su sami autori sistema, uz vlastite mikro-benchmarkove. Nezavisna,
statistički rigorozna evaluacija nad stvarnim skupom podataka u akademskoj
literaturi izostaje.

# 4. Kako se teza dokazuje

Teza se dokazuje **dvjema nezavisnim intervencijama** nad analitičkim
opterećenjem, uz transakcijski sloj držan potpuno nepromijenjenim. Ključ je u
tome što obje ciljaju isti mehanizam, a ne dijele ništa drugo.

## Poluga 1 — paralelizam (metodološki najčistiji dokaz)

Analitičkim upitima je stepen paralelizma podignut s `MAXDOP 1` na `MAXDOP 2`.
Nepromijenjeni ostaju: shema baze, tabele, indeksi, pohranjene procedure,
medij pohrane, model izvršavanja, postavka durabilnosti i podaci.
**Razlikuje se jedan broj u jednom query hintu.**

| Konkurentnost | Prije | Poslije | Dobitak |
|---|---:|---:|---:|
| C = 4 | 3.027 ops/s | 3.658 ops/s | **1,21$\times$** |
| C = 16 | 7.726 ops/s | 18.939 ops/s | **2,45$\times$** |
| C = 32 | 6.325 ops/s | 22.808 ops/s | **3,61$\times$** |

Transakcijska propusnost raste do 3,6 puta, **a u transakcijskom sloju nije
promijenjeno ništa.** Ovo je tvrdnja rada u najdirektnijem obliku i ne oslanja
se ni na kakvu arhitekturalnu usporedbu.

## Poluga 2 — smještaj analitike

Analitički upiti su preusmjereni s memorijsko-optimiziranih tabela na
columnstore kopiju istih podataka, pri **izjednačenom** paralelizmu.

| Konkurentnost | Dobitak | Cohenov *d* |
|---|---:|---:|
| C = 4 | 2,76$\times$ | 4,51 |
| C = 16 | 1,90$\times$ | 5,33 |
| C = 32 | 1,92$\times$ | 7,52 |

Sve razlike značajne na $p < 0{,}001$ nakon Bonferroni korekcije.

![Transakcijska propusnost pod objema intervencijama, pri omjeru opterećenja 80/20 OLTP/OLAP. Prelaz sivo $\rightarrow$ narandžasto izoluje efekt paralelizma; narandžasto $\rightarrow$ plavo izoluje efekt smještaja pri jednakom paralelizmu. Transakcijski sloj je identičan u sve tri kolone.](slika1.png)

## Poluga 3 — mjereni mehanizam

Objašnjenje putem natjecanja za procesor je tvrdnja o hardveru, pa je tako i
provjerena. Radne veze benchmarka su označene tako da se procesorsko vrijeme iz
`sys.dm_exec_sessions` može odvojeno pripisati transakcijskim i analitičkim
nitima, uz uzorkovanje `sys.dm_os_wait_stats` kroz mjernu fazu.

| Konkurentnost | Udio analitike u CPU vremenu | Čekanje na procesorski kvantum |
|---|---:|---:|
| C = 4 | 91 % | 0,4 s |
| C = 16 | 82 % | 4,3 s |
| C = 32 | 85 % | **56,4 s** |

Analitika, iako čini svega 20 % operacija, troši preko 80 % procesorskog
vremena. Čekanje `SOS_SCHEDULER_YIELD` — koje bilježi da je zadatak potrošio
dodijeljeni procesorski kvantum i morao ustupiti mjesto — raste za **dva reda
veličine** kroz ispitani raspon konkurentnosti.

Mehanizam time nije pretpostavljen iz plana izvršavanja upita, nego izmjeren.

# 5. Dodatni doprinos: metodološko upozorenje

Prva verzija analize uspoređivala je dvije konfiguracije direktno i dobila jaz
od 3,3$\times$ do 6,9$\times$. Kontrolni eksperiment je pokazao da je ta usporedba mijenjala
**dvije stvari odjednom** — smještaj analitike i stepen paralelizma — jer je
memorijsko-optimizirana konfiguracija koristila `MAXDOP 1` da izbjegne
`CXSYNC_PORT` zastoje svojstvene paralelnim planovima nad Hekaton tabelama.

Razdvajanjem tih članova pokazalo se sljedeće:

- Pri C = 32, **oko dvije trećine prividne arhitekturalne prednosti** bila je
  razlika u paralelizmu.
- Nekontrolirana usporedba raste s konkurentnošću (3,33 $\rightarrow$ 6,92), što navodi na
  zaključak da se arhitekturalna interferencija pojačava sa zasićenjem sistema.
  Kontrolirano, efekt smještaja je **ravan** (2,76 $\rightarrow$ 1,90 $\rightarrow$ 1,92). Ono što
  skalira jeste član paralelizma.

Nekontrolirana usporedba dakle ne bi samo precijenila veličinu efekta, nego bi
**pogrešno pripisala i njegov trend**.

Pouka je općenitija od ovog rada: `MAXDOP 1` nije proizvoljan hendikep nego
tehnički nužna odluka za tu konfiguraciju. Odluka o podešavanju koja je
**pojedinačno potpuno opravdana** postaje confounding varijabla čim se
konfiguracije počnu uspoređivati. HTAP evaluacije koje izvještavaju omjere na
razini arhitekture trebale bi navesti kako su takvi parametri držani — a
uglavnom to ne čine.

Ovaj nalaz smatram vrijednim koliko i glavnu tezu, jer je primjenjiv na svaku
komparativnu evaluaciju baza podataka.

# 6. Struktura rada

| Sekcija | Sadržaj |
|---|---|
| I. Uvod | HTAP kontekst, praznina u literaturi, formulacija dviju intervencija |
| II. Teorijska osnova | Hekaton, columnstore, arhitekturalna nespojivost MVCC i kompresiranih segmenata; pregled radova o interferenciji i izolaciji |
| III. Eksperimentalni dizajn | Tri ruke eksperimenta, radna opterećenja, skup podataka, statistička metodologija |
| IV. Rezultati | Poluga paralelizma; poluga smještaja; confound kao nalaz; mjereni mehanizam; analitička latencija |
| V. Prijetnje validnosti | Šta eksperiment ne pokriva, otvoreno navedeno |
| VI. Zaključak | Praktična i metodološka poruka, dva pravca za dalje |

Rad sadrži tri slike i jednu tabelu, i staje u zadana četiri stranice.

# 7. Eksperimentalna osnova

| | |
|---|---|
| **Skup podataka** | StackOverflow2010 — javni dump produkcijske baze, oko 19,2 miliona zapisa |
| **Zašto ne TPC** | stvarna Pareto distribucija korisničke aktivnosti, koju sintetički generatori ne reproduciraju |
| **Dizajn** | puni faktorijalni 4 x 3 x 3 (konfiguracija x omjer opterećenja x konkurentnost), 30 ponavljanja po ćeliji |
| **Obim** | 1.080 planiranih serija, 1.070 validnih (oko 21 h mjerenja) |
| **Kontrolni eksperiment** | dodatnih 90 serija pri izjednačenom paralelizmu |
| **Trajanje runa** | 10 s zagrijavanja (odbacuje se) + 60 s mjerenja |
| **Opterećenje** | 6 transakcijskih procedura (75 % upisa) + 5 analitičkih agregacijskih upita |
| **Hardver** | Intel Core i9-14900HX (24 jezgra / 32 niti), 32 GB DDR5, NVMe SSD |
| **Softver** | SQL Server 2022 Developer Edition, Windows 11, .NET 8 mjerna aplikacija |
| **Statistika** | Shapiro-Wilk (nenormalnost potvrđena), Mann-Whitney *U* s Bonferroni korekcijom, Cohenov *d*, log-linearna OLS regresija |

Mjerna aplikacija je razvijena namjenski u .NET 8, s asinhronim transakcijskim
i analitičkim radnim nitima preko odvojenih veza, i podržava nastavak rada
nakon prekida.

# 8. Doprinosi rada

1. **Kvantificiran transakcijski povrat od ubrzanja analitike** — do 3,6$\times$, uz
   transakcijski sloj držan nepromijenjenim, dokazan dvjema nezavisnim
   intervencijama.

2. **Mehanizam izmjeren, a ne pretpostavljen** — atribucija procesorskog
   vremena po tipu radne niti i statistika čekanja na razini raspoređivača.

3. **Kvantificiran confound koji druge evaluacije ne kontroliraju** —
   precjenjivanje do 3,6$\times$ i pogrešno pripisan trend.

4. **Nezavisna evaluacija SQL Server 2022 mehanizama** nad stvarnim skupom
   podataka, u punom faktorijalnom dizajnu s neparametarskom analizom.

5. **Potpuna reproducibilnost** — izvorni kod, SQL skripte, mjerni rezultati i
   analitičke skripte javno dostupni na
   <https://github.com/itsnejra/htap-sqlserver-benchmark>.

# 9. Ograničenja koja rad otvoreno navodi

Smatram da rad dobija na uvjerljivosti time što ograničenja navodi sam, prije
nego što ih recenzent nađe:

- **Kontrola paralelizma provedena u jednom smjeru.** Paralelizam je izjednačen
  na DOP = 2. Recipročna ruka (preusmjerena konfiguracija na DOP = 1) nije dala
  upotrebljiva mjerenja i ne izvještava se.

- **Serverski brojači pokrivaju jednu ruku.** Instrumentacija je dodana nakon
  glavne mjerne kampanje, pa opisuje potrošnju procesora u row-mode ruci bez
  kontrasta prema preusmjerenoj.

- **Bez troška sinhronizacije.** Preusmjerena konfiguracija ne održava svježinu
  analitičke kopije tokom mjerenja, pa je taj rezultat gornja granica.
  *Rezultat za paralelizam ne nosi tu ogradu — ne uključuje nikakvu kopiju.*

- **Natjecanje, ne zasićenje.** Ukupna iskorištenost procesora doseže 26,8 % od
  32 dostupne niti, pa rad govori o natjecanju za vrijeme raspoređivača, a ne o
  zasićenju mašine. To je slabija i tačnija tvrdnja od one koju bi podaci na
  prvi pogled dopustili.

- **Opseg.** Jedna instanca, jedan skup podataka, jedna hardverska
  konfiguracija.

# 10. Status i šta preostaje

**Završeno:**

- Rad napisan i kompajliran — 4 stranice, tri slike, bez grešaka
- Sve brojke u tekstu su izmjerene; nema nijedne nepokrivene tvrdnje
- Kontrolni eksperiment proveden i uključen
- Mjerna infrastruktura, analitičke skripte i dijagnostika u repozitoriju

**Preostaje prije slanja:**

1. **Provjera bibliografije.** Nekoliko referenci treba dopuniti punim
   podacima i potvrditi. Ovo smatram prioritetom.
2. **Prilagodba predlošku** koji TELFOR propisuje, uz ponovnu provjeru limita
   od četiri stranice.
3. **Opciono:** ponoviti neuspjelu kontrolnu ruku, čime bi se efekt smještaja
   utvrdio na dvije razine paralelizma umjesto na jednoj.

# 11. Molba

Bila bih Vam zahvalna na mišljenju o sljedećem:

- Je li teza dovoljno jasno postavljena i je li odabrani naglasak
  (poluga paralelizma kao primarni dokaz) pravi?
- Smatrate li da je metodološki nalaz iz sekcije 5 vrijedan isticanja u
  sažetku, ili bi rad bio jači bez njega?
- Postoji li literatura koju bi trebalo uključiti, a koju sam propustila?
- Je li TELFOR pravi izbor, ili biste predložili drugu konferenciju?

Rad, izvorni kod i svi mjerni podaci stoje Vam na raspolaganju u repozitoriju.
