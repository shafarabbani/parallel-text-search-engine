"""Pendekatan 2: pencarian MULTITHREAD (``ThreadPoolExecutor``).

Dua varian sinkronisasi tersedia (Fase 5):
    * ``sync="merge"`` (DEFAULT final): tiap thread accumulate di
      ``SearchResult`` lokal, digabung (reduce) di thread utama ⇒ tanpa
      kontensi lock sama sekali.
    * ``sync="lock"``: penghitung BERSAMA yang dinaiki dengan
      ``threading.Lock`` — dipakai untuk mengukur synchronization overhead.

Catatan GIL: pencocokan regex adalah kerja CPU murni; GIL CPython membuat
thread tidak menambah parallelisme CPU, tetapi pembacaan file (I/O)
melepas GIL sehingga thread tetap berguna — terutama saat page cache
panas. Hasil tetap dijamin identik dengan sequential.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Sequence

from textsearch.chunking import (
    GRANULARITY_PER_WORKER,
    Chunk,
    make_chunks,
    proses_byte_range,
)
from textsearch.identity import NPM
from textsearch.matcher import (
    MAX_SAMPLE_CHARS,
    DEFAULT_SAMPLES,
    RunReport,
    Sample,
    SearchResult,
    compile_pattern,
    match_line,
)
from textsearch.params import derive_params

# Lock global untuk pencetakan log agar baris log tidak tercampur (thread-safe).
_print_lock = threading.Lock()


def _log(pesan: str, verbose: bool) -> None:
    if verbose:
        with _print_lock:
            print(pesan, flush=True)


def _task_merge(chunk: Chunk, keywords: Sequence[str], max_samples: int) -> tuple[SearchResult, float]:
    """Satu task thread varian merge: hasil LOKAL + durasi (tanpa lock)."""
    t0 = time.perf_counter()
    hasil = proses_byte_range(chunk.path, chunk.start, chunk.end, keywords)
    return hasil, time.perf_counter() - t0


class _SharedCounter:
    """Penghitung bersama yang dilindungi ``threading.Lock`` (varian lock)."""

    def __init__(self, keywords: Sequence[str], max_samples: int) -> None:
        self.lock = threading.Lock()
        self.counts: dict[str, list[int]] = {k.lower(): [0, 0] for k in keywords}
        self.total_lines = 0
        self.total_bytes = 0
        self.samples: dict[str, list[Sample]] = {k.lower(): [] for k in keywords}
        self.max_samples = max_samples

    def tambah(self, lines_bytes: int, counter: dict, sample: Sample | None) -> None:
        """Read-modify-write terlindungi lock — pembanding bug race condition."""
        with self.lock:
            self.total_lines += 1
            self.total_bytes += lines_bytes
            for kw, n in counter.items():
                c = self.counts.setdefault(kw, [0, 0])
                c[0] += 1
                c[1] += n
                if sample is not None:
                    sp = self.samples.setdefault(kw, [])
                    sp.append(sample)
                    sp.sort(key=lambda s: s.urutan)
                    del sp[self.max_samples:]

    def hasil(self) -> SearchResult:
        res = SearchResult(max_samples=self.max_samples)
        res.counts = {k: list(v) for k, v in self.counts.items()}
        res.total_lines = self.total_lines
        res.total_bytes = self.total_bytes
        res.samples = {k: list(v) for k, v in self.samples.items()}
        return res


def _task_lock(chunk: Chunk, keywords: Sequence[str], shared: _SharedCounter) -> tuple[float, int]:
    """Satu task varian lock: cocokkan baris lalu naikan penghitung bersama."""
    t0 = time.perf_counter()
    pola = compile_pattern(keywords)
    jumlah_baris = 0
    with open(chunk.path, "rb") as fh:
        if chunk.start > 0:
            fh.seek(chunk.start - 1)
            fh.readline()
        pos = fh.tell()
        while pos < chunk.end:
            mentah = fh.readline()
            if not mentah:
                break
            teks = mentah.decode("utf-8", errors="replace").rstrip("\r\n")
            counter = match_line(pola, teks)
            sample = Sample(chunk.path, pos, teks[:MAX_SAMPLE_CHARS]) if counter else None
            shared.tambah(len(mentah), counter, sample)
            jumlah_baris += 1
            pos += len(mentah)
    return time.perf_counter() - t0, jumlah_baris


def search_threaded(
    paths: Sequence[str | Path],
    keywords: Sequence[str] | None = None,
    n_threads: int = 4,
    *,
    sync: str = "merge",
    verbose: bool = False,
    max_samples: int = DEFAULT_SAMPLES,
    granularity: int = GRANULARITY_PER_WORKER,
) -> RunReport:
    """Cari keyword dengan pool thread.

    Args:
        paths: daftar file dataset.
        keywords: default turunan NPM.
        n_threads: jumlah thread (>= 1).
        sync: ``"merge"`` (local accumulation + reduce, default) atau
            ``"lock"`` (penghitung bersama + threading.Lock).
        verbose: cetak log thread-safe.
        granularity: jumlah chunk PER worker (dynamic scheduling).

    Returns:
        RunReport mode="thread".

    Raises:
        ValueError: n_threads <= 0 atau sync tidak dikenal.
    """
    if n_threads <= 0:
        raise ValueError(f"n_threads harus > 0, diterima: {n_threads}")
    if sync not in ("merge", "lock"):
        raise ValueError(f"sync harus 'merge' atau 'lock', diterima: {sync!r}")
    keywords = tuple(keywords or derive_params(NPM).keywords)
    chunks = make_chunks([Path(p) for p in paths], n_threads * granularity)
    _log(f"Thread pool siap: {n_threads} thread, {len(chunks)} chunk", verbose)

    mulai = time.perf_counter()
    per_worker: list[float] = []
    if sync == "merge":
        hasil = SearchResult.empty(keywords, max_samples)
        with ThreadPoolExecutor(max_workers=n_threads) as pool:
            futs = [
                pool.submit(_task_merge, c, keywords, max_samples) for c in chunks
            ]
            for i, fut in enumerate(as_completed(futs), start=1):
                res, dt = fut.result()
                _log(f"[SELESAI] chunk {i}/{len(chunks)} dalam {dt:.3f}s", verbose)
                hasil.merge(res)
                per_worker.append(dt)
    else:
        shared = _SharedCounter(keywords, max_samples)
        with ThreadPoolExecutor(max_workers=n_threads) as pool:
            futs = [pool.submit(_task_lock, c, keywords, shared) for c in chunks]
            for i, fut in enumerate(as_completed(futs), start=1):
                dt, _n = fut.result()
                _log(f"[SELESAI] chunk {i}/{len(chunks)} dalam {dt:.3f}s", verbose)
                per_worker.append(dt)
        hasil = shared.hasil()
    elapsed = time.perf_counter() - mulai
    _log("SEMUA PENCARIAN SELESAI", verbose)
    return RunReport(
        mode="thread",
        workers=n_threads,
        elapsed_sec=elapsed,
        result=hasil,
        chunks=len(chunks),
        per_worker_times=per_worker,
        sync=sync,
    )
