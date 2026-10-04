"""Tests de ParesEvaluator: categorías, comparación y valor."""

import pytest

from mus_engine import GameConfig
from mus_engine.cards import Rank, RankingPolicy, cards_from_codes
from mus_engine.errors import InvalidCardError
from mus_engine.players import SeatId
from mus_engine.rules import (
    LanceType,
    ParesCategory,
    ParesEvaluator,
    ParesHand,
    pares_points,
    resolve,
)

PARES = ParesEvaluator()
NO_EIGHT = ParesEvaluator(RankingPolicy(kings_are_threes=False, aces_are_twos=False))


def cls(codes: str) -> ParesHand:
    return PARES.classify(cards_from_codes(codes))


def st(codes: str) -> tuple[int, ...]:
    return PARES.strength(cards_from_codes(codes))


def test_lance_type() -> None:
    assert PARES.lance is LanceType.PARES


@pytest.mark.parametrize(
    ("codes", "expected"),
    [
        # Sin pares
        ("12O 11C 10E 7B", ParesHand(ParesCategory.NONE)),
        ("1O 4C 5E 6B", ParesHand(ParesCategory.NONE)),
        ("3O 11C 2E 7B", ParesHand(ParesCategory.NONE)),
        # Pareja
        ("7O 7C 6E 5B", ParesHand(ParesCategory.PAREJA, (Rank.SIETE,))),
        ("12O 3C 6E 5B", ParesHand(ParesCategory.PAREJA, (Rank.REY,))),  # 3 = rey
        ("1O 2C 6E 5B", ParesHand(ParesCategory.PAREJA, (Rank.AS,))),  # 2 = as
        ("10O 10C 1E 12B", ParesHand(ParesCategory.PAREJA, (Rank.SOTA,))),
        # Medias
        ("12O 3C 12E 1B", ParesHand(ParesCategory.MEDIAS, (Rank.REY,))),
        ("4O 4C 4E 12B", ParesHand(ParesCategory.MEDIAS, (Rank.CUATRO,))),
        ("2O 1C 2E 7B", ParesHand(ParesCategory.MEDIAS, (Rank.AS,))),
        # Duples
        ("12O 3C 1E 2B", ParesHand(ParesCategory.DUPLES, (Rank.REY, Rank.AS))),
        ("12O 3C 11E 11B", ParesHand(ParesCategory.DUPLES, (Rank.REY, Rank.CABALLO))),
        ("5O 5C 4E 4B", ParesHand(ParesCategory.DUPLES, (Rank.CINCO, Rank.CUATRO))),
        ("12O 12C 3E 3B", ParesHand(ParesCategory.DUPLES, (Rank.REY, Rank.REY))),  # cuatro reyes
        ("6O 6C 6E 6B", ParesHand(ParesCategory.DUPLES, (Rank.SEIS, Rank.SEIS))),  # cuatro iguales
    ],
)
def test_classification(codes: str, expected: ParesHand) -> None:
    assert cls(codes) == expected
    assert PARES.has_pares(cards_from_codes(codes)) == expected.has_pares


def test_without_eight_kings_three_and_king_do_not_pair() -> None:
    assert NO_EIGHT.classify(cards_from_codes("12O 3C 6E 5B")).category is ParesCategory.NONE
    assert NO_EIGHT.classify(cards_from_codes("3O 3C 6E 5B")).ranks == (Rank.TRES,)


@pytest.mark.parametrize(
    ("better", "worse"),
    [
        # Entre categorías
        ("1O 2C 4E 4B", "12O 12C 12E 11B"),  # duples (los peores) > medias (las mejores)
        ("4O 4C 4E 5B", "12O 3C 11E 7B"),  # medias > pareja
        ("1O 2C 4E 5B", "12O 11C 10E 7B"),  # pareja (la peor) > sin pares
        # Dentro de pareja
        ("12O 3C 4E 5B", "11O 11C 4E 5B"),
        ("4O 4C 1E 5B", "1O 2C 4E 5B"),  # dos ases es la peor pareja
        # Dentro de medias
        ("12O 12C 3E 1B", "11O 11C 11E 12B"),
        ("4O 4C 4E 1B", "2O 1C 1E 12B"),
        # Dentro de duples: par mayor y luego par menor
        ("12O 12C 1E 1B", "11O 11C 10E 10B"),
        ("12O 12C 4E 4B", "12E 3B 1O 1C"),
        ("12O 12C 3E 3B", "12O 12C 11E 11B"),  # cuatro reyes es lo máximo
        ("7O 7C 7E 7B", "7O 7C 6E 6B"),
        ("11O 11C 1E 1B", "10O 10C 10E 10B"),  # par mayor manda sobre cuatro iguales menores
    ],
)
def test_ordering(better: str, worse: str) -> None:
    assert st(better) > st(worse)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("12O 12C 4E 5B", "3O 12E 7C 6B"),  # la pareja empata; los sueltos no cuentan
        ("7O 7C 7E 1B", "7B 7O 7E 12C"),  # medias iguales
        ("12O 3C 1E 2B", "12C 3B 2E 1O"),  # duples iguales
        ("12O 11C 10E 7B", "1O 4C 5E 6B"),  # sin pares empatan entre sí
    ],
)
def test_ties(a: str, b: str) -> None:
    assert st(a) == st(b)


def test_tie_resolved_by_mano() -> None:
    hands = {
        SeatId(0): cards_from_codes("12O 12C 4E 5B"),
        SeatId(1): cards_from_codes("3O 3C 7C 6B"),
    }
    assert resolve(PARES, hands, mano=SeatId(0)).winner == 0
    assert resolve(PARES, hands, mano=SeatId(1)).winner == 1
    assert resolve(PARES, hands, mano=SeatId(3)).winner == 0


@pytest.mark.parametrize(
    ("category", "points"),
    [
        (ParesCategory.NONE, 0),
        (ParesCategory.PAREJA, 1),
        (ParesCategory.MEDIAS, 2),
        (ParesCategory.DUPLES, 3),
    ],
)
def test_points_default(category: ParesCategory, points: int) -> None:
    assert pares_points(category, GameConfig()) == points


def test_points_follow_config() -> None:
    config = GameConfig(points_pareja=2, points_medias=4, points_duples=6)
    assert pares_points(ParesCategory.DUPLES, config) == 6


def test_invalid_hand() -> None:
    with pytest.raises(InvalidCardError):
        PARES.classify(cards_from_codes("12O 12C 4E"))
