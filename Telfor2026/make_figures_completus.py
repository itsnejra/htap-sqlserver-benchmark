#!/usr/bin/env python3
"""
Generates the print-ready pipeline figure for the TELFOR 2026 Completus paper.

The source paper carried this diagram as a 216 ppi raster; it is redrawn here
as vector output so that it stays sharp at print resolution and matches the
typography of the surrounding text.

Output: Telfor2026/figures/fig_pipeline.pdf (vector, Type-42 fonts)

Usage:  python3 Telfor2026/make_figures_completus.py   (run from anywhere)
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUTDIR = Path(__file__).resolve().parent / "figures"
OUTDIR.mkdir(parents=True, exist_ok=True)

# IEEE two-column width
DBL_W = 7.16

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Liberation Serif", "Times New Roman", "Nimbus Roman", "DejaVu Serif"],
    "font.size": 8,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "figure.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.01,
})

# Colour-blind safe and separable in grayscale (light -> dark), as in the
# companion HTAP paper. Stages are shaded by role, not by position.
DATA = "#E8E8E8"
PREP = "#BBD4E6"
TRAIN = "#1B5E8C"
SERVE = "#4E9E7E"

STAGES = [
    ("CodeSearch-\nNet", DATA, "black"),
    ("Quality\nfilter", PREP, "black"),
    ("FIM\ntransform", PREP, "black"),
    ("QLoRA\nfine-tune", TRAIN, "white"),
    ("Merge and\nGGUF export", TRAIN, "white"),
    ("Ollama\nserving", SERVE, "white"),
    ("Editor\nplugin", DATA, "black"),
]

# Bosanska varijanta oznaka za prijevod rada
STAGES_BS = [
    ("CodeSearch-\nNet", DATA, "black"),
    ("Filter\nkvaliteta", PREP, "black"),
    ("FIM\ntransformacija", PREP, "black"),
    ("QLoRA\nfine-tuning", TRAIN, "white"),
    ("Spajanje i\nGGUF izvoz", TRAIN, "white"),
    ("Ollama\nserviranje", SERVE, "white"),
    ("Dodatak za\neditor", DATA, "black"),
]


def draw(lang: str = "en") -> None:
    stages = STAGES_BS if lang == "bs" else STAGES
    fig, ax = plt.subplots(figsize=(DBL_W, 0.78))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    n = len(stages)
    gap = 0.022
    box_w = (1.0 - gap * (n - 1)) / n
    box_h = 0.86
    y0 = 0.07

    for i, (label, face, textcolor) in enumerate(stages):
        x0 = i * (box_w + gap)
        ax.add_patch(FancyBboxPatch(
            (x0, y0), box_w, box_h,
            boxstyle="round,pad=0,rounding_size=0.012",
            linewidth=0.6, edgecolor="black", facecolor=face,
            mutation_aspect=box_w / box_h))
        ax.text(x0 + box_w / 2, y0 + box_h / 2, label,
                ha="center", va="center", color=textcolor, fontsize=8,
                linespacing=1.25)
        if i < n - 1:
            ax.add_patch(FancyArrowPatch(
                (x0 + box_w + 0.002, y0 + box_h / 2),
                (x0 + box_w + gap - 0.002, y0 + box_h / 2),
                arrowstyle="-|>", mutation_scale=6,
                linewidth=0.7, color="black", shrinkA=0, shrinkB=0))

    name = "fig_pipeline_bs.pdf" if lang == "bs" else "fig_pipeline.pdf"
    fig.savefig(OUTDIR / name)
    plt.close(fig)
    print(f"Figure written to {OUTDIR / name}")


def main() -> None:
    draw("en")
    draw("bs")


if __name__ == "__main__":
    main()
