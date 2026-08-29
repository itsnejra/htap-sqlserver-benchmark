#!/usr/bin/env bash
# Kompajlira sve radove za TELFOR 2026.
# Literatura je u refs_*.bib, pa je potreban i bibtex korak:
#   pdflatex -> bibtex -> pdflatex -> pdflatex
set -e
cd "$(dirname "$0")"

python3 make_figures.py            # slike za HTAP rad (iz Results/summary.csv)
python3 make_figures_completus.py  # pipeline slika za Completus

for f in telfor2026_htap telfor2026_htap_bs telfor2026_completus telfor2026_completus_bs; do
  pdflatex -interaction=nonstopmode "$f.tex" >/dev/null
  bibtex   "$f"                              >/dev/null
  pdflatex -interaction=nonstopmode "$f.tex" >/dev/null
  pdflatex -interaction=nonstopmode "$f.tex" >/dev/null
  printf '%-28s %s\n' "$f.pdf" "$(pdfinfo "$f.pdf" | awk '/^Pages/{print $2" stranica"}')"
done
