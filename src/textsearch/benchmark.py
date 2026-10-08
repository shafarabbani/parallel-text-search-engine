"""Benchmark sistematis: menjalankan semua konfigurasi -> ``results/benchmark.csv``.

Prosedur (TASK.md bagian 12.1):
    * Dataset dibangkitkan SEKALI (seed deterministik dari NPM) dan dipakai
      ulang oleh semua percobaan.
    * Warm-up 1x (tidak dicatat) untuk menstabilkan page cache OS.
    * Tiap konfigurasi diulang ``--reps`` kali (default 3); dicatat median
      (utama), min, mean, stdev di ``results/summary.csv``.
    * Hasil tiap run diverifikasi terhadap ground truth manifest; bila
      berbeda baris CSV ditandai ``correct=False`` dan program berhenti
      dengan peringatan.
    * Spesifikasi mesin disimpan di ``results/system_info.json``.

Cara menjalankan::

    python -m textsearch.benchmark            # penuh (1M baris)
    python -m textsearch.benchmark --quick    # dataset kecil, uji cepat
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from textsearch.dataset_gen import find_meta, generate_dataset, parse_line_count
from textsearch.identity import NAMA, NPM, banner
from textsearch.multiproc import search_multiprocess
from textsearch.params import derive_params
from textsearch.sequential import search_sequential
from textsearch.threaded import search_threaded

ROOT = Path(__file__).resolve().parents[2]

# Nilai yang diuji pada mode penuh (TASK.md bagian 12.1).
THREAD_WORKERS = [1, 2, 4, 8, 16]
PROCESS_WORKERS = [1, 2, 4, 8]
DATA_VARIASI = [100_000, 500_000, 1_000_000]
FILE_VARIASI = [1, 10, 50]

QUICK = dict(
    thread_workers=[1, 2, 4], process_workers=[1, 2, 4],
    data=[20_000, 40_000, 60_000], files=[1, 3, 6],
)


@dataclass
class Konfigurasi:
    """Satu titik dalam desain percobaan."""

    variasi: str          # threads | processes | data | files
    mode: str             # sequential | thread | process
    workers: int
    dataset: Path         # file tunggal ATAU direktori multi-file
    lines: int
    files: int
    sync: str = "merge"


class BuktiSalah(Exception):
    """Hasil pencarian tidak sama dengan ground truth manifest."""


def system_info() -> dict:
    """Kumpulkan spesifikasi mesin (OS, Python, CPU, RAM, disk)."""
    info = {
        "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "python": sys.version.split()[0],
        "cpu_model": platform.processor() or "tidak diketahui",
        "cpu_logical": None,
        "cpu_physical": None,
        "ram_gb": None,
        "disk_tipe": "tidak diketahui",
    }
    try:
        import psutil

        info["cpu_logical"] = psutil.cpu_count(logical=True)
        info["cpu_physical"] = psutil.cpu_count(logical=False)
        info["ram_gb"] = round(psutil.virtual_memory().total / 2**30, 2)
        part = psutil.disk_partitions()[0]
        if "ssd" in part.device.lower():
            info["disk_tipe"] = "SSD"
        try:
            info["cpu_model"] = (
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "(Get-CimInstance Win32_Processor | Select-Object -First 1).Name"],
                    capture_output=True, text=True, timeout=15,
                ).stdout.strip() or info["cpu_model"]
            )
        except Exception:
            pass
    except ImportError:  # pragma: no cover
        import os

        info["cpu_logical"] = os.cpu_count()
    return info


def siapkan_dataset(quick: bool, keywords: Sequence[str], seed: int, diam: bool) -> dict[int, Path]:
    """Pastikan dataset per-ukuran ada di ``data/`` (dibangkitkan bila perlu)."""
    sizes = QUICK["data"] if quick else DATA_VARIASI
    out: dict[int, Path] = {}
    base = ROOT / "data"
    for n in sizes:
        p = base / f"corpus_{n}.txt"
        if not p.is_file():
            if not diam:
                print(f"[SETUP] generate dataset {n:,} baris ...", flush=True)
            generate_dataset(n, p, seed=seed, keywords=keywords,
                             quiet=diam)
        out[n] = p
    return out


def siapkan_multi(n_lines: int, jumlah_file: int, keywords: Sequence[str], seed: int, diam: bool) -> Path:
    """Pastikan dataset multi-file ada; kembalikan direktorinya."""
    d = ROOT / "data" / f"files_{jumlah_file}_{n_lines // 1000}K"
    meta = d / "dataset.meta.json"
    if not meta.is_file():
        if not diam:
            print(f"[SETUP] generate {jumlah_file} file total {n_lines:,} baris ...", flush=True)
        generate_dataset(n_lines, f"{d}/", seed=seed, keywords=keywords,
                         files=jumlah_file, quiet=diam)
    return d


def verifikasi(hasil, meta_path: Path, dataset_dir: Path) -> None:
    """Bandingkan hasil pencarian dengan ground truth manifest.

    Raises:
        BuktiSalah: bila lines/occurrences/total_lines berbeda.
    """
    gt = json.loads(meta_path.read_text(encoding="utf-8"))
    if hasil.total_lines != gt["lines"]:
        raise BuktiSalah(f"total_lines {hasil.total_lines} != {gt['lines']}")
    for kw, v in gt["ground_truth"].items():
        got = hasil.counts.get(kw, [0, 0])
        if got[0] != v["lines"] or got[1] != v["occurrences"]:
            raise BuktiSalah(f"{kw}: {got} != {v}")


def cari(konfig: Konfigurasi, keywords: Sequence[str]) -> float:
    """Jalankan satu pencarian sesuai konfigurasi; kembalikan detik."""
    rep = jalankan_konfig(konfig, keywords)
    return rep.elapsed_sec


def jalankan_konfig(konfig: Konfigurasi, keywords: Sequence[str]):
    """Dispatch pencarian sesuai konfigurasi; kembalikan RunReport."""
    files = (
        sorted(konfig.dataset.glob("*.txt"))
        if konfig.dataset.is_dir()
        else [konfig.dataset]
    )
    if konfig.mode == "sequential":
        return search_sequential(files, keywords)
    if konfig.mode == "thread":
        return search_threaded(files, keywords, konfig.workers, sync=konfig.sync)
    if konfig.mode == "process":
        return search_multiprocess(files, keywords, konfig.workers)
    raise ValueError(f"mode tidak dikenal: {konfig.mode}")


def bangun_konfigurasi(quick: bool, keywords: Sequence[str], seed: int,
                       single: dict[int, Path], diam: bool) -> list[Konfigurasi]:
    """Susun seluruh titik percobaan (variasi thread, process, data, file)."""
    tw = QUICK["thread_workers"] if quick else THREAD_WORKERS
    pw = QUICK["process_workers"] if quick else PROCESS_WORKERS
    besar = max(s for s in (QUICK["data"] if quick else DATA_VARIASI))
    sedang = sorted(s for s in (QUICK["data"] if quick else DATA_VARIASI))[1]
    konfigs: list[Konfigurasi] = []

    # baseline sequential pada dataset terbesar (untuk speedup)
    konfigs.append(Konfigurasi("threads", "sequential", 1, single[besar], besar, 1))
    for w in tw:
        konfigs.append(Konfigurasi("threads", "thread", w, single[besar], besar, 1))
    # varian sync=lock (pengukuran synchronization overhead, pembanding merge)
    for w in [x for x in tw if x <= (8 if not quick else 4)]:
        konfigs.append(Konfigurasi("threads", "thread", w, single[besar], besar, 1, sync="lock"))
    for w in pw:
        konfigs.append(Konfigurasi("processes", "process", w, single[besar], besar, 1))
    # variasi jumlah data
    for n, p in single.items():
        konfigs.append(Konfigurasi("data", "sequential", 1, p, n, 1))
        konfigs.append(Konfigurasi("data", "thread", 4, p, n, 1))
        konfigs.append(Konfigurasi("data", "process", 4, p, n, 1))
    # variasi jumlah file (total baris tetap = sedang)
    for f in (QUICK["files"] if quick else FILE_VARIASI):
        d = siapkan_multi(sedang, f, keywords, seed, diam)
        konfigs.append(Konfigurasi("files", "sequential", 1, d, sedang, f))
        konfigs.append(Konfigurasi("files", "thread", 4, d, sedang, f))
        konfigs.append(Konfigurasi("files", "process", 4, d, sedang, f))
    return konfigs


def jalankan(reps: int, quick: bool, outdir: Path, diam: bool = False) -> Path:
    """Prosedur lengkap benchmark; kembalikan path benchmark.csv."""
    p = derive_params(NPM)
    keywords = p.keywords
    print(banner())
    info = system_info()
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "system_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"Mesin: {info['cpu_model']} | {info['cpu_physical']} core fisik / "
          f"{info['cpu_logical']} logis | RAM {info['ram_gb']} GB | {info['os']}")

    single = siapkan_dataset(quick, keywords, p.seed, diam)
    konfigs = bangun_konfigurasi(quick, keywords, p.seed, single, diam)

    # WARM-UP: satu kali sequential pada dataset terbesar (tidak dicatat)
    if not diam:
        print("[WARMUP] 1x sequential ...", flush=True)
    cari(konfigs[0], keywords)

    csv_path = outdir / "benchmark.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["variasi", "mode", "workers", "lines", "files", "sync",
                    "run", "elapsed_sec", "correct"])
        for i, konfig in enumerate(konfigs, start=1):
            meta = find_meta(konfig.dataset)
            # verifikasi kebenaran SEKALI per konfigurasi (deterministik);
            # kegagalan menghentikan benchmark dengan peringatan (wajib soal)
            benar = True
            try:
                verifikasi(jalankan_konfig(konfig, keywords).result, meta, konfig.dataset)
            except BuktiSalah as exc:
                benar = False
                w.writerow([konfig.variasi, konfig.mode, konfig.workers,
                            konfig.lines, konfig.files, konfig.sync, 0,
                            "", False])
                fh.flush()
                print(f"[PERINGATAN] hasil != ground truth ({exc}) "
                      f"pada {konfig.mode} w={konfig.workers}", file=sys.stderr)
                raise SystemExit(f"[BENCH GAGAL] verifikasi ground truth gagal: {exc}")
            for run in range(1, reps + 1):
                detik = cari(konfig, keywords)
                w.writerow([konfig.variasi, konfig.mode, konfig.workers,
                            konfig.lines, konfig.files, konfig.sync, run,
                            round(detik, 6), benar])
                fh.flush()
                if not diam:
                    print(f"[{i:>2}/{len(konfigs)}] {konfig.variasi:<9} {konfig.mode:<10} "
                          f"w={konfig.workers:<3} files={konfig.files:<3} "
                          f"run {run}: {detik:.3f}s", flush=True)

    ringkas = buat_ringkasan(csv_path, outdir / "summary.csv")
    if not diam:
        print(f"\nSelesai. CSV: {csv_path}\nRingkasan: {ringkas}")
    return csv_path


def buat_ringkasan(bench_csv: Path, summary_csv: Path) -> Path:
    """Agregasi benchmark.csv -> summary.csv (median/min/mean/stdev + speedup)."""
    baris: list[dict] = []
    with open(bench_csv, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            baris.append(r)
    kelompok: dict[tuple, list[float]] = {}
    for r in baris:
        kunci = (r["variasi"], r["mode"], int(r["workers"]), int(r["lines"]),
                 int(r["files"]), r["sync"])
        kelompok.setdefault(kunci, []).append(float(r["elapsed_sec"]))
    baseline: dict[tuple, float] = {}
    for kunci, ts in kelompok.items():
        _, mode, _, lines, files, _ = kunci
        if mode == "sequential":
            # speedup selalu terhadap sequential pada VOLUME data yang sama
            baseline.setdefault((lines, files), statistics.median(ts))
    out = []
    for kunci, ts in sorted(kelompok.items(), key=lambda kv: str(kv[0])):
        variasi, mode, workers, lines, files, sync = kunci
        med = statistics.median(ts)
        base = baseline.get((lines, files))
        sp = base / med if base and mode != "sequential" else 1.0
        ef = sp / max(workers, 1)
        out.append({
            "variasi": variasi, "mode": mode, "workers": workers, "lines": lines,
            "files": files, "sync": sync, "n_run": len(ts),
            "median_sec": round(med, 6), "min_sec": round(min(ts), 6),
            "mean_sec": round(statistics.mean(ts), 6),
            "stdev_sec": round(statistics.stdev(ts), 6) if len(ts) > 1 else 0.0,
            "speedup": round(sp, 3), "efficiency": round(ef, 3),
        })
    with open(summary_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    return summary_csv


def main(argv: Sequence[str] | None = None) -> int:
    """CLI benchmark. Opsi --quick untuk uji cepat, --reps ulangan."""
    ap = argparse.ArgumentParser(prog="textsearch.benchmark",
                                 description="Benchmark semua konfigurasi -> CSV")
    ap.add_argument("--quick", action="store_true", help="Dataset kecil, uji cepat")
    ap.add_argument("--reps", type=int, default=3, help="Pengulangan tiap konfigurasi")
    ap.add_argument("--outdir", default=str(ROOT / "results"), help="Folder output")
    ap.add_argument("--quiet", action="store_true", help="Minimalkan output layar")
    args = ap.parse_args(argv)
    if args.reps < 3 and not args.quick:
        print("[ERROR] benchmark penuh wajib --reps >= 3 (soal)", file=sys.stderr)
        return 2
    try:
        jalankan(max(args.reps, 1 if args.quick else 3), args.quick, Path(args.outdir), args.quiet)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
