"""VERSI BER-BUG (sengaja) — demo race condition & load imbalance.

Keputusan desain (TASK.md bagian 9): modul ini BERDIRI SENDIRI dan tidak
boleh diimpor oleh modul final (sequential/threaded/multiproc/cli/dst).
Ia hanya memakai dataset_gen, params, matcher, dan identity.

Bug utama   : RACE CONDITION — beberapa thread menaikkan penghitung
              bersama ``shared[kw]`` tanpa lock memakai pola read-modify-
              write eksplisit::

                  tmp = shared[kw]     # read
                  time.sleep(0)        # celah: thread lain bisa menyusup
                  shared[kw] = tmp + 1 # write (update hilang)

              Di CPython, GIL membuat bug ini jarang muncul untuk operasi
              sederhana. ``sys.setswitchinterval(1e-6)`` + ``sleep(0)``
              menciptakan celah *context switch* yang lebar sehingga bug
              tampil konsisten — TANPA celah pun bug tetap ada secara teori
              (tidak ada jaminan atomisitas read-modify-write antar bytecode).

Bug sekunder: LOAD IMBALANCE — pembagian kerja statis berdasarkan JUMLAH
              file (bukan ukuran/byte), sehingga pada dataset file tidak
              seragam satu worker mengerjakan mayoritas byte sendirian.

Cara menjalankan::

    python -m textsearch.buggy_search --lines 200K --threads 8 --runs 10
"""

from __future__ import annotations

import argparse
import csv
import sys
import threading
import time
from pathlib import Path
from typing import Sequence

from textsearch.chunking import Chunk, make_chunks
from textsearch.dataset_gen import generate_dataset, parse_line_count
from textsearch.identity import NPM, banner
from textsearch.matcher import compile_pattern
from textsearch.params import derive_params

# Status modul: menandai bahwa file ini sengaja tidak dipakai modul final.
ADALAH_VERSI_BUG = True


def _scan_tanpa_lock(
    worker_id: int,
    chunks: Sequence[Chunk],
    pola,
    shared: dict,
    celah: bool = True,
) -> list[float]:
    """Worker BER-BUG: naikan penghitung shared tanpa lock (race condition).

    Args:
        worker_id: nomor thread (untuk log).
        chunks: chunk yang menjadi tanggung jawab thread ini (pembagian
            statis — bagian dari bug load imbalance).
        pola: regex terkompilasi.
        shared: dict penghitung BERSAMA tanpa proteksi.
        celah: True ⇒ sisipkan ``time.sleep(0)`` antara read dan write agar
            bug tampil konsisten di CPython.

    Returns:
        list[float]: durasi kerja thread (untuk analisis imbalance).
    """
    durasi: list[float] = []
    for ch in chunks:
        t0 = time.perf_counter()
        with open(ch.path, "rb") as fh:
            if ch.start > 0:
                fh.seek(ch.start - 1)
                fh.readline()
            pos = fh.tell()
            while pos < ch.end:
                mentah = fh.readline()
                if not mentah:
                    break
                teks = mentah.decode("utf-8", errors="replace")
                for m in pola.finditer(teks):
                    kw = m.group(0).lower()
                    # --- read-modify-write TANPA LOCK (inti bug) ---
                    tmp = shared[kw]
                    if celah:
                        time.sleep(0)   # sukarela yield -> context switch
                    shared[kw] = tmp + 1
                    # -------------------------------
                pos += len(mentah)
        durasi.append(time.perf_counter() - t0)
    return durasi


def ground_truth_sequensial(paths: Sequence[Path], keywords: Sequence[str]) -> dict[str, int]:
    """Hitung kebenaran dengan satu thread + penghitung LOKAL (benar)."""
    pola = compile_pattern(keywords)
    lokal = {k.lower(): 0 for k in keywords}
    for p in paths:
        with open(p, "rb") as fh:
            for mentah in fh:
                teks = mentah.decode("utf-8", errors="replace")
                for m in pola.finditer(teks):
                    lokal[m.group(0).lower()] += 1
    return lokal


