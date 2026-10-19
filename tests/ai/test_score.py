from __future__ import annotations

import pytest

from mus_engine.ai.score import HAND_POINTS, ScoreAgent, win_probability


def test_symmetry_and_bounds() -> None:
    for a in range(0, 40, 3):
        for b in range(0, 40, 3):
            assert win_probability(a, b) + win_probability(b, a) == pytest.approx(1.0)
            assert 0.0 <= win_probability(a, b) <= 1.0


def test_more_tantos_is_better() -> None:
    for b in (0, 20, 38):
        values = [win_probability(a, b) for a in range(40)]
        assert values == sorted(values)


def test_finished_games() -> None:
    assert win_probability(40, 12) == 1.0
    assert win_probability(12, 41) == 0.0
    assert win_probability(40, 40) == 0.5
    assert win_probability(-3, 0) == win_probability(0, 0)


def test_agent_values_outcomes_by_score() -> None:
    agent = ScoreAgent(target=40)
    # Con el rival a punto de ganar, perder un tanto es casi perder la partida...
    behind = agent.win(20, 38) - agent.outcome(20, 38, 0, 2)
    # ...y con la partida encarrilada, ganar tantos apenas cambia nada.
    ahead = agent.outcome(38, 10, 1, 0) - agent.win(38, 10)
    assert agent.outcome(20, 38, 0, 2) == 0.0
    assert behind < 0.01
    assert ahead < 0.02
    assert agent.win(0, 0) == 0.5


def test_hand_points_are_a_distribution() -> None:
    assert sum(HAND_POINTS.values()) == pytest.approx(0.5, abs=0.05)  # media tabla
    assert all(a + b > 0 for a, b in HAND_POINTS)


def test_other_targets() -> None:
    assert ScoreAgent(target=30).win(25, 0) > ScoreAgent(target=40).win(25, 0)
