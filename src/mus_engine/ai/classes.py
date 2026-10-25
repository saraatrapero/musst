"""Clases de mano: lo único que importa de una mano para el Mus.

Todos los lances (grande, chica, pares, juego y punto) dependen sólo del **rango
efectivo** de cada naipe (en ocho reyes el 3 juega como rey y el 2 como as); el palo no
importa nunca. Con la baraja de 40 hay 8 rangos efectivos y sólo **330 clases** de mano
(multiconjuntos de 4 rangos), frente a 91.390 manos concretas. Por eso se puede
calcular de forma **exacta** la probabilidad de cada mano rival, sin simular.

>>> from mus_engine.cards.card import Card
>>> hand_class([Card.from_code(c) for c in ("12O", "3C", "1E", "2B")]).ranks
(1, 1, 12, 12)
>>> len(all_classes(RankingPolicy()))
330
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from itertools import combinations_with_replacement
from math import comb

from mus_engine.cards.card import Card
from mus_engine.cards.deck import full_deck_cards
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.rules.evaluation import Strength
from mus_engine.rules.juego import JUEGO_THRESHOLD, JuegoEvaluator
from mus_engine.rules.lance import LanceType
from mus_engine.rules.lances import evaluator_for
from mus_engine.rules.pares import ParesEvaluator
from mus_engine.rules.signals import Signal, true_signals

HAND_SIZE = 4


@dataclass(frozen=True, slots=True)
class HandClass:
    """Una clase de mano: sus 4 rangos efectivos, de menor a mayor."""

    ranks: tuple[int, ...]
    has_pares: bool
    has_juego: bool
    strengths: Mapping[LanceType, Strength | None]  # None: no puede jugar ese lance
    signals: frozenset[Signal] = frozenset()  # señas que describen con verdad esta mano

    def counts(self) -> Counter[int]:
        return Counter(self.ranks)

    def weight(self, available: Mapping[int, int]) -> int:
        """Cuántas manos concretas de esta clase se pueden formar con ``available``."""
        total = 1
        for rank, needed in self.counts().items():
            total *= comb(available.get(rank, 0), needed)
        return total


def hand_class(cards: Sequence[Card], policy: RankingPolicy | None = None) -> HandClass:
    policy = policy or RankingPolicy()
    ranks = tuple(sorted(int(policy.effective_rank(c)) for c in cards))
    return classes_by_ranks(policy)[ranks]


def rank_supply(policy: RankingPolicy) -> dict[int, int]:
    """Naipes de cada rango efectivo en la baraja completa (8 reyes y 8 ases)."""
    return dict(Counter(int(policy.effective_rank(c)) for c in full_deck_cards()))


def remaining(policy: RankingPolicy, known: Iterable[Card]) -> dict[int, int]:
    """Naipes de cada rango que pueden estar en manos ajenas, quitando ``known``."""
    supply = rank_supply(policy)
    for card in known:
        supply[int(policy.effective_rank(card))] -= 1
    return supply


@cache
def all_classes(policy: RankingPolicy) -> tuple[HandClass, ...]:
    return tuple(classes_by_ranks(policy).values())


@cache
def classes_by_ranks(policy: RankingPolicy) -> dict[tuple[int, ...], HandClass]:
    by_rank: dict[int, list[Card]] = {}
    for card in full_deck_cards():
        by_rank.setdefault(int(policy.effective_rank(card)), []).append(card)
    pares = ParesEvaluator(policy)
    juego = JuegoEvaluator(policy)
    found: dict[tuple[int, ...], HandClass] = {}
    for ranks in combinations_with_replacement(sorted(by_rank), HAND_SIZE):
        used: Counter[int] = Counter()
        cards: list[Card] = []
        for rank in ranks:
            cards.append(by_rank[rank][used[rank]])
            used[rank] += 1
        has_pares = pares.has_pares(cards)
        total = juego.classify(cards).total
        has_juego = total >= JUEGO_THRESHOLD
        strengths: dict[LanceType, Strength | None] = {
            LanceType.GRANDE: evaluator_for(LanceType.GRANDE, policy).strength(cards),
            LanceType.CHICA: evaluator_for(LanceType.CHICA, policy).strength(cards),
            LanceType.PARES: pares.strength(cards) if has_pares else None,
            LanceType.JUEGO: juego.strength(cards) if has_juego else None,
            LanceType.PUNTO: (
                None if has_juego else evaluator_for(LanceType.PUNTO, policy).strength(cards)
            ),
        }
        found[ranks] = HandClass(
            ranks, has_pares, has_juego, strengths, true_signals(cards, policy)
        )
    return found
