"""Lance de grande: gana la jugada más alta.

- C.VI-16: en grande los naipes se cantan de mayor a menor; se compara carta a carta
  en ese orden (D-10). Los palos no cuentan.
- C.II-3: en ocho reyes el tres vale como rey y el dos como as.
- C.VI-7: la jugada máxima es cuatro reyes.
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
class GrandeEvaluator:
    policy: RankingPolicy = field(default_factory=RankingPolicy)
    lance: ClassVar[LanceType] = LanceType.GRANDE

    def strength(self, cards: Sequence[Card]) -> Strength:
        """Rangos efectivos de mayor a menor: ``(12, 12, 11, 1)`` para R-R-C-A."""
        ranks = (int(self.policy.effective_rank(card)) for card in check_hand(cards))
        return tuple(sorted(ranks, reverse=True))