def demo_race(
    paths: Sequence[Path],
    keywords: Sequence[str],
    n_threads: int,
    runs: int,
    gt: dict[str, int],
) -> list[dict]:
    """Jalankan ``runs`` percobaan race condition, kembalikan bukti per run."""
    total_target = sum(gt.values())
    pola = compile_pattern(keywords)
    hasil_run: list[dict] = []
    for r in range(1, runs + 1):
        shared = {k.lower(): 0 for k in keywords}
        chunks = make_chunks(list(paths), n_threads)
        # pembagian STATIS per thread (rate load imbalance juga)
        bagian: list[list[Chunk]] = [[] for _ in range(n_threads)]
        for i, c in enumerate(chunks):
            bagian[i % n_threads].append(c)
        mulai = time.perf_counter()
        threads = [
            threading.Thread(target=_scan_tanpa_lock, args=(i + 1, bagian[i], pola, shared))
            for i in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.perf_counter() - mulai
        buggy_total = sum(shared.values())
        hasil_run.append({
            "run": r,
            "threads": n_threads,
            "ground_truth": total_target,
            "hasil_bug": buggy_total,
            "lost_update": total_target - buggy_total,
            "elapsed_sec": round(elapsed, 4),
        })
    return hasil_run


def demo_load_imbalance(paths: Sequence[Path], keywords: Sequence[str], n_threads: int) -> list[float]:
    """Ukura waktu per worker pada pembagian kerja STATIS berdasar nomor file.

    Pada dataset multi-file yang ukurannya tidak seragam, worker yang
    kebagian file besar bekerja jauh lebih lama => load imbalance.
    """
    pola = compile_pattern(keywords)
    bagian: list[list[Chunk]] = [[] for _ in range(n_threads)]
    # BUG: pembagian per FILE (statis), bukan per byte yang setara
    for i, p in enumerate(sorted(paths, key=lambda x: x.stat().st_size, reverse=True)):
        bagian[i % n_threads].append(Chunk(str(p), 0, p.stat().st_size))
    durasi_per_thread: list[list[float]] = [[] for _ in range(n_threads)]

    def kerja(idx: int, chs: list[Chunk]) -> None:
        durasi_per_thread[idx] = _scan_tanpa_lock(idx + 1, chs, pola, dict.fromkeys((k.lower() for k in keywords), 0), celah=False)

    threads = [threading.Thread(target=kerja, args=(i, bagi)) for i, bagi in enumerate(bagian) if bagi]
    mulai = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    per_thread = [sum(d) for d in durasi_per_thread if d]
    return per_thread


def _dataset_tidak_seragam(workdir: Path, lines: int, keywords: Sequence[str], seed: int) -> list[Path]:
    """Buat 8 file dengan bobot ukuran 40/25/15/6/5/4/3/2% (bahan demo imbalance)."""
    bobot = [0.40, 0.25, 0.15, 0.06, 0.05, 0.04, 0.03, 0.02]
    d = workdir / "tidak_seragam"
    d.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, b in enumerate(bobot, start=1):
        p = d / f"bag_{i}.txt"
        if not p.is_file():
            generate_dataset(max(1_000, int(lines * b)), p, seed=seed, keywords=keywords, quiet=True)
        paths.append(p)
    return paths


def jalankan_demo(
    lines: int = 20_000,
    threads: int = 8,
    runs: int = 10,
    workdir: str | Path | None = None,
    seed: int | None = None,
) -> dict:
    """Bangkitkan dataset kecil lalu jalankan demo race + load imbalance.

    Returns:
        dict: {"runs": [...], "gt": {...}, "imbalance": [durasi per worker]}
    """
    workdir = Path(workdir or "data/_buggy_demo")
    workdir.mkdir(parents=True, exist_ok=True)
    keywords = derive_params(NPM).keywords
    seed = seed if seed is not None else derive_params(NPM).seed
    corpus = workdir / "corpus_bug.txt"
    if not corpus.is_file():
        generate_dataset(lines, corpus, seed=seed, keywords=keywords, quiet=True)
    gt = ground_truth_sequensial([corpus], keywords)
    lama = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)   # perlebar jendela context switch
    try:
        runs_result = demo_race([corpus], keywords, threads, runs, gt)
    finally:
        sys.setswitchinterval(lama)
    tidak_seragam = _dataset_tidak_seragam(workdir, lines, keywords, seed)
    imbalance = demo_load_imbalance(tidak_seragam, keywords, threads)
    return {"runs": runs_result, "gt": gt, "imbalance": imbalance}


def simpan_bukti(runs_result: list[dict], out_csv: str | Path) -> Path:
    """Simpan bukti race condition ke CSV (dikutip laporan Bagian B)."""
    out = Path(out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["run", "threads", "ground_truth", "hasil_bug", "lost_update", "elapsed_sec"])
        for r in runs_result:
            w.writerow([r["run"], r["threads"], r["ground_truth"], r["hasil_bug"], r["lost_update"], r["elapsed_sec"]])
    return out


def main(argv: Sequence[str] | None = None) -> int:
    """CLI demo bug. Exit != 0 bila argumen salah."""
    print(banner())
    ap = argparse.ArgumentParser(
        prog="textsearch.buggy_search",
        description="Demo race condition (VERSI BER-BUG, berdiri sendiri).",
    )
    ap.add_argument("--lines", default="200K", help="Jumlah baris dataset demo")
    ap.add_argument("--threads", type=int, default=8, help="Jumlah thread")
    ap.add_argument("--runs", type=int, default=10, help="Jumlah pengulangan demo")
    ap.add_argument("--out", default="results/bug_evidence.csv", help="CSV bukti")
    args = ap.parse_args(argv)

    try:
        lines = parse_line_count(args.lines)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    if args.threads <= 0 or args.runs <= 0:
        print("[ERROR] --threads dan --runs harus > 0", file=sys.stderr)
        return 2

    print(f"Jumlah thread : {args.threads}")
    print(f"Jumlah run    : {args.runs}")
    print(f"Dataset demo  : {lines:,} baris (seed & keyword dari NPM {NPM})")
    print("-" * 62)
    bukti = jalankan_demo(lines, args.threads, args.runs)
    gt_total = sum(bukti["gt"].values())
    salah = 0
    print(f"Ground truth (total kemunculan, 1 thread + counter lokal) : {gt_total:,}")
    for r in bukti["runs"]:
        status = "SALAH" if r["lost_update"] != 0 else "kebetulan benar"
        if r["lost_update"] != 0:
            salah += 1
        print(
            f"Run {r['run']:>2}: hasil versi ber-bug = {r['hasil_bug']:>10,} "
            f"| lost update = {r['lost_update']:>6,} | {status}"
        )
    print("-" * 62)
    print(f"Run yang salah: {salah}/{args.runs} ({100.0 * salah / args.runs:.0f}%)")
    print("Jenis bug: RACE CONDITION pada shared counter tanpa lock.")
    imb = bukti["imbalance"]
    if len(imb) >= 2:
        print(
            f"Load imbalance (demo sekunder): waktu worker max/min = "
            f"{max(imb):.3f}s / {min(imb):.3f}s"
        )
    path_csv = simpan_bukti(bukti["runs"], args.out)
    print(f"Bukti disimpan ke {path_csv}")
    print("SEMUA PENCARIAN SELESAI")
    print(banner())
    return 0


if __name__ == "__main__":
    sys.exit(main())
