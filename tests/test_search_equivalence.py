"""Test ekuivalensi: sequential == thread(merge/lock) == process, dan == ground truth."""

import json

import pytest

from textsearch.chunking import GRANULARITY_PER_WORKER
from textsearch.dataset_gen import generate_dataset
from textsearch.matcher import SearchResult
from textsearch.multiproc import search_multiprocess
from textsearch.sequential import search_sequential
from textsearch.threaded import search_threaded

KWS = ("error", "cache", "timeout")


@pytest.fixture(scope="module")
def ds(tmp_path_factory):
    d = tmp_path_factory.mktemp("eq")
    satu = d / "corpus.txt"
    info = generate_dataset(8_000, satu, keywords=KWS, batch_size=1_000)
    multi = d / "multi"
    generate_dataset(6_000, f"{multi}/", files=4, keywords=KWS, batch_size=900)
    return {
        "single": [satu],
        "multi": sorted(multi.glob("*.txt")),
        "info": info,
    }


def _sig(res: SearchResult):
    return (res.counts, res.total_lines, res.total_bytes,
            {k: [(s.path, s.offset, s.text) for s in v] for k, v in res.samples.items()})


@pytest.mark.parametrize("dataset", ["single", "multi"])
@pytest.mark.parametrize("workers", [1, 2, 4, 8])
def test_semua_mode_identik(dataset, workers, ds):
    paths = ds[dataset]
    seq = search_sequential(paths, KWS).result
    thr = search_threaded(paths, KWS, workers).result
    proc = search_multiprocess(paths, KWS, workers).result
    assert _sig(thr) == _sig(seq), f"thread w={workers} dataset={dataset}"
    assert _sig(proc) == _sig(seq), f"process w={workers} dataset={dataset}"


@pytest.mark.parametrize("workers", [1, 2, 4])
def test_lock_sama_dengan_merge(workers, ds):
    paths = ds["single"]
    merge = search_threaded(paths, KWS, workers, sync="merge").result
    lock = search_threaded(paths, KWS, workers, sync="lock").result
    assert merge.counts == lock.counts
    assert (merge.total_lines, merge.total_bytes) == (lock.total_lines, lock.total_bytes)
    assert {k: [s.urutan for s in v] for k, v in merge.samples.items()} == \
           {k: [s.urutan for s in v] for k, v in lock.samples.items()}


def test_hasil_sama_ground_truth(ds):
    meta = json.loads(ds["info"].meta_path.read_text(encoding="utf-8"))
    for res in (
        search_sequential(ds["single"], KWS).result,
        search_threaded(ds["single"], KWS, 4).result,
        search_multiprocess(ds["single"], KWS, 4).result,
    ):
        for kw, v in meta["ground_truth"].items():
            assert res.counts[kw] == [v["lines"], v["occurrences"]], kw
        assert res.total_lines == meta["lines"]
        assert res.total_bytes == meta["size_bytes"]


def test_final_berulang_selalu_sama(ds):
    """Bukti bug hilang: 20x run paralel hasil selalu identik."""
    paths = ds["multi"]
    dasar = _sig(search_sequential(paths, KWS).result)
    for _ in range(20):
        assert _sig(search_threaded(paths, KWS, 6).result) == dasar
        assert _sig(search_multiprocess(paths, KWS, 3).result) == dasar


def test_worker_jauh_lebih_banyak_dari_baris(ds):
    p = ds["single"]
    dasar = _sig(search_sequential(p, KWS).result)
    assert _sig(search_threaded(p, KWS, 32, granularity=2).result) == dasar
