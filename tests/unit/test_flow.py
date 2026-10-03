"""Tests de las transiciones automáticas."""

import pytest

from mus_engine import Game, Phase
from mus_engine.errors import InvariantViolationError
from mus_engine.game import flow
from mus_engine.game.state import GameState


def _new_state() -> GameState:
    return Game(seed=1).get_state()


def test_deal_requires_dealer() -> None:
    with pytest.raises(InvariantViolationError, match="repartidor"):
        flow.deal(_new_state().evolve(phase=Phase.DEAL))


def test_resting_state_is_returned_unchanged() -> None:
    state = _new_state()
    assert flow.run_automatic(state) == (state, ())


def test_automatic_phase_without_transition(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(flow.AUTOMATIC_STEPS, Phase.DEAL)
    with pytest.raises(InvariantViolationError, match="sin transición"):
        flow.run_automatic(_new_state().evolve(phase=Phase.DEAL))


def test_infinite_automatic_loop_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(flow.AUTOMATIC_STEPS, Phase.DEAL, lambda s: (s, ()))
    with pytest.raises(InvariantViolationError, match="Demasiadas"):
        flow.run_automatic(_new_state().evolve(phase=Phase.DEAL))


def test_choose_first_dealer_then_deal() -> None:
    state = _new_state().evolve(phase=Phase.CHOOSE_FIRST_DEALER)
    after, emitted = flow.run_automatic(state)
    assert after.phase is Phase.MUS_DECISION
    assert after.pending_dealer is None
    assert after.hand is not None
    assert emitted
