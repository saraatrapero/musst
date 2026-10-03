"""Evaluador de cada lance y valor de las jugadas por jugador."""

from __future__ import annotations

from collections.abc import Sequence

from mus_engine.cards.card import Card
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.config import GameConfig
from mus_engine.rules.chica import ChicaEvaluator
from mus_engine.rules.evaluation import LanceEvaluator
from mus_engine.rules.grande import GrandeEvaluator
from mus_engine.rules.juego import JuegoEvaluator, juego_points
from mus_engine.rules.lance import LanceType
from mus_engine.rules.pares import ParesEvaluator, pares_points
from mus_engine.rules.punto import PuntoEvaluator, punto_points

LANCE_ORDER: tuple[LanceType, ...] = (
    LanceType.GRANDE,
    LanceType.CHICA,
    LanceType.PARES,
    LanceType.JUEGO,
    LanceType.PUNTO,
)
"""C.VII-2: grande, chica, pares, juego o punto (juego y punto son excluyentes)."""


def evaluator_for(lance: LanceType, policy: RankingPolicy) -> LanceEvaluator:
    evaluators: dict[LanceType, LanceEvaluator] = {
        LanceType.GRANDE: GrandeEvaluator(policy),
        LanceType.CHICA: ChicaEvaluator(policy),
        LanceType.PARES: ParesEvaluator(policy),
        LanceType.JUEGO: JuegoEvaluator(policy),
        LanceType.PUNTO: PuntoEvaluator(policy),
    }
    return evaluators[lance]


def jugada_points(lance: LanceType, cards: Sequence[Card], config: GameConfig) -> int:
    """Valor propio de la jugada de un jugador en pares o juego (D-02); 0 en otros lances."""
    policy = RankingPolicy.from_config(config)
    if lance is LanceType.PARES:
        return pares_points(ParesEvaluator(policy).classify(cards).category, config)
    if lance is LanceType.JUEGO:
        return juego_points(JuegoEvaluator(policy).classify(cards), config)
    return 0


def lance_value(lance: LanceType, config: GameConfig) -> int:
    """Valor del lance cuando no depende de las jugadas: punto (D-02)."""
    return punto_points(config) if lance is LanceType.PUNTO else 0
