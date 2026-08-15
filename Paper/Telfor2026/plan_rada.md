---
title: "Plan rada za TELFOR 2026"
subtitle: "Šta koristiti iz postojećeg istraživanja, šta pisati, i odakle svaki rezultat dolazi"
author: "Projekat HTAPBenchmark · Nejra Smajlović"
date: "August 2026"
lang: bs
geometry: margin=2.3cm
fontsize: 11pt
---

> **Zašto ovaj dokument.** Tokom provjere rezultata otkrivena su dva problema u
> mjerenju koja mijenjaju koji se zaključci mogu izvesti. Ovdje je izloženo:
> šta je od postojećeg rada upotrebljivo, šta nije, koji rad se može napisati
> tako da svaka tvrdnja stoji, i odakle dolazi svaka pojedinačna brojka.

\tableofcontents

\newpage

# 1. Odakle krećemo

## 1.1 Šta postoji

Projekat od 43 stranice sadrži:

| Resurs | Obim |
|---|---|
| Mjerna kampanja | 1.080 serija, 1.070 valjanih, ~21 sat |
| Dizajn | puni faktorijalni 4 konfiguracije x 3 omjera x 3 razine x 30 ponavljanja |
| Skup podataka | StackOverflow2010, ~19,2 miliona zapisa |
| Mjerni sistem | .NET 8 aplikacija, javni repozitorij |
| Statistika | Kruskal-Wallis, Mann-Whitney + Bonferroni, Cohenov d, OLS |

Kasnije je dodano:

| Dodatak | Šta daje |
|---|---|
| Serverska instrumentacija | procesorsko vrijeme po tipu radne niti, wait statistika |
| Kontrolne ruke | 3 x 90 serija u jednoj sesiji (d1base, d2, d1base2) |
| Automatska revizija | preračunava svaku brojku iz rada iz sirovih podataka |
| Dijagnostika i test drifta | provjera stabilnosti mjerenja |

## 1.2 Šta je otkriveno tokom provjere

**Nalaz A — mijenjane su dvije stvari odjednom.** Usporedba IM protiv HTAP
razlikovala se i po smještaju analitike i po stepenu paralelizma (`MAXDOP 1`
naspram `MAXDOP 2`). Zaključak od 3,3–6,9x pripisan je arhitekturi, a sadržavao
je oba člana.

**Nalaz B — sistem se mijenja kroz vrijeme mjerenja.** Ista konfiguracija, ista
postavka, ista sesija, izmjerena na početku i na kraju:

| Razina konkurentnosti | prvo mjerenje | zadnje mjerenje | pomak |
|---|---|---|---|
| C = 4 | 7.030 | 6.410 | 0,91 |
| C = 16 | 21.512 | 29.345 | 1,36 |
| C = 32 | 24.760 | **50.229** | **2,03** |

Kroz oko 6,5 sati sistem se pri najvišem opterećenju **udvostručio**, bez
ijedne izmjene.

**Nalaz C — postavka koja je izgledala korisno zapravo šteti.** Kad se iz
mjerenja ukloni gornji trend:

| C | rad tvrdi | stvarno |
|---|---|---|
| 4 | +21 % | **−46 %** |
| 16 | +145 % | **−26 %** |
| 32 | +261 % | **−39 %** |

Ne samo da efekta nema — **predznak je obrnut**.

\newpage

# 2. Šta se iz postojećeg rada može, a šta ne može koristiti

## 2.1 Upotrebljivo bez ograde

| Element | Zašto stoji |
|---|---|
| Opis četiri konfiguracije | činjenični opis sistema, ne rezultat |
| Skup podataka i opravdanje izbora | Pareto distribucija stvarne aktivnosti |
| Radna opterećenja (6 OLTP procedura, 5 OLAP upita) | dokumentirano u kodu |
| Hardversko-softversko okruženje | nepromijenjeno |
| Opis mjernog sistema | .NET 8, javni izvorni kod |
| Teorijska osnova (Hekaton, columnstore, nespojivost) | literatura, ne mjerenje |
| Statistička metodologija | ispravna, uz jednu ispravku (v. 2.3) |

## 2.2 Upotrebljivo kao **predmet analize**, ne kao rezultat

Sama kampanja od 1.070 serija — ali u novoj ulozi. Umjesto da bude izvor
zaključaka o arhitekturi, ona postaje **materijal na kojem se pokazuje problem**.

