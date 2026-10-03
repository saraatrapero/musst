"""Carta física de la baraja española.

Una :class:`Card` representa el naipe tal y como es (un tres es un tres). Su
equivalencia en el Mus de ocho reyes (el tres cuenta como rey, el dos como as;
Reglamento FEM C.II-3) no vive aquí sino en :class:`mus_engine.cards.ranking.RankingPolicy`,
porque depende de la configuración de la partida.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum

from mus_engine.errors import InvalidCardError


class Suit(Enum):
    """Palos de la baraja española, en el orden del sorteo de C.III-1."""

    OROS = "O"
    COPAS = "C"
    ESPADAS = "E"
    BASTOS = "B"

    @property
    def display_name(self) -> str:
        return _SUIT_NAMES[self]


class Rank(IntEnum):
    """Naipes de la baraja española de 40 (sin ochos ni nueves).

    El valor numérico es el número impreso en el naipe. No es un orden de juego:
    para comparar en grande, chica o juego se usa ``RankingPolicy``.
    """

    AS = 1
    DOS = 2
    TRES = 3
    CUATRO = 4
    CINCO = 5
    SEIS = 6
    SIETE = 7
    SOTA = 10
    CABALLO = 11
    REY = 12

    @property
    def display_name(self) -> str:
        return _RANK_NAMES[self]


_SUIT_NAMES: dict[Suit, str] = {
    Suit.OROS: "Oros",
    Suit.COPAS: "Copas",
    Suit.ESPADAS: "Espadas",
    Suit.BASTOS: "Bastos",
}

_RANK_NAMES: dict[Rank, str] = {
    Rank.AS: "As",
    Rank.DOS: "Dos",
    Rank.TRES: "Tres",
    Rank.CUATRO: "Cuatro",
    Rank.CINCO: "Cinco",
    Rank.SEIS: "Seis",
    Rank.SIETE: "Siete",
    Rank.SOTA: "Sota",
    Rank.CABALLO: "Caballo",
    Rank.REY: "Rey",
}


@dataclass(frozen=True, slots=True)
class Card:
    """Naipe inmutable. Dos cartas son iguales si tienen el mismo rango y palo.

    No define ``<``: el orden de las cartas depende del lance y de la configuración,
    así que compararlas directamente sería un error silencioso.
    """

    rank: Rank
    suit: Suit

    def __post_init__(self) -> None:
        # Protege frente a construcciones como Card(8, Suit.OROS) desde código no tipado.
        if not isinstance(self.rank, Rank):
            raise InvalidCardError(f"Rango inválido: {self.rank!r}")
        if not isinstance(self.suit, Suit):
            raise InvalidCardError(f"Palo inválido: {self.suit!r}")

    @property
    def code(self) -> str:
        """Código corto y estable: número impreso + inicial del palo (``"12O"``, ``"1B"``)."""
        return f"{int(self.rank)}{self.suit.value}"

    @classmethod
    def from_code(cls, code: str) -> Card:
        """Inverso de :attr:`code`. Lanza :class:`InvalidCardError` si no es válido."""
        if len(code) < 2:
            raise InvalidCardError(f"Código de carta inválido: {code!r}")
        number, suit_letter = code[:-1], code[-1]
        try:
            suit = Suit(suit_letter)
            rank = Rank(int(number))
        except ValueError as exc:
            raise InvalidCardError(f"Código de carta inválido: {code!r}") from exc
        return cls(rank, suit)

    def __str__(self) -> str:
        return f"{self.rank.display_name} de {self.suit.display_name}"

    def __repr__(self) -> str:
        return f"Card({self.code})"


def cards_from_codes(codes: str) -> tuple[Card, ...]:
    """Atajo para tests y documentación: ``cards_from_codes("12O 12C 1E 4B")``."""
    return tuple(Card.from_code(code) for code in codes.split())
