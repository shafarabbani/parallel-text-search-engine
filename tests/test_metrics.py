"""Test rumus metrik: speedup, efisiensi, throughput, dan kasus invalid."""

import pytest

from textsearch.metrics import efficiency, speedup, throughput, throughput_mb


def test_speedup_rumus():
    assert speedup(10.0, 2.5) == 4.0
    assert speedup(1.0, 1.0) == 1.0


def test_efficiency_rumus():
    assert efficiency(3.2, 4) == pytest.approx(0.8)
    assert efficiency(1.0, 1) == 1.0


def test_throughput_rumus():
    assert throughput(1_000_000, 2.0) == 500_000.0
    assert throughput_mb(2_000_000, 2.0) == pytest.approx(1.0)


@pytest.mark.parametrize("t", [0.0, -1.0, float("nan")])
def test_pembagian_nol_error(t):
    with pytest.raises(ValueError):
        speedup(5.0, t)
    with pytest.raises(ValueError):
        throughput(100, t)


def test_workers_nol_error():
    with pytest.raises(ValueError):
        efficiency(2.0, 0)
    with pytest.raises(ValueError):
        efficiency(-1.0, 2)


def test_baris_negatif_error():
    with pytest.raises(ValueError):
        throughput(-5, 1.0)
