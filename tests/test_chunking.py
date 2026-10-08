"""Test chunking byte-range: kepemilikan baris, kasus tepi, validasi argumen."""

import pytest

from textsearch.chunking import Chunk, make_chunks, process_chunk
from textsearch.matcher import SearchResult

KWS = ("error", "cache")


def _tulis(tmp_path, teks, nama="f.txt"):
    p = tmp_path / nama
    # tulis biner agar newline tidak dikonversi ke \r\n di Windows
    p.write_bytes(teks.encode("utf-8"))
    return p


@pytest.mark.parametrize("n", [1, 2, 3, 7, 64, 500])
def test_chunk_menutup_file_tanpa_overlap(n, tmp_path):
    baris = [f"baris {i} error" if i % 5 == 0 else f"baris {i} biasa" for i in range(200)]
    p = _tulis(tmp_path, "\n".join(baris) + "\n")
    chunks = make_chunks([p], n)
    # coverage & non-overlap
    ukuran = p.stat().st_size
    assert chunks[0].start == 0 and chunks[-1].end == ukuran
    for a, b in zip(chunks, chunks[1:]):
        assert a.path == b.path
        assert a.end == b.start


@pytest.mark.parametrize("n", [1, 2, 3, 7, 64, 500])
def test_semua_baris_diproses_tepat_sekali(n, tmp_path):
    baris = [f"isi {i} " + ("error cache" if i % 3 == 0 else "ok") for i in range(137)]
    p = _tulis(tmp_path, "\n".join(baris) + "\n")
    total = SearchResult.empty(KWS)
    for c in make_chunks([p], n):
        total.merge(process_chunk(c, KWS))
    assert total.total_lines == 137
    assert total.total_bytes == p.stat().st_size
    assert total.counts["error"][0] == len([b for b in baris if "error" in b])


def test_file_kosong(tmp_path):
    p = _tulis(tmp_path, "")
    chunks = make_chunks([p], 4)
    total = SearchResult.empty(KWS)
    for c in chunks:
        total.merge(process_chunk(c, KWS))
    assert total.total_lines == 0 and total.total_bytes == 0


def test_satu_baris_tanpa_newline_akhir(tmp_path):
    p = _tulis(tmp_path, "satu-satunya error")
    total = SearchResult.empty(KWS)
    for c in make_chunks([p], 4):
        total.merge(process_chunk(c, KWS))
    assert total.total_lines == 1
    assert total.counts["error"] == [1, 1]


def test_batas_tepat_di_newline(tmp_path):
    # 5 baris @20 byte: batas chunk jatuh tepat di '\n'
    p = _tulis(tmp_path, "".join(f"{'baris'+str(i):<19}" + "\n" for i in range(5)))
    assert p.stat().st_size == 100
    for n in (2, 5):
        total = SearchResult.empty(KWS)
        for c in make_chunks([p], n):
            total.merge(process_chunk(c, KWS))
        assert total.total_lines == 5, f"n={n}"


def test_baris_sangat_panjang_melintasi_banyak_chunk(tmp_path):
    panjang = "x" * 10_000 + " error " + "y" * 10_000
    p = _tulis(tmp_path, f"pendek error\n{panjang}\npendek2\n")
    total = SearchResult.empty(KWS)
    for c in make_chunks([p], 16):
        total.merge(process_chunk(c, KWS))
    assert total.total_lines == 3          # baris panjang dimiliki 1 chunk
    assert total.counts["error"][0] == 2   # baris 1 dan 2
    assert total.total_bytes == p.stat().st_size


def test_beberapa_file(tmp_path):
    a = _tulis(tmp_path, "error\n" * 10, "a.txt")
    b = _tulis(tmp_path, "cache cache\n" * 3, "b.txt")
    c = _tulis(tmp_path, "", "c.txt")
    total = SearchResult.empty(KWS)
    for ch in make_chunks([a, b, c], 8):
        total.merge(process_chunk(ch, KWS))
    assert total.total_lines == 13
    assert total.counts["error"] == [10, 10]
    assert total.counts["cache"] == [3, 6]


def test_n_chunks_nol_error(tmp_path):
    p = _tulis(tmp_path, "isi\n")
    with pytest.raises(ValueError):
        make_chunks([p], 0)
    with pytest.raises(ValueError):
        make_chunks([p], -3)


def test_path_tidak_ada(tmp_path):
    with pytest.raises(FileNotFoundError):
        make_chunks([tmp_path / "tidakada.txt"], 4)


def test_worker_lebih_banyak_dari_baris(tmp_path):
    p = _tulis(tmp_path, "error\n")
    total = SearchResult.empty(KWS)
    chunks = make_chunks([p], 64)
    assert len(chunks) >= 1
    for c in chunks:
        total.merge(process_chunk(c, KWS))
    assert total.total_lines == 1
