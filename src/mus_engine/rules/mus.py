"""Reglas puras del mus y de los descartes.

- C.IV-4: orden para dar o cortar el mus (mano, 2º, 3º, 4º; D-04).
- C.III-11: se descarta primero el que reparte y el último es el mano.
- C.III-2: en los descartes se sirve de una vez a cada jugador, en el mismo orden (D-06).
- C.III-15: si se acaba el mazo, se recoge todo el descarte, se baraja y se sirve (D-07).
- D-13: se descartan entre 1 y 4 naipes.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations

from mus_engine.cards.card import Card
from mus_engine.cards.deck import Deck
from mus_engine.errors import InvalidDiscardError
from mus_engine.players.seating import SeatId
from mus_engine.rng import Rng


def discard_options(
    hand: Sequence[Card], minimum: int, maximum: int
) -> tuple[frozenset[Card], ...]:
    """Todos los descartes legales de ``hand`` (subconjuntos de tamaño mínimo..máximo).

    El orden es determinista: por tamaño y después por posición en la mano.
    """
    return tuple(
        frozenset(combo)
        for size in range(minimum, maximum + 1)
        for combo in combinations(hand, size)
    )


def check_discard(hand: Sequence[Card], cards: frozenset[Card], minimum: int, maximum: int) -> None:
    """Lanza :class:`InvalidDiscardError` con el motivo concreto si el descarte no vale."""
    foreign = sorted(card.code for card in cards if card not in hand)
    if foreign:
        raise InvalidDiscardError(f"Esos naipes no están en tu mano: {foreign}")
    if not minimum <= len(cards) <= maximum:
        raise InvalidDiscardError(
            f"Hay que descartar entre {minimum} y {maximum} naipes; se han indicado {len(cards)}"
        )


@dataclass(frozen=True, slots=True)
class Served:
    """Resultado de servir los descartes de una ronda de mus."""

    hands: tuple[tuple[Card, ...], ...]
    stock: Deck
    discard_pile: tuple[Card, ...]
    received: tuple[tuple[Card, ...], ...]  # naipes recibidos por asiento
    reshuffles: tuple[Deck, ...]  # barajas formadas al rebarajar el descarte (C.III-15)
    rng: Rng


def serve_discards(
    hands: tuple[tuple[Card, ...], ...],
    stock: Deck,
    discard_pile: tuple[Card, ...],
    discards: tuple[frozenset[Card], ...],
    order: tuple[SeatId, ...],
    rng: Rng,
) -> Served:
    """Retira los descartes y sirve a cada jugador, de una vez, en ``order``.

    Primero todos los descartes pasan al montón (los jugadores se descartan antes de que
    se sirva). Si al servir se acaba el mazo, el montón completo se baraja y forma el
    nuevo mazo (C.III-15, literal "todo el descarte"; D-07).
    """
    kept = [tuple(card for card in hands[p] if card not in discards[p]) for p in range(len(hands))]
    pile = discard_pile + tuple(
        card for p in order for card in sorted_by_hand(hands[p], discards[p])
    )
    received: list[tuple[Card, ...]] = [() for _ in hands]
    reshuffles: list[Deck] = []
    for player in order:
        needed = len(discards[player])
        taken, stock = stock.draw(min(needed, len(stock)))
        if len(taken) < needed:
            stock, rng = Deck(pile).shuffled(rng)
            pile = ()
            reshuffles.append(stock)
            more, stock = stock.draw(needed - len(taken))
            taken += more
        received[player] = taken
        kept[player] = kept[player] + taken
    return Served(tuple(kept), stock, pile, tuple(received), tuple(reshuffles), rng)


def sorted_by_hand(hand: tuple[Card, ...], cards: frozenset[Card]) -> tuple[Card, ...]:
    """Los naipes de ``cards`` en el orden en que están en ``hand`` (determinismo)."""
    return tuple(card for card in hand if card in cards)
