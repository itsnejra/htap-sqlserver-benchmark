# TELFOR 2026 — konferencijski rad

Rad za **34. Telekomunikacioni forum TELFOR 2026** (Beograd, Srbija), izveden iz
projekta *Evaluacija performansi hibridne transakcijsko-analitičke obrade (HTAP)
u Microsoft SQL Serveru*.

**Naslov:** *Empirical Evaluation of HTAP Storage Configurations in Microsoft SQL Server 2022*
**Autor:** Nejra Smajlović, Politehnički fakultet, Univerzitet u Zenici

## Sadržaj foldera

| Datoteka | Opis |
|---|---|
| `telfor2026_htap.tex` | Izvorni LaTeX kod rada (IEEEtran, A4, dvokolonski) |
| `telfor2026_htap.pdf` | Kompajlirani rad — **4 stranice A4** |
| `make_figures.py` | Generiše slike direktno iz `Results/summary.csv` |
| `figures/*.pdf` | Vektorske slike (Type-42 fontovi, IEEE širine kolona) |

## Kompajliranje

```bash
python3 Telfor2026/make_figures.py     # iz korijena repozitorija
cd Telfor2026
pdflatex telfor2026_htap.tex
pdflatex telfor2026_htap.tex           # drugi prolaz zbog referenci
```

Potreban je TeX Live s paketima `texlive-publishers` (IEEEtran), `texlive-latex-recommended`
i `texlive-latex-extra`. Bibliografija je upisana kao `thebibliography` (bez BibTeX-a),
pa je dovoljno dva puta pokrenuti `pdflatex`.

## Usklađenost s TELFOR pravilima

| Pravilo | Status |
|---|---|
| Dvokolonski A4, standardni IEEE konferencijski template | `\documentclass[10pt,conference,a4paper]{IEEEtran}` |
| Maksimalno 4 stranice A4 (redovni i studentski radovi) | 4 stranice |
| Copyright napomena na dnu prve stranice | `\IEEEpubid` — **vidi napomenu ispod** |
| Predaja u PDF formatu kroz TELFOR sistem | PDF se generiše `pdflatex`-om |
| Jezik rada | engleski (radovi idu u IEEE Xplore) |

### ⚠️ Prije predaje obavezno provjeriti

1. **Copyright string.** U preambuli stoji rezervirano mjesto
   `978-1-XXXX-XXXX-X/26/$31.00 ©2026 IEEE`. TELFOR svake godine objavi tačan IEEE
   ISBN/copyright string u *Instructions for Authors*
   (<https://registration.telfor.rs/Info/InstructionsForAuthors>) — taj tačan niz
   treba upisati umjesto `XXXX-XXXX`. (Domena telfor.rs nije bila dostupna iz
   okruženja u kojem je rad pripremljen, pa string nije mogao biti automatski
   preuzet.)
2. **Koautorstvo.** Rad je trenutno potpisan s jednim autorom. Ako mentor treba biti
   koautor, dodaje se u `\author{...}` bloku (i u `\thanks` fusnotu).
3. **Rok i sekcija.** Odabrati odgovarajuću TELFOR sekciju pri predaji i provjeriti
   aktuelne rokove na telfor.rs.
4. **IEEE PDF eXpress.** Finalnu verziju propustiti kroz PDF eXpress radi
   Xplore-kompatibilnosti (ugrađivanje fontova i sl.).

## Odnos prema izvornom istraživanju

Svi brojevi u radu (propusnost, latencije, veličine efekta, regresijski koeficijenti)
reproducirani su direktno iz `Results/summary.csv` i izvještaja u `Results/`, bez
zaokruživanja koje bi mijenjalo zaključke. Zbog ograničenja od 4 stranice, iz
originalnog projektnog izvještaja preneseni su:

- kompletan eksperimentalni dizajn (4×3×3, 30 ponavljanja, 1 070 validnih serija);
- sve tri hipoteze s izmjerenim ishodima (H1 djelimično potvrđena, H2 potvrđena,
  H3 odbačena);
- centralna tablica rezultata (propusnost OLTP + latencija OLAP za svih 36 ćelija);
- oba OLS regresijska modela;
- sva ograničenja validnosti iz originalnog rada.

**Napomena o H2:** vrijednosti 67,4 % (CS) naspram 55,9 % (HTAP) vrijede za razinu
konkurentnosti *C* = 16, kako ih računa `Analysis/02_statistical_tests.py`. U radu je
to eksplicitno navedeno, a Slika 1 prikazuje degradaciju za sve tri razine
konkurentnosti, gdje je razlika CS–HTAP značajna samo pri *C* = 16.

Izostavljeni su prilozi s kodom pohranjenih procedura i detaljna metodološka razrada
(dostupni u repozitoriju i originalnom izvještaju).

## Dodatne slike

`make_figures.py` generiše i dvije slike koje nisu uključene u verziju od 4 stranice,
ali su spremne za prošireni/journal oblik rada:

- `fig1_oltp_scaling.pdf` — skalabilnost OLTP propusnosti po omjeru opterećenja (2 kolone);
- `fig2_olap_latency.pdf` — distribucija OLAP *P*₅₀ latencije pri *C* = 32.
