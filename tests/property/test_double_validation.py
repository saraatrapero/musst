"""Validación doble: el motor acepta una acción si y sólo si es legal.

Para estados alcanzados con juego aleatorio, se prueba un universo amplio de acciones
candidatas para los cuatro jugadores: las que no figuran en ``get_legal_actions`` deben
rechazarse con un ``MusEngineError`` sin cambiar el estado; las que figuran, aceptarse.
"""

from hypothesis import given, settings
from hypothesis import strategies as st
from tests.factories import game_with_state
from tests.strategies import play_seeded

from mus_engine import (
    AcceptAction,
    Action,
    BetAction,
    CutMusAction,
    DiscardAction,
    Game,
    MusAction,
    OrdagoAction,
    PassAction,
    RaiseAction,
    RejectAction,
)
from mus_engine.cards import Deck
from mus_engine.errors import MusEngineError
from mus_engine.players import ALL_SEATS, SeatId

FIXED: tuple[Action, ...] = (
    MusAction(),
    CutMusAction(),
    PassAction(),
    AcceptAction(),
    RejectAction(),
    OrdagoAction(),
    BetAction(1),
    BetAction(2),
    BetAction(7),
    RaiseAction(1),
    RaiseAction(2),
    RaiseAction(5),
    DiscardAction(()),
)


def candidates(game: Game, seat: SeatId) -> list[Action]:
    actions = list(FIXED)
    hand = game.get_state().hand
    if hand is not None:
        own = hand.hand_of(seat)
        actions += [DiscardAction(own[:n]) for n in range(1, 5)]
        foreign = next(c for c in Deck.standard() if c not in own)
        actions += [DiscardAction((foreign,)), DiscardAction((own[0], foreign))]
    return actions


@settings(max_examples=60, deadline=None)
@given(st.integers(0, 2**32), st.integers(0, 2**32), st.integers(0, 80))
def test_accepted_iff_legal(seed: int, choices: int, steps: int) -> None:
    game = Game(seed=seed)
    game.start()
    play_seeded(game, choices, steps)
    state = game.get_state()
    for seat in ALL_SEATS:
        legal = game.get_legal_actions(seat)
        for action in candidates(game, seat):
            probe = game_with_state(state)
            is_legal = seat in game.current_actors() and legal.contains(action)
            try:
                probe.apply_action(seat, action)
            except MusEngineError:
                assert not is_legal, f"Rechazada una acción legal: {seat} {action}"
                assert probe.get_state() is state
            else:
                assert is_legal, f"Aceptada una acción ilegal: {seat} {action}"
