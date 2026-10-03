"""Tests de la fachada RulesEngine (reglas puras sobre GameState)."""

import pytest
from tests.factories import started_game

from mus_engine import CutMusAction, MusAction, PassAction, Phase, RulesEngine
from mus_engine.errors import NotYourTurnError


def test_queries_match_game() -> None:
    game = started_game()
    state = game.get_state()
    assert RulesEngine.actors(state) == game.current_actors()
    assert RulesEngine.legal_actions(state, game.mano) == game.get_legal_actions(game.mano)
    assert RulesEngine.is_legal(state, game.mano, MusAction())
    assert not RulesEngine.is_legal(state, game.mano, PassAction())
    assert not RulesEngine.is_legal(state, (game.mano + 1) % 4, MusAction())


def test_apply_returns_new_state_without_touching_the_game() -> None:
    game = started_game()
    state = game.get_state()
    new_state, emitted = RulesEngine.apply(state, game.mano, CutMusAction())
    assert new_state.phase is Phase.LANCE
    assert emitted
    assert game.get_state() is state
    assert game.phase is Phase.MUS_DECISION


def test_validate_raises_specific_errors() -> None:
    game = started_game()
    with pytest.raises(NotYourTurnError):
        RulesEngine.validate(game.get_state(), (game.mano + 1) % 4, MusAction())
    RulesEngine.validate(game.get_state(), game.mano, MusAction())
