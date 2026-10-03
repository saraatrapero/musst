"""Eventos del motor y su visibilidad.

Cada transición produce eventos. Un evento **nunca** decide su propia visibilidad
implícitamente: va envuelto en un :class:`EventEnvelope` con una :class:`Visibility`
explícita, y los filtros para jugadores son listas blancas.

- ``PUBLIC``: lo saben los cuatro jugadores (y un espectador).
- ``PRIVATE``: sólo lo sabe ``EventEnvelope.audience`` (p. ej. las cartas recibidas).
- ``ENGINE``: sólo para auditoría y replay (semilla, orden de la baraja). Ningún
  jugador lo recibe jamás.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mus_engine.cards.card import Card
from mus_engine.players.seating import SeatId


class Visibility(Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    ENGINE = "engine"


@dataclass(frozen=True, slots=True)
class Event:
    """Base de todos los eventos. Inmutable."""


@dataclass(frozen=True, slots=True)
class GameStarted(Event):
    player_names: tuple[str, str, str, str]
    target_score: int


@dataclass(frozen=True, slots=True)
class RngSeeded(Event):
    """ENGINE: semilla de la partida. Conocerla equivale a conocer todas las cartas."""

    seed: int


@dataclass(frozen=True, slots=True)
class FirstDealerDrawn(Event):
    """C.III-1: sorteo del primer reparto por el palo del naipe que sale al cortar."""

    shuffler: SeatId
    cutter: SeatId
    card_shown: Card
    dealer: SeatId


@dataclass(frozen=True, slots=True)
class FirstDealerFixed(Event):
    """El primer repartidor viene fijado por configuración (sin sorteo)."""

    dealer: SeatId


@dataclass(frozen=True, slots=True)
class DeckShuffled(Event):
    """ENGINE: orden completo de la baraja tras barajar."""

    order: tuple[Card, ...]


@dataclass(frozen=True, slots=True)
class HandStarted(Event):
    """Nueva jugada: quién reparte y quién es mano. Cada jugador recibe 4 naipes."""

    hand_number: int
    dealer: SeatId
    mano: SeatId
    cards_per_player: int


@dataclass(frozen=True, slots=True)
class CardsDealt(Event):
    """PRIVATE: los naipes que ha recibido ``seat``."""

    seat: SeatId
    cards: tuple[Card, ...]


@dataclass(frozen=True, slots=True)
class PhaseChanged(Event):
    """La máquina de estados ha entrado en ``phase`` (nombre de :class:`Phase`)."""

    phase: str


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    seq: int
    hand_number: int
    visibility: Visibility
    event: Event
    audience: SeatId | None = None  # obligatorio si y sólo si visibility es PRIVATE

    def __post_init__(self) -> None:
        if (self.visibility is Visibility.PRIVATE) != (self.audience is not None):
            raise ValueError("Un evento PRIVATE necesita audiencia; los demás no la admiten")

    def visible_to(self, viewer: SeatId) -> bool:
        if self.visibility is Visibility.PUBLIC:
            return True
        if self.visibility is Visibility.PRIVATE:
            return self.audience == viewer
        return False


@dataclass(frozen=True, slots=True)
class Emission:
    """Evento emitido por una transición, antes de numerarlo en el registro."""

    event: Event
    visibility: Visibility = Visibility.PUBLIC
    audience: SeatId | None = None

    @classmethod
    def public(cls, event: Event) -> Emission:
        return cls(event)

    @classmethod
    def private(cls, seat: SeatId, event: Event) -> Emission:
        return cls(event, Visibility.PRIVATE, seat)

    @classmethod
    def engine(cls, event: Event) -> Emission:
        return cls(event, Visibility.ENGINE)
