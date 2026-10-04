"""Orden de la mesa: asientos, parejas, mano, postre y turnos.

Convención única del motor: los asientos se numeran ``0..3`` **en el orden en que se
habla**. ``next_player(s)`` es el jugador que habla después de ``s`` (el que está a su
derecha según el reglamento). Todas las demás nociones de orden se derivan de aquí.

Conceptos (no confundir):

- **Repartidor / postre**: quien da las cartas; es el último en hablar.
- **Mano**: el jugador a la derecha del que reparte (Voc. "Mano"), es decir
  ``next_player(repartidor)``. Habla primero y gana los empates.
- **Mano del lance**: en pares o juego, el primer jugador que los tiene (Voc. "Mano").
- **Turno**: quien debe actuar ahora; lo decide la máquina de estados.

Todas las funciones son puras y validan sus argumentos.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum
from typing import NewType

from mus_engine.cards.card import Suit
from mus_engine.errors import InvalidPlayerError

SeatId = NewType("SeatId", int)

NUM_SEATS = 4
ALL_SEATS: tuple[SeatId, ...] = tuple(SeatId(i) for i in range(NUM_SEATS))


class TeamId(Enum):
    """Las dos parejas: compañeros sentados enfrente (asientos 0-2 y 1-3)."""

    A = 0
    B = 1


def seat(value: object) -> SeatId:
    """Valida y convierte un identificador de asiento. Lanza :class:`InvalidPlayerError`."""
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < NUM_SEATS:
        raise InvalidPlayerError(f"Jugador inexistente: {value!r} (válidos: 0..{NUM_SEATS - 1})")
    return SeatId(value)


def next_player(player: SeatId) -> SeatId:
    """Jugador que habla después de ``player``."""
    return SeatId((seat(player) + 1) % NUM_SEATS)


def previous_player(player: SeatId) -> SeatId:
    """Jugador que habla antes de ``player``."""
    return SeatId((seat(player) - 1) % NUM_SEATS)


def partner(player: SeatId) -> SeatId:
    """Compañero de pareja (sentado enfrente)."""
    return SeatId((seat(player) + 2) % NUM_SEATS)


def team_of(player: SeatId) -> TeamId:
    return TeamId(seat(player) % 2)


def team_seats(team: TeamId) -> tuple[SeatId, SeatId]:
    return SeatId(team.value), SeatId(team.value + 2)


def opponent(team: TeamId) -> TeamId:
    return TeamId.B if team is TeamId.A else TeamId.A


def are_teammates(a: SeatId, b: SeatId) -> bool:
    """``True`` si ``a`` y ``b`` son de la misma pareja (incluido ``a == b``)."""
    return team_of(a) is team_of(b)


# --- Mano y postre ------------------------------------------------------------------


def mano_for_dealer(dealer: SeatId) -> SeatId:
    """Voc. "Mano": el jugador a la derecha del que reparte."""
    return next_player(dealer)


def dealer_for_mano(mano: SeatId) -> SeatId:
    """Inverso de :func:`mano_for_dealer`: el postre es quien reparte."""
    return previous_player(mano)


def next_dealer(dealer: SeatId) -> SeatId:
    """D-15: reparte la jugada siguiente el que ha sido mano en esta."""
    return mano_for_dealer(dealer)


def order_from(start: SeatId) -> tuple[SeatId, ...]:
    """Los cuatro asientos en orden de habla empezando por ``start``."""
    first = seat(start)
    return tuple(SeatId((first + i) % NUM_SEATS) for i in range(NUM_SEATS))


def distance_from_mano(player: SeatId, mano: SeatId) -> int:
    """0 para la mano, 1, 2 y 3 para el postre. Base de los desempates (D-09)."""
    return (seat(player) - seat(mano)) % NUM_SEATS


def is_mano(player: SeatId, mano: SeatId) -> bool:
    return seat(player) == seat(mano)


def is_postre(player: SeatId, mano: SeatId) -> bool:
    return distance_from_mano(player, mano) == NUM_SEATS - 1


def closest_to_mano(players: Iterable[SeatId], mano: SeatId) -> SeatId:
    """El jugador más cercano a la mano entre ``players`` (gana los empates, D-09)."""
    candidates = tuple(players)
    if not candidates:
        raise ValueError("Se necesita al menos un jugador")
    return min(candidates, key=lambda p: distance_from_mano(p, mano))


def eligible_in_order(mano: SeatId, eligible: Iterable[SeatId]) -> tuple[SeatId, ...]:
    """Los jugadores de ``eligible`` en orden de habla desde la mano."""
    allowed = {seat(p) for p in eligible}
    return tuple(p for p in order_from(mano) if p in allowed)


def lance_mano(mano: SeatId, eligible: Iterable[SeatId]) -> SeatId | None:
    """Voc. "Mano": en pares o juego, el primer jugador que los tiene. ``None`` si nadie."""
    ordered = eligible_in_order(mano, eligible)
    return ordered[0] if ordered else None


def lance_postre(mano: SeatId, eligible: Iterable[SeatId]) -> SeatId | None:
    """El último jugador, en orden de habla, entre los que tienen pares o juego."""
    ordered = eligible_in_order(mano, eligible)
    return ordered[-1] if ordered else None


# --- Órdenes específicos del reglamento ---------------------------------------------


def mus_order(mano: SeatId) -> tuple[SeatId, ...]:
    """Orden para dar o cortar el mus: mano, 2º, 3º, 4º (C.IV-4, D-04)."""
    return order_from(mano)


def discard_order(mano: SeatId) -> tuple[SeatId, ...]:
    """C.III-11: se descarta primero el que reparte y el último es el mano.

    "El descarte continuará de izquierda a derecha hasta el mano", es decir, en sentido
    contrario al de habla: postre, 3º, 2º, mano. Las cartas se sirven en este mismo
    orden (D-06).
    """
    return tuple(reversed(order_from(mano)))


def deal_order(dealer: SeatId) -> tuple[SeatId, ...]:
    """C.III-2: el reparto inicial se da de uno en uno empezando por la mano."""
    return order_from(mano_for_dealer(dealer))


# --- Sorteo del primer reparto (C.III-1, C.III-3) -----------------------------------

_SUIT_OFFSET_FROM_CUTTER: dict[Suit, int] = {
    Suit.OROS: 1,  # primer jugador a la derecha del que corta
    Suit.COPAS: 2,  # segundo
    Suit.ESPADAS: 3,  # tercero
    Suit.BASTOS: 0,  # el que los muestra (el que corta)
}


def cutter_for(shuffler: SeatId) -> SeatId:
    """C.III-3: corta el jugador a la izquierda del que ha barajado.

    A la izquierda está quien habla antes (a la derecha, quien habla después).
    """
    return previous_player(shuffler)


def first_dealer_by_suit(cutter: SeatId, suit: Suit) -> SeatId:
    """C.III-1: el palo del naipe que sale al cortar decide quién da primero.

    Oros → primer jugador a la derecha del que corta; copas → segundo; espadas →
    tercero; bastos → el que lo muestra.
    """
    return SeatId((seat(cutter) + _SUIT_OFFSET_FROM_CUTTER[suit]) % NUM_SEATS)
