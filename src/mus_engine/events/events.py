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
from mus_engine.config import GameConfig
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
    """Público: jugadores y reglas de la partida (la configuración no es secreta)."""

    player_names: tuple[str, str, str, str]
    config: GameConfig


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
class MusRequested(Event):
    seat: SeatId


@dataclass(frozen=True, slots=True)
class MusCut(Event):
    seat: SeatId


@dataclass(frozen=True, slots=True)
class DiscardDeclared(Event):
    """Público: cuántos naipes pide ``seat`` (no cuáles)."""

    seat: SeatId
    count: int


@dataclass(frozen=True, slots=True)
class CardsDiscarded(Event):
    """PRIVATE: naipes que ``seat`` ha tirado y los que ha recibido a cambio."""

    seat: SeatId
    discarded: tuple[Card, ...]
    received: tuple[Card, ...]


@dataclass(frozen=True, slots=True)
class DiscardPileReshuffled(Event):
    """Público: se acabó el mazo y se ha barajado el descarte (C.III-15).

    No indica cuántos naipes forman el nuevo mazo: el reglamento prohíbe contar el
    mazo (C.III-16). El orden y el tamaño sólo constan en ``DeckShuffled`` (motor).
    """


@dataclass(frozen=True, slots=True)
class ParesDeclared(Event):
    """Público: quién tiene pares (declaración veraz y automática; C.VI-17, R-20)."""

    holders: tuple[bool, bool, bool, bool]


@dataclass(frozen=True, slots=True)
class JuegoDeclared(Event):
    """Público: quién tiene juego (declaración veraz y automática; C.VI-20, R-20)."""

    holders: tuple[bool, bool, bool, bool]


@dataclass(frozen=True, slots=True)
class LanceStarted(Event):
    """Empiezan los envites de ``lance``; hablan ``participants`` en este orden."""

    lance: str
    participants: tuple[SeatId, ...]


@dataclass(frozen=True, slots=True)
class LanceUncontested(Event):
    """Sólo una pareja tiene la jugada: no hay envites y cobra al final (D-20)."""

    lance: str
    team: str


@dataclass(frozen=True, slots=True)
class LanceNotPlayed(Event):
    """Nadie tiene la jugada: el lance no se juega."""

    lance: str


@dataclass(frozen=True, slots=True)
class Passed(Event):
    seat: SeatId
    lance: str


@dataclass(frozen=True, slots=True)
class BetPlaced(Event):
    seat: SeatId
    lance: str
    amount: int


@dataclass(frozen=True, slots=True)
class BetRaised(Event):
    """Revoque: ``seat`` sube ``increment`` sobre lo envidado; ahora se juegan ``total``."""

    seat: SeatId
    lance: str
    increment: int
    total: int


@dataclass(frozen=True, slots=True)
class OrdagoDeclared(Event):
    seat: SeatId
    lance: str


@dataclass(frozen=True, slots=True)
class BetAccepted(Event):
    seat: SeatId
    lance: str
    amount: int  # 0 si es un órdago


@dataclass(frozen=True, slots=True)
class OrdagoAccepted(Event):
    seat: SeatId
    lance: str


@dataclass(frozen=True, slots=True)
class BetRejected(Event):
    """ "No quiero" de ``seat``. El lance se cierra cuando rechazan todos los rivales."""

    seat: SeatId
    lance: str


@dataclass(frozen=True, slots=True)
class LanceClosed(Event):
    """Los envites del lance han terminado."""

    lance: str
    resolution: str
    amount: int
    team: str | None


@dataclass(frozen=True, slots=True)
class HandsRevealed(Event):
    """Público: se enseñan las cartas (C.VII-9 al final; C.VI-6 en un órdago aceptado)."""

    hands: tuple[tuple[Card, ...], ...]


@dataclass(frozen=True, slots=True)
class LanceResolved(Event):
    """Resultado a cartas de un lance (sólo cuando se comparan jugadas)."""

    lance: str
    winner: SeatId
    tied: tuple[SeatId, ...]


@dataclass(frozen=True, slots=True)
class PointsAwarded(Event):
    team: str
    points: int
    lance: str
    reason: str
    tantos_after: tuple[int, int]


@dataclass(frozen=True, slots=True)
class GameWon(Event):
    """Una pareja gana un juego (alcanza el tanteo o gana un órdago)."""

    team: str
    games: tuple[int, int]
    final_tantos: tuple[int, int]


@dataclass(frozen=True, slots=True)
class GameFinished(Event):
    """La partida termina: ``winner`` ha ganado los juegos necesarios."""

    winner: str
    games: tuple[int, int]


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
