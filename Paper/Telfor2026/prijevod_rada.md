# Prijevod Telfor rada na bosanski

Radna verzija za čitanje — **nije** za slanje. Rad se šalje na engleskom
(`telfor2026.tex`). Ovo služi samo da vidiš šta tekst zapravo tvrdi.

> **Verzija 2** — rad je prepisan nakon MAXDOP kontrolnog eksperimenta.
> Teza je ostala ista, ali su brojke i glavni dokaz drugi. Sve brojke u ovoj
> verziji su izmjerene; jedino što fali su e-mail adrese autora.

---

## Naslov

**Ubrzanje analitike kao optimizacija transakcija: dvije nezavisne poluge nad
istim mehanizmom u SQL Serveru 2022**

---

## Sažetak

HTAP se obično vrednuje kao kompromis, gdje se analitička propusnost plaća
gubitkom transakcijske. Mi izvještavamo o kontroliranim mjerenjima u kojima
vrijedi suprotno: u single-engine postavci, **omogućiti analitičkim upitima da
se prije završe vraća transakcijski kapacitet**, jer oba opterećenja crpe iz
istih procesora.

To pokazujemo dvjema nezavisnim intervencijama nad jednom konfiguracijom SQL
Servera 2022, čiji je transakcijski sloj cijelo vrijeme držan fiksnim:

- **Podizanje stepena paralelizma analitičkih upita** — promjena jednog jedinog
  query hinta, uz istu shemu, isti medij pohrane i isti model izvršavanja —
  podiže **transakcijsku** propusnost 1,2× do 3,6×.
- **Premještanje analitike na columnstore kopiju** podiže je 1,9× do 2,8× nad
  istom osnovom, pri izjednačenom paralelizmu.

Serverski brojači potvrđuju mehanizam direktno: analitičke niti troše 82–91%
procesorskog vremena benchmarka, a čekanja na dodjelu procesorskog kvantuma
rastu s 0,4 s na 56,4 s po runu od 60 s između najniže i najviše razine
konkurentnosti.

Mjerenja potiču iz punog faktorijalnog dizajna nad StackOverflow2010 (~19,2
miliona zapisa) s 30 runova po ćeliji. Pokazujemo i da nekontrolirana
usporedba, u kojoj se paralelizam razlikuje između ruku, **precjenjuje efekt
do 3,6×**.

---

## I. Uvod

Sistemi koji iz jedne baze opslužuju i transakcijska i analitička opterećenja
moraju pomiriti dva suprotna obrasca pristupa: kratke točkaste operacije uz
stroge zahtjeve konzistentnosti, i duga skeniranja koja agregiraju milione
redova.

Literatura izbor između dizajna postavlja kao kompromis u **izolaciji**:
odvajanje analitičkog engina štiti transakcijske performanse, po cijenu
replikacije i sinhronizacije. Taj okvir tretira ubrzanje analitike kao korist
za analitiku, plaćenu negdje drugdje.

**Ovaj rad tvrdi da je taj obračun nepotpun.** Gdje jedan engine opslužuje oba
opterećenja, procesori koje analitičko skeniranje zauzima jesu procesori koje
transakcijski engine ne može koristiti — pa je sve što skraćuje to skeniranje
ujedno i transakcijska optimizacija.

To testiramo intervenirajući nad analitičkim opterećenjem **dvaput**, na načine
koji ne dijele ništa osim mehanizma koji ciljaju:

1. **Paralelizam.** Podigni stepen paralelizma analitičkih upita s 1 na 2.
   Shema, medij, model izvršavanja i svaki transakcijski objekt su
   nepromijenjeni; razlikuje se jedan query hint.
2. **Smještaj.** Premjesti analitičke upite s memorijsko-optimiziranih tabela
   na columnstore kopiju istih podataka, pri jednakom paralelizmu.

Ako je objašnjenje putem natjecanja tačno, obje intervencije trebaju podići
transakcijsku propusnost, i nijedna se ne može objasniti transakcijskim
inženjeringom. **Obje je podižu.**

---

## II. Teorijska osnova

*(Ova sekcija je uglavnom nepromijenjena u odnosu na prvu verziju.)*

**Hekaton** je redizajnirani OLTP engine — optimistična viševerzijska kontrola
konkurentnosti, lock-free strukture koje zaobilaze buffer pool, nativno
kompajlirane procedure; 10–30× za točkaste operacije. Ali nije građen za
skeniranja: hash indeksi ne služe rasponskom pristupu, i nema batch-mode.

**Columnstore** pohranjuje vrijednosti stupca u kompresiranim segmentima,
obrađuje ih batch-mode executor nad ~1000 redova odjednom, 10–100× za skladišne
upite.

Dva dizajna su nespojiva u jednom smjeru: **MVCC version chains se ne mogu
održavati nad nepromjenjivim kompresiranim segmentima.** Zato analitički upiti
u memorijsko-optimiziranoj shemi padaju u row-mode — i to je izvor efekta koji
mjerimo.

