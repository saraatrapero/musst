"""CardCountingAgent (``docs/ai-design.md`` §3.1): qué pueden tener los demás.

En el Mus cada jugada se baraja la baraja entera y los descartes ajenos van boca
abajo, así que el conteo es modesto pero útil:

- los naipes que **yo** tengo o he descartado en esta jugada no los tiene nadie (hasta
  que se rebaraje el descarte, C.III-15);
- las **declaraciones** de pares y juego (sí/no) recortan las manos posibles de cada uno;
- cuántos naipes ha **pedido** cada uno en cada descarte (quien pide 1 suele tener
  jugada) se registra para los perfiles.

Sólo usa la observación del jugador.
"""

from __future__ import annotations

from dataclasses import dataclass

from mus_engine.ai.classes import remaining
from mus_engine.cards.card import Card
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.events.events import CardsDiscarded, DiscardDeclared, DiscardPileReshuffled
from mus_engine.game.observations import Observation
from mus_engine.players.seating import ALL_SEATS, SeatId


@dataclass(frozen=True, slots=True)
class Knowledge:
    """Lo que un jugador sabe de las manos ajenas en la jugada actual."""

    seat: SeatId
    mano: SeatId
    my_hand: tuple[Card, ...]
    out_of_play: tuple[Card, ...]  # mis descartes que no pueden volver
    available: dict[int, int]  # naipes de cada rango efectivo que pueden tener los demás
    pares: tuple[bool | None, ...]  # declaración de cada asiento (None: aún no)
    juego: tuple[bool | None, ...]
    requested: tuple[tuple[int, ...], ...]  # naipes pedidos por cada asiento, por ronda


class CardCounter:
    def __init__(self, policy: RankingPolicy) -> None:
        self.policy = policy

    def read(self, observation: Observation) -> Knowledge:
        me = observation.seat
        out: list[Card] = []
        requested: dict[SeatId, list[int]] = {s: [] for s in ALL_SEATS}
        for envelope in observation.events:
            if envelope.hand_number != observation.hand_number:
                continue
            event = envelope.event
            if isinstance(event, CardsDiscarded) and event.seat == me:
                out.extend(event.discarded)
            elif isinstance(event, DiscardPileReshuffled):
                out.clear()  # mis descartes vuelven al mazo
            elif isinstance(event, DiscardDeclared):
                requested[event.seat].append(event.count)
        mano = observation.mano if observation.mano is not None else me
        hand = observation.my_hand
        return Knowledge(
            seat=me,
            mano=mano,
            my_hand=hand,
            out_of_play=tuple(out),
            available=remaining(self.policy, (*hand, *out)),
            pares=_declared(observation.pares_holders),
            juego=_declared(observation.juego_holders),
            requested=tuple(tuple(requested[s]) for s in ALL_SEATS),
        )


def _declared(holders: tuple[bool, ...] | None) -> tuple[bool | None, ...]:
    if holders is None:
        return (None,) * len(ALL_SEATS)
    return tuple(holders)
