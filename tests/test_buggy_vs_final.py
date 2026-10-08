"""Test versi ber-bug vs final: mekanisme bug ada, final selalu benar,
dan modul final tidak mengimpor buggy_search (isolasinya terjaga)."""

import subprocess
import sys
from pathlib import Path

import pytest

from textsearch.buggy_search import ground_truth_sequensial, jalankan_demo
from textsearch.dataset_gen import generate_dataset
from textsearch.multiproc import search_multiprocess
from textsearch.params import derive_params
from textsearch.sequential import search_sequential
from textsearch.threaded import search_threaded

NPM = "247006111020"
MODUL_FINAL = [
    "sequential.py", "threaded.py", "multiproc.py", "cli.py", "benchmark.py",
    "plots.py", "matcher.py", "chunking.py", "dataset_gen.py", "metrics.py",
    "params.py", "identity.py",
]


@pytest.fixture(scope="module")
def demo_result(tmp_path_factory):
    """Satu kali demo bug skala kecil (dipakai semua test di file ini)."""
    d = tmp_path_factory.mktemp("buggy")
    return jalankan_demo(lines=20_000, threads=8, runs=6, workdir=d)


def test_mekanisme_bug_ada(demo_result):
    """Hasil ber-bug TIDAK PERNAH melebihi ground truth (lost update, bukan extra)."""
    gt_total = sum(demo_result["gt"].values())
    for r in demo_result["runs"]:
        assert r["hasil_bug"] <= gt_total
        assert r["lost_update"] >= 0


def test_bug_terlihat(demo_result):
    """Bila pada mesin ini bug muncul (didukung setswitchinterval), buktikan;
    jika tidak muncul sama sekali, skip — test tidak boleh gagal acak."""
    salah = [r for r in demo_result["runs"] if r["lost_update"] > 0]
    if not salah:
        pytest.skip("race condition tidak tereproduksi pada mesin ini")
    assert len(salah) >= 1
    for r in salah:
        assert r["hasil_bug"] < r["ground_truth"]


def test_load_imbalance_terukur(demo_result):
    imb = demo_result["imbalance"]
    if len(imb) < 2:
        pytest.skip("worker aktif kurang dari 2 pada mesin ini")
    # pembagian statis per-file pada ukuran file tidak seragam => timpang
    assert max(imb) > 1.5 * min(imb) or max(imb) == sum(imb)


def test_final_selalu_benar(tmp_path):
    """Versi final (merge & lock, thread & process) == ground truth, berulang."""
    kws = derive_params(NPM).keywords
    out = tmp_path / "corpus.txt"
    info = generate_dataset(15_000, out, keywords=kws, batch_size=2_000)
    gt = info.ground_truth
    dasar = search_sequential([out], kws).result
    for _ in range(5):
        for res in (
            search_threaded([out], kws, 4).result,
            search_threaded([out], kws, 4, sync="lock").result,
            search_multiprocess([out], kws, 2).result,
        ):
            assert res.counts == dasar.counts
            for kw, v in gt.items():
                assert res.counts[kw] == [v["lines"], v["occurrences"]]


def test_bug_tidak_bocor_ke_modul_final():
    """Tidak ada modul final yang mengimpor/mereferensi buggy_search."""
    src = Path(__file__).resolve().parents[1] / "src" / "textsearch"
    for nama in MODUL_FINAL:
        teks = (src / nama).read_text(encoding="utf-8")
        assert "buggy_search" not in teks, nama


def test_imp_or_final_tidak_mengaktifkan_buggy():
    """Di interpreter bersih: mengimpor semua modul final tidak memuat buggy_search."""
    kode = (
        "import sys; sys.path.insert(0, 'src');"
        "import textsearch.cli, textsearch.benchmark, textsearch.plots, "
        "textsearch.threaded, textsearch.multiproc, textsearch.sequential;"
        "assert 'textsearch.buggy_search' not in sys.modules; print('OK')"
    )
    r = subprocess.run([sys.executable, "-c", kode], capture_output=True, text=True,
                       cwd=str(Path(__file__).resolve().parents[1]))
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout
