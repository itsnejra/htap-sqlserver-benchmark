---
title: "Šta smo istraživali, kako, i šta se upravo dešava"
subtitle: "Potpuno objašnjenje projekta HTAPBenchmark, od nule"
author: "Projekat: Evaluacija HTAP obrade u Microsoft SQL Serveru 2022"
date: "August 2026"
lang: bs
geometry: margin=2.4cm
fontsize: 11pt
---

> **Za koga je ovaj dokument.** Za nekoga ko nikad nije radio s bazama podataka.
> Sve je objašnjeno od početka, običnim jezikom, uz poređenja iz svakodnevnog
> života. Stručni izrazi se uvode tek kad su potrebni, i uvijek se prvo objasne.

\tableofcontents

\newpage

# DIO 1: Osnove — šta je problem

## 1.1 Šta baza podataka uopšte radi

Zamislite veliku prodavnicu. Ona ima dvije potpuno različite vrste posla.

**Prvi posao: blagajna.** Kupac dolazi, kupuje tri stvari, plaća, odlazi. To
traje trideset sekundi. Kroz dan prođe hiljadu kupaca. Svaka transakcija je
kratka, dodiruje malo stvari, i mora biti **tačna** — ne smije se desiti da
novac ode a roba ne.

**Drugi posao: inventura i izvještaji.** Na kraju mjeseca neko sjedne i pita:
*„Koji artikal se najbolje prodavao? Koliko smo zaradili po odjelu? Kako se to
mijenjalo kroz godinu?"* Da bi odgovorio, mora **pregledati sve** — svaki
račun, svaki artikal, cijelu godinu. To traje satima.

Baza podataka radi tačno te dvije stvari, i one imaju imena:

| Naziv | Šta je | Primjer |
|---|---|---|
| **OLTP** | posao blagajne — kratke, brze operacije nad malo podataka | „upiši novi glas", „promijeni cijenu" |
| **OLAP** | posao izvještaja — duga čitanja koja pregledaju sve | „koliko postova mjesečno kroz tri godine" |

OLTP se izgovara *o-el-ti-pi*, OLAP *o-el-ap*. Slova znače „obrada transakcija
u realnom vremenu" odnosno „analitička obrada", ali to nije bitno zapamtiti.

## 1.2 Zašto se ta dva posla svađaju

Vratimo se u prodavnicu. Šta se desi ako inventuru radite **usred radnog dana**,
dok blagajne rade?

Osoba koja broji zalihe zauzima prolaze. Blagajnica koja treba nešto provjeriti
mora čekati. Red se stvara. Kupci odlaze.

Isto se dešava u bazi. Analitički upit koji čita **tri i po miliona redova**
zauzima procesor. Dok ga zauzima, transakcije koje trebaju taj isti procesor
čekaju.

> **Ovo je srž cijelog istraživanja.** Dva posla se bore za isti resurs.

## 1.3 Kako se to rješavalo do sada

Tradicionalno rješenje je jednostavno: **napravi dvije prodavnice.**

Jedna baza radi samo blagajnu. Druga baza radi samo izvještaje. Svaku noć se
podaci prekopiraju iz prve u drugu.

Taj noćni prepis zove se **ETL** (*extract-transform-load* — izvuci, preoblikuj,
učitaj). Radi, ali ima cijenu:

- **Izvještaji kasne.** Ako se kopira jednom dnevno, jutros gledate jučerašnje
  stanje.
- **Dva sistema.** Dvostruko održavanje, dvostruki trošak, dvostruko mjesta gdje
  nešto može puknuti.

Za neke stvari to je neprihvatljivo. Banka koja provjerava sumnjivu transakciju
ne može čekati do sutra. Detekcija prevare mora vidjeti **sadašnje** stanje.

## 1.4 HTAP — ideja da se to spoji

Otuda ideja: **neka jedna baza radi oba posla.** Bez noćnog kopiranja, bez
kašnjenja, bez dva sistema.

To se zove **HTAP** — *hibridna transakcijsko-analitička obrada*. Termin je
skovala istraživačka kuća Gartner 2014. godine.

Zvuči odlično. Problem je što se ta dva posla i dalje svađaju — samo što se sad
svađaju **unutar iste mašine**.

