"""Órdago: declaración, respuesta, resolución y final de juego."""

import pytest
from tests.factories import game_at_lance
from tests.play import act, pass_lance, points_events

from mus_engine import (
    AcceptAction,
    BetAction,
    GameScore,
    OrdagoAction,
    PassAction,
    Phase,
    RaiseAction,
    RejectAction,
)
from mus_engine.errors import GameFinishedError, InvalidBetError
from mus_engine.events import (
    GameFinished,
    GameWon,
    HandsRevealed,
    LanceResolved,
    OrdagoAccepted,
    OrdagoDeclared,
)
from mus_engine.players import TeamId

# 0 gana grande (A); 1 gana chica (B).
HANDS = ("12O 12C 12E 1B", "1C 1E 4O 5O", "7O 7C 6E 5B", "11O 10C 2B 4B")


def kinds(game) -> list[type]:  # type: ignore[no-untyped-def]
    return [type(e.event) for e in game.event_log]


def test_ordago_accepted_resolves_immediately() -> None:
    game = game_at_lance(HANDS)
    act(game, OrdagoAction(), AcceptAction())
    assert game.is_finished
    assert game.winner is TeamId.A
    assert game.get_state().score == GameScore((40, 0), (1, 0))
    events = kinds(game)
    for kind in (
        OrdagoDeclared,
        OrdagoAccepted,
        HandsRevealed,
        LanceResolved,
        GameWon,
        GameFinished,
    ):
        assert kind in events
    assert events.index(HandsRevealed) > events.index(OrdagoAccepted)


def test_ordago_lost_by_the_proposer() -> None:
    game = game_at_lance(HANDS)
    pass_lance(game)  # grande
    act(game, OrdagoAction(), AcceptAction())  # 0 echa órdago a chica; 1 la tiene mejor
    assert game.winner is TeamId.B


def test_ordago_rejected_is_a_negada() -> None:
    game = game_at_lance(HANDS)
    act(game, OrdagoAction(), RejectAction(), RejectAction())
    assert not game.is_finished
    assert [(p.team, p.points, p.reason) for p in points_events(game)] == [("A", 1, "negada")]


def test_ordago_over_a_bet_rejected_gives_previous_bet() -> None:
    game = game_at_lance(HANDS)
    act(game, BetAction(3), OrdagoAction(), RejectAction(), RejectAction())
    assert [(p.team, p.points, p.reason) for p in points_events(game)] == [
        ("B", 3, "envite_no_querido")
    ]


def test_ordago_cannot_be_raised() -> None:
    game = game_at_lance(HANDS)
    act(game, OrdagoAction())
    with pytest.raises(InvalidBetError, match="órdago"):
        game.apply_action(1, RaiseAction(2))
    with pytest.raises(InvalidBetError, match="órdago"):
        game.apply_action(1, OrdagoAction())


def test_ordago_annuls_previous_accepted_bets() -> None:
    """C.VII-12: un órdago aceptado anula los envites aceptados en lances anteriores."""
    game = game_at_lance(HANDS, tantos=(30, 0))
    act(game, BetAction(20), AcceptAction())  # A tiene la grande: le daría el juego al contar
    act(game, PassAction(), OrdagoAction(), AcceptAction())  # 1 echa órdago a chica; 2 quiere
    assert game.winner is TeamId.B
    assert not [p for p in points_events(game) if p.reason == "envite"]


def test_ordago_keeps_points_already_scored() -> None:
    game = game_at_lance(HANDS, tantos=(5, 5))
    act(game, BetAction(2), RejectAction(), RejectAction())  # negada para A: 6
    act(game, OrdagoAction(), AcceptAction())  # chica: gana B
    assert game.get_state().score.tantos == (6, 40)


def test_no_actions_after_ordago_finishes_the_game() -> None:
    game = game_at_lance(HANDS)
    act(game, OrdagoAction(), AcceptAction())
    with pytest.raises(GameFinishedError):
        game.apply_action(0, PassAction())
    assert game.phase is Phase.GAME_OVER
    assert game.current_actors() == ()


def test_ordago_with_several_games_starts_a_new_game() -> None:
    game = game_at_lance(HANDS, games_to_win=2, tantos=(12, 30))
    hand_number = game.get_state().current_hand.number
    dealer = game.dealer
    act(game, OrdagoAction(), AcceptAction())
    assert not game.is_finished
    assert game.get_state().score == GameScore((0, 0), (1, 0))
    assert game.phase is Phase.MUS_DECISION
    assert game.get_state().current_hand.number == hand_number + 1
    assert game.dealer == (dealer + 1) % 4
