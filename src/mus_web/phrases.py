"""Frases de los avatares de los bots (IA-10).

Cada frase responde a un **hecho público** de la mesa (un envite, un lance ganado, una
mano enseñada…), nunca a las cartas ocultas de quien habla: así una frase no puede dar
pistas a nadie. Las frases se eligen al azar entre las del momento y se pueden desactivar
por sala.
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass

from mus_engine.events.events import (
    BetAccepted,
    BetPlaced,
    BetRaised,
    BetRejected,
    EventEnvelope,
    GameFinished,
    HandsRevealed,
    LanceResolved,
    MusCut,
    MusRequested,
    OrdagoAccepted,
    OrdagoDeclared,
    Passed,
    Visibility,
)
from mus_engine.players.seating import ALL_SEATS, SeatId, TeamId, team_of
from mus_engine.rules.juego import JuegoEvaluator
from mus_web.avatars_pack import Avatar

_BY_EVENT: dict[type, str] = {
    MusRequested: "pide_mus",
    MusCut: "corta_mus",
    Passed: "pasa",
    BetPlaced: "envida",
    BetRaised: "envida",
    OrdagoDeclared: "ordago",
    BetAccepted: "acepta",
    OrdagoAccepted: "acepta",
    BetRejected: "rechaza",
}

# Probabilidad de que un bot comente cada momento (el final de partida, siempre).
CHANCE: dict[str, float] = {"gana_partida": 1.0, "pierde_partida": 1.0, "ordago": 0.8}
DEFAULT_CHANCE = 0.3
MAX_PER_BATCH = 2

_JUEGO = JuegoEvaluator()


@dataclass(frozen=True, slots=True)
class Phrase:
    seat: SeatId
    text: str


def moments(events: Iterable[EventEnvelope]) -> Iterator[tuple[SeatId, str]]:
    """Momentos comentables de una serie de eventos (sólo los públicos)."""
    for envelope in events:
        if envelope.visibility is not Visibility.PUBLIC:
            continue
        event = envelope.event
        moment = _BY_EVENT.get(type(event))
        if moment is not None:
            yield event.seat, moment  # type: ignore[attr-defined]
        elif isinstance(event, LanceResolved):
            winner_team = team_of(event.winner)
            for seat in ALL_SEATS:
                yield seat, "gana_lance" if team_of(seat) is winner_team else "pierde_lance"
        elif isinstance(event, HandsRevealed):
            for seat, hand in zip(ALL_SEATS, event.hands, strict=True):
                if len(hand) == 4 and _JUEGO.classify(hand).total == 31:
                    yield seat, "revela_31"
        elif isinstance(event, GameFinished):
            winner = TeamId[event.winner]
            for seat in ALL_SEATS:
                yield seat, "gana_partida" if team_of(seat) is winner else "pierde_partida"


class PhraseMaker:
    """Elige qué dicen los bots. ``speakers``: asiento → avatar (sólo bots)."""

    def __init__(self, speakers: Mapping[SeatId, Avatar], rng: random.Random) -> None:
        self._speakers = dict(speakers)
        self._rng = rng

    def react(self, events: Iterable[EventEnvelope]) -> list[Phrase]:
        said: list[Phrase] = []
        for seat, moment in moments(events):
            avatar = self._speakers.get(seat)
            if avatar is None or moment not in avatar.phrases:
                continue
            if any(p.seat == seat for p in said) or len(said) >= MAX_PER_BATCH:
                continue
            if self._rng.random() < CHANCE.get(moment, DEFAULT_CHANCE):
                said.append(Phrase(seat, self._rng.choice(avatar.phrases[moment])))
        return said
