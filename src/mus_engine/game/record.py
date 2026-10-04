"""Registro reproducible de una partida y su reconstrucción a partir de los eventos.

Una partida queda totalmente determinada por ``(jugadores, configuración, semilla,
acciones)``. :meth:`GameRecord.from_events` obtiene ese registro **sólo a partir del
registro completo de eventos** (incluidos los privados y los de motor): es la prueba de
que los eventos bastan para reconstruir la partida (event sourcing).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from mus_engine.config import GameConfig
from mus_engine.errors import InvariantViolationError
from mus_engine.events.events import (
    BetAccepted,
    BetPlaced,
    BetRaised,
    BetRejected,
    CardsDiscarded,
    DiscardDeclared,
    EventEnvelope,
    GameStarted,
    MusCut,
    MusRequested,
    OrdagoAccepted,
    OrdagoDeclared,
    Passed,
    RngSeeded,
)
from mus_engine.game.actions import (
    AcceptAction,
    Action,
    BetAction,
    CutMusAction,
    DiscardAction,
    MusAction,
    OrdagoAction,
    PassAction,
    RaiseAction,
    RejectAction,
)
from mus_engine.players.seating import SeatId


@dataclass(frozen=True, slots=True)
class GameRecord:
    player_names: tuple[str, str, str, str]
    config: GameConfig
    seed: int
    actions: tuple[tuple[SeatId, Action], ...]

    @classmethod
    def from_events(cls, log: Sequence[EventEnvelope]) -> GameRecord:
        """Reconstruye el registro a partir del registro completo de eventos."""
        names: tuple[str, str, str, str] | None = None
        config: GameConfig | None = None
        seed: int | None = None
        actions: list[tuple[SeatId, Action]] = []
        pending_discards: dict[SeatId, int] = {}  # asiento -> posición en ``actions``
        for envelope in log:
            event = envelope.event
            if isinstance(event, GameStarted):
                names, config = event.player_names, event.config
            elif isinstance(event, RngSeeded):
                seed = event.seed
            elif isinstance(event, MusRequested):
                actions.append((event.seat, MusAction()))
            elif isinstance(event, MusCut):
                actions.append((event.seat, CutMusAction()))
            elif isinstance(event, DiscardDeclared):
                # Los naipes concretos se conocen al servir (evento privado CardsDiscarded).
                pending_discards[event.seat] = len(actions)
                actions.append((event.seat, DiscardAction(())))
            elif isinstance(event, CardsDiscarded):
                index = pending_discards.pop(event.seat)
                actions[index] = (event.seat, DiscardAction(event.discarded))
            elif isinstance(event, Passed):
                actions.append((event.seat, PassAction()))
            elif isinstance(event, BetPlaced):
                actions.append((event.seat, BetAction(event.amount)))
            elif isinstance(event, BetRaised):
                actions.append((event.seat, RaiseAction(event.increment)))
            elif isinstance(event, OrdagoDeclared):
                actions.append((event.seat, OrdagoAction()))
            elif isinstance(event, (BetAccepted, OrdagoAccepted)):
                actions.append((event.seat, AcceptAction()))
            elif isinstance(event, BetRejected):
                actions.append((event.seat, RejectAction()))
        if names is None or config is None or seed is None:
            raise InvariantViolationError(
                "El registro de eventos no contiene GameStarted y RngSeeded: "
                "se necesita el registro completo (Game.event_log)"
            )
        if pending_discards:
            # Descartes declarados de una ronda aún no servida: sólo puede faltar la ronda
            # en curso, cuyos naipes siguen pendientes. No se pueden reconstruir.
            raise InvariantViolationError(
                "Hay descartes declarados sin servir: no se pueden reconstruir sus naipes"
            )
        return cls(names, config, seed, tuple(actions))
