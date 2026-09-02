# TELFOR 2026 — konferencijski radovi

Rad za **34. Telekomunikacioni forum TELFOR 2026** (Beograd, Srbija), izveden iz
projekta *Evaluacija performansi hibridne transakcijsko-analitičke obrade (HTAP)
u Microsoft SQL Serveru*.

**Naslov:** *On HTAP Storage Configurations in SQL Server 2022: An Empirical Evaluation*
(bosanski: *O konfiguracijama pohrane za HTAP u SQL Serveru 2022:
empirijska evaluacija*)
**Autori:** Nejra Smajlović (Univerzitet u Zenici, Politehnički fakultet)
· Alen Begović (Univerzitet u Sarajevu, Elektrotehnički fakultet)

## Sadržaj foldera

| Datoteka | Opis |
|---|---|
| `telfor2026_htap.tex` | Izvorni LaTeX kod rada, engleski (IEEEtran, A4, dvokolonski) |
| `telfor2026_htap.pdf` | Kompajlirani rad, engleski — **4 stranice A4** |
| `telfor2026_htap_bs.tex` | Bosanska verzija istog rada (isti template) |
| `telfor2026_htap_bs.pdf` | Kompajlirani rad, bosanski — **4 stranice A4** |
| `make_figures.py` | Generiše slike direktno iz `Results/summary.csv` |
| `figures/*.pdf` | Vektorske slike (Type-42 fontovi, IEEE širine kolona) |
| `telfor2026_completus.tex` | Drugi rad za TELFOR 2026 (Completus), engleski |
| `telfor2026_completus.pdf` | Kompajlirani rad — **4 stranice A4** |
| `telfor2026_completus_bs.tex` | Bosanska verzija Completusa (isti template) |
| `telfor2026_completus_bs.pdf` | Kompajlirani rad, bosanski — **4 stranice A4** |
| `make_figures_completus.py` | Generiše `figures/fig_pipeline.pdf` i `_bs.pdf` |
| `refs_htap.bib` | Literatura HTAP rada — dijele je **obje** jezičke verzije |
| `refs_completus.bib` | Literatura Completusa — dijele je **obje** jezičke verzije |
| `build.sh` | Kompajlira sva četiri rada (uključuje bibtex korak) |

## Kompajliranje

Najlakše: `./Telfor2026/build.sh` — generiše slike i kompajlira sva četiri rada.

Ručno, po radu (literatura je u `.bib`, pa je **obavezan** bibtex korak):

```bash
cd Telfor2026
pdflatex telfor2026_htap.tex
bibtex   telfor2026_htap
pdflatex telfor2026_htap.tex
pdflatex telfor2026_htap.tex
```

Bosanska verzija dodatno traži `texlive-lang-european` (babel obrazac za
prelamanje riječi; koristi se `croatian`, jer bosanski nema zaseban obrazac).

Potreban je TeX Live s paketima `texlive-publishers` (IEEEtran i `IEEEtran.bst`),
`texlive-latex-recommended` i `texlive-latex-extra`.

**O literaturi.** Svaki par radova (engleski + bosanski) dijeli jedan `.bib`, pa se
ispravka reference unosi na jednom mjestu umjesto na dva. Skraćivanje na
`et al.` kontroliše `IEEEtranBSTCTL` unos na dnu svakog `.bib`: radovi s pet ili
manje autora ispisuju se u cijelosti, sa šest i više skraćuju se na prvog autora,
kako IEEE template i traži. Reference se numerišu po redoslijedu prvog citiranja,
što BibTeX radi automatski.

**O pravopisu.** Oba engleska rada pisana su **britanskim** engleskim
(`-ise`/`-yse`: *analysed*, *optimisation*, *synchronisation*, *quantisation*,
*favourable*, *artefact*), radi usklađenosti s ranijim TELFOR radovima koautora.
IEEE ne propisuje varijantu, ali traži dosljednost unutar rada. Četiri mjesta
namjerno zadržavaju američki oblik i **ne smiju se mijenjati**:

