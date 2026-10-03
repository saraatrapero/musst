"""Lance de punto: se juega sólo si nadie tiene juego (Voc. "No Juego", D-20).

- Gana el total más alto; la jugada máxima es 30 (C.VI-7).
- D-02: el punto vale 1 tanto.
- Empates: el más cercano a la mano (D-09), en ``evaluation.resolve``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import ClassVar

from mus_engine.cards.card import Card
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.config import GameConfig
from mus_engine.errors import InvalidCardError
from mus_engine.rules.evaluation import Strength, check_hand
from mus_engine.rules.juego import JUEGO_THRESHOLD
from mus_engine.rules.lance import LanceType


@dataclass(frozen=True, slots=True)
class PuntoEvaluator:
    policy: RankingPolicy = field(default_factory=RankingPolicy)
    lance: ClassVar[LanceType] = LanceType.PUNTO

    def total(self, cards: Sequence[Card]) -> int:
        return self.policy.total_game_points(check_hand(cards))

    def strength(self, cards: Sequence[Card]) -> Strength:
        """``(total,)``. Una jugada con juego no puede ir a punto (error)."""
        total = self.total(cards)
        if total >= JUEGO_THRESHOLD:
            raise InvalidCardError(f"Una jugada con juego ({total}) no se juega a punto")
        return (total,)


def punto_points(config: GameConfig) -> int:
    """Tantos que vale ganar el punto (D-02)."""
    return config.points_punto
