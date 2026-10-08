"""Test determinisme parameter turunan NPM (Fase 1)."""

import pytest

from textsearch.params import KEYWORD_POOL, derive_params

NPM = "247006111020"


def test_derive_params_deterministik():
    a = derive_params(NPM)
    b = derive_params(NPM)
    assert a == b
    assert a.keywords == b.keywords
    assert a.seed == b.seed == int(NPM)


def test_keywords_unik_dari_pool():
    p = derive_params(NPM)
    assert len(p.keywords) == 5
    assert len(set(p.keywords)) == 5
    for kw in p.keywords:
        assert kw in KEYWORD_POOL


def test_npm_berbeda_hasil_berbeda():
    assert derive_params(NPM).keywords != derive_params("123456789012").keywords


def test_npm_non_numerik_error():
    for buruk in ["", "abc", "2470-0611", " 247006111020 "]:
        with pytest.raises(ValueError):
            derive_params(buruk)


def test_pool_meminimal_12_keyword():
    assert len(KEYWORD_POOL) >= 12
