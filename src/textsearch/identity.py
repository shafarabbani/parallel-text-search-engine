"""Identitas pemilik proyek: nama, NPM, judul, dan banner wajib.

Banner ini WAJIB ditampilkan oleh semua entry point yang dapat dijalankan
(CLI utama, demo bug, benchmark, generator dataset).
"""

from __future__ import annotations

GARIS = "=" * 62

NAMA = "SHAFA RABBANI FITYATUL MUKARRAMAH"
NPM = "247006111020"
JUDUL = "PARALLEL TEXT SEARCH ENGINE"


def banner() -> str:
    """Mengembalikan banner tiga lapis sesuai spesifikasi soal UTS.

    Returns:
        str: Teks banner berisi judul, nama, dan NPM pemilik proyek.
    """
    return "\n".join(
        [
            GARIS,
            JUDUL,
            f"By {NAMA} ({NPM})",
            GARIS,
        ]
    )
