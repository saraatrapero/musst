"""Lances completos con envites a través de la API pública.

Manos de referencia (reparte 3, mano 0; pareja A = 0 y 2, pareja B = 1 y 3):

- 0: R R R A → gana grande; medias de reyes; 31 (único con juego).
- 1: A A 4 5 → gana chica; pareja de ases.
- 2: 7 7 6 5 → pareja de sietes.
- 3: C S 2 4 → sin pares.
"""

import pytest
from tests.factories import game_at_lance
from tests.play import act, actor, pass_lance, points_events

from mus_engine import (
    AcceptAction,
    BetAction,
    CutMusAction,
    DiscardAction,
    Game,
    MusAction,
    OrdagoAction,
    PassAction,
    Phase,
    RaiseAction,
    RejectAction,
)
from mus_engine.errors import InvalidBetError, InvalidStateError, NotYourTurnError
from mus_engine.events import (
    HandsRevealed,
    JuegoDeclared,
    LanceNotPlayed,
    LanceStarted,
    LanceUncontested,
    ParesDeclared,
)
from mus_engine.players import SeatId
from mus_engine.rules import LanceType

HANDS = ("12O 12C 12E 1B", "1C 1E 4O 5O", "7O 7C 6E 5B", "11O 10C 2B 4B")


def lance_of(game: Game) -> LanceType | None:
    return game.get_state().current_hand.lance


def summary(game) -> list[tuple[str, int, str, str]]:  # type: ignore[no-untyped-def]
    return [(p.team, p.points, p.lance, p.reason) for p in points_events(game)]


def test_all_pass() -> None:
    game = game_at_lance(HANDS)
    for _ in range(3):  # grande, chica, pares
        pass_lance(game)
    assert summary(game) == [
        ("A", 1, "grande", "paso"),
        ("B", 1, "chica", "paso"),
        ("A", 3, "pares", "pares"),  # medias (2) + pareja de sietes (1)
        ("A", 3, "juego", "juego"),  # 31, sin envites porque sólo la pareja A tiene juego
    ]
    assert game.get_state().score.tantos == (7, 1)
    assert game.phase is Phase.MUS_DECISION  # nueva jugada
    assert game.get_state().current_hand.number == 2


def test_lance_order_and_participants() -> None:
    game = game_at_lance(HANDS)
    started = []
    for _ in range(3):
        started.append(lance_of(game))
        pass_lance(game)
    assert started == [LanceType.GRANDE, LanceType.CHICA, LanceType.PARES]
    events = [e.event for e in game.get_events()]
    lance_started = [e for e in events if isinstance(e, LanceStarted)]
    # El LanceStarted de grande se emite al preparar la partida (fuera del registro).
    assert [e.participants for e in lance_started] == [(0, 1, 2, 3), (0, 1, 2)]
    assert ParesDeclared((True, True, True, False)) in events
    assert JuegoDeclared((True, False, False, False)) in events
    assert LanceUncontested("juego", "A") in events


def test_grande_accepted_scores_at_the_end() -> None:
    game = game_at_lance(HANDS)
    act(game, BetAction(2), AcceptAction())
    assert summary(game) == []  # nada se anota hasta el final (C.VI-6)
    pass_lance(game)
    pass_lance(game)
    assert summary(game)[0] == ("A", 2, "grande", "envite")
    assert ("A", 1, "grande", "paso") not in summary(game)


def test_negada_is_scored_immediately() -> None:
    game = game_at_lance(HANDS)
    act(game, BetAction(2), RejectAction(), RejectAction())  # rechazan 1 y 3
    assert summary(game) == [("A", 1, "grande", "negada")]
    assert game.get_state().score.tantos == (1, 0)
    assert lance_of(game) is LanceType.CHICA


def test_one_rival_rejects_partner_accepts() -> None:
    game = game_at_lance(HANDS)
    act(game, BetAction(2), RejectAction())
    assert game.current_actors() == (3,)
    act(game, AcceptAction())
    assert lance_of(game) is LanceType.CHICA
    assert summary(game) == []


def test_rejected_raise_in_grande_has_no_deje() -> None:
    game = game_at_lance(HANDS)
    act(game, BetAction(2), RaiseAction(3))  # 0 envida 2, 1 sube 3 (5)
    assert game.current_actors() == (2,)  # contestan los rivales de 1: 2 y luego 0
    act(game, RejectAction(), RejectAction())
    assert summary(game) == [("B", 2, "grande", "envite_no_querido")]


def test_rejected_raise_in_pares_adds_deje_and_proposer_collects_pares() -> None:
    game = game_at_lance(HANDS)
    pass_lance(game)  # grande
    pass_lance(game)  # chica
    assert game.current_actors() == (0,)
    act(game, BetAction(2), RaiseAction(2), RejectAction(), RejectAction())
    # 1 revoca: lo querido (2) + deje (1) en el acto.
    assert summary(game)[0] == ("B", 3, "pares", "envite_no_querido")
    # Al final la pareja B cobra sus pares (pareja de ases de 1) aunque A tenía medias.
    assert ("B", 1, "pares", "pares") in summary(game)
    assert ("A", 3, "pares", "pares") not in summary(game)


