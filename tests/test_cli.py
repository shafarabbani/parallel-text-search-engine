"""Test CLI utama: konten output wajib, argumen salah, --json valid."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from textsearch.cli import main
from textsearch.dataset_gen import generate_dataset

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def korpus(tmp_path_factory):
    d = tmp_path_factory.mktemp("cli")
    out = d / "corpus.txt"
    generate_dataset(4_000, out, batch_size=500)
    return out


def test_output_muat_nama_npm_dan_waktu(korpus, capsys):
    rc = main(["--input", str(korpus), "--mode", "thread", "--workers", "2", "--quiet"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "SHAFA RABBANI FITYATUL MUKARRAMAH" in out
    assert "247006111020" in out
    assert "Jumlah thread" in out
    assert "Waktu total" in out
    assert "Throughput" in out


def test_mode_sequential(korpus, capsys):
    rc = main(["--input", str(korpus), "--mode", "sequential", "--quiet"])
    out = capsys.readouterr().out
    assert rc == 0 and "sequential" in out and "Waktu total" in out


def test_mode_proses_menyebut_process(korpus, capsys):
    rc = main(["--input", str(korpus), "--mode", "process", "--workers", "2", "--quiet"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Jumlah process" in out


def test_mode_all_dengan_speedup(korpus, capsys):
    rc = main(["--input", str(korpus), "--mode", "all", "--workers", "2", "--quiet"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "PERBANDINGAN MODE" in out
    assert "Speedup" in out and "Efisiensi" in out


def test_json_valid(korpus, capsys):
    rc = main(["--input", str(korpus), "--mode", "sequential", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert data["identitas"]["npm"] == "247006111020"
    assert data["runs"][0]["result"]


def test_input_tidak_ada(korpus, capsys):
    rc = main(["--input", str(korpus.parent / "tidakada.txt"), "--mode", "sequential"])
    err = capsys.readouterr().err
    assert rc != 0
    assert "ERROR" in err or "ERROR" in err


def test_workers_nol(korpus, capsys):
    rc = main(["--input", str(korpus), "--mode", "thread", "--workers", "0"])
    err = capsys.readouterr().err
    assert rc != 0
    assert "workers" in err


def test_mode_tidak_dikenal():
    with pytest.raises(SystemExit) as e:
        main(["--input", "x", "--mode", "kuantum"])
    assert e.value.code == 2


def test_subprocess_cli_banner(korpus):
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
    r = subprocess.run(
        [sys.executable, "-m", "textsearch.cli", "--input", str(korpus),
         "--mode", "thread", "--workers", "2", "--quiet"],
        capture_output=True, text=True, cwd=str(ROOT), env=env, timeout=120,
    )
    assert r.returncode == 0, r.stderr
    assert "SHAFA RABBANI FITYATUL MUKARRAMAH" in r.stdout
    assert "247006111020" in r.stdout


def test_input_dir_multi_file(tmp_path, korpus):
    from textsearch.dataset_gen import generate_dataset as g
    d = tmp_path / "multi"
    g(3_000, f"{d}/", files=3, batch_size=300)
    rc = main(["--input", str(d), "--mode", "thread", "--workers", "2", "--quiet"])
    assert rc == 0