1. `MEMORY\_OPTIMIZED = ON` — T-SQL ključna riječ, kod a ne proza;
2. „Quantized LoRA (QLoRA)" — širenje akronima onako kako ga daju autori QLoRA-e;
3. naslovi citiranih radova u literaturi (npr. Diaconuov *„...memory-optimized
   OLTP engine"*, Dettmersov *„...finetuning of quantized LLMs"*) — reference se
   navode doslovno;
4. `q4\_k\_m` i slični identifikatori formata.

Provjera: `grep -o '[A-Za-z-]*iz\(e\|ed\|ing\|ation\)' *.tex` smije vratiti samo
gornje slučajeve (plus `size`/`footnotesize`, koji nisu taj sufiks).

Napomena: BibTeX nema komentare u smislu `%` — znak `@` bilo gdje u fajlu započinje
unos, pa ga u komentarima ne smije biti.

## Usklađenost s TELFOR pravilima

| Pravilo | Status |
|---|---|
| Dvokolonski A4, standardni IEEE konferencijski template | `\documentclass[10pt,conference,a4paper]{IEEEtran}` |
| Maksimalno 4 stranice A4 (redovni i studentski radovi) | 4 stranice |
| Jezik rada | **engleski ili srpski** — šalje se engleska verzija |
| Naslov i sažetak bez matematike, simbola i fusnota | provjereno, ispunjeno |
| Fontovi i prored nepromijenjeni u odnosu na IEEEtran | popis literature vraćen na propisanih 8 pt |
| Jedinice u zaglavljima tabela i na osama slika u zagradama | `(op/s)`, `(ms)`, `(%)` |
| Oznake na slikama 8 pt | `make_figures.py`, `font.size = 8` |
| Podnaslovi samo ako ih ima najmanje dva | "Ograničenja validnosti" promovirano u zasebnu sekciju |
| Slike i tabele umetnute nakon prvog spominjanja | Slika 1 pomjerena na dno kolone (`[b]`) |
| Akronimi definisani pri prvom pojavljivanju u tekstu | ETL, OLS, CTE dopunjeni |
| Prefiks "non" bez crtice | `nonparametric`, `nonmonotonically` |
| Grčki simboli uspravni (ne kurziv) | paket `upgreek`, `\upalpha` |
| Svi autori navedeni kad ih je manje od šest | provjereno na izvorima za svih 17 referenci |
| Predaja u PDF formatu kroz TELFOR sistem | PDF se generiše `pdflatex`-om |
| Bosanska verzija | **ne može se predati** (TELFOR prima samo engleski ili srpski) — služi za čitanje |
| Blok autora: grad/država i e-mail ispod ustanove | ispunjeno; za redoslijed ustanova/fakultet v. napomenu ispod |
| arXiv preprinti: `..., GODINA, arXiv:ID.` (uspravno) | ispravljeno — bili su kurzivirani kao naziv časopisa |
| Naslov i sažetak bez matematike, simbola, fusnota i citata | provjereno programski, 0 pojavljivanja |
| „data" je množina | 0 pojavljivanja „data is/was" |
| Nula ispred decimalne tačke | ispunjeno (jedini pogoci su e-mail adrese) |
| „(1)", ne „Eq. (1)" / bez `eqnarray` | 0 pojavljivanja |
| „Fig. 1", ne „Figure 1" | 0 pojavljivanja |
| `\label` **poslije** `\caption` | ispunjeno u svim plutajućim okruženjima |
| „et al." bez tačke iza „et" | ispunjeno |
| Prefiks „non" bez crtice | ispravljeno `non-uniformity` → `nonuniformity` |
| Naslov tabele iznad, potpis slike ispod | provjereno programski u svim okruženjima |
| Slike i tabele poslije prvog citiranja | provjereno; Slika 1 u HTAP-u renderuje se ispod svog citata |
| Margine, kolone i prored neizmijenjeni | nema `geometry`, `setlength`, `baselinestretch` |
| A4 i ugrađeni fontovi (preduslov za PDF eXpress) | 595 × 842 pt, svi fontovi `emb=yes` |