Ono što u literaturi nedostaje jeste **transakcijski povrat od ubrzanja
analitike, izoliran od svake druge razlike.** Usporedbe između HTAP sistema
nužno mijenjaju medij, durabilnost, engine i model izvršavanja zajedno. Naša
prva poluga mijenja jedan query hint i ništa drugo.

---

## III. Eksperimentalni dizajn

### Tri ruke

| | **IM** | **IM-P** | **OFF** |
|---|---|---|---|
| OLTP pohrana | Hekaton (RAM) | Hekaton (RAM) | Hekaton (RAM) |
| OLTP indeksi | hash + range | hash + range | hash + range |
| OLTP procedure | nativne | nativne | nativne |
| Durabilnost | `SCHEMA_ONLY` | `SCHEMA_ONLY` | `SCHEMA_ONLY` |
| **OLAP cilj** | iste tabele | iste tabele | **columnstore** |
| **OLAP izvršavanje** | row-mode | row-mode | **batch-mode** |
| **OLAP MAXDOP** | **1** | **2** | **2** |

- **IM i IM-P razlikuju se u tačno jednom query hintu.**
- **IM-P i OFF razlikuju se u smještaju analitike, pri jednakom paralelizmu.**
- Par IM/OFF — usporedba koju smo prvo napravili — razlikuje se u oboje
  odjednom, i sekcija IV-C pokazuje šta to košta.

### Opterećenje i okruženje

StackOverflow2010 (~19,2 miliona zapisa), odabran zbog Pareto distribucije
korisničke aktivnosti koju TPC generatori ne reproduciraju.

Šest transakcijskih procedura s težinom na upisima (35% unos glasa, 25%
ažuriranje score-a, 15% unos komentara, 25% čitanja). Pet analitičkih
agregacijskih upita s punim skeniranjima.

Puni faktorijalni: 3 omjera × 3 razine konkurentnosti (C ∈ {4, 16, 32}) × 30
runova. Rezultati se izvještavaju pri omjeru 80/20, gdje je pitanje
transakcijskog povrata najoštrije. Svaki run: 10 s warmup (odbacuje se) + 60 s
mjerenja.

Hardver: i9-14900HX (24 jezgra / 32 niti), 32 GB DDR5, NVMe SSD, Windows 11,
SQL Server 2022 Developer Edition.

---

## IV. Rezultati

### A. Poluga jedan: paralelizam

Podizanje analitičkog paralelizma s 1 na 2, uz sve ostalo nepromijenjeno,
podiže transakcijsku propusnost:

| | dobitak |
|---|---|
| C = 4 | **1,21×** |
| C = 16 | **2,45×** |
| C = 32 | **3,61×** |

U apsolutnim brojevima pri C = 32: **6.325 → 22.808 ops/s**.

> Ništa u transakcijskoj putanji nije dirano. Nijedan indeks, nijedna
> procedura, nijedna postavka durabilnosti, nijedan medij, nijedna shema.
> Analitički upiti se jednostavno prije završe, a transakcijski engine povrati
> procesore koje su držali.

**Ovo je tvrdnja rada u najdirektnijem obliku i ne ovisi ni o kakvoj
arhitekturalnoj usporedbi.**

### B. Poluga dva: smještaj

Premještanje analitike na columnstore kopiju, mjereno protiv IM-P tako da je
paralelizam jednak:

| | dobitak | Cohenov d |
|---|---|---|
| C = 4 | 2,76× | 4,51 |
| C = 16 | 1,90× | 5,33 |
| C = 32 | 1,92× | 7,52 |

Sve razlike značajne na p < 0,001 nakon Bonferroni korekcije.

Zanimljivo: **smještaj ne dominira nad paralelizmom.** Pri visokoj
konkurentnosti, dati row-mode skeniranjima drugi procesor vraća više
transakcijske propusnosti (3,61×) nego premjestiti ih na columnstore pri
fiksnom paralelizmu (1,92×). Ono što dijele jeste smjer i mehanizam.

### C. Confounding varijabla paralelizma

Direktna usporedba IM protiv OFF — prirodna arhitekturalna usporedba, i ona
koju smo prvo napravili — daje 3,33×, 4,65× i 6,92×. Te brojke **miješaju obje
poluge.**

Odnos nekontrolirane i kontrolirane usporedbe je 1,21×, 2,45× i 3,61×: pri
C = 32, **otprilike dvije trećine prividne arhitekturalne prednosti jeste
razlika u paralelizmu.**

Iskrivljenje nije ravnomjerno, i to je bitno za tumačenje:

- Nekontrolirana usporedba **strmo raste** s konkurentnošću (3,33 → 6,92), što
  navodi na čitanje da se arhitekturalna interferencija pojačava kako se
  sistem zasićuje.
- Kontrolirano, efekt smještaja je **ravan do blago opadajući**
  (2,76 → 1,90 → 1,92); ono što skalira jeste **član paralelizma**.

Evaluacija koja ostavi `MAXDOP` nekontroliranim ne bi dakle samo precijenila
veličinu — nego bi **pogrešno pripisala i trend**.

