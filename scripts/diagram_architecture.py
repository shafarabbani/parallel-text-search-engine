"""Hasilkan diagram arsitektur sistem -> figures/architecture.png (matplotlib).

Diagram alur: Dataset/Input -> Chunking & Task Split -> Worker Pool
(Thread/Process 1..N) -> Merge/Reduce -> Metrics & Report, plus jalur
generator dataset dan manifest ground truth.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parents[1] / "figures" / "architecture.png"


def kotak(ax, x, y, w, h, judul, isi, warna):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012",
                                fc=warna, ec="#333333", lw=1.2))
    ax.text(x + w / 2, y + h - 0.035, judul, ha="center", va="top",
            fontsize=10, fontweight="bold")
    ax.text(x + w / 2, y + h / 2 - 0.02, isi, ha="center", va="center", fontsize=8)


def panah(ax, x1, y1, x2, y2, label=""):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>",
                                 mutation_scale=14, lw=1.2, color="#333333"))
    if label:
        ax.text((x1 + x2) / 2 + 0.012, (y1 + y2) / 2, label, fontsize=7.5, va="center")


def gambar():
    fig, ax = plt.subplots(figsize=(11, 6.6), dpi=150)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("Arsitektur Parallel Text Search Engine — alur data", fontsize=12, fontweight="bold")

    kotak(ax, 0.01, 0.72, 0.19, 0.20, "Dataset Generator",
          "dataset_gen.py\nstreaming per batch\nmanifest .meta.json", "#e8f4ea")
    kotak(ax, 0.24, 0.72, 0.19, 0.20, "Input",
          "file tunggal /\ndirektori multi-file\n(data/*.txt)", "#dfe8f5")
    kotak(ax, 0.47, 0.72, 0.21, 0.20, "Chunking & Task Split",
          "chunking.py\nbyte-range (path,start,end)\ngranularity 4 chunk/worker", "#fde9d9")
    kotak(ax, 0.72, 0.66, 0.26, 0.30, "Worker Pool (1..N)",
          "threaded.py / multiproc.py\nbaca chunk -> regex word-boundary\n-> counter LOKAL + top-K sample\n(sequential.py = 1 worker)", "#f5d8d8")
    kotak(ax, 0.72, 0.30, 0.26, 0.22, "Merge / Reduce",
          "SearchResult.merge()\nasosiatif & komutatif\nvarian pembanding: Lock", "#efe3f7")
    kotak(ax, 0.35, 0.30, 0.30, 0.22, "Metrics & Report",
          "metrics.py: speedup, efisiensi,\nthroughput | cli.py, benchmark.py\n-> results/*.csv, figures/*.png", "#e0f0ef")
    kotak(ax, 0.03, 0.34, 0.27, 0.16, "Verifikasi",
          "hasil == ground truth\nmanifest (correct=True)", "#fff3c4")

    panah(ax, 0.20, 0.82, 0.24, 0.82, "tulise file")
    panah(ax, 0.43, 0.82, 0.47, 0.82)
    panah(ax, 0.68, 0.82, 0.72, 0.82, "N chunk ringan")
    panah(ax, 0.85, 0.66, 0.85, 0.52, "SearchResult kecil")
    panah(ax, 0.72, 0.41, 0.65, 0.41, "hasil akhir")
    panah(ax, 0.35, 0.42, 0.30, 0.42, "validasi")
    fig.savefig(OUT, bbox_inches="tight")
    print(f"Diagram dibuat: {OUT}")


if __name__ == "__main__":
    gambar()
