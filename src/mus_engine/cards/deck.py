"""Baraja española de 40 naipes (Reglamento FEM C.II-3, C.III-1).

:class:`Deck` es un valor inmutable: una secuencia ordenada de naipes distintos, donde
el primero es el siguiente en robarse. Sirve tanto para la baraja completa como para
el mazo restante durante una jugada.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from mus_engine.cards.card import Card, Rank, Suit
from mus_engine.config import DeckType
from mus_engine.errors import InvalidDeckError
from mus_engine.rng import Rng

SPANISH_40_CARDS: tuple[Card, ...] = tuple(Card(rank, suit) for suit in Suit for rank in Rank)
"""Composición canónica: 4 palos × 10 naipes (1–7, sota, caballo, rey)."""

_SPANISH_40_SET = frozenset(SPANISH_40_CARDS)


def full_deck_cards(deck_type: DeckType = DeckType.SPANISH_40) -> tuple[Card, ...]:
    """Naipes de una baraja completa, en orden canónico."""
    if deck_type is DeckType.SPANISH_40:
        return SPANISH_40_CARDS
    raise InvalidDeckError(f"Tipo de baraja no soportado: {deck_type!r}")  # pragma: no cover


def validate_complete(cards: Iterable[Card], deck_type: DeckType = DeckType.SPANISH_40) -> None:
    """Comprueba que ``cards`` es exactamente una baraja completa, sin duplicados.

    Útil como invariante: manos + mazo + descartes deben formar una baraja completa.
    """
    cards = tuple(cards)
    expected = frozenset(full_deck_cards(deck_type))
    _check_no_duplicates(cards)
    got = frozenset(cards)
    if got != expected:
        missing = sorted(card.code for card in expected - got)
        foreign = sorted(card.code for card in got - expected)
        raise InvalidDeckError(f"Baraja incompleta o ajena. Faltan: {missing}; sobran: {foreign}")


def _check_no_duplicates(cards: tuple[Card, ...]) -> None:
    counts = Counter(cards)
    duplicated = sorted(card.code for card, n in counts.items() if n > 1)
    if duplicated:
        raise InvalidDeckError(f"Naipes duplicados: {duplicated}")


@dataclass(frozen=True, slots=True)
class Deck:
    """Secuencia inmutable de naipes distintos de la baraja española.

    Se valida al construirse: nunca puede existir un ``Deck`` con duplicados o con
    naipes que no pertenezcan a la baraja.
    """

    cards: tuple[Card, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.cards, tuple):
            raise InvalidDeckError("Deck.cards debe ser una tupla")
        for card in self.cards:
            if not isinstance(card, Card):
                raise InvalidDeckError(f"Elemento no es una carta: {card!r}")
            if card not in _SPANISH_40_SET:  # pragma: no cover - Card ya lo garantiza
                raise InvalidDeckError(f"Naipe ajeno a la baraja: {card!r}")
        _check_no_duplicates(self.cards)

    @classmethod
    def standard(cls, deck_type: DeckType = DeckType.SPANISH_40) -> Deck:
        """Baraja completa en orden canónico (sin barajar)."""
        return cls(full_deck_cards(deck_type))

    def shuffled(self, rng: Rng) -> tuple[Deck, Rng]:
        """Devuelve la baraja barajada y el siguiente estado del generador."""
        cards, next_rng = rng.shuffle(self.cards)
        return Deck(cards), next_rng

    def draw(self, count: int) -> tuple[tuple[Card, ...], Deck]:
        """Roba ``count`` naipes de arriba. Lanza :class:`InvalidDeckError` si no hay."""
        if count < 0:
            raise InvalidDeckError(f"No se puede robar un número negativo de naipes: {count}")
        if count > len(self.cards):
            raise InvalidDeckError(f"Se piden {count} naipes y sólo quedan {len(self.cards)}")
        return self.cards[:count], Deck(self.cards[count:])

    def validate_complete(self) -> None:
        """Comprueba que es exactamente la baraja completa de 40."""
        validate_complete(self.cards)

    def __len__(self) -> int:
        return len(self.cards)

    def __iter__(self) -> Iterator[Card]:
        return iter(self.cards)

    def __contains__(self, item: object) -> bool:
        return item in self.cards
