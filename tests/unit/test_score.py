"""Tests del marcador."""

import pytest

from mus_engine import GameScore
from mus_engine.players import TeamId


def test_defaults() -> None:
    score = GameScore()
    assert score.tantos == (0, 0)
    assert score.games == (0, 0)


def test_accessors() -> None:
    score = GameScore(tantos=(17, 39), games=(1, 0))
    assert score.tantos_of(TeamId.A) == 17
    assert score.tantos_of(TeamId.B) == 39
    assert score.games_of(TeamId.A) == 1
    assert score.amarracos_of(TeamId.A, 5) == (3, 2)
    assert score.amarracos_of(TeamId.B, 5) == (7, 4)


@pytest.mark.parametrize(
    "kwargs",
    [{"tantos": (-1, 0)}, {"tantos": (0, True)}, {"games": (0, -1)}, {"tantos": (1.5, 0)}],
)
def test_invalid_scores(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="inválido"):
        GameScore(**kwargs)  # type: ignore[arg-type]
