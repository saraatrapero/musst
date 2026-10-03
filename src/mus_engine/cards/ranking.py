"""Equivalencias de Mus de cada naipe según la modalidad configurada.

- C.II-3: en la modalidad de ocho reyes y ocho ases los treses valen como reyes y los
  doses como ases. Se aplica a **todos** los lances (grande, chica, pares, juego).
- D-01 (decisión aprobada; el reglamento no lo define): para juego y punto las
  figuras valen 10, el as vale 1 y el resto su número impreso.

Los evaluadores de lances (fases 7–10) se construyen sobre :meth:`effective_rank` y
:meth:`game_points`; nunca sobre el rango impreso.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from mus_engine.cards.card import Card, Rank
from mus_engine.config import GameConfig

_FACE_VALUE = 10
_FACE_RANKS = frozenset({Rank.SOTA, Rank.CABALLO, Rank.REY})


@dataclass(frozen=True, slots=True)
class RankingPolicy:
    kings_are_threes: bool = True
    aces_are_twos: bool = True

    @classmethod
    def from_config(cls, config: GameConfig) -> RankingPolicy:
        return cls(kings_are_threes=config.kings_are_threes, aces_are_twos=config.aces_are_twos)

    def effective_rank(self, card: Card) -> Rank:
        """Rango con el que el naipe juega: en ocho reyes 3 → Rey y 2 → As."""
        if self.kings_are_threes and card.rank is Rank.TRES:
            return Rank.REY
        if self.aces_are_twos and card.rank is Rank.DOS:
            return Rank.AS
        return card.rank

    def game_points(self, card: Card) -> int:
        """Valor del naipe para juego y punto (D-01)."""
        rank = self.effective_rank(card)
        if rank in _FACE_RANKS:
            return _FACE_VALUE
        return int(rank)

    def total_game_points(self, cards: Iterable[Card]) -> int:
        """Suma de puntos de una jugada (base de juego y punto)."""
        return sum(self.game_points(card) for card in cards)

    @property
    def playing_ranks(self) -> tuple[Rank, ...]:
        """Rangos efectivos posibles, de menor a mayor (orden de grande)."""
        return tuple(
            rank
            for rank in Rank
            if not (self.kings_are_threes and rank is Rank.TRES)
            and not (self.aces_are_twos and rank is Rank.DOS)
        )
