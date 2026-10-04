"""Lance de pares.

- R-18 (C.VI-17, C.VIII-2): categorías pares (pareja), medias y duples.
- R-17 (C.VI-7): cuatro naipes iguales cuentan como duples; cuatro reyes es la máxima.
- C.VI-8: la jugada mínima son dos ases.
- C.II-3: en ocho reyes el tres es rey y el dos es as (también para formar pares).
- D-11: entre categorías iguales decide el rango del par o del trío; en duples, el par
  mayor y después el menor. Los naipes sueltos no cuentan.
- D-02: pareja 1 tanto, medias 2, duples 3 (valores en ``GameConfig``).
- Empates: el más cercano a la mano (D-09), en ``evaluation.resolve``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import IntEnum
from typing import ClassVar

from mus_engine.cards.card import Card, Rank
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.config import GameConfig
from mus_engine.rules.evaluation import Strength, check_hand
from mus_engine.rules.lance import LanceType


class ParesCategory(IntEnum):
    """Categorías en orden creciente de valor."""

    NONE = 0
    PAREJA = 1
    MEDIAS = 2
    DUPLES = 3


@dataclass(frozen=True, slots=True)
class ParesHand:
    """Clasificación de una jugada en pares.

    ``ranks`` según la categoría: ``()`` sin pares; ``(par,)`` en pareja; ``(trío,)`` en
    medias; ``(par mayor, par menor)`` en duples (iguales si son cuatro iguales).
    """

    category: ParesCategory
    ranks: tuple[Rank, ...] = ()

    @property
    def has_pares(self) -> bool:
        return self.category is not ParesCategory.NONE


@dataclass(frozen=True, slots=True)
class ParesEvaluator:
    policy: RankingPolicy = field(default_factory=RankingPolicy)
    lance: ClassVar[LanceType] = LanceType.PARES

    def classify(self, cards: Sequence[Card]) -> ParesHand:
        counts = Counter(self.policy.effective_rank(card) for card in check_hand(cards))
        groups = sorted(counts.items(), key=lambda item: (item[1], item[0]), reverse=True)
        (top_rank, top_count), *rest = groups
        if top_count == 4:
            return ParesHand(ParesCategory.DUPLES, (top_rank, top_rank))
        if top_count == 3:
            return ParesHand(ParesCategory.MEDIAS, (top_rank,))
        if top_count == 2:
            second_rank, second_count = rest[0]
            if second_count == 2:
                return ParesHand(ParesCategory.DUPLES, (top_rank, second_rank))
            return ParesHand(ParesCategory.PAREJA, (top_rank,))
        return ParesHand(ParesCategory.NONE)

    def has_pares(self, cards: Sequence[Card]) -> bool:
        return self.classify(cards).has_pares

    def strength(self, cards: Sequence[Card]) -> Strength:
        """``(categoría, rangos...)``: p. ej. duples R-R-A-A → ``(3, 12, 1)``."""
        hand = self.classify(cards)
        return (int(hand.category), *(int(rank) for rank in hand.ranks))


def pares_points(category: ParesCategory, config: GameConfig) -> int:
    """Tantos que vale una jugada de pares (D-02). Sin pares vale 0."""
    return {
        ParesCategory.NONE: 0,
        ParesCategory.PAREJA: config.points_pareja,
        ParesCategory.MEDIAS: config.points_medias,
        ParesCategory.DUPLES: config.points_duples,
    }[category]
