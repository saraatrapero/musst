"""Resolución genérica de un lance a partir de un evaluador.

Un evaluador asigna a cada jugada una **fuerza**: una tupla de enteros comparable en
la que *mayor es mejor*. Resolver un lance es elegir la fuerza máxima entre los
jugadores que participan y, si hay empate, dar el lance al más cercano a la mano
(D-09). Así el desempate es explícito y nunca depende del orden de los datos.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from mus_engine.cards.card import Card
from mus_engine.errors import InvalidCardError
from mus_engine.players.seating import SeatId, TeamId, closest_to_mano, team_of
from mus_engine.rules.lance import LanceType

Strength = tuple[int, ...]

HAND_SIZE = 4


class LanceEvaluator(Protocol):
    @property
    def lance(self) -> LanceType: ...

    def strength(self, cards: Sequence[Card]) -> Strength:
        """Fuerza de la jugada en este lance (mayor es mejor)."""
        ...


@dataclass(frozen=True, slots=True)
class LanceResult:
    """Ganador de un lance por cartas."""

    lance: LanceType
    winner: SeatId
    strength: Strength
    tied: tuple[SeatId, ...]  # jugadores con la misma fuerza que el ganador (incluido él)

    @property
    def winning_team(self) -> TeamId:
        return team_of(self.winner)

    @property
    def decided_by_mano(self) -> bool:
        """``True`` si hubo empate y lo resolvió la posición respecto a la mano."""
        return len(self.tied) > 1


def check_hand(cards: Sequence[Card]) -> tuple[Card, ...]:
    """Una jugada son exactamente cuatro naipes distintos (Voc. "Jugada")."""
    hand = tuple(cards)
    if len(hand) != HAND_SIZE or len(set(hand)) != HAND_SIZE:
        raise InvalidCardError(f"Una jugada son 4 naipes distintos: {hand!r}")
    if not all(isinstance(card, Card) for card in hand):
        raise InvalidCardError(f"La jugada contiene objetos que no son naipes: {hand!r}")
    return hand


def resolve(
    evaluator: LanceEvaluator,
    hands: Mapping[SeatId, Sequence[Card]],
    mano: SeatId,
) -> LanceResult:
    """Ganador entre los jugadores de ``hands`` (todos o sólo los que van al lance)."""
    if not hands:
        raise ValueError("Un lance necesita al menos un jugador")
    strengths = {player: evaluator.strength(cards) for player, cards in hands.items()}
    best = max(strengths.values())
    tied = tuple(sorted(p for p, s in strengths.items() if s == best))
    winner = closest_to_mano(tied, mano)
    ordered_tied = tuple(sorted(tied, key=lambda p: (p != winner, p)))
    return LanceResult(evaluator.lance, winner, best, ordered_tied)
