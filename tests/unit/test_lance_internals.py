"""Ramas defensivas del flujo de lances e invariantes de envites."""

import dataclasses
from typing import Any

import pytest
from tests.factories import game_at_lance

from mus_engine import GameConfig, Phase
from mus_engine.betting import BetStatus, apply_bet, open_bet
from mus_engine.cards import cards_from_codes
from mus_engine.errors import InvariantViolationError
from mus_engine.game import invariants, lance_flow
from mus_engine.game.handlers.lance import LanceHandler
from mus_engine.game.state import GameState
from mus_engine.players import SeatId
from mus_engine.rules import LanceType
from mus_engine.rules.lances import jugada_points

HANDS = ("12O 12C 12E 1B", "1C 1E 4O 5O", "7O 7C 6E 5B", "11O 10C 2B 4B")


def _state() -> GameState:
    return game_at_lance(HANDS).get_state()


def _with_hand(state: GameState, **changes: Any) -> GameState:
    return state.evolve(hand=dataclasses.replace(state.current_hand, **changes))


def _with_bet(state: GameState, **changes: Any) -> GameState:
    bet = state.current_hand.bet
    assert bet is not None
    return _with_hand(state, bet=dataclasses.replace(bet, **changes))


def test_valid_lance_state_passes() -> None:
    invariants.check_state(_state())


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"lance": LanceType.CHICA}, "no corresponde"),
    ],
)
def test_hand_level_bet_invariants(changes: dict[str, Any], message: str) -> None:
    with pytest.raises(InvariantViolationError, match=message):
        invariants.check_state(_with_hand(_state(), **changes))


def test_lance_without_bet() -> None:
    with pytest.raises(InvariantViolationError, match="sin envite"):
        invariants.check_state(_with_hand(_state(), bet=None))


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"status": BetStatus.ACCEPTED}, "cerrado"),
        ({"to_act": ()}, "cerrado"),
        (
            {"to_act": (SeatId(0),), "participants": (SeatId(1), SeatId(3), SeatId(2))},
            "no participa",
        ),
        ({"participants": (SeatId(0), SeatId(2)), "to_act": (SeatId(0),)}, "dos parejas"),
        ({"proposer": SeatId(0)}, "abierto"),
        ({"status": BetStatus.PENDING, "proposer": SeatId(1), "to_act": (SeatId(3),)}, "rivales"),
        (
            {
                "status": BetStatus.PENDING,
                "proposer": SeatId(0),
                "to_act": (SeatId(1),),
                "pending": 2,
                "accepted": 2,
            },
            "incoherentes",
        ),
    ],
)
def test_bet_invariants(changes: dict[str, Any], message: str) -> None:
    with pytest.raises(InvariantViolationError, match=message):
        invariants.check_state(_with_bet(_state(), **changes))


def test_handler_requires_bet() -> None:
    with pytest.raises(InvariantViolationError, match="sin envite"):
        LanceHandler().actors(_with_hand(_state(), bet=None))


def test_lance_start_requires_lance() -> None:
    state = _with_hand(_state(), lance=None).evolve(phase=Phase.LANCE_START)
    with pytest.raises(InvariantViolationError, match="sin lance"):
        lance_flow.lance_start(state)


def test_close_bet_requires_closed_bet() -> None:
    bet = apply_bet(
        open_bet(LanceType.GRANDE, tuple(map(SeatId, range(4)))), SeatId(0), 2, GameConfig()
    )
    with pytest.raises(InvariantViolationError, match="sin cerrar"):
        lance_flow.close_bet(_state(), bet)


def test_ordago_showdown_requires_accepted_ordago() -> None:
    with pytest.raises(InvariantViolationError, match="órdago"):
        lance_flow.ordago_showdown(_state().evolve(phase=Phase.ORDAGO_SHOWDOWN))


def test_jugada_points_only_for_pares_and_juego() -> None:
    cards = cards_from_codes("12O 12C 12E 1B")
    assert jugada_points(LanceType.GRANDE, cards, GameConfig()) == 0
    assert jugada_points(LanceType.PARES, cards, GameConfig()) == 2
    assert jugada_points(LanceType.JUEGO, cards, GameConfig()) == 3