Napominjemo da `MAXDOP 1` nije proizvoljan hendikep: nužan je da se izbjegnu
`CXSYNC_PORT` zastoji na memorijsko-optimiziranim tabelama pod paralelnim
planovima, i zato ga je originalna konfiguracija i koristila. Confound nastaje
upravo zato što se **obranjiva odluka o podešavanju po konfiguraciji razlikuje
između ruku.**

### D. Direktan dokaz mehanizma

Radne veze su označene tako da se `cpu_time` iz `sys.dm_exec_sessions` može
atribuirati transakcijskim i analitičkim nitima odvojeno, a
`sys.dm_os_wait_stats` uzorkuje kroz mjernu fazu.

| C | udio analitike u CPU vremenu | SOS_SCHEDULER_YIELD |
|---|---|---|
| 4 | 91% | 0,4 s |
| 16 | 82% | 4,3 s |
| 32 | 85% | **56,4 s** |

Rast od dva reda veličine u čekanju na procesorski kvantum.

> **Važna ograda u radu:** ukupna iskorištenost procesora doseže 26,8% od 32
> dostupne hardverske niti pri C = 32, dakle mašina **nije zasićena u cjelini**.
> Natjecanje je za vrijeme raspoređivača među nitima koje su stvarno angažirane,
> a ne za posljednju jedinicu kapaciteta mašine. To je slabija i tačnija tvrdnja
> od „zasićenja procesora", i to je ono što brojači podupiru.

### E. Analitička latencija

Analitička strana pokazuje istu granicu iz drugog smjera. Pri C = 4 row-mode je
zapravo **brži** od columnstore kopije (641 ms naspram 832 ms): sa svim
podacima u RAM-u i nezauzetim procesorima, row-mode skeniranje je sasvim
dovoljno. Poredak se obrće kako konkurentnost raste — 2.126 vs 1.045 ms pri
C = 16, i 3.292 vs 1.768 ms pri C = 32.

Analitičke i transakcijske performanse dakle **degradiraju zajedno, preko istog
raspona, jer degradiraju iz istog razloga.**

---

## V. Prijetnje validnosti

**Samo jedan smjer kontrole paralelizma.** Izjednačili smo paralelizam na
DOP = 2. Recipročna ruka, koja bi preusmjerenu konfiguraciju pustila na
DOP = 1, nije dala upotrebljiva mjerenja i ne izvještava se. Efekt smještaja je
stoga utvrđen na jednoj razini paralelizma, a ne na dvije.

**Brojači pokrivaju samo jednu ruku.** Serverska atribucija procesora dodana je
nakon glavne mjerne kampanje i dostupna je samo za IM-P ruku. Slika 3 opisuje
kako analitika troši procesorsko vrijeme u row-mode ruci; ne stavlja to u
kontrast s preusmjerenom rukom, što bi tražilo ponavljanje cijele kampanje pod
instrumentacijom.

**Nema troška sinhronizacije.** Preusmjerena ruka odvaja slojeve, ali tokom
mjerenja ne radi nikakav mehanizam sinhronizacije. Rezultat za smještaj je
**gornja granica**, i aplikacije bi vidjele analitiku nad podacima koji nisu
svježi u realnom vremenu. **Rezultat za paralelizam ne nosi tu ogradu** — ne
uključuje nikakvu kopiju.

**Memorija i durabilnost.** Preusmjerena ruka drži podatke dvaput, otprilike
udvostručujući zahtjev za RAM-om. Sve ruke koriste `SCHEMA_ONLY`, čime se
eliminiraju upisi u transakcijski log.

**Opseg.** Jedna instanca, jedan skup podataka, jedna hardverska konfiguracija.

---

## VI. Zaključak

Dvije nezavisne intervencije nad analitičkim opterećenjem jedne konfiguracije
SQL Servera 2022 — podizanje paralelizma upita i premještanje upita na
columnstore kopiju — svaka podiže transakcijsku propusnost **bez ijedne izmjene
u transakcijskom sloju**, za 1,2–3,6× odnosno 1,9–2,8×.

U single-engine HTAP postavci, **trošak analitike nije ograničen na analitiku**,
i ubrzanje upita treba budžetirati i prema transakcijskom kapacitetu, a ne samo
prema analitičkoj latenciji.

Studija nosi i **metodološko upozorenje**. Naša vlastita početna usporedba, koja
je mijenjala smještaj i paralelizam zajedno, precijenila je arhitekturalni efekt
do 3,6× i **obrnula njegov prividni trend s konkurentnošću**. Odluke o
podešavanju po konfiguraciji, koje su pojedinačno obranjive, postaju confounding
varijable kada se konfiguracije uspoređuju — pa HTAP evaluacije koje izvještavaju
omjere na razini arhitekture trebaju navesti kako su takvi parametri držani.

Slijede dva pravca: izmjeriti trošak sinhronizacije koji ovaj dizajn isključuje,
i ispitati može li raspoređivač svjestan opterećenja usmjeravati analitičke
upite na sloj koji trenutno ima procesorskog prostora.
