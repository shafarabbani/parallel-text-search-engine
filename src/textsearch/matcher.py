"""Logika pencocokan keyword yang dipakai oleh KETIGA pendekatan pencarian.

Semantik pencarian (identik untuk sequential, thread, dan process):
    * Case-insensitive.
    * Whole-word (batas kata): keyword ``error`` cocok pada ``Error:`` dan
      ``ERROR``, tetapi TIDAK cocok pada ``errors`` atau ``terror``.
    * Hasil per keyword: ``lines`` (jumlah baris yang memuat keyword) dan
      ``occurrences`` (total kemunculan, satu baris bisa memuat >1).
    * Contoh baris disimpan maksimum ``max_samples`` per keyword dan
      diidentifikasi dengan BYTE OFFSET (keputusan desain: byte offset dapat
      digabung secara deterministik antar worker tanpa tahu nomor baris
      global, sehingga hasil paralel identik dengan sequential).

Dataclass :class:`SearchResult` memiliki metode :meth:`SearchResult.merge`
yang asosiatif dan komutatif sehingga hasil worker boleh digabung dengan
urutan apa pun.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Sequence

# Panjang maksimum teks contoh baris yang disimpan/ditampilkan.
MAX_SAMPLE_CHARS = 110
# Default jumlah contoh baris per keyword.
DEFAULT_SAMPLES = 5

GARIS = "=" * 62


def _batas(kata: str, awal: bool) -> str:
    """\\b hanya valid jika ujung keyword adalah karakter word (alnum/underscore).

    Keyword seperti ``c++`` berakhir dengan ``+`` (non-word) sehingga \\b di
    ujung itu akan gagal; untuk kasus tersebut tidak perlu \\b — karakter
    non-word itu sendiri sudah menjadi pemisah.
    """
    karakter = kata[0] if awal else kata[-1]
    return r"\b" if (karakter.isalnum() or karakter == "_") else ""


def compile_pattern(keywords: Sequence[str]) -> re.Pattern[str]:
    """Kompilasi satu regex ``(?:p1|p2|...)`` dengan IGNORECASE + batas kata.

    Keyword di-``re.escape`` agar karakter spesial regex (mis. ``c++``)
    diperlakukan literal. Batas kata ``\\b`` dipasang HANYA pada ujung
    keyword yang berupa karakter word (lihat :func:`_batas`) sehingga
    keyword non-word tetap dapat dicocokkan dengan benar. Kata yang
    dicocokkan selalu di-normalisasi ke huruf kecil agar kunci hasil
    counting seragam.

    Args:
        keywords: Urutan keyword pencarian (duplikat case-insensitive
            digabung otomatis).

    Returns:
        re.Pattern: pola yang sudah dikompilasi (kompilasi cukup sekali
        per worker).

    Raises:
        ValueError: Jika daftar keyword kosong.
    """
    unik: list[str] = []
    looked: set[str] = set()
    for kw in keywords:
        k = kw.lower()
        if k not in looked:
            looked.add(k)
            unik.append(k)
    if not unik:
        raise ValueError("Daftar keyword tidak boleh kosong")
    alternatif = "|".join(
        f"{_batas(k, True)}{re.escape(k)}{_batas(k, False)}" for k in unik
    )
    return re.compile(f"(?:{alternatif})", re.IGNORECASE)


def match_line(pattern: re.Pattern[str], line: str) -> Counter:
    """Hitung kemunculan tiap keyword pada satu baris.

    Args:
        pattern: Hasil :func:`compile_pattern`.
        line: Satu baris teks (sudah didekode UTF-8).

    Returns:
        Counter: pemetaan keyword (huruf kecil) -> jumlah kemunculan pada
        baris tersebut. Baris tanpa kecocokan menghasilkan Counter kosong.
    """
    return Counter(m.group(0).lower() for m in pattern.finditer(line))


@dataclass(frozen=True)
class Sample:
    """Satu contoh baris hasil pencarian.

    Attributes:
        path: File sumber baris.
        offset: Byte offset awal baris (identikator global yang stabil).
        text: Isi baris (newline dibuang, dipotong ke MAX_SAMPLE_CHARS).
    """

    path: str
    offset: int
    text: str

    @property
    def urutan(self) -> tuple[str, int]:
        """Kunci pengurutan deterministik untuk memilih K contoh teratas."""
        return (self.path, self.offset)


def _empty_counts() -> dict[str, list[int]]:
    return {}


@dataclass
class SearchResult:
    """Hasil (partial) pencarian yang dapat digabung dengan :meth:`merge`.

    Attributes:
        counts: keyword -> ``[lines, occurrences]``.
        total_lines: jumlah baris yang diproses.
        total_bytes: jumlah byte baris yang diproses.
        samples: keyword -> daftar (maks ``max_samples``) contoh baris,
            selalu K offset TERKECIL agar merge deterministik.
        max_samples: batas contoh per keyword.
    """

    counts: dict[str, list[int]] = field(default_factory=_empty_counts)
    total_lines: int = 0
    total_bytes: int = 0
    samples: dict[str, list[Sample]] = field(default_factory=dict)
    max_samples: int = DEFAULT_SAMPLES

    @classmethod
    def empty(cls, keywords: Sequence[str], max_samples: int = DEFAULT_SAMPLES) -> "SearchResult":
        """Buat hasil kosong dengan semua keyword terinisialisasi nol."""
        res = cls(max_samples=max_samples)
        for kw in keywords:
            k = kw.lower()
            res.counts.setdefault(k, [0, 0])
            res.samples.setdefault(k, [])
        return res

    def record_line(self, line_bytes: int, counter: Counter, sample: Sample | None) -> None:
        """Catat satu baris yang sudah dicocokkan ke dalam hasil.

        Args:
            line_bytes: panjang baris dalam byte (untuk total_bytes).
            counter: hasil :func:`match_line` baris ini.
            sample: objek :class:`Sample` baris ini (boleh None bila baris
                tidak cocok dengan keyword mana pun).
        """
        self.total_lines += 1
        self.total_bytes += line_bytes
        for kw, n in counter.items():
            c = self.counts.setdefault(kw, [0, 0])
            c[0] += 1          # lines: baris ini memuat keyword kw
            c[1] += n          # occurrences: n kemunculan pada baris ini
            sp = self.samples.setdefault(kw, [])
            # Chunk diproses urut dari offset kecil, jadi K entri pertama
            # sudah merupakan K offset terkecil di chunk ini.
            if sample is not None and len(sp) < self.max_samples:
                sp.append(sample)

    def merge(self, other: "SearchResult") -> "SearchResult":
        """Gabungkan hasil ``other`` ke ``self`` (in-place) dan kembalikan self.

        Sifat merge: ASOSIATIF dan KOMUTATIF.
        * counts dan total: penjumlahan integer (komutatif & asosiatif).
        * samples: gabungan dua daftar diambil ``max_samples`` terkecil
            menurut kunci ``(path, offset)``. Karena setiap worker hanya
            menyimpan K offset terkecil lokal, K terkecil global selalu
            termuat di gabungan tersebut (bukti: jika sebuah entri masuk
            top-K global, chunk asalnya tidak boleh menyumbang >K entri
            yang lebih kecil, jadi entri itu pasti tersimpan lokal).
        """
        self.total_lines += other.total_lines
        self.total_bytes += other.total_bytes
        for kw, (lines, occ) in ((k, v) for k, v in other.counts.items()):
            c = self.counts.setdefault(kw, [0, 0])
            c[0] += lines
            c[1] += occ
        for kw, sp in other.samples.items():
            mine = self.samples.setdefault(kw, [])
            gabungan = sorted(mine + sp, key=lambda s: s.urutan)[: self.max_samples]
            self.samples[kw] = gabungan
        return self

    def lines_for(self, keyword: str) -> int:
        """Jumlah baris yang memuat ``keyword``."""
        return self.counts.get(keyword.lower(), [0, 0])[0]

    def occurrences_for(self, keyword: str) -> int:
        """Total kemunculan ``keyword``."""
        return self.counts.get(keyword.lower(), [0, 0])[1]

    def as_dict(self) -> dict[str, dict[str, int]]:
        """Representasi JSON-friendly: keyword -> {lines, occurrences}."""
        return {
            kw: {"lines": v[0], "occurrences": v[1]}
            for kw, v in sorted(self.counts.items())
        }


@dataclass
class RunReport:
    """Laporan satu kali eksekusi pencarian (dipakai CLI dan benchmark).

    Attributes:
        mode: ``sequential`` | ``thread`` | ``process``.
        workers: jumlah thread/process yang digunakan.
        elapsed_sec: waktu eksekusi dari ``time.perf_counter``.
        result: hasil akhir yang sudah di-merge.
        chunks: jumlah chunk yang dikerjakan.
        per_worker_times: durasi tiap task/chunk (analisis load imbalance).
        sync: varian sinkronisasi thread (``merge`` atau ``lock``).
    """

    mode: str
    workers: int
    elapsed_sec: float
    result: SearchResult
    chunks: int
    per_worker_times: list[float] = field(default_factory=list)
    sync: str = "merge"

    @property
    def total_lines(self) -> int:
        return self.result.total_lines

    @property
    def total_bytes(self) -> int:
        return self.result.total_bytes


def format_hasil_tabel(result: SearchResult, keywords: Sequence[str]) -> str:
    """Kembalikan tabel teks hasil pencarian (baris header + per keyword)."""
    baris = [f"{'Keyword':<12} | {'Baris cocok':>11} | {'Total kemunculan':>15}"]
    baris.append("-" * len(baris[0]))
    for kw in (k.lower() for k in keywords):
        lines, occ = result.counts.get(kw, [0, 0])
        baris.append(f"{kw:<12} | {lines:>11,} | {occ:>15,}")
    return "\n".join(baris)
