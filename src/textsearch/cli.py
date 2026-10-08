"""CLI utama: ``python -m textsearch.cli``.

Contoh::

    python -m textsearch.cli --input data/corpus_1M.txt --mode sequential
    python -m textsearch.cli --input data/corpus_1M.txt --mode thread --workers 8
    python -m textsearch.cli --input data/multi_500K/ --mode process --workers 4
    python -m textsearch.cli --input data/corpus_1M.txt --mode all --workers 4

Output wajib: banner nama+NPM, dataset, jumlah thread/process, waktu total
eksekusi, throughput; speedup & efisiensi bila ``--mode all``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from textsearch.identity import NPM, banner
from textsearch.matcher import GARIS, RunReport, format_hasil_tabel
from textsearch.metrics import efficiency, speedup, throughput, throughput_mb
from textsearch.multiproc import search_multiprocess
from textsearch.params import derive_params
from textsearch.sequential import search_sequential
from textsearch.threaded import search_threaded

MODE_LABEL = {
    "sequential": "sequential (baseline 1 urutan)",
    "thread": "multithread (ThreadPoolExecutor)",
    "process": "multiprocessing (ProcessPoolExecutor)",
}


def kumpulkan_file(input_path: str | Path) -> list[Path]:
    """Normalisasi ``--input`` (file tunggal atau direktori) menjadi daftar file.

    Raises:
        FileNotFoundError: path tidak ada, atau direktori tanpa file .txt.
    """
    p = Path(input_path)
    if p.is_dir():
        files = sorted(p.glob("*.txt"))
        if not files:
            raise FileNotFoundError(f"Direktori {p} tidak memuat file .txt")
        return files
    if p.is_file():
        return [p]
    raise FileNotFoundError(f"Input tidak ditemukan: {p}")


def _label_pekerja(mode: str) -> str:
    return "thread" if mode == "thread" else "process" if mode == "process" else "sequence"


def jalankan_mode(mode: str, files: list[Path], keywords: Sequence[str], workers: int,
                  sync: str, verbose: bool, samples: int) -> RunReport:
    """Dispatch satu mode pencarian dan kembalikan RunReport-nya."""
    if mode == "sequential":
        return search_sequential(files, keywords, verbose=verbose, max_samples=samples)
    if mode == "thread":
        return search_threaded(files, keywords, workers, sync=sync,
                               verbose=verbose, max_samples=samples)
    if mode == "process":
        return search_multiprocess(files, keywords, workers,
                                   verbose=verbose, max_samples=samples)
    raise ValueError(f"Mode tidak dikenal: {mode!r}")


def lapor(report: RunReport, keywords: Sequence[str], ukuran_byte: int, verbose: bool, samples: int) -> None:
    """Cetak laporan satu run sesuai format wajib soal."""
    label = _label_pekerja(report.mode)
    if report.mode == "sequential":
        print(f"Mode            : {MODE_LABEL[report.mode]}")
    else:
        print(f"Mode            : {MODE_LABEL[report.mode]}")
        print(f"Jumlah {label:<7}: {report.workers}")
        if report.mode == "thread":
            print(f"Sinkronisasi    : {report.sync}")
    if report.mode != "sequential" and not verbose:
        print(f"{label.capitalize()}-{report.workers} menyelesaikan {report.chunks} chunk")
        print("SEMUA PENCARIAN SELESAI")
    print()
    print(format_hasil_tabel(report.result, keywords))
    if samples > 0:
        print()
        print("Contoh baris (ditandai byte offset file, lihat DOKUMENTASI):")
        for kw in (k.lower() for k in keywords):
            for s in report.result.samples.get(kw, [])[:samples]:
                print(f"  [{kw}] {Path(s.path).name}@{s.offset:,}: {s.text}")
    print(f"Waktu total     : {report.elapsed_sec:.3f} detik")
    print(f"Throughput      : {throughput(report.total_lines, report.elapsed_sec):,.0f} baris/detik"
          f"  ({throughput_mb(report.total_bytes, report.elapsed_sec):,.1f} MB/detik)")


def _json_report(rep: RunReport, keywords: Sequence[str]) -> dict:
    return {
        "mode": rep.mode,
        "workers": rep.workers,
        "sync": rep.sync,
        "elapsed_sec": rep.elapsed_sec,
        "chunks": rep.chunks,
        "total_lines": rep.total_lines,
        "total_bytes": rep.total_bytes,
        "throughput_lines_per_sec": throughput(rep.total_lines, rep.elapsed_sec),
        "throughput_mb_per_sec": throughput_mb(rep.total_bytes, rep.elapsed_sec),
        "result": rep.result.as_dict(),
        "samples": {
            kw: [{"path": s.path, "offset": s.offset, "text": s.text} for s in sp]
            for kw, sp in rep.result.samples.items()
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point CLI. Return 0 sukses; != 0 bila argumen/error validasi salah."""
    ap = argparse.ArgumentParser(
        prog="textsearch.cli",
        description="Parallel Text Search Engine — cari keyword pada dataset besar "
                    "secara sequential / multithread / multiprocessing.",
    )
    ap.add_argument("--input", required=True, help="File dataset atau direktori multi-file")
    ap.add_argument("--mode", default="all",
                    choices=["sequential", "thread", "process", "all"],
                    help="Pendekatan pencarian (default: all = bandingkan ketiganya)")
    ap.add_argument("--workers", type=int, default=4, help="Jumlah thread/process (>=1)")
    ap.add_argument("--keywords", default=None,
                    help="Daftar keyword dipisah koma (default: 5 keyword turunan NPM)")
    ap.add_argument("--sync", default="merge", choices=["merge", "lock"],
                    help="Varian sinkronisasi mode thread")
    ap.add_argument("--verbose", action="store_true", help="Cetak log per chunk")
    ap.add_argument("--quiet", action="store_true", help="Tanpa log worker (default)")
    ap.add_argument("--samples", type=int, default=5, help="Contoh baris per keyword (0=tanpa)")
    ap.add_argument("--json", action="store_true", help="Output mesin format JSON")
    args = ap.parse_args(argv)

    if args.workers <= 0:
        print("[ERROR] --workers harus > 0", file=sys.stderr)
        return 2
    keywords = (
        tuple(k.strip().lower() for k in args.keywords.split(",") if k.strip())
        if args.keywords
        else derive_params(NPM).keywords
    )
    if not keywords:
        print("[ERROR] --keywords kosong", file=sys.stderr)
        return 2
    verbose = args.verbose and not args.quiet

    try:
        files = kumpulkan_file(args.input)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    total_byte = sum(f.stat().st_size for f in files)
    ukuran_mb = total_byte / 1e6

    if args.json:
        modes = ["sequential", "thread", "process"] if args.mode == "all" else [args.mode]
        keluaran = {"identitas": {"nama": "SHAFA RABBANI FITYATUL MUKARRAMAH", "npm": NPM},
                    "input": str(args.input), "keywords": list(keywords), "runs": []}
        try:
            for m in modes:
                rep = jalankan_mode(m, files, keywords, args.workers, args.sync, verbose, args.samples)
                keluaran["runs"].append(_json_report(rep, keywords))
        except Exception as exc:  # pragma: no cover
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 3
        print(json.dumps(keluaran, indent=2, ensure_ascii=False))
        return 0

    print(banner())
    jumlah_baris_hanya_info = ""
    if len(files) == 1:
        jumlah_baris_hanya_info = f"{files[0]}"
    else:
        jumlah_baris_hanya_info = f"{args.input} ({len(files)} file)"
    print(f"Dataset         : {jumlah_baris_hanya_info}  ({ukuran_mb:,.1f} MB)")
    print(f"Keyword         : {', '.join(keywords)}")
    print(GARIS)

    modes = ["sequential", "thread", "process"] if args.mode == "all" else [args.mode]
    reports: dict[str, RunReport] = {}
    try:
        for m in modes:
            rep = jalankan_mode(m, files, keywords, args.workers, args.sync, verbose, args.samples)
            reports[m] = rep
            print()
            lapor(rep, keywords, total_byte, verbose, args.samples)
            print(GARIS)
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 3

    if args.mode == "all":
        t_seq = reports["sequential"].elapsed_sec
        print("PERBANDINGAN MODE")
        print(f"{'Mode':<12} | {'Worker':>6} | {'Waktu (s)':>9} | {'Speedup':>8} | {'Efisiensi':>9}")
        print("-" * 62)
        for m in modes:
            rep = reports[m]
            sp = speedup(t_seq, rep.elapsed_sec)
            ef = efficiency(sp, rep.workers)
            print(f"{m:<12} | {rep.workers:>6} | {rep.elapsed_sec:>9.3f} | {sp:>7.2f}x | {ef * 100:>8.1f}%")
    print(banner())
    return 0


if __name__ == "__main__":
    sys.exit(main())