def test_player_without_pares_cannot_speak_in_pares() -> None:
    game = game_at_lance(HANDS)
    pass_lance(game)
    pass_lance(game)
    act(game, PassAction(), PassAction())  # 0 y 1
    assert game.current_actors() == (2,)
    with pytest.raises(NotYourTurnError):
        game.apply_action(3, PassAction())


def test_pares_not_played_when_nobody_has_pares() -> None:
    hands = ("12O 11C 7E 1B", "10C 6E 4O 5O", "7O 11O 6C 5B", "12C 10O 2B 4B")
    game = game_at_lance(hands)
    pass_lance(game)
    pass_lance(game)
    assert LanceNotPlayed("pares") in [e.event for e in game.get_events()]


def test_punto_when_nobody_has_juego() -> None:
    hands = ("12O 11C 5E 5B", "10C 6E 4O 4C", "7O 11O 6C 1E", "12C 10O 2B 4B")
    # totales: 30, 24, 24, 25. Nadie tiene juego: se juega al punto.
    # Pares: 0 (cincos) y 1 (cuatros) -> se juega pares.
    game = game_at_lance(hands)
    pass_lance(game)
    pass_lance(game)
    assert lance_of(game) is LanceType.PARES
    pass_lance(game)
    assert lance_of(game) is LanceType.PUNTO
    act(game, BetAction(2), AcceptAction())
    tail = summary(game)[-2:]
    assert tail == [("A", 2, "punto", "envite"), ("A", 1, "punto", "punto")]


def test_contested_juego_accepted() -> None:
    hands = ("12O 12C 12E 1B", "11C 10E 7O 5O", "7C 6C 6E 5B", "11O 10C 3B 1C")
    # 0: 31 (A); 1: 32 (B); 3: 31 (B). Juego entre 0, 1 y 3.
    # Pares: sólo 0 (medias) y 2 (seises), ambos de A -> sin envites.
    game = game_at_lance(hands)
    pass_lance(game)
    pass_lance(game)
    assert lance_of(game) is LanceType.JUEGO
    assert LanceUncontested("pares", "A") in [e.event for e in game.get_events()]
    assert game.get_state().current_hand.bet.participants == (0, 1, 3)  # type: ignore[union-attr]
    act(game, BetAction(2), AcceptAction())
    # 0 y 3 tienen 31; 0 es mano: gana la pareja A, que cobra envite + su juego (3).
    assert summary(game)[-2:] == [("A", 2, "juego", "envite"), ("A", 3, "juego", "juego")]


def test_hands_revealed_only_at_the_end() -> None:
    game = game_at_lance(HANDS)
    pass_lance(game)
    pass_lance(game)
    assert not any(isinstance(e.event, HandsRevealed) for e in game.event_log)
    pass_lance(game)
    revealed = [e for e in game.event_log if isinstance(e.event, HandsRevealed)]
    assert len(revealed) == 1


def test_legal_actions_by_bet_state() -> None:
    game = game_at_lance(HANDS)
    legal = game.get_legal_actions(0)
    assert legal.action_types() == {PassAction, BetAction, OrdagoAction}
    assert legal.bet is not None
    assert legal.bet.minimum == 2
    act(game, BetAction(2))
    legal = game.get_legal_actions(1)
    assert legal.action_types() == {AcceptAction, RejectAction, RaiseAction, OrdagoAction}
    act(game, OrdagoAction())
    legal = game.get_legal_actions(actor(game))
    assert legal.action_types() == {AcceptAction, RejectAction}
    assert not game.get_legal_actions(1)


@pytest.mark.parametrize("action", [AcceptAction(), RejectAction(), RaiseAction(2), BetAction(1)])
def test_invalid_bets_when_open(action) -> None:  # type: ignore[no-untyped-def]
    game = game_at_lance(HANDS)
    with pytest.raises(InvalidBetError):
        game.apply_action(0, action)


@pytest.mark.parametrize("action", [PassAction(), BetAction(4), RaiseAction(1)])
def test_invalid_bets_when_pending(action) -> None:  # type: ignore[no-untyped-def]
    game = game_at_lance(HANDS)
    act(game, BetAction(2))
    with pytest.raises(InvalidBetError):
        game.apply_action(1, action)


@pytest.mark.parametrize("action", [MusAction(), CutMusAction(), DiscardAction([])])
def test_mus_actions_during_lance(action) -> None:  # type: ignore[no-untyped-def]
    game = game_at_lance(HANDS)
    with pytest.raises(InvalidStateError):
        game.apply_action(0, action)


def test_partner_of_proposer_cannot_raise() -> None:
    """C.VI-2: con un envite en litigio, el compañero no puede subirlo."""
    game = game_at_lance(HANDS)
    act(game, BetAction(2))
    with pytest.raises(NotYourTurnError):
        game.apply_action(2, RaiseAction(2))


def test_rejected_action_leaves_state_untouched() -> None:
    game = game_at_lance(HANDS)
    before = game.get_state()
    with pytest.raises(InvalidBetError):
        game.apply_action(0, AcceptAction())
    assert game.get_state() is before


def test_seat_ids_in_events_are_seats() -> None:
    game = game_at_lance(HANDS)
    act(game, BetAction(2), AcceptAction())
    assert all(isinstance(p, int) for p in game.get_state().current_hand.outcomes[0].participants)
    assert SeatId(0) in game.get_state().current_hand.outcomes[0].participants
