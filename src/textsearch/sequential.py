"""Pendekatan 1: pencarian SEQUENTIAL (baseline, satu chunk penuh per file)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Sequence

from textsearch.chunking import Chunk, proses_byte_range
from textsearch.identity import NPM
from textsearch.matcher import DEFAULT_SAMPLES, GARIS, RunReport, SearchResult
from textsearch.params import derive_params


def _daftar_file(input_path: str | Path) -> list[Path]:
    """Normalisasi input (file atau direktori) menjadi daftar file .txt."""
    p = Path(input_path)
    if p.is_dir():
        return sorted(p.glob("*.txt"))
    return [p]


def search_sequential(
    paths: Sequence[str | Path],
    keywords: Sequence[str] | None = None,
    *,
    verbose: bool = False,
    max_samples: int = DEFAULT_SAMPLES,
) -> RunReport:
    """Cari keyword pada semua file secara BERURUTAN (tanpa pool).

    Setiap file dibaca penuh dari byte 0 sampai EOF oleh satu loop tunggal.
    Ini baseline untuk menghitung speedup.

    Args:
        paths: daftar file dataset.
        keywords: default 5 keyword turunan NPM.
        verbose: cetak log bergaya contoh soal ke stdout.
        max_samples: contoh baris per keyword.

    Returns:
        RunReport dengan mode="sequential", workers=1.
    """
    keywords = tuple(keywords or derive_params(NPM).keywords)
    chunks = [Chunk(str(p), 0, Path(p).stat().st_size) for p in paths]
    mulai = time.perf_counter()
    hasil = SearchResult.empty(keywords, max_samples)
    per_chunk: list[float] = []
    for i, ch in enumerate(chunks, start=1):
        if verbose:
            print(f"Sequential mulai bekerja")
            print(f"[MULAI] chunk {i}/{len(chunks)} (offset {ch.start:,}-{ch.end:,})")
        t0 = time.perf_counter()
        hasil.merge(proses_byte_range(ch.path, ch.start, ch.end, keywords))
        per_chunk.append(time.perf_counter() - t0)
    elapsed = time.perf_counter() - mulai
    if verbose:
        print("SEMUA PENCARIAN SELESAI")
    return RunReport(
        mode="sequential",
        workers=1,
        elapsed_sec=elapsed,
        result=hasil,
        chunks=len(chunks),
        per_worker_times=per_chunk,
    )


if __name__ == "__main__":  # pragma: no cover - utilitas kecil untuk uji manual
    print(GARIS)
    print("Sequential demo: gunakan python -m textsearch.cli --mode sequential")
