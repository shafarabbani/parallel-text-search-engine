"""Pembagian file menjadi task byte-range ``(path, start, end)`` + pemrosesan chunk.

Aturan kepemilikan baris (krusial, cegah baris hilang/dobel):
    * Sebuah baris dimiliki oleh chunk yang memuat **offset awal baris**.
    * Saat ``process_chunk`` mulai di ``start > 0``: seek ke ``start - 1``,
      ``readline()`` sekali lalu BUANG hasilnya. readline tersebut membaca
      sisa baris yang dimulai di chunk sebelumnya. Jika byte di ``start - 1``
      sudah ``\\n``, readline hanya consuming 1 byte sehingga baris yang
      dimulai tepat di ``start`` tetap diproses chunk ini.
    * Posisi ``pos`` dilacak manual (``pos += len(line_raw)``); loop berhenti
      ketika ``pos >= end`` atau EOF. Dengan begitu chunk tidak tumpang
      tindih dan gabungannya menutup seluruh file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from textsearch.matcher import (
    MAX_SAMPLE_CHARS,
    Sample,
    SearchResult,
    compile_pattern,
    match_line,
)

# Granularitas default: berapa chunk dibuat PER worker agar dynamic
# scheduling bisa meratakan beban (mengurangi load imbalance).
GRANULARITY_PER_WORKER = 4


@dataclass(frozen=True)
class Chunk:
    """Satu unit pekerjaan: rentang byte [start, end) pada sebuah file.

    Attributes:
        path: lokasi file (string agar mudah di-pickle).
        start: offset byte awal (inklusif).
        end: offset byte akhir (eksklusif).
    """

    path: str
    start: int
    end: int

    @property
    def size(self) -> int:
        """Lebar rentang dalam byte."""
        return self.end - self.start


def make_chunks(paths: Sequence[Path], n_chunks: int) -> list[Chunk]:
    """Bagi daftar file menjadi daftar chunk byte-range.

    Alokasi: jumlah chunk per file proporsional terhadap ukuran file,
    minimum 1 chunk per file, titik potong dibagi rata di dalam file.
    File kosong tetap mendapat satu chunk ``(0, 0)`` yang tidak memproses
    baris apa pun.

    Args:
        paths: daftar file (harus ada di disk).
        n_chunks: perkiraan TOTAL chunk yang diinginkan.

    Returns:
        list[Chunk]: chunk yang tidak overlap dan menutup seluruh file.

    Raises:
        ValueError: jika ``n_chunks <= 0``.
        FileNotFoundError: jika salah satu path tidak ada.
    """
    if n_chunks <= 0:
        raise ValueError(f"n_chunks harus > 0, diterima: {n_chunks}")
    ukuran: list[tuple[str, int]] = []
    for p in paths:
        p = Path(p)
        if not p.is_file():
            raise FileNotFoundError(f"File tidak ditemukan: {p}")
        ukuran.append((str(p), p.stat().st_size))
    total = sum(s for _, s in ukuran)
    chunks: list[Chunk] = []
    for path, size in ukuran:
        if total == 0:
            jatah = 1                      # semua file kosong: 1 chunk dummy
        else:
            # proporsi ukuran, minimal 1; gunakan max(1, round(...))
            jatah = max(1, round(n_chunks * size / total))
        for i in range(jatah):
            start = i * size // jatah
            end = (i + 1) * size // jatah
            chunks.append(Chunk(path=path, start=start, end=end))
    return chunks


def proses_byte_range(path: str, start: int, end: int, keywords: Sequence[str]) -> SearchResult:
    """Inti pembacaan chunk; dipakai :func:`process_chunk` dan modul lain.

    Lihat docstring modul untuk aturan kepemilikan baris.
    """
    pattern = compile_pattern(keywords)
    hasil = SearchResult.empty(keywords)
    with open(path, "rb") as fh:
        if start > 0:
            fh.seek(start - 1)
            fh.readline()          # buang: menyelesaikan baris chunk sebelumnya
        pos = fh.tell()
        while pos < end:
            mentah = fh.readline()
            if not mentah:         # EOF sebelum end (mis. newline akhir hilang)
                break
            teks = mentah.decode("utf-8", errors="replace").rstrip("\r\n")
            counter = match_line(pattern, teks)
            sample: Sample | None = None
            if counter:
                sample = Sample(
                    path=path,
                    offset=pos,
                    text=teks[:MAX_SAMPLE_CHARS],
                )
            hasil.record_line(len(mentah), counter, sample)
            pos += len(mentah)
    return hasil


def process_chunk(chunk: Chunk, keywords: Sequence[str]) -> SearchResult:
    """Proses satu :class:`Chunk` dan kembalikan ``SearchResult`` parsial.

    Fungsi ini adalah SATU-SATUNYA kode pembacaan file yang dijalankan
    worker (thread maupun process). Ia *top-level* dan argumen/kembalianya
    picklable sehingga aman untuk ``multiprocessing`` dengan start method
    ``spawn`` (Windows).
    """
    return proses_byte_range(chunk.path, chunk.start, chunk.end, keywords)
