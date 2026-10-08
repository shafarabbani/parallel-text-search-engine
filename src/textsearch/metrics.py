"""Fungsi pengukuran metrik performa paralel.

Rumus standar:
    * speedup     = T_sequential / T_paralel
    * efisiensi   = speedup / jumlah worker (dibatasi 0..1 secara pelaporan)
    * throughput  = jumlah baris (atau MB) per detik
Semua fungsi memvalidasi input: pembagi nol / nilai negatif memicu
:class:`ValueError` agar kegagalan terdeteksi dini, bukan menghasilkan
angka tak berhingga yang diam-diam.
"""

from __future__ import annotations


def _cek_waktu(t: float, nama: str) -> float:
    if t != t or t <= 0:  # NaN atau <= 0
        raise ValueError(f"{nama} harus > 0 dan bukan NaN, diterima: {t!r}")
    return float(t)


def speedup(t_seq: float, t_par: float) -> float:
    """Speedup = waktu sequential dibagi waktu paralel.

    Raises:
        ValueError: bila salah satu waktu <= 0.
    """
    return _cek_waktu(t_seq, "t_seq") / _cek_waktu(t_par, "t_par")


def efficiency(sp: float, workers: int) -> float:
    """Efisiensi = speedup / jumlah worker (dalam fraksi, 1.0 = 100%).

    Raises:
        ValueError: workers <= 0 atau speedup negatif.
    """
    if workers <= 0:
        raise ValueError(f"workers harus > 0, diterima: {workers}")
    if sp < 0:
        raise ValueError(f"speedup tidak boleh negatif, diterima: {sp}")
    return float(sp) / workers


def throughput(jumlah_baris: int, detik: float) -> float:
    """Throughput baris/detik.

    Raises:
        ValueError: detik <= 0 atau jumlah_baris < 0.
    """
    if jumlah_baris < 0:
        raise ValueError(f"jumlah_baris tidak boleh negatif: {jumlah_baris}")
    return jumlah_baris / _cek_waktu(detik, "detik")


def throughput_mb(byte_count: int, detik: float) -> float:
    """Throughput MB/detik (MB = 10^6 byte agar seragam dengan laporan)."""
    return throughput(byte_count, detik) / 1e6
