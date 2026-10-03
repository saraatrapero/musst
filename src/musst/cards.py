from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Suit(StrEnum):
    OROS = "oros"
    COPAS = "copas"
    ESPADAS = "espadas"
    BASTOS = "bastos"


RANKS_40 = (1, 2, 3, 4, 5, 6, 7, 10, 11, 12)


@dataclass(frozen=True)
class Card:
    suit: Suit
    rank: int


def mus_equivalent_rank(rank: int) -> int:
    """Map ranks to FEM eight-kings/eight-aces equivalence.

    In this modality: 3s count as kings and 2s count as aces.
    """
    if rank == 3:
        return 12
    if rank == 2:
        return 1
    return rank


class SpanishDeck40:
    """Spanish 40-card deck used by Mus."""

    @staticmethod
    def create() -> list[Card]:
        return [Card(suit=suit, rank=rank) for suit in Suit for rank in RANKS_40]
