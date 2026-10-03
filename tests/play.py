"""Ayudas para tests que juegan partidas mediante la API pública."""

from __future__ import annotations

from mus_engine import CutMusAction, DiscardAction, Game, MusAction, Phase
from mus_engine.cards import Card
from mus_engine.players import SeatId


def actor(game: Game) -> SeatId:
    (player,) = game.current_actors()
    return player


def all_mus(game: Game) -> None:
    """Los cuatro dan mus, en orden."""
    for _ in range(4):
        game.apply_action(actor(game), MusAction())
    assert game.phase is Phase.DISCARD


def discard_all(game: Game, count: int = 4) -> None:
    """Cada jugador, en su turno, tira sus ``count`` primeros naipes."""
    for _ in range(4):
        player = actor(game)
        hand = game.get_state().current_hand.hand_of(player)
        game.apply_action(player, DiscardAction(hand[:count]))


def hand_of(game: Game, player: int) -> tuple[Card, ...]:
    return game.get_state().current_hand.hand_of(SeatId(player))


def cut(game: Game) -> None:
    game.apply_action(actor(game), CutMusAction())
