"""Membuat grafik PNG dari ``results/benchmark.csv`` (matplotlib, backend Agg).

Grafik wajib sesuai soal UTS:
    1. ``figures/time_vs_threads.png``    — waktu vs jumlah thread (+ baseline sequential)
    2. ``figures/time_vs_processes.png``  — waktu vs jumlah process (+ baseline)
    3. ``figures/speedup_vs_config.png``  — speedup thread & process + garis ideal

Tambahan yang dianjurkan: waktu vs jumlah data, dan bar chart lock vs merge.
"""

from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # tanpa display; WAJIB di-set sebelum pyplot impor
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WARNA = {"sequential": "#444444", "thread": "#1f77b4", "process": "#d62728",
         "lock": "#2ca02c", "merge": "#1f77b4"}


def muat(bench_csv: Path) -> list[dict]:
    """Baca benchmark.csv menjadi list of dict dengan tipe yang benar."""
    with open(bench_csv, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["workers"] = int(r["workers"])
        r["lines"] = int(r["lines"])
        r["files"] = int(r["files"])
        r["elapsed_sec"] = float(r["elapsed_sec"])
    return rows


def median_per(rows: list[dict], variasi: str, mode: str, sync: str | None = None) -> dict[int, float]:
    """Median waktu per jumlah worker untuk satu variasi+mode."""
    kump: dict[int, list[float]] = defaultdict(list)
    for r in rows:
        if r["variasi"] == variasi and r["mode"] == mode and (sync is None or r["sync"] == sync):
            kump[r["workers"]].append(r["elapsed_sec"])
    return {w: statistics.median(ts) for w, ts in kump.items()}


def _baseline_sequential(rows: list[dict], variasi: str) -> float | None:
    """Median waktu sequential pada volume data yang sama dgn variasi ini."""
    ukuran = {(r["lines"], r["files"]) for r in rows if r["variasi"] == variasi}
    if not ukuran:
        return None
    # pakai titik pertama variasi (dataset terbesar yg dipakai variasi tsb)
    lines, files = sorted(ukuran)[-1]
    ts = [r["elapsed_sec"] for r in rows
          if r["mode"] == "sequential" and r["lines"] == lines and r["files"] == files]
    return statistics.median(ts) if ts else None


def plot_time_vs(rows: list[dict], variasi: str, modes: list[str], judul: str, out: Path,
                xlabel: str) -> None:
    """Grafik waktu vs jumlah worker dengan baseline sequential (bila ada)."""
    plt.figure(figsize=(8, 5))
    base_val = _baseline_sequential(rows, variasi)
    if base_val:
        plt.axhline(base_val, ls="--", color=WARNA["sequential"],
                    label=f"Baseline sequential ({base_val:.2f}s)")
    for m in modes:
        d = median_per(rows, variasi, m)
        if d:
            plt.plot(sorted(d), [d[k] for k in sorted(d)], marker="o",
                     color=WARNA[m], label=f"{m} (median)")
    plt.title(judul)
    plt.xlabel(xlabel)
    plt.ylabel("Waktu eksekusi (detik)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out, dpi=150)
    plt.close()


def buat_semua(results_dir: Path | None = None, figures_dir: Path | None = None) -> list[Path]:
    """Hasilkan SEMUA grafik wajib + tambahan. Kembalikan list path PNG."""
    results_dir = results_dir or ROOT / "results"
    figures_dir = figures_dir or ROOT / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    rows = muat(results_dir / "benchmark.csv")
    dibuat: list[Path] = []

    p1 = figures_dir / "time_vs_threads.png"
    plot_time_vs(rows, "threads", ["thread"],
                 "Waktu Eksekusi vs Jumlah Thread (median)", p1, "Jumlah thread")
    dibuat.append(p1)

    p2 = figures_dir / "time_vs_processes.png"
    plot_time_vs(rows, "processes", ["process"],
                 "Waktu Eksekusi vs Jumlah Process (median)", p2, "Jumlah process")
    dibuat.append(p2)

    # speedup vs konfigurasi: thread & process dalam satu gambar + garis ideal
    plt.figure(figsize=(8, 5))
    sp_t = _speedup_median(rows, "threads", "thread")
    sp_p = _speedup_median(rows, "processes", "process")
    if sp_t:
        xs = sorted(sp_t)
        plt.plot(xs, [sp_t[x] for x in xs], marker="o", color=WARNA["thread"], label="thread")
    if sp_p:
        xs = sorted(sp_p)
        plt.plot(xs, [sp_p[x] for x in xs], marker="o", color=WARNA["process"], label="process")
    batas = max(list(sp_t) + list(sp_p) or [1])
    ideal = list(range(1, int(batas) + 1))
    plt.plot(ideal, ideal, ls="--", color=WARNA["sequential"], label="Speedup ideal")
    plt.title("Speedup vs Jumlah Worker (median)")
    plt.xlabel("Jumlah worker (thread/process)")
    plt.ylabel("Speedup (x)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    p3 = figures_dir / "speedup_vs_config.png"
    plt.savefig(p3, dpi=150)
    plt.close()
    dibuat.append(p3)

    # tambahan 1: waktu vs jumlah data
    plt.figure(figsize=(8, 5))
    for m in ("sequential", "thread", "process"):
        agg = _median_by_lines([r for r in rows if r["variasi"] == "data" and r["mode"] == m])
        if agg:
            xs = sorted(agg)
            plt.plot(xs, [agg[x] for x in xs], marker="o", color=WARNA[m], label=m)
    plt.title("Waktu Eksekusi vs Jumlah Data (median)")
    plt.xlabel("Jumlah baris dataset")
    plt.ylabel("Waktu eksekusi (detik)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    p4 = figures_dir / "time_vs_data.png"
    plt.savefig(p4, dpi=150)
    plt.close()
    dibuat.append(p4)

    # tambahan 2: bar chart lock vs merge (variasi threads)
    lock = median_per(rows, "threads", "thread", sync="lock")
    merge = median_per(rows, "threads", "thread", sync="merge")
    if lock and merge:
        import numpy as np

        xs = sorted(set(lock) | set(merge))
        pos = np.arange(len(xs))
        lv = [lock.get(x, float("nan")) for x in xs]
        mv = [merge.get(x, float("nan")) for x in xs]
        plt.figure(figsize=(8, 5))
        plt.bar(pos - 0.18, mv, width=0.36, label="merge (default final)", color=WARNA["merge"])
        plt.bar(pos + 0.18, lv, width=0.36, label="lock (kontensi)", color=WARNA["lock"])
        plt.xticks(pos, [str(x) for x in xs])
        plt.title("Synchronization Overhead: lock vs merge (median)")
        plt.xlabel("Jumlah thread")
        plt.ylabel("Waktu eksekusi (detik)")
        plt.legend()
        plt.grid(True, axis="y", alpha=0.3)
        plt.tight_layout()
        p5 = figures_dir / "lock_vs_merge.png"
        plt.savefig(p5, dpi=150)
        plt.close()
        dibuat.append(p5)
    return dibuat


def _median_by_lines(rows: list[dict]) -> dict[int, float]:
    kump: dict[int, list[float]] = defaultdict(list)
    for r in rows:
        kump[r["lines"]].append(r["elapsed_sec"])
    return {k: statistics.median(v) for k, v in kump.items()}


def _speedup_median(rows: list[dict], variasi: str, mode: str) -> dict[int, float]:
    par = median_per(rows, variasi, mode)
    if not par:
        return {}
    lines_utama = {r["lines"] for r in rows if r["variasi"] == variasi and r["mode"] == mode}
    files_utama = {r["files"] for r in rows if r["variasi"] == variasi and r["mode"] == mode}
    base = [r["elapsed_sec"] for r in rows
            if r["mode"] == "sequential" and r["lines"] in lines_utama and r["files"] in files_utama]
    if not base:
        return {}
    t0 = statistics.median(base)
    return {w: t0 / t for w, t in par.items()}


def main() -> int:
    """CLI kecil: python -m textsearch.plots"""
    print(buat_semua())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
