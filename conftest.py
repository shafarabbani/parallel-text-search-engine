"""Konftes akar: menambahkan ``src/`` ke ``sys.path`` agar ``pytest`` dan
``python -m textsearch.cli`` dapat dijalankan langsung dari root proyek
tanpa instalasi paket."""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
