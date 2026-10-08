"""Pendekatan 3: pencarian MULTIPROCESSING (``ProcessPoolExecutor``).

Hanya ``Chunk`` (3 angka + path) dan daftar keyword yang dikirim ke worker
(payload pickling ringan); worker mengembalikan ``SearchResult`` kecil
(counts + maksimal K sample). Karena tiap process punya interpreter sendiri,
GIL tidak membatasi parallelisme CPU — tetapi ada overhead *spawn* dan
serialisasi pickling yang diukur pada benchmark.

Fungsi worker bersifat *top-level* dan picklable — wajib untuk start method
``spawn`` di Windows. Semua entry point pemanggil tetap memakai
``if __name__ == "__main__":`` (CLI/benchmark/demo), sehingga modul ini aman
diimpor oleh modul lain.
"""

from __future__ import annotations

import multiprocessing
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Sequence

from textsearch.chunking import (
    GRANULARITY_PER_WORKER,
    Chunk,
    make_chunks,
    proses_byte_range,
)
from textsearch.identity import NPM
from textsearch.matcher import DEFAULT_SAMPLES, RunReport, SearchResult
from textsearch.params import derive_params

# Penanda agar "Process-N mulai bekerja" hanya dicetak sekali per worker.
_mulai_dicetak: set[str] = set()


def _task(chunk: Chunk, keywords: Sequence[str], max_samples: int, verbose: bool) -> tuple[SearchResult, float]:
    """Fungsi worker top-level: proses satu chunk, kembalikan hasil + durasi."""
    if verbose:
        nama = multiprocessing.current_process().name
        if nama not in _mulai_dicetak:
            _mulai_dicetak.add(nama)
            print(f"{nama} mulai bekerja", flush=True)
    t0 = time.perf_counter()
    hasil = proses_byte_range(chunk.path, chunk.start, chunk.end, keywords)
    return hasil, time.perf_counter() - t0


def search_multiprocess(
    paths: Sequence[str | Path],
    keywords: Sequence[str] | None = None,
    n_procs: int = 4,
    *,
    verbose: bool = False,
    max_samples: int = DEFAULT_SAMPLES,
    granularity: int = GRANULARITY_PER_WORKER,
) -> RunReport:
    """Cari keyword dengan pool proses.

    Args:
        paths: daftar file dataset.
        keywords: default turunan NPM.
        n_procs: jumlah proses (>= 1).
        verbose: log per worker.
        granularity: chunk per worker untuk dynamic scheduling.

    Returns:
        RunReport mode="process".

    Raises:
        ValueError: n_procs <= 0.
    """
    if n_procs <= 0:
        raise ValueError(f"n_procs harus > 0, diterima: {n_procs}")
    keywords = tuple(keywords or derive_params(NPM).keywords)
    chunks = make_chunks([Path(p) for p in paths], n_procs * granularity)
    if verbose:
        print(f"Process pool siap: {n_procs} proses, {len(chunks)} chunk", flush=True)

    hasil = SearchResult.empty(keywords, max_samples)
    per_worker: list[float] = []
    mulai = time.perf_counter()
    with ProcessPoolExecutor(max_workers=n_procs) as pool:
        futs = [pool.submit(_task, c, keywords, max_samples, verbose) for c in chunks]
        for i, fut in enumerate(as_completed(futs), start=1):
            res, dt = fut.result()
            if verbose:
                print(f"[SELESAI] chunk {i}/{len(chunks)} dalam {dt:.3f}s", flush=True)
            hasil.merge(res)
            per_worker.append(dt)
    elapsed = time.perf_counter() - mulai
    if verbose:
        print("SEMUA PENCARIAN SELESAI", flush=True)
    return RunReport(
        mode="process",
        workers=n_procs,
        elapsed_sec=elapsed,
        result=hasil,
        chunks=len(chunks),
        per_worker_times=per_worker,
    )
