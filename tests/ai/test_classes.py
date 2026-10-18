from __future__ import annotations

from math import comb

from mus_engine.ai.classes import all_classes, hand_class, rank_supply, remaining
from mus_engine.cards.card import Card
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.rules.lance import LanceType

POLICY = RankingPolicy()


def cards(*codes: str) -> list[Card]:
    return [Card.from_code(c) for c in codes]


def test_there_are_330_classes_covering_every_hand() -> None:
    classes = all_classes(POLICY)
    assert len(classes) == 330
    supply = rank_supply(POLICY)
    assert sum(supply.values()) == 40
    assert supply[12] == 8  # ocho reyes
    assert supply[1] == 8  # ocho ases
    assert sum(c.weight(supply) for c in classes) == comb(40, 4)


def test_suits_and_equivalent_ranks_do_not_matter() -> None:
    a = hand_class(cards("12O", "3C", "1E", "2B"))
    b = hand_class(cards("12B", "12C", "1O", "1C"))
    assert a is b
    assert a.ranks == (1, 1, 12, 12)
    assert a.has_pares
    assert not a.has_juego  # 10 + 10 + 1 + 1 = 22
    assert a.strengths[LanceType.JUEGO] is None
    assert a.strengths[LanceType.PUNTO] == (22,)


def test_juego_hands_cannot_play_punto() -> None:
    cls = hand_class(cards("12O", "11O", "10O", "1O"))  # 31
    assert cls.has_juego
    assert cls.strengths[LanceType.PUNTO] is None
    assert cls.strengths[LanceType.PARES] is None


def test_remaining_removes_known_cards() -> None:
    left = remaining(POLICY, cards("12O", "3C", "4E"))
    assert left[12] == 6
    assert left[4] == 3
    assert hand_class(cards("4O", "4C", "4E", "4B")).weight(left) == 0
    assert hand_class(cards("4O", "4C", "4B", "5O")).weight(left) == 1 * 4