To je ključna promjena: kampanja se ne odbacuje, nego se **analizira**.

## 2.3 Neupotrebljivo, i zašto

| Element | Problem |
|---|---|
| Zaključci H1, H2, H3 | svi počivaju na usporedbama među konfiguracijama mjerenim u različitim trenucima |
| Rezultati konfiguracije Baseline | `usp_InsertVote` ima 40,6 % uspješnosti, `Q3` 53,9 % — ostale konfiguracije ~100 % |
| `per_operation_stats.csv` | pokriva 6,1 % operacija za Baseline a 0,03 % za HTAP; udio uzorka se razlikuje 200 puta |
| P95 od 11,9 ms naspram 4,3 ms | izveden iz gornjeg fajla, poredi neuporedive uzorke |
| Cohenov d | parametrijska mjera uz neparametrijski test; zamijeniti Cliffovom deltom |
| Tvrdnja da razlika raste s konkurentnošću | kontrolirano, razlika je ravna |

\newpage

# 3. Predloženi rad

## 3.1 Naslov

**Engleski (za slanje):**

> *When the Benchmark Moves: Measurement-Order Effects Exceed Architectural
> Differences in HTAP Evaluation*

**Bosanski (radni):**

> *Kada se mjerilo pomjera: efekti redoslijeda mjerenja nadmašuju arhitekturalne
> razlike u evaluaciji HTAP sistema*

## 3.2 Teza

> **U dugim mjernim kampanjama sistem se mijenja brže nego što se razlikuju
> arhitekture koje se tim kampanjama porede. Razlike koje se pripisuju
> arhitekturi mogu u cijelosti poticati od trenutka mjerenja.**

## 3.3 Zašto je ovo dobar rad, a ne priznanje neuspjeha

Tri razloga.

**Prvo, tvrdnja je potkrijepljena, a ne pretpostavljena.** Ista konfiguracija
izmjerena dvaput u istoj sesiji razlikuje se 2,03 puta. To nije procjena — to
je izmjereno, s 30 ponavljanja po tački.

**Drugo, postoji konkretna žrtva.** Podešavanje koje je u nekontroliranom
mjerenju izgledalo kao poboljšanje od 261 % zapravo je pogoršanje od 39 %.
Predznak se obrnuo. To je najuvjerljiviji mogući primjer.

**Treće, primjenjivo je izvan ovog rada.** Svaka evaluacija koja konfiguracije
mjeri sekvencijalno nosi isti rizik. Predložene metode su jednostavne i jeftine.

## 3.4 Struktura, četiri stranice

| Dio | Prostor | Sadržaj |
|---|---|---|
| I. Uvod | 0,5 str. | Kako se HTAP sistemi porede; niko ne provjerava miruje li mjerilo |
| II. Postavka | 0,7 str. | Konfiguracije, podaci, opterećenje, okruženje — sažeto |
| III. Metoda | 0,8 str. | ABA raspored, test drifta, korekcija trenda |
| IV. Rezultati | 1,5 str. | Pomak kroz sesiju; drift unutar serije; obrnut predznak |
| V. Preporuke i zaključak | 0,5 str. | Šta autori benchmarkova trebaju raditi |

Tri slike, jedna tabela.

\newpage

# 4. Rezultati — odakle svaki dolazi

## 4.1 Glavni nalaz: pomak kroz sesiju

**Slika 1.** Ista postavka izmjerena na početku i na kraju sesije.

| C | prvo | zadnje | pomak |
|---|---|---|---|
| 4 | 7.030 | 6.410 | 0,91 |
| 16 | 21.512 | 29.345 | 1,36 |
| 32 | 24.760 | 50.229 | **2,03** |

**Odakle:** ruke `im@d1base` i `im@d1base2`, po 90 serija svaka, mjerene u istoj
sesiji s rukom `im@d2` između njih. Skripta `Analysis/09_reviewer_followup.py`,
sekcija 8.

**Zašto se ovome može vjerovati:** obje ruke su **identična konfiguracija i
identična postavka**. Ne postoji ništa što bi ih razlikovalo osim trenutka
mjerenja.

## 4.2 Drift unutar jedne serije ponavljanja

