"""Lance de juego.

- Voc. "No Juego": hay juego si los cuatro naipes suman 31 o más (R-15).
- D-01: figuras (y treses en ocho reyes) valen 10; ases (y doses) 1; resto su número.
- D-08: orden 31 > 32 > 40 > 39 > 38 > 37 > 36 > 35 > 34 > 33. El reglamento sólo fija
  los extremos: 31 es la jugada máxima (C.VI-7) y 33 la mínima (C.VI-8, C.VI-9).
- D-02: el juego de 31 vale 3 tantos; cualquier otro juego, 2.
- Empates: el más cercano a la mano (D-09), en ``evaluation.resolve``.

Se separan explícitamente *tener juego* (:attr:`JuegoHand.has_juego`) y *qué juego*
(:attr:`JuegoHand.total`, su posición en :data:`JUEGO_ORDER`).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import ClassVar

from mus_engine.cards.card import Card
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.config import GameConfig
from mus_engine.rules.evaluation import Strength, check_hand
from mus_engine.rules.lance import LanceType

JUEGO_THRESHOLD = 31
JUEGO_ORDER: tuple[int, ...] = (31, 32, 40, 39, 38, 37, 36, 35, 34, 33)
"""Totales con juego, del mejor al peor (D-08). 38 y 39 figuran por completitud, pero
no se pueden dar con la baraja española (tres naipes de 10 suman 30 y no hay naipe de
8 ni de 9)."""


@dataclass(frozen=True, slots=True)
class JuegoHand:
    """Total de puntos de una jugada (base común de juego y punto)."""

    total: int

    @property
    def has_juego(self) -> bool:
        return self.total >= JUEGO_THRESHOLD

    @property
    def juego_rank(self) -> int | None:
        """Posición en :data:`JUEGO_ORDER` (0 = 31, la mejor) o ``None`` sin juego."""
        return JUEGO_ORDER.index(self.total) if self.has_juego else None


@dataclass(frozen=True, slots=True)
class JuegoEvaluator:
    policy: RankingPolicy = field(default_factory=RankingPolicy)
    lance: ClassVar[LanceType] = LanceType.JUEGO

    def classify(self, cards: Sequence[Card]) -> JuegoHand:
        return JuegoHand(self.policy.total_game_points(check_hand(cards)))

    def has_juego(self, cards: Sequence[Card]) -> bool:
        return self.classify(cards).has_juego

    def strength(self, cards: Sequence[Card]) -> Strength:
        """``(10 - posición,)`` con juego (31 → 10, 33 → 1); ``(0,)`` sin juego."""
        rank = self.classify(cards).juego_rank
        return (0,) if rank is None else (len(JUEGO_ORDER) - rank,)


def juego_points(hand: JuegoHand, config: GameConfig) -> int:
    """Tantos que vale una jugada en el lance de juego (D-02). Sin juego vale 0."""
    if not hand.has_juego:
        return 0
    if hand.total == JUEGO_THRESHOLD:
        return config.points_juego_31
    return config.points_juego_other


def juego_or_punto(hands: Iterable[Sequence[Card]], evaluator: JuegoEvaluator) -> LanceType:
    """Si algún jugador tiene juego se juega juego; si no, punto (Voc. "No Juego", D-20)."""
    if any(evaluator.has_juego(cards) for cards in hands):
        return LanceType.JUEGO
    return LanceType.PUNTO
