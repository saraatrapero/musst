"""Tests del generador determinista."""

import dataclasses
from collections import Counter

import pytest

from mus_engine.rng import Rng


def test_rng_is_immutable() -> None:
    rng = Rng(1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        rng.seed = 2  # type: ignore[misc]


def test_shuffle_does_not_mutate_input() -> None:
    items = [1, 2, 3, 4, 5]
    Rng(3).shuffle(items)
    assert items == [1, 2, 3, 4, 5]


def test_shuffle_advances_stream() -> None:
    _, nxt = Rng(3, stream=5).shuffle([1, 2])
    assert nxt == Rng(3, stream=6)


def test_shuffle_empty_and_single() -> None:
    assert Rng(1).shuffle([])[0] == ()
    assert Rng(1).shuffle(["x"])[0] == ("x",)


def test_choice_index_bounds() -> None:
    rng = Rng(9)
    for _ in range(200):
        index, rng = rng.choice_index(4)
        assert 0 <= index < 4


def test_choice_index_rejects_non_positive() -> None:
    with pytest.raises(ValueError, match="positivo"):
        Rng(1).choice_index(0)


def test_choice_index_is_roughly_uniform() -> None:
    rng = Rng(2024)
    counts: Counter[int] = Counter()
    for _ in range(4000):
        index, rng = rng.choice_index(4)
        counts[index] += 1
    for value in range(4):
        assert 850 < counts[value] < 1150


def test_shuffle_positions_roughly_uniform() -> None:
    # Cada elemento debe acabar en la posición 0 con frecuencia similar.
    counts: Counter[int] = Counter()
    rng = Rng(77)
    for _ in range(4000):
        shuffled, rng = rng.shuffle(range(4))
        counts[shuffled[0]] += 1
    for value in range(4):
        assert 850 < counts[value] < 1150


def test_large_bound() -> None:
    index, _ = Rng(5).choice_index(10**12)
    assert 0 <= index < 10**12
