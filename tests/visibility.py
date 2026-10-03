"""Herramientas para comprobar qué naipes puede conocer un jugador."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping

from mus_engine import Game
from mus_engine.cards import Card
from mus_engine.events import CardsDealt, CardsDiscarded, FirstDealerDrawn, HandsRevealed
from mus_engine.players import SeatId


def cards_in(obj: object) -> set[Card]:
    """Todos los naipes contenidos (a cualquier profundidad) en ``obj``."""
    found: set[Card] = set()
    stack: list[object] = [obj]
    while stack:
        item = stack.pop()
        if isinstance(item, Card):
            found.add(item)
        elif dataclasses.is_dataclass(item) and not isinstance(item, type):
            stack.extend(getattr(item, f.name) for f in dataclasses.fields(item))
        elif isinstance(item, Mapping):
            stack.extend(item.keys())
            stack.extend(item.values())
        elif isinstance(item, Iterable) and not isinstance(item, (str, bytes)):
            stack.extend(item)
    return found


def cards_ever_held(game: Game, player: SeatId) -> set[Card]:
    """Naipes que ``player`` ha tenido legítimamente en la mano (repartidos o recibidos)."""
    held: set[Card] = set()
    for env in game.event_log:
        event = env.event
        if isinstance(event, CardsDealt) and event.seat == player:
            held.update(event.cards)
        if isinstance(event, CardsDiscarded) and event.seat == player:
            held.update(event.received)
    return held


def cards_known(game: Game, player: SeatId) -> set[Card]:
    """Naipes que ``player`` puede conocer legítimamente: los suyos, los enseñados al
    final de una jugada o en un órdago (C.VII-9, C.VI-6) y el del sorteo inicial."""
    known = cards_ever_held(game, player)
    for env in game.event_log:
        if isinstance(env.event, HandsRevealed):
            known.update(card for hand in env.event.hands for card in hand)
        if isinstance(env.event, FirstDealerDrawn):
            known.add(env.event.card_shown)
    return known