**Slika 2.** Propusnost raste kroz 30 ponavljanja iste stvari.

Sedam od dvadeset jedne ćelije pokazuje jak trend (Spearmanov rho > 0,5 uz
p < 0,05). Najizraženiji slučaj: zadnjih pet ponavljanja **2,25 puta** brže od
prvih pet.

**Odakle:** sve mjerne ruke, sekcija 7 iste skripte. Računa se Spearmanova
korelacija rednog broja ponavljanja i propusnosti, unutar svake ćelije.

**Zašto je bitno:** trideset ponavljanja tretiraju se kao nezavisni uzorci — to
pretpostavlja i Mann-Whitney test i uzimanje medijana. Ako propusnost raste kroz
seriju, medijan djelimično mjeri **koliko je serija trajala**, a ne samo
konfiguraciju.

## 4.3 Konkretna žrtva: obrnut predznak

**Slika 3.** Efekt podešavanja prije i poslije uklanjanja trenda.

| C | nekontrolirano | nakon korekcije |
|---|---|---|
| 4 | 1,21x | **0,54x** |
| 16 | 2,45x | **0,74x** |
| 32 | 3,61x | **0,61x** |

**Odakle:** ruka `im@d2` mjerena je vremenski tačno između `im@d1base` i
`im@d1base2`. Očekivana vrijednost bez ikakvog efekta podešavanja dobija se
linearnom interpolacijom između prve i treće ruke. Omjer izmjerenog i očekivanog
je efekt očišćen od trenda. Sekcija 9 iste skripte.

**Ograda koju treba navesti:** pretpostavlja se da je trend linearan u vremenu.
To je najjednostavnija pretpostavka koju tri tačke dopuštaju.

## 4.4 Posljedica po izvornu kampanju

Redoslijed mjerenja u kampanji bio je: Baseline, CS, IM, HTAP.

HTAP je mjeren **posljednji** — u trenutku kad je sistem, prema mjerenju iz
4.1, bio najbrži.

Prijavljena prednost HTAP-a nad IM iznosi 6,92x pri C = 32. Izmjereni pomak
kroz sesiju iznosi 2,03x. **To su veličine istog reda.**

**Šta se smije reći:** da je dio prijavljene razlike mogao poticati od
redoslijeda, i da se bez kontrole ta dva člana ne mogu razdvojiti.

**Šta se ne smije reći:** da je cijela razlika artefakt. Za to nema dokaza — a
jedan podatak govori protiv: u kampanji su prve tri konfiguracije ravne
(5.691, 5.505, 6.325), pa slijedi skok na 43.751. Postepen trend bi dao
postepen rast, a ne skok.

\newpage

# 5. Preporuke — praktični dio rada

Ovo je dio koji rad čini korisnim drugima. Četiri postupka, svi jeftini.

## 5.1 ABA raspored

Izmjeriti polaznu konfiguraciju, pa ispitivanu, pa **ponovo polaznu**. Razlika
između prvog i trećeg mjerenja je pomak sistema. Ako je blizu 1,00, poređenje
vrijedi; ako nije, ta se veličina mora oduzeti.

**Cijena:** jedna dodatna ruka, oko 2 sata.

## 5.2 Test drifta unutar serije

Spearmanova korelacija rednog broja ponavljanja i mjerene vrijednosti, po svakoj
ćeliji. Jak trend znači da ponavljanja nisu razmjenjiva.

**Cijena:** nekoliko redova koda, bez dodatnog mjerenja.

## 5.3 Nasumičan ili ispreplitan redoslijed

Umjesto 90 serija konfiguracije A pa 90 serija konfiguracije B, izmjenjivati ih.
Time se trend raspoređuje ravnomjerno na obje umjesto da pogodi jednu.

**Cijena:** izmjena redoslijeda petlje, bez dodatnog vremena.

## 5.4 Objaviti sirova mjerenja s rednim brojem i vremenom

Bez rednog broja ponavljanja i vremenske oznake, drift se ne može ni provjeriti.
Većina objavljenih benchmarkova prijavljuje samo agregate.

**Cijena:** nikakva.

\newpage

# 6. Šta još treba izmjeriti

Rad se može napisati i bez sljedećeg, ali s tim je bitno jači.

## 6.1 Obavezno prije slanja — ništa

Svi nalazi iz poglavlja 4 već su izmjereni.

