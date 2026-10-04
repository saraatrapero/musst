"""Lance de chica: gana la jugada más baja.

- C.VI-16: en chica los naipes se cantan de menor a mayor; se compara carta a carta en
  ese orden (D-10). Los palos no cuentan.
- C.II-3: en ocho reyes el dos vale como as y el tres como rey.
- C.VI-7: la jugada máxima es cuatro ases.
- Empates: gana el más cercano a la mano (D-09), en ``evaluation.resolve``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import ClassVar

from mus_engine.cards.card import Card
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.rules.evaluation import Strength, check_hand
from mus_engine.rules.lance import LanceType


@dataclass(frozen=True, slots=True)
class ChicaEvaluator:
    policy: RankingPolicy = field(default_factory=RankingPolicy)
    lance: ClassVar[LanceType] = LanceType.CHICA

    def strength(self, cards: Sequence[Card]) -> Strength:
        """Rangos efectivos de menor a mayor, negados para que mayor sea mejor.

        A-A-4-5 → ``(-1, -1, -4, -5)``, que supera a A-4-4-5 → ``(-1, -4, -4, -5)``.
        """
        ranks = sorted(int(self.policy.effective_rank(card)) for card in check_hand(cards))
        return tuple(-rank for rank in ranks)
