"""Parameter unik proyek yang diturunkan secara deterministik dari NPM.

Soal UTS mensyaratkan parameter ditentukan dari NIM/NPM. Modul ini memilih
5 keyword dari sebuah pool menggunakan ``random.Random(int(npm))`` sehingga
hasil selalu identik untuk NPM yang sama, dan seed yang sama dipakai sebagai
seed default generator dataset (dataset menjadi unik untuk NPM ini).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

# Pool kandidat keyword (minimal 12 kata) bertema komputasi/log.
KEYWORD_POOL: tuple[str, ...] = (
    "error",
    "warning",
    "timeout",
    "server",
    "network",
    "thread",
    "process",
    "cache",
    "latency",
    "database",
    "kernel",
    "request",
    "memory",
    "socket",
)

JUMLAH_KEYWORD = 5


@dataclass(frozen=True)
class ProjectParams:
    """Parameter proyek hasil turunan NPM.

    Attributes:
        npm: NPM pemilik proyek (string digit).
        seed: Seed deterministik, bernilai sama dengan ``int(npm)``.
        keywords: Tuple 5 keyword unik yang terpilih untuk NPM ini.
    """

    npm: str
    seed: int
    keywords: tuple[str, ...]


def derive_params(npm: str) -> ProjectParams:
    """Menurunkan seed dan 5 keyword dari sebuah NPM secara deterministik.

    Langkah kerja:
        1. Validasi ``npm`` hanya berisi digit dan tidak kosong.
        2. Bangkitkan ``random.Random(int(npm))`` (generator lokal, bukan global).
        3. ``rng.sample(KEYWORD_POOL, 5)`` -> 5 keyword unik, urutan stabil.

    Args:
        npm: NPM/NIM sebagai string digit, mis. ``"247006111020"``.

    Returns:
        ProjectParams: Seed dan tuple keyword.

    Raises:
        ValueError: Jika ``npm`` bukan string digit murni.
    """
    if not npm or not npm.isdigit():
        raise ValueError(
            f"NPM harus string digit murni, diterima: {npm!r}"
        )
    seed = int(npm)
    rng = random.Random(seed)
    keywords = tuple(rng.sample(KEYWORD_POOL, JUMLAH_KEYWORD))
    return ProjectParams(npm=npm, seed=seed, keywords=keywords)