**Provjera literature s originalnim paketom.** Bibliografije su prekompajlirane
s `IEEEtran.bst` **v1.12** iz zvaničnog `IEEEtranBST2.zip` koji dijeli TELFOR.
Rezultat je bajt-identičan onome iz sistemske v1.14 (razlikuje se samo komentar
s brojem verzije) i BibTeX ne prijavljuje nijedno upozorenje. `IEEEtran.cls` iz
priloženog template-a identičan je sistemskom (V1.8b, 2015/08/26).

**Svjesno odstupanje 1 — redoslijed ustanove i fakulteta.** Zvanični template
u bloku autora navodi prvo odsjek pa ustanovu (`dept. name of organization`,
zatim `name of organization`). Ovdje je namjerno obrnuto — **ustanova pa
fakultet** — na izričit zahtjev autorice, i isti redoslijed prati fusnota na
prvoj stranici. Ovo je stilska, ne tehnička stavka; ne utiče ni na PDF eXpress
ni na indeksiranje u Xploreu. Ako se ikad vraća na template-ov redoslijed,
mijenjaju se dvije `\textit` linije po autoru **i** rečenica u `\thanks`.

**Svjesno odstupanje 2 — arXiv URL.** Template u referenci [8] uz arXiv navodi i
`[Online]. Available: <url>`. URL je izostavljen jer je oznaka `arXiv:ID` sama
po sebi razrješiva, a šest URL-ova dodaje ~8 redova i probija limit od 4
stranice. Redoslijed polja (godina prije oznake, uspravno) prati template.

**GGUF.** Format se pri prvom pojavljivanju u tijelu rada objašnjava kao
„the llama.cpp model container" (bs: „jednodatotečni kontejner modela izvršnog
okruženja llama.cpp"). Namjerno se **ne** navodi širenje slova GGUF: llama.cpp
ga u vlastitoj specifikaciji tretira kao ime formata i ne razrješava akronim,
pa bi svako „širenje" bilo nagađanje.

### ⚠️ Prije predaje obavezno provjeriti

1. **Copyright string.** Provjereno u punom tekstu TELFOR-ovog *Instructions
   for Authors* (august 2026): copyright linija na radu se **ne spominje**.
   Nema je ni u zvaničnom IEEE konferencijskom template-u, pa je iz radova
   uklonjena (`\IEEEpubid` blok ostao je zakomentarisan u preambuli).
   Zasebna stavka „IEEE copyright info" u TELFOR meniju odnosi se na
   elektronski copyright obrazac koji autori potpisuju, ne na štampanu liniju.

2. **Studentska sekcija — bitno.** Uputstvo kaže: *„Only the bachelor's degree
   and master's degree students can be authors and can present their papers in
   this section, with the arbitrary notification of a teacher-mentor."*
   Autori dakle moraju biti samo studenti, ali se **mentor smije navesti**.
   Ako Alen jeste mentor a ne koautor, radovi mogu u studentsku sekciju (bez
   kotizacije) uz njegovo navođenje u fusnoti prve stranice.

