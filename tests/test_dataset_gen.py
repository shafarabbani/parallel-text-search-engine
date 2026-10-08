"""Test generator dataset (Fase 2): streaming, determinisme, manifest, multi-file."""

import hashlib
import inspect
import json
import re
from pathlib import Path

import pytest

from textsearch.dataset_gen import (
    DECOY_POOL,
    FILLER_WORDS,
    iter_batches,
    parse_line_count,
    validate_vocabulary,
    generate_dataset,
    meta_path_for,
)
from textsearch.params import derive_params

NPM = "247006111020"


def _hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ------------------------------- parse_line_count --------------------------
@pytest.mark.parametrize("teks,expected", [
    ("1000", 1000),
    ("1_000_000", 1_000_000),
    ("1M", 1_000_000),
    ("1m", 1_000_000),
    ("500K", 500_000),
    ("500k", 500_000),
])
def test_parse_line_count_valid(teks, expected):
    assert parse_line_count(teks) == expected


@pytest.mark.parametrize("buruk", ["abc", "0", "-5", "", "  ", "1X", "1.5", "K", "M"])
def test_parse_line_count_invalid(buruk):
    with pytest.raises(ValueError):
        parse_line_count(buruk)


# ------------------------------- jumlah baris ------------------------------
@pytest.mark.parametrize("n", [1, 10, 1_000, 10_000])
def test_jumlah_baris_tepat(n, tmp_path):
    out = tmp_path / f"c{n}.txt"
    generate_dataset(n, out, batch_size=300)
    with open(out, encoding="utf-8") as fh:
        assert sum(1 for _ in fh) == n


# ------------------------------- determinisme ------------------------------
def test_seed_sama_file_identik(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    generate_dataset(3_000, a, seed=123, batch_size=700)
    generate_dataset(3_000, b, seed=123, batch_size=100)
    assert _hash(a) == _hash(b)


def test_seed_beda_file_beda(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    generate_dataset(3_000, a, seed=1)
    generate_dataset(3_000, b, seed=2)
    assert _hash(a) != _hash(b)


def test_batch_size_tidak_mengubah_isi(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    generate_dataset(2_500, a, seed=99, batch_size=10)
    generate_dataset(2_500, b, seed=99, batch_size=5_000)
    assert _hash(a) == _hash(b)


def test_iter_batches_adalah_generator(tmp_path):
    src = (f"baris{i}" for i in range(50))
    it = iter_batches(src, 7)
    assert inspect.isgenerator(it)
    gabung = "".join(it)
    assert gabung.count("\n") == 50


# ------------------------------- variasi keyword ---------------------------
def test_frekuensi_tidak_seragam(tmp_path):
    out = tmp_path / "c.txt"
    info = generate_dataset(20_000, out)
    gt = info.ground_truth
    lines = {kw: v["lines"] for kw, v in gt.items()}
    tiers = info.tiers
    common = max(lines[k] for k, t in tiers.items() if t == "common")
    medium = max(lines[k] for k, t in tiers.items() if t == "medium")
    rare = max(lines[k] for k, t in tiers.items() if t == "rare")
    for kw, v in gt.items():
        assert v["occurrences"] >= 1, f"keyword {kw} tidak muncul"
    assert common > medium > rare, f"tier tidak terurut: {lines}"


def test_manifest_dan_ground_truth_konsisten(tmp_path):
    out = tmp_path / "c.txt"
    info = generate_dataset(5_000, out)
    meta = json.loads(meta_path_for(out).read_text(encoding="utf-8"))
    assert meta["lines"] == 5_000
    assert meta["ground_truth"] == info.ground_truth
    assert meta["size_bytes"] == out.stat().st_size
    # verifikasi INDEPENDEN: regex naif pada file yang sudah ditulis
    pola = re.compile(
        r"\b(" + "|".join(map(re.escape, info.keywords)) + r")\b",
        re.IGNORECASE,
    )
    hitung_lines = {k: 0 for k in info.keywords}
    hitung_occ = {k: 0 for k in info.keywords}
    for baris in out.read_text(encoding="utf-8").splitlines():
        for m in pola.finditer(baris):
            k = m.group(0).lower()
            hitung_occ[k] += 1
        for k in {m.group(0).lower() for m in pola.finditer(baris)}:
            hitung_lines[k] += 1
    for kw in info.keywords:
        assert meta["ground_truth"][kw]["lines"] == hitung_lines[kw]
        assert meta["ground_truth"][kw]["occurrences"] == hitung_occ[kw]


# ------------------------------- kosakata ----------------------------------
def test_validate_vocabulary_lolos():
    validate_vocabulary()  # tidak boleh raise
    assert len(set(FILLER_WORDS)) >= 190


def test_decoy_tidak_cocok(tmp_path):
    out = tmp_path / "d.txt"
    kws = derive_params(NPM).keywords
    teks = " ".join(d for kw in kws for d in DECOY_POOL[kw][:3])
    out.write_text(teks + "\n", encoding="utf-8")
    from textsearch.chunking import process_chunk, Chunk
    from textsearch.matcher import compile_pattern, match_line
    pola = compile_pattern(kws)
    assert match_line(pola, teks) == {}


# ------------------------------- multi-file --------------------------------
@pytest.mark.parametrize("files", [2, 3, 10])
def test_mode_multi_file(files, tmp_path):
    d = tmp_path / f"multi{files}"
    info = generate_dataset(5_000, f"{d}/", files=files, batch_size=400)
    parts = sorted(d.glob("part_*.txt"))
    assert len(parts) == files
    total = 0
    for p in parts:
        with open(p, encoding="utf-8") as fh:
            total += sum(1 for _ in fh)
    assert total == 5_000
    assert (d / "dataset.meta.json").is_file()


# ------------------------------- encoding ----------------------------------
def test_utf8_terbaca(tmp_path):
    out = tmp_path / "u.txt"
    generate_dataset(5_000, out, seed=7)
    teks = out.read_text(encoding="utf-8")
    assert any(w in teks for w in ("café", "naïve", "résumé", "façade", "jalapeño"))


def test_generate_validasi_argumen(tmp_path):
    with pytest.raises(ValueError):
        generate_dataset(0, tmp_path / "x.txt")
    with pytest.raises(ValueError):
        generate_dataset(10, tmp_path / "x.txt", files=0)
    with pytest.raises(ValueError):
        generate_dataset(10, tmp_path / "x.txt", batch_size=0)


def test_cli_main_sukses(tmp_path, capsys):
    from textsearch.dataset_gen import main
    out = tmp_path / "cli.txt"
    rc = main(["--lines", "1K", "--out", str(out), "--quiet"])
    assert rc == 0
    teks = capsys.readouterr().out
    assert "247006111020" in teks and "SHAFA RABBANI" in teks
    assert "Ground truth" in teks


def test_cli_main_input_salah(tmp_path, capsys):
    from textsearch.dataset_gen import main
    rc = main(["--lines", "abc", "--out", str(tmp_path / "x.txt")])
    assert rc == 2
    assert "ERROR" in capsys.readouterr().err


def test_progress_stderr_dan_batch_kecil(tmp_path, capsys):
    out = tmp_path / "p.txt"
    generate_dataset(500, out, batch_size=100, quiet=False)
    err = capsys.readouterr().err
    assert "[GEN] 500 / 500 baris" in err
