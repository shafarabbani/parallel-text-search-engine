"""Test logika pencocokan keyword: case-insensitive, word-boundary, merge."""

import pytest

from textsearch.matcher import Sample, SearchResult, compile_pattern, match_line


KWS = ("error", "server", "cache", "kernel", "timeout")


@pytest.fixture()
def pola():
    return compile_pattern(KWS)


def test_case_insensitive(pola):
    assert match_line(pola, "Error: disk full")["error"] == 1
    assert match_line(pola, "ERROR ERROR")["error"] == 2


def test_word_boundary(pola):
    assert match_line(pola, "errors terror") == {}
    assert match_line(pola, "serverless servers") == {}
    assert match_line(pola, "server ok")["server"] == 1


def test_multi_keyword_satu_baris(pola):
    c = match_line(pola, "error at server, error again")
    assert c["error"] == 2 and c["server"] == 1


def test_lines_vs_occurrences():
    res = SearchResult.empty(KWS)
    counter = match_line(compile_pattern(KWS), "error error")
    res.record_line(12, counter, Sample("f", 0, "error error"))
    assert res.counts["error"] == [1, 2]  # 1 baris, 2 kemunculan


def test_keyword_karakter_regex_aman():
    p = compile_pattern(["c++", "a.b"])
    assert match_line(p, "bahasa c++ oke")["c++"] == 1
    assert match_line(p, "axb") == {}


def test_baris_kosong(pola):
    assert match_line(pola, "") == {}


def test_unicode(pola):
    assert match_line(pola, "café error naïve")["error"] == 1


def test_compile_pattern_keyword_kosong():
    with pytest.raises(ValueError):
        compile_pattern([])


def test_compile_pattern_normalisasi_case():
    p = compile_pattern(["ERROR"])
    assert match_line(p, "error")["error"] == 1


def _res(pairs, lines=0, bytes_=0):
    r = SearchResult.empty(KWS)
    for kw, (ln, oc) in pairs.items():
        r.counts[kw] = [ln, oc]
    r.total_lines, r.total_bytes = lines, bytes_
    return r


def test_merge_komutatif():
    a = _res({"error": [5, 7]}, 10, 100)
    b = _res({"error": [2, 3], "cache": [1, 1]}, 4, 40)
    ab = _res({"error": [5, 7]}, 10, 100).merge(_res({"error": [2, 3], "cache": [1, 1]}, 4, 40))
    ba = b.merge(_res({"error": [5, 7]}, 10, 100))
    assert ab.counts == ba.counts
    assert (ab.total_lines, ab.total_bytes) == (ba.total_lines, ba.total_bytes)


def test_merge_asosiatif():
    def segitiga():
        return (_res({"error": [1, 1]}, 1, 10),
                _res({"error": [2, 3]}, 2, 20),
                _res({"cache": [4, 5]}, 3, 30))
    a2, b2, c2 = segitiga()
    kiri = a2.merge(b2).merge(c2)
    a3, b3, c3 = segitiga()
    kanan = a3.merge(b3.merge(c3))
    assert kiri.counts == kanan.counts
    assert (kiri.total_lines, kiri.total_bytes) == (kanan.total_lines, kanan.total_bytes)


def test_merge_sample_top_k_konsisten():
    K = 3
    a = SearchResult.empty(KWS, max_samples=K)
    b = SearchResult.empty(KWS, max_samples=K)
    for i in range(5):
        a.samples["error"].append(Sample("f", i, f"a{i}"))
        b.samples["error"].append(Sample("f", 100 + i, f"b{i}"))
    a.merge(b)
    assert [s.offset for s in a.samples["error"]] == [0, 1, 2]