3. **Popis autora se ne smije mijenjati nakon prihvatanja** (*„it is not
   acceptable to change the authors' list"*), pa odluku o autorstvu treba
   donijeti prije predaje.

4. **Najviše tri rada po osobi**, kao autor ili koautor.
5. **Rok i sekcija.** Odabrati odgovarajuću TELFOR sekciju pri predaji i provjeriti
   aktuelne rokove na telfor.rs.
6. **IEEE PDF eXpress.** Finalnu verziju propustiti kroz PDF eXpress radi
   Xplore-kompatibilnosti (ugrađivanje fontova i sl.).
7. **Obje verzije.** Svaka izmjena teksta mora se unijeti u oba `.tex` fajla,
   jer engleska i bosanska verzija nisu automatski povezane.
8b. **Ponovna provjera literature (septembar 2026).** Svih 33 unosa provjereno
   je iznova na izvorima. Potvrđeni su autori, naslov, mjesto objave, volumen,
   broj, stranice i godina za 30 unosa. Ispravljena su tri:

   | Unos | Bilo | Sada | Izvor |
   |---|---|---|---|
   | HTAP [4] Zhang, *HTAP databases: A survey* | bez vol./br./str. | vol. 36, no. 11, pp. 6410–6429 | IEEE TKDE / IEEE Xplore |
   | Completus [11] Xue, *Clean code, better models* | 2025 | 2026, `in press` | ACM DL: još „Just Accepted", online 5. 2. 2026, bez vol./br./str. |
   | Completus [16] Husain, *CodeSearchNet* | `MSR-TR-2019-45` | `arXiv:1909.09436` | broj tehničkog izvještaja ne postoji ni na stranici Microsoft Researcha |

   Uz to su ispravljena **dva pogrešna pripisivanja** u tekstu (referenca je
   bila tačna, ali tvrdnja uz nju nije bila ono što izvor kaže):

   * StackOverflow2010 i njegova Pareto raspodjela bili su pripisani HTAP
     survey-u [4]; taj rad ne govori o tom skupu podataka. Citat uklonjen —
     raspodjela je svojstvo samog skupa i ne treba referencu.
   * Čekanje `RESOURCE_SEMAPHORE` bilo je pripisano Zengu i drugima [17]; taj
     rad mjeri Parquet i ORC i ne može potkrijepiti tvrdnju o wait tipu
     specifičnom za SQL Server. Rečenica je preformulisana tako da referenca
     stoji uz ono što Zeng zaista pokazuje.

   Napomena o metodi: DBLP, CrossRef, OpenAlex i arXiv nisu dostupni kroz
   mrežni proxy ovog okruženja (HTTP 403), pa je provjera rađena pretragom uz
   potvrdu na stranicama izdavača (VLDB, ACM, IEEE, ACL Anthology, ScienceDirect,
   EDP Sciences, Microsoft Research).

8. **Literatura je provjerena referencu po referencu na izvorima** (august
   2026). Svih 17 referenci provjereno; osim ranije ispravljenih autora,
   ispravljeni su i: [2] str. 1159--1168 (bilo 1170), [5] str. 3313--3325
   (bilo 3326) i [9] godina 2011 (bilo 2012, SIGMOD Record 40(4) je izašao u
   decembru 2011). Ispravljeni su
   pogrešni popisi autora u [7], [8], [11] i [14], pogrešna prezimena prvog
   autora u [13], [15] i [17], te dopunjeni nedostajući volumeni i stranice.
   Referenca [14] je bila pripisana pogrešnim autorima i pogrešnom časopisu
   (Kang, Chen i Li u *BenchCouncil Trans. Benchmarks Standards Eval.*, ne
   Zhao i drugi u *Inf. Syst.*), pa je i ime u tekstu promijenjeno.
   Pri svakoj budućoj izmjeni literature ponoviti ovu provjeru.

## Drugi rad: Completus

`telfor2026_completus.tex` je rad *Completus: Consumer-GPU QLoRA Fine-Tuning of a
1.5B Code Model for Local Autocompletion* (Nejra Smajlović, Adi Kadušić,
Alen Begović), prenesen iz IHCONCS formata u isti TELFOR/IEEEtran template i pod istim
pravilima kao HTAP rad.

```bash
python3 Telfor2026/make_figures_completus.py
cd Telfor2026
pdflatex telfor2026_completus.tex    && pdflatex telfor2026_completus.tex
pdflatex telfor2026_completus_bs.tex && pdflatex telfor2026_completus_bs.tex
```

Šta je promijenjeno u odnosu na izvornu verziju:

- IEEEtran, A4, dvokolonski, **4 stranice** umjesto 6 jednokolonskih na Letteru;
- struktura sažeta na šest sekcija: Uvod, Dosadašnja istraživanja, Pipeline
  (3 podsekcije), Evaluacija (3 podsekcije), Diskusija s ograničenjima,
  Zaključak — Diskusija i ograničenja su spojeni, kako se ne bi dobila sekcija
  s jednim podnaslovom, što IEEE template zabranjuje;
- **Acknowledgement uklonjen** na zahtjev autorice; link na repozitorij prebačen
  u nenumerisanu fusnotu prve stranice, gdje ga IEEE template i traži;
- četiri tabele svedene na tri, a slika pipeline-a preslikana iz rastera od
  216 ppi u vektor (`make_figures_completus.py`);
- iz sažetka uklonjeni matematika i specijalni znakovi (u izvorniku je
  `\(q4\_k\_m\)` doslovno curilo kao LaTeX kod u tekst);
- uklonjena referenca na nepostojeću „Fig. 3" iz izvornika;
- akronimi GPU, QLoRA, CI, LLM, PEFT, LoRA, FIM i NF4 definisani pri prvom
  pojavljivanju u tekstu;
- ORCID nije upisan ni za jednog autora; izvornik je za drugog autora imao
  rezervirano mjesto `0000-0000-0000-0000`, pa su ostavljene samo e-mail adrese.

**Provjeriti prije predaje:**

1. Brojevi u donjem bloku Tabele III (CodeLlama, StarCoderBase,
   DeepSeek-Coder) pripisani su referenci [9]; potvrditi da su zaista preuzeti
   iz te usporedne tabele. Reference [3], [11] i [13] provjerene su na
   izvorima i tačne su.
2. **Literatura Completusa provjerena je referencu po referencu** (august
   2026) — svih 16 unosa tačno: autori, mjesto objave, volumen, stranice,
   arXiv brojevi i godine. Nije bilo ispravki. Jedina sitnica: [10] koristi
   arXiv naslov (`AdaLoRA: Adaptive budget allocation...`) uz ICLR kao mjesto
   objave, gdje je zvanični naslov bez prefiksa `AdaLoRA:`. Bezopasno, ali se
   može uskladiti.
3. **Nad kojim artefaktom je pokrenut HumanEval?** Izvorni rad kaže da izvoz
   piše i `safetensors` checkpoint i kvantizovani GGUF, a evaluacija govori
   samo o „both checkpoints". Ako je mjereno nad FP16 checkpointom, onda
   42,68 % nije kvalitet onoga što Ollama servira, i to treba reći. Jedna
   rečenica u sekciji IV-A rješava pitanje.

Peto ograničenje u sekciji V eksplicitno navodi da latencija, propusnost i
zauzeće memorije servisiranog modela nisu mjereni. To je najveća stvarna
praznina rada i prva stvar koju vrijedi dodati ako bude mjerenja.

**Sekcija III-D „Hardware Constraints on Local Serving"** izvodi analitičku
granicu brzine serviranja iz objavljenih specifikacija: RTX 4060 Laptop ima
256 GB/s (8 GB GDDR6, 128-bitna magistrala, 16 Gbit/s po pinu); `q4_k_m`
izdanje modela zauzima ~1 GB, pa je plafon ~250 tokena/s, dok je poluprecizni
checkpoint od 3,1 GB ograničen na ~80. Uzrok je što dekodiranje pri seriji od
jednog uzorka nema ponovne upotrebe podataka, pa je aritmetički intenzitet
~1 op/bajt i ograničava propusnost memorije, ne račun. Navedeni su i korektivni
članovi: keš ključeva/vrijednosti (~28 kB po tokenu, ~60 MB pri punom prozoru
od 2048) i cijena raspakivanja K-kvantova.

**Ovo su izvedene granice, ne mjerenja.** Sekcija to izričito kaže i upućuje na
peto ograničenje. Prirodan sljedeći korak: izmjeriti tokena/s, vrijeme do
prvog prijedloga i zauzeće VRAM-a, pa uporediti s ovim plafonom — time se peto
ograničenje briše umjesto da se zaobilazi.

Hardverska argumentacija (sekcije III-B i III-C) objašnjava *zašto* postavke iz
Tabele II izgledaju kako izgledaju: memorijski budžet od 8 GB, razlog za podjelu
serije 2 × 8 umjesto 16 odjednom, mješovita preciznost `q4_k_m` sheme, i to da
je latencija dekodiranja pri seriji od jednog uzorka ograničena propusnošću
memorije, a ne računom. Nijedan od tih pasusa ne uvodi novo mjerenje —
objašnjavaju postojeće brojeve i eksplicitno upućuju na peto ograničenje.

Napomena o kompajliranju: `balance` paket ostavlja upozorenje
`Overfull \vbox (1.33 pt)` na zadnjoj stranici. Provjereno je da tekst završava
na oko 450 pt, daleko iznad dna bloka (718 pt) — upozorenje dolazi iz internog
računa paketa, ne iz prelijevanja sadržaja.

## Zahvala

Oba rada imaju kratku sekciju *Acknowledgment* / *Zahvala* prije literature.
Tekst je **formulacija koju je dao mentor**, prenesena doslovno:

> HTAP: *This paper is based, in part, on research conducted during the first
> author's ongoing master's studies in Software Engineering at the University
> of Zenica, focusing on database optimization.*

> Completus: *This paper is based, in part, on research conducted during the
> first and second authors' ongoing master's studies in Software Engineering
> at the University of Zenica, focusing on data mining.*

Formulacija ovisi o redoslijedu autora: „first author" je Nejra u HTAP-u,
„first and second authors" su Nejra i Adi u Completusu. **Ako se redoslijed
autora promijeni, ove rečenice se moraju uskladiti.**

**Napomena o prostoru:** sekcija košta oko sedam redova bez obzira na dužinu
rečenice, jer naslov i razmaci oko njega troše više od teksta. Da bi stala,
zaključci oba HTAP-a više ne ponavljaju glavni uvid koji Diskusija ionako
razrađuje, a nekoliko formulacija je zbijeno. Nijedan broj, statistika ni
zaključak nisu mijenjani.

## Odnos prema izvornom istraživanju

Svi brojevi u radu (propusnost, latencije, veličine efekta, regresijski koeficijenti)
reproducirani su direktno iz `Results/summary.csv` i izvještaja u `Results/`, bez
zaokruživanja koje bi mijenjalo zaključke. Zbog ograničenja od 4 stranice, iz
originalnog projektnog izvještaja preneseni su:

- kompletan eksperimentalni dizajn (4×3×3, 30 ponavljanja, 1 070 validnih serija);
- centralna tablica rezultata (propusnost OLTP + latencija OLAP za svih 36 ćelija);
- oba OLS regresijska modela;
- sva ograničenja validnosti iz originalnog rada.

**Napomena o hipotezama:** originalni izvještaj iznosi tri hipoteze (H1–H3) i za svaku
daje presudu. U ovom radu ta forma je uklonjena na zahtjev autorice — isti nalazi se
iznose direktno, a pregled literature završava s tri istraživačka pitanja umjesto s
hipotezama. Mjerenja i zaključci su nepromijenjeni.

**Napomena o degradaciji:** vrijednosti 67,4 % (CS) naspram 55,9 % (HTAP) vrijede za
razinu konkurentnosti *C* = 16, kako ih računa `Analysis/02_statistical_tests.py`. U
radu je to eksplicitno navedeno, a Slika 1 prikazuje degradaciju za sve tri razine,
gdje je razlika CS–HTAP značajna samo pri *C* = 16.

**Napomena o latencijama Baseline konfiguracije:** pri *C* = 32 uspješnost OLAP-a
Baseline konfiguracije je 83,6 %, jer upiti prekoračuju klijentski timeout. Takvi
upiti ne doprinose uzorku latencije, pa su Baseline latencije u Tabeli I
survivor-biased i potcjenjuju stvarni trošak — što je u radu eksplicitno navedeno.

Izostavljeni su prilozi s kodom pohranjenih procedura i detaljna metodološka razrada
(dostupni u repozitoriju i originalnom izvještaju).

## Dodatne slike

`make_figures.py` generiše i dvije slike koje nisu uključene u verziju od 4 stranice,
ali su spremne za prošireni/journal oblik rada:

- `fig1_oltp_scaling.pdf` — skalabilnost OLTP propusnosti po omjeru opterećenja (2 kolone);
- `fig2_olap_latency.pdf` — distribucija OLAP *P*₅₀ latencije pri *C* = 32.

Slika koja jest u radu generiše se u dvije jezičke varijante:
`fig3_degradation.pdf` (engleska) i `fig3_degradation_bs.pdf` (bosanska).
