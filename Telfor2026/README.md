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
| `make_figures_completus.py` | Generiše `figures/fig_pipeline.pdf` |

## Kompajliranje

```bash
python3 Telfor2026/make_figures.py     # iz korijena repozitorija
cd Telfor2026
pdflatex telfor2026_htap.tex
pdflatex telfor2026_htap.tex           # drugi prolaz zbog referenci

pdflatex telfor2026_htap_bs.tex        # bosanska verzija
pdflatex telfor2026_htap_bs.tex
```

Bosanska verzija dodatno traži `texlive-lang-european` (babel obrazac za
prelamanje riječi; koristi se `croatian`, jer bosanski nema zaseban obrazac).

Potreban je TeX Live s paketima `texlive-publishers` (IEEEtran), `texlive-latex-recommended`
i `texlive-latex-extra`. Bibliografija je upisana kao `thebibliography` (bez BibTeX-a),
pa je dovoljno dva puta pokrenuti `pdflatex`.

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

### ⚠️ Prije predaje obavezno provjeriti

1. **Copyright string.** TELFOR-ovo uputstvo za autore ne traži IEEE copyright
   liniju na radu koji se predaje, a nema je ni zvanični IEEE konferencijski
   template, pa je iz rada uklonjena (izvorni `\IEEEpubid` blok ostao je
   zakomentarisan u preambuli). Ako TELFOR objavi copyright string za finalnu
   (camera-ready) verziju, otkomentarisati taj blok i upisati niz.
2. **Rok i sekcija.** Odabrati odgovarajuću TELFOR sekciju pri predaji i provjeriti
   aktuelne rokove na telfor.rs.
3. **IEEE PDF eXpress.** Finalnu verziju propustiti kroz PDF eXpress radi
   Xplore-kompatibilnosti (ugrađivanje fontova i sl.).
4. **Obje verzije.** Svaka izmjena teksta mora se unijeti u oba `.tex` fajla,
   jer engleska i bosanska verzija nisu automatski povezane.
5. **Literatura je provjerena na izvorima** (august 2026). Ispravljeni su
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
cd Telfor2026 && pdflatex telfor2026_completus.tex && pdflatex telfor2026_completus.tex
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

**Provjeriti prije predaje:** brojevi u donjem bloku Tabele III (CodeLlama,
StarCoderBase, DeepSeek-Coder) pripisani su referenci [9]; potvrditi da su
zaista preuzeti iz te usporedne tabele. Reference [3], [11] i [13] provjerene
su na izvorima i tačne su.

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