## 6.2 Preporučeno: HTAP u kontroliranoj sesiji

Restartovati server, pa izmjeriti **HTAP i IM zaredom, HTAP prvi**, u svježoj
sesiji.

**Šta dobijamo:** prvi put čistu usporedbu te dvije konfiguracije. Ako razlika
opstane, kampanja je u tom dijelu potvrđena i to se smije reći. Ako ne opstane,
imamo drugi nalaz iste težine.

**Cijena:** oko 4 sata.

## 6.3 Opciono: potvrda mehanizma

Uz gornje mjerenje dolaze i serverski brojači za HTAP, pa se dobija procesorsko
vrijeme po analitičkom upitu:

| Ruka | CPU po upitu |
|---|---|
| `MAXDOP 1` | 344 ms |
| `MAXDOP 2` | 271 ms |
| columnstore | **nedostaje** |

Ako columnstore ispadne bitno niži, potvrđuje se precizirana teza iz 7.2.

\newpage

# 7. Alternativa — ako se želi zadržati izvorna tema

Postoji i druga mogućnost, ali s jasnim uslovom.

## 7.1 Šta je od izvorne teze palo

Izvorna teza glasila je: *ubrzanje analitike vodi ubrzanju transakcija.*

Mjerenje daje kontraprimjer. Podizanje paralelizma **jest** ubrzalo analitiku —
1.622 završena upita naspram 933 — a transakcije su **pale** 39 %.

Opšta tvrdnja time pada.

## 7.2 Šta preživljava, u preciziranom obliku

> **Ubrzanje analitike pomaže transakcijama samo kada smanjuje potrošnju
> resursa. Ubrzanje koje samo dodaje paralelizam ne pomaže — ono se natječe.**

Ovo objašnjava **oba** ishoda:

| Poluga | Kako ubrzava | Ishod za transakcije |
|---|---|---|
| Paralelizam | dodaje radnike na isti posao | **pogoršanje** |
| Columnstore | isti posao uz manje rada po redu | poboljšanje (nepotvrđeno) |

**Uslov:** ovaj rad traži mjerenje iz 6.2 **i** 6.3. Bez njih druga polovina
tabele nije dokazana, a rad bi ponovio istu grešku koju smo upravo ispravili.

## 7.3 Preporuka

Ići s temom iz poglavlja 3. Razlozi:

- Svi rezultati su **već izmjereni** — nema rizika da mjerenje ne ispadne
- Nalaz je **primjenjiv izvan ovog rada**, što ga čini citabilnim
- Precizirana teza iz 7.2 može biti **sljedeći rad**, kad mjerenja budu gotova

\newpage

# 8. Sažetak plana

## Šta pišemo

Rad o tome da se mjerni sistem mijenja brže nego razlike koje mjeri, i o
metodama kojima se to otkriva i ispravlja.

## Šta koristimo iz postojećeg rada

Postavku, podatke, opterećenje, okruženje, teorijsku osnovu — i **samu kampanju
kao predmet analize**.

## Odakle rezultati

| Rezultat | Izvor |
|---|---|
| Pomak kroz sesiju 2,03x | ruke `im@d1base` i `im@d1base2`, po 90 serija |
| Drift u 7 od 21 ćelije | sve ruke, Spearmanova korelacija |
| Obrnut predznak podešavanja | ruka `im@d2` uz interpolaciju između prve i treće |
| Redoslijed u kampanji | dnevnik izvršavanja |

Sve tri skripte su u repozitoriju i ponovljive.

## Šta ne koristimo

Zaključke o hipotezama, rezultate konfiguracije Baseline, i `per_operation_stats.csv`.

## Šta ostaje otvoreno

Je li prednost HTAP-a nad IM stvarna. To rješava mjerenje iz 6.2, i može biti
sljedeći rad.

---

## Jedna napomena o tonu

Rad ne treba pisati kao ispravku vlastite greške. Treba ga pisati kao **metodološki
nalaz**: mjerili smo koliko se sistem pomjeri sam od sebe, i ispalo je da se
pomjeri više nego što iznose razlike koje se rutinski pripisuju arhitekturi.

Da bismo to pokazali, koristili smo vlastitu kampanju kao primjer — što je
pošteno i uvjerljivo, jer nas pogađa jednako kao i svakog drugog.
