import pytest

from musst.actions import ActionType, GameAction
from musst.rules import RulesEngine
from musst.state import GamePhase, GameState, PendingBet


def _state(phase: GamePhase, pending: PendingBet | None = None) -> GameState:
    return GameState(
        player_order=["p1", "p2", "p3", "p4"],
        hands={"p1": [], "p2": [], "p3": [], "p4": []},
        phase=phase,
        pending_bet=pending,
    )


def test_mus_phase_actions() -> None:
    rules = RulesEngine()
    actions = rules.legal_actions(_state(GamePhase.MUS), "p1")
    assert actions == {ActionType.MUS, ActionType.NO_MUS}


def test_response_actions_enabled_on_pending_bet() -> None:
    rules = RulesEngine()
    state = _state(GamePhase.GRANDE, pending=PendingBet(bettor_id="p1", amount=2))
    actions = rules.legal_actions(state, "p2")
    assert {ActionType.ACCEPT, ActionType.REJECT, ActionType.RAISE}.issubset(actions)


def test_reject_illegal_action() -> None:
    rules = RulesEngine()
    state = _state(GamePhase.MUS)
    with pytest.raises(ValueError):
        rules.validate_action(state, GameAction(actor_id="p1", action_type=ActionType.BET, amount=2))