> **Pitanje kojim se bavi cijelo ovo istraživanje:** koliko tačno jedan posao
> smeta drugom, i šta se protiv toga može uraditi?

\newpage

# DIO 2: Alati koje smo mjerili

Microsoft SQL Server nudi dvije tehnologije koje pomažu svakoj strani. Njih smo
mjerili.

## 2.1 Hekaton — ubrzava blagajnu

**Hekaton** (zvanično „In-Memory OLTP") drži podatke **u radnoj memoriji**,
umjesto na disku.

Disk je kao skladište u podrumu — svaki put kad nešto trebate, neko mora sići i
donijeti. Memorija je polica iza leđa.

Uz to Hekaton koristi trik koji se zove **MVCC** (*viševerzijska kontrola
konkurentnosti*). Umjesto da zaključa red dok ga mijenja — što bi natjeralo
druge da čekaju — on napravi **novu verziju** tog reda. Ko je počeo čitati
ranije, vidi staru verziju. Niko ne čeka.

Zamislite dokument u koji svi mogu pisati istovremeno, a svako vidi svoju
snimljenu kopiju. Nema zaključavanja, nema reda.

**Rezultat:** transakcije 10 do 30 puta brže.

**Ali:** Hekaton je loš za analitiku. Njegovi indeksi su napravljeni da nađu
**jedan** red brzo, ne da pročitaju **sve** redove brzo. Kad analitički upit
mora pregledati sve, Hekaton to radi red po red — sporo.

## 2.2 Columnstore — ubrzava izvještaje

**Columnstore** (stupčasta pohrana) mijenja **način na koji su podaci složeni**.

Obična baza pamti podatke po redovima, kao tabelu u svesci:

```
Marko | 25 | Zenica
Ana   | 31 | Sarajevo
Ivan  | 28 | Tuzla
```

Columnstore pamti po stupcima:

```
imena:    Marko, Ana, Ivan
godine:   25, 31, 28
gradovi:  Zenica, Sarajevo, Tuzla
```

Zašto je to bolje za izvještaje? Ako pitate *„koliki je prosjek godina"*, u
prvom slučaju morate proći kroz sve — i imena, i gradove — da izvučete godine.
U drugom slučaju uzmete samo red „godine" i gotovo.

Uz to, kad su slične vrijednosti jedna do druge, **odlično se pakuju** (25, 31,
28 zauzimaju mnogo manje mjesta nego izmiješani podaci), i procesor ih može
obrađivati **hiljadu odjednom** umjesto jednu po jednu.

**Rezultat:** analitički upiti 10 do 100 puta brži.

## 2.3 Zašto se to dvoje ne može spojiti

Logično pitanje: zašto onda ne staviti columnstore **na** Hekaton tabele, pa da
oboje bude brzo?

**Zato što se međusobno isključuju.**

Hekaton stalno pravi nove verzije redova — to mu je princip rada. Columnstore
pakuje podatke u **zapečaćene, kompresovane pakete** koji se ne mogu mijenjati;
tako i postiže brzinu.

Ne možete istovremeno imati nešto što se stalno mijenja i nešto što je
zapečaćeno.

> **Ovo tehničko ograničenje je uzrok svega što mjerimo.** Jer ono znači da
> analitika nad Hekaton tabelama **mora** raditi na spori način, red po red.

\newpage

# DIO 3: Šta smo tačno napravili

## 3.1 Četiri konfiguracije

Napravili smo **četiri različita načina** da se isti podaci pohrane, u istoj
bazi, s istim sadržajem:

| Oznaka | Kako radi | Uloga |
|---|---|---|
| **Baseline** | sve na disku, klasično | referentna tačka |
| **CS** | na disku + columnstore za analitiku | brza analitika |
| **IM** | sve u memoriji (Hekaton) | brze transakcije |
| **HTAP** | transakcije u memoriji + **posebna kopija** za analitiku | pokušaj da se dobije oboje |

HTAP je zanimljiva. Pošto se Hekaton i columnstore ne mogu spojiti, ona ih
**razdvaja**: transakcije rade nad memorijskim tabelama, a analitika nad
odvojenom columnstore kopijom istih podataka.

To je kao da u prodavnici napravite **drugu prostoriju s kopijom zaliha**, pa
inventura ide tamo i ne smeta blagajnama.

## 3.2 Podaci

Koristili smo **stvarnu bazu Stack Overflowa** (sajt gdje programeri postavljaju
pitanja) iz 2010. godine — oko **19,2 miliona zapisa**.

Zašto stvarni podaci a ne izmišljeni? Zato što se u stvarnom životu aktivnost
**ne raspoređuje ravnomjerno**. Mali broj korisnika napiše ogromnu većinu
sadržaja. Izmišljeni podaci to ne oponašaju, pa daju previše lijepe rezultate.

## 3.3 Kako se mjeri

Napisali smo program koji **glumi korisnike**. On otvara više veza prema bazi
istovremeno — neke rade transakcije, neke analitiku — i mjeri koliko posla
stigne obaviti.

Svako mjerenje traje **70 sekundi**: prvih 10 se odbaci (sistem se „zagrijava"),
sljedećih 60 se broji.

Mijenjali smo tri stvari:

1. **Konfiguracija** — koja od četiri
2. **Omjer posla** — 80% transakcija / 20% analitike, pa 50/50, pa 20/80
3. **Opterećenje** — 4, 16 ili 32 istovremena korisnika

Sve kombinacije: 4 × 3 × 3 = **36 kombinacija**. Svaka ponovljena **30 puta**,
jer se pojedinačno mjerenje uvijek malo razlikuje.

**Ukupno: 1.080 mjerenja, oko 21 sat neprekidnog rada.** Nakon izbacivanja
nestabilnih, ostalo je **1.070 valjanih**.

## 3.4 Zašto 30 puta

Ako izmjerite jednom, ne znate je li broj tačan ili slučajnost. Ako izmjerite
trideset puta, vidite **koliko se vrijednosti rasipaju** i možete statistički
provjeriti je li razlika stvarna ili slučajna.

Za to koristimo **Mann-Whitneyev test**. On odgovara na pitanje: *„Kolika je
vjerovatnoća da bih ovakvu razliku dobio pukim slučajem?"* Ako je manja od
jedan promil, razliku smatramo stvarnom.

\newpage

# DIO 4: Prvi rezultati i naša pretpostavka

## 4.1 Šta smo izmjerili

HTAP konfiguracija je bila najbrža — očekivano. Ali jedna stvar nije bila
očekivana.

Uporedili smo **IM** i **HTAP**. One imaju **identičan transakcijski dio** —
iste tabele u memoriji, isti indeksi, iste procedure, iste postavke. Razlikuju
se **samo po tome gdje se izvršava analitika**.

I razlika u **transakcijskoj** propusnosti bila je 3,3 do 6,9 puta.

> Analitika je premještena, a **transakcije** su ubrzane. Iako u transakcijskom
> dijelu nije promijenjeno ništa.

## 4.2 Naša pretpostavka o tome šta se dešava

Objašnjenje koje smo ponudili:

> Analitički upit koji traje tri sekunde **drži procesor** tri sekunde. Ubrzajte
> ga da traje jednu — dvije sekunde procesora se oslobode i preuzmu ih
> transakcije.

Znači: **ubrzavanje analitike je istovremeno i ubrzavanje transakcija.** To je
zanimljivo jer se protivi uobičajenom shvatanju, po kojem se bolja analitika
uvijek plaća lošijim transakcijama.

## 4.3 Zašto pretpostavka nije bila dovoljna

Problem: mi to **nismo izmjerili**. Zaključili smo iz načina na koji baza
izvršava upite.

To nije dokaz. To je logično objašnjenje koje **može** biti tačno.

Zato smo dodali mjerenje serverskih brojača — sad znamo koliko procesorskog
vremena ide na transakcije, a koliko na analitiku, i koliko se čeka na procesor.

\newpage

# DIO 5: Prva greška koju smo sami našli

## 5.1 Šta je MAXDOP

Kad baza dobije težak upit, može ga podijeliti na više radnika. Postavka koja to
određuje zove se **MAXDOP** (*maksimalni stepen paralelizma*).

- `MAXDOP 1` = jedan radnik radi cijeli posao
- `MAXDOP 2` = dva radnika dijele posao

Kao kad kuću farba jedan majstor ili dvojica.

## 5.2 Greška

U IM konfiguraciji analitika je bila na `MAXDOP 1`. U HTAP na `MAXDOP 2`.

Postojao je razlog — pri više radnika nad memorijskim tabelama javljao se
problem sinhronizacije. Ali to znači da smo **mijenjali dvije stvari odjednom**:

1. gdje se analitika izvršava, **i**
2. koliko radnika je radi

Pa nismo mogli znati **koja od te dvije** je zaslužna za razliku.

To je kao da testirate novi recept i istovremeno promijenite i sastojke i
temperaturu pećnice. Kolač jeste bolji — ali zbog čega?

## 5.3 Kontrolni eksperiment

Rješenje: izmjeriti **IM s `MAXDOP 2`** — dakle izjednačiti broj radnika, pa
vidjeti koliko razlike ostane.

Rezultat:

| Opterećenje | Prije kontrole | Poslije kontrole |
|---|---|---|
| 4 korisnika | 3,33x | 2,76x |
| 16 korisnika | 4,65x | 1,90x |
| 32 korisnika | 6,92x | 1,92x |

**Oko dvije trećine razlike bio je broj radnika, ne arhitektura.**

Uz to, jedan argument iz rada je pao. Tvrdili smo da razlika **raste** s
opterećenjem, što bi značilo da se problem pogoršava kad se sistem puni.
Kontrolirano — razlika je **ravna**.

## 5.4 I jedno iznenađenje

Kad smo IM-u samo digli broj radnika s 1 na 2, njegova **transakcijska**
propusnost je skočila 3,6 puta — a u transakcijskom dijelu nije dirano ništa.

To je zapravo ista teza, dokazana **drugim putem** i mnogo čistije: mijenja se
jedan jedini broj u jednoj postavci, sve ostalo je identično.

\newpage

# DIO 6: Druga greška — i zašto sad mjerimo ponovo

## 6.1 Problem

Original je mjeren u jednoj **21-satnoj kampanji**. Kontrolna ruka je mjerena
**nekoliko sedmica kasnije**, u zasebnoj sesiji.

Između te dvije tačke: SQL Server je restartovan, tabele su izgubile sadržaj i
ponovo su učitane, mašina je bila u drugom stanju.

> Poredimo dvije stvari mjerene u **različitim uslovima**, a razliku pripisujemo
> jednoj postavci.

To je kao da mjerite koliko brzo trčite ujutro, pa isto to izmjerite nakon deset
sati posla — i razliku pripišete novim patikama.

## 6.2 Zašto sumnjamo da je efekt velik

Kratki probni test iste konfiguracije, u svježoj sesiji, dao je oko **26.000
transakcija u sekundi**. Ista konfiguracija u originalnoj kampanji: **6.325**.

Četiri puta razlike — **bez ijedne promjene u postavkama.**

Probni test je bio kratak, pa precjenjuje. Ali razlika je prevelika da bi se
ignorisala.

## 6.3 Šta upravo mjerimo

Sve tri konfiguracije, **jednu za drugom, u istoj sesiji**, bez restarta između:

1. IM s `MAXDOP 1`
2. IM s `MAXDOP 2`
3. HTAP

Traje oko 5,5 sati. Time se uklanja razlika u uslovima — sve tri se mjere pod
istim.

\newpage

# DIO 7: Kako se teza mijenja, ovisno o ishodu

Sve zavisi od toga hoće li razlika između `MAXDOP 1` i `MAXDOP 2` opstati kad
se obje mjere u istim uslovima.

## Scenarij A — razlika ostaje (oko 3,6x)

**Zaključak:** efekt je stvaran, a razlika u sesijama nije bila kriva.

**Teza rada:** *Ubrzanje analitike vraća transakcijski kapacitet.*

Rad ostaje kakav jeste, uz manje ispravke. Najlakši ishod.

## Scenarij B — razlika se smanji (oko 1,5–2x)

**Zaključak:** efekt postoji, ali je bio precijenjen zato što su ruke mjerene u
različitim uslovima.

**Teza rada:** ista, samo s manjim brojevima i uz izričitu napomenu koliko je
otpadalo na uslove mjerenja.

Rad je i dalje dobar — čak pošteniji, jer sam navodi svoju grešku.

## Scenarij C — razlika nestane

**Zaključak:** onih 3,6x nije bio `MAXDOP`, nego razlika u uslovima mjerenja.

Ovo na prvi pogled izgleda kao propast. **Nije.**

**Nova teza:** *U dugim mjernim kampanjama, redoslijed mjerenja sam po sebi
proizvodi razlike veće od onih koje se pripisuju arhitekturi.*

Ako ista konfiguracija, s istim postavkama, na istoj mašini daje četiri puta
različit rezultat samo zato što je mjerena u drugom trenutku — to je **nalaz
koji pogađa svaki rad ove vrste**, ne samo naš.

Dokaz bi bio već izmjeren. A poruka bi bila primjenjiva na cijelu oblast, ne
samo na jednu bazu.

## Šta ostaje sigurno u sva tri slučaja

| | |
|---|---|
| 1.070 valjanih mjerenja | ostaje |
| Poređenja **unutar** kampanje | ostaju valjana — sve četiri konfiguracije mjerene pod istim uslovima |
| Nalaz da analitika troši 83–91% procesora | ostaje |
| Mjerna infrastruktura i javni repozitorij | ostaje |
| Automatska provjera svake brojke u radu | ostaje |

**Ni u jednom scenariju se ne gubi rad.** Mijenja se samo koja tvrdnja stoji
naprijed.

\newpage

# DIO 8: Zašto je ovo, sve u svemu, dobra vijest

Postoje dva načina da rad ima grešku.

**Prvi:** greška ostane skrivena, rad se objavi, pa je neko drugi nađe. To je
loše — i za rad i za autora.

**Drugi:** autor je nađe sam, izmjeri koliko iznosi, i uvrsti je u rad kao
nalaz.

Mi smo u drugom slučaju. **Dvaput.**

Prvo smo našli da smo mijenjali dvije stvari odjednom — izmjerili smo koliko je
to iznosilo i to postalo dio rada. Sad smo našli da smo poredili mjerenja iz
različitih uslova — i to upravo mjerimo.

Rad koji sam pronađe svoje slabosti i izbroji ih **jači je** od onog koji ih
prešuti. Recenzenti to prepoznaju.

## Šta ovaj projekat ima, a većina nema

- **1.070 mjerenja** u punom faktorijalnom dizajnu
- **Neparametarsku statistiku** primjerenu podacima koji nisu normalno
  raspoređeni
- **Direktno mjerenje mehanizma** — ne samo pretpostavku
- **Kontrolni eksperiment** koji je razdvojio dvije pomiješane stvari
- **Automatsku reviziju** koja preračunava svaku brojku iz sirovih podataka i
  javlja ako se ne poklapa
- **Javni repozitorij** s kodom, skriptama i mjerenjima

To je više nego što ima većina radova ovog obima.

---

## Rječnik

| Pojam | Znači |
|---|---|
| **OLTP** | kratke, brze operacije — „posao blagajne" |
| **OLAP** | duga čitanja koja pregledaju sve — „posao izvještaja" |
| **HTAP** | jedna baza radi oba posla |
| **ETL** | noćno prekopiranje podataka iz jedne baze u drugu |
| **Hekaton** | tehnologija koja drži podatke u memoriji radi bržih transakcija |
| **Columnstore** | podaci složeni po stupcima radi brže analitike |
| **MVCC** | pravljenje novih verzija reda umjesto zaključavanja |
| **MAXDOP** | koliko radnika baza koristi za jedan upit |
| **Propusnost** | koliko posla se obavi u sekundi |
| **Latencija** | koliko traje jedna operacija |
| **Medijan** | srednja vrijednost po redoslijedu — otpornija na izuzetke od prosjeka |
| **Konfiguracija** | jedan od četiri načina pohrane koje smo mjerili |
| **Ruka** | jedna serija mjerenja pod određenim uslovima |
