from __future__ import annotations

import random

import pytest

from mus_engine.ai.classes import hand_class, rank_supply, remaining
from mus_engine.ai.counting import Knowledge
from mus_engine.ai.equity import Distribution, distribution, lance_equity, team_equity
from mus_engine.cards.card import Card
from mus_engine.cards.deck import full_deck_cards
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.players.seating import SeatId, distance_from_mano, team_of
from mus_engine.rules.lance import LanceType
from mus_engine.rules.lances import evaluator_for
from mus_engine.rules.signals import Signal

POLICY = RankingPolicy()


def cards(*codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(c) for c in codes)


def knowledge(
    hand: tuple[Card, ...],
    mano: int = 0,
    pares: tuple[bool | None, ...] = (None,) * 4,
    juego: tuple[bool | None, ...] = (None,) * 4,
) -> Knowledge:
    return Knowledge(
        SeatId(0), SeatId(mano), hand, (), remaining(POLICY, hand), pares, juego, ((),) * 4
    )


def simulated(hand: tuple[Card, ...], lance: LanceType, mano: int, n: int, seed: int) -> float:
    """Reparte de verdad y resuelve el lance con el evaluador del motor."""
    rng = random.Random(seed)
    evaluator = evaluator_for(lance, POLICY)
    rest = [c for c in full_deck_cards() if c not in hand]
    wins = 0
    for _ in range(n):
        rng.shuffle(rest)
        hands = [hand, tuple(rest[0:4]), tuple(rest[4:8]), tuple(rest[8:12])]
        strengths = {
            s: hand_class(h).strengths[lance]
            for s, h in enumerate(hands)
            if hand_class(h).strengths[lance] is not None
        }
        if not strengths:
            continue
        best = max(strengths.values())  # type: ignore[type-var]
        tied = [s for s, v in strengths.items() if v == best]
        winner = min(tied, key=lambda s: distance_from_mano(SeatId(s), SeatId(mano)))
        assert evaluator.lance is lance
        wins += team_of(SeatId(winner)) is team_of(SeatId(0))
    return wins / n


@pytest.mark.parametrize(
    ("hand", "lance", "mano"),
    [
        (cards("12O", "4E", "11C", "3C"), LanceType.GRANDE, 0),
        (cards("1B", "6O", "4C", "5C"), LanceType.CHICA, 1),
        (cards("12C", "5B", "2O", "3C"), LanceType.PARES, 2),
        (cards("6O", "5C", "11C", "4O"), LanceType.GRANDE, 3),
        (cards("12O", "11O", "10O", "1O"), LanceType.JUEGO, 0),
    ],
)
def test_exact_equity_matches_dealing_real_hands(
    hand: tuple[Card, ...], lance: LanceType, mano: int
) -> None:
    exact = team_equity(knowledge(hand, mano), lance, POLICY)
    assert exact == pytest.approx(simulated(hand, lance, mano, 3000, seed=1), abs=0.03)


def test_partner_counts() -> None:
    weak = cards("4O", "5C", "6E", "7B")
    team = team_equity(knowledge(weak), LanceType.GRANDE, POLICY)
    alone = lance_equity(hand_class(weak), LanceType.GRANDE, POLICY) ** 2  # a dos rivales
    assert team > 0.25  # casi todo lo gana mi compañero
    assert alone < 0.01


def test_declarations_change_the_odds() -> None:
    hand = cards("12O", "12C", "4E", "5B")  # pareja de reyes
    unknown = team_equity(knowledge(hand), LanceType.PARES, POLICY)
    rivals_have_pares = team_equity(
        knowledge(hand, pares=(True, True, True, True)), LanceType.PARES, POLICY
    )
    rivals_without = team_equity(
        knowledge(hand, pares=(True, False, False, False)), LanceType.PARES, POLICY
    )
    assert rivals_without == pytest.approx(1.0)
    assert rivals_have_pares < unknown < rivals_without


def test_windows_model_strong_and_weak_rivals() -> None:
    hand = cards("12O", "12C", "11E", "5B")
    k = knowledge(hand)
    base = team_equity(k, LanceType.GRANDE, POLICY)
    strong = team_equity(k, LanceType.GRANDE, POLICY, {SeatId(1): lambda d: d.window(0.7, 1.0)})
    weak = team_equity(k, LanceType.GRANDE, POLICY, {SeatId(1): lambda d: d.window(0.0, 0.3)})
    assert strong < base < weak


def test_distribution_window_edge_cases() -> None:
    dist = distribution(LanceType.PARES, rank_supply(POLICY), POLICY)
    assert 0 < dist.none < 1
    assert dist.window(1.0, 1.0) is dist  # tramo vacío: sin cambios
    only_none = dist.window(0.0, dist.none / 2)
    assert only_none.none == pytest.approx(1.0)
    assert only_none.strengths == ()
    top = dist.window(0.9, 1.0)
    assert top.none == 0
    assert sum(top.mass) == pytest.approx(1.0)
    less, equal = top.below((99,))
    assert less == pytest.approx(1.0)
    assert equal == 0.0


def test_impossible_constraints_mean_the_seat_cannot_play() -> None:
    empty = {rank: 0 for rank in rank_supply(POLICY)}
    dist = distribution(LanceType.GRANDE, empty, POLICY)
    assert dist == Distribution((), (), (), 1.0)


def test_solo_equity_of_extremes() -> None:
    best_grande = hand_class(cards("12O", "12C", "12E", "12B"))
    assert lance_equity(best_grande, LanceType.GRANDE, POLICY) > 0.99
    assert lance_equity(best_grande, LanceType.JUEGO, POLICY) > 0.5  # 40
    no_juego = hand_class(cards("1O", "1C", "4E", "5B"))
    assert lance_equity(no_juego, LanceType.JUEGO, POLICY) == 0.0


def seen(seat: int, signal: Signal) -> tuple[frozenset[Signal], ...]:
    return tuple(frozenset({signal}) if s == seat else frozenset() for s in range(4))


def test_seen_signals_change_the_odds() -> None:
    """Fase G: la seña vista del compañero (o de un rival) cambia la probabilidad."""
    from dataclasses import replace

    hand = cards("4O", "5C", "6E", "7B")  # nada: todo depende de mi compañero
    k = knowledge(hand)
    base = team_equity(k, LanceType.PARES, POLICY)
    mate_duples = team_equity(replace(k, signals=seen(2, Signal.DUPLES)), LanceType.PARES, POLICY)
    mate_blind = team_equity(replace(k, signals=seen(2, Signal.CIEGO)), LanceType.PARES, POLICY)
    rival_duples = team_equity(replace(k, signals=seen(1, Signal.DUPLES)), LanceType.PARES, POLICY)
    assert mate_duples > base + 0.1  # 0,31 → 0,49
    assert mate_blind < base
    assert rival_duples < base
    # Una seña nunca anula del todo las manos que no cuadran (puede ser un farol).
    d = distribution(LanceType.PARES, k.available, POLICY, signals=frozenset({Signal.CIEGO}))
    assert 0 < 1 - d.none < 0.5
