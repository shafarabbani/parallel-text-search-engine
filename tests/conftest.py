"""Konftes test: path ``src/`` + fixture dataset kecil bersama."""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest  # noqa: E402

from textsearch.dataset_gen import generate_dataset  # noqa: E402
from textsearch.params import derive_params  # noqa: E402

NPM = "247006111020"
KEYWORDS = derive_params(NPM).keywords


@pytest.fixture(scope="session")
def keywords():
    """5 keyword deterministik proyek (turunan NPM)."""
    return KEYWORDS


@pytest.fixture(scope="session")
def seed():
    return int(NPM)


@pytest.fixture(scope="session")
def dataset_10k(tmp_path_factory):
    """Dataset 10.000 baris (satu file) + path manifest, dipakai bersama."""
    d = tmp_path_factory.mktemp("ds10k")
    out = d / "corpus.txt"
    info = generate_dataset(10_000, out, files=1, batch_size=2_000)
    return out, info
