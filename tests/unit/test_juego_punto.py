"""Tests de JuegoEvaluator y PuntoEvaluator."""

import pytest

from mus_engine import GameConfig
from mus_engine.cards import RankingPolicy, cards_from_codes
from mus_engine.errors import InvalidCardError
from mus_engine.players import SeatId
from mus_engine.rules import (
    JUEGO_ORDER,
    JuegoEvaluator,
    JuegoHand,
    LanceType,
    PuntoEvaluator,
    juego_or_punto,
    juego_points,
    punto_points,
    resolve,
)

JUEGO = JuegoEvaluator()
PUNTO = PuntoEvaluator()


def total(codes: str) -> int:
    return JUEGO.classify(cards_from_codes(codes)).total


def js(codes: str) -> tuple[int, ...]:
    return JUEGO.strength(cards_from_codes(codes))


def ps(codes: str) -> tuple[int, ...]:
    return PUNTO.strength(cards_from_codes(codes))


def test_lance_types() -> None:
    assert JUEGO.lance is LanceType.JUEGO
    assert PUNTO.lance is LanceType.PUNTO


@pytest.mark.parametrize(
    ("codes", "expected"),
    [
        ("12O 12C 12E 1B", 31),
        ("3O 11C 10E 1B", 31),  # el tres vale 10
        ("7O 7C 7E 10B", 31),  # sin trato especial ("31 real")
        ("12O 12C 12E 2B", 31),  # el dos vale 1
        ("12O 11C 5E 7B", 32),
        ("12O 12C 12E 12B", 40),
        ("12O 11C 10E 4B", 34),
        ("12O 11C 7E 6B", 33),
        ("12O 11C 5E 5B", 30),
        ("1O 2C 1E 2B", 4),
        ("7O 6C 5E 4B", 22),
    ],
)
def test_totals(codes: str, expected: int) -> None:
    assert total(codes) == expected
    assert PUNTO.total(cards_from_codes(codes)) == expected


def test_has_juego_boundary() -> None:
    assert not JuegoHand(30).has_juego
    assert JuegoHand(31).has_juego
    assert JuegoHand(40).has_juego
    assert JUEGO.has_juego(cards_from_codes("12O 12C 12E 1B"))
    assert not JUEGO.has_juego(cards_from_codes("12O 11C 5E 5B"))


def test_juego_rank() -> None:
    assert JuegoHand(31).juego_rank == 0
    assert JuegoHand(32).juego_rank == 1
    assert JuegoHand(40).juego_rank == 2
    assert JuegoHand(33).juego_rank == 9
    assert JuegoHand(30).juego_rank is None


def test_juego_order_is_complete() -> None:
    assert sorted(JUEGO_ORDER) == list(range(31, 41))
    assert JUEGO_ORDER[0] == 31
    assert JUEGO_ORDER[-1] == 33


@pytest.mark.parametrize(
    ("better", "worse"),
    [
        ("12O 12C 10E 1B", "12O 11C 5E 7B"),  # 31 > 32
        ("12O 11C 5E 7B", "12E 12B 11E 10O"),  # 32 > 40
        ("12O 12C 12E 12B", "12E 11B 10E 7O"),  # 40 > 37
        ("12E 11B 10E 7O", "12O 11C 10E 4B"),  # 37 > 34
        ("12O 11C 10E 4B", "12O 11C 7E 6B"),  # 34 > 33
        ("12O 11C 7E 6B", "12O 11C 5E 5B"),  # 33 (juego) > 30 (sin juego)
    ],
)
def test_juego_ordering(better: str, worse: str) -> None:
    assert js(better) > js(worse)


def test_juego_strengths_follow_order() -> None:
    strengths = [(len(JUEGO_ORDER) - i,) for i in range(len(JUEGO_ORDER))]
    assert strengths == sorted(strengths, reverse=True)
    assert js("12O 11C 5E 5B") == (0,)


def test_juego_tie_resolved_by_mano() -> None:
    hands = {
        SeatId(1): cards_from_codes("12O 12C 12E 1B"),
        SeatId(3): cards_from_codes("7O 7C 7E 10B"),
    }
    assert js("12O 12C 12E 1B") == js("7O 7C 7E 10B")
    assert resolve(JUEGO, hands, mano=SeatId(0)).winner == 1
    assert resolve(JUEGO, hands, mano=SeatId(2)).winner == 3


@pytest.mark.parametrize(
    ("hand", "points"),
    [
        (JuegoHand(31), 3),
        (JuegoHand(32), 2),
        (JuegoHand(40), 2),
        (JuegoHand(33), 2),
        (JuegoHand(30), 0),
    ],
)
def test_juego_points(hand: JuegoHand, points: int) -> None:
    assert juego_points(hand, GameConfig()) == points


def test_juego_points_follow_config() -> None:
    config = GameConfig(points_juego_31=5, points_juego_other=4)
    assert juego_points(JuegoHand(31), config) == 5
    assert juego_points(JuegoHand(35), config) == 4


@pytest.mark.parametrize(
    ("better", "worse"),
    [
        ("12O 11C 5E 5B", "12O 11C 5E 4B"),  # 30 > 29
        ("12O 11C 4E 5B", "7O 6C 5E 4B"),  # 29 > 22
        ("4O 1C 1E 1B", "1O 2C 1E 2B"),  # 7 > 4
    ],
)
def test_punto_ordering(better: str, worse: str) -> None:
    assert ps(better) > ps(worse)


def test_punto_tie_resolved_by_mano() -> None:
    hands = {
        SeatId(0): cards_from_codes("12O 11C 5E 5B"),
        SeatId(2): cards_from_codes("3O 10C 6E 4B"),
    }
    assert ps("12O 11C 5E 5B") == ps("3O 10C 6E 4B") == (30,)
    assert resolve(PUNTO, hands, mano=SeatId(1)).winner == 2
    assert resolve(PUNTO, hands, mano=SeatId(3)).winner == 0


def test_punto_rejects_hands_with_juego() -> None:
    with pytest.raises(InvalidCardError, match="punto"):
        PUNTO.strength(cards_from_codes("12O 12C 12E 1B"))


def test_punto_points() -> None:
    assert punto_points(GameConfig()) == 1
    assert punto_points(GameConfig(points_punto=2)) == 2


def test_juego_or_punto() -> None:
    no_juego = [cards_from_codes("12O 11C 5E 5B"), cards_from_codes("7O 6C 5E 4B")]
    assert juego_or_punto(no_juego, JUEGO) is LanceType.PUNTO
    assert juego_or_punto([*no_juego, cards_from_codes("12O 11C 7E 6B")], JUEGO) is LanceType.JUEGO


def test_without_eight_kings_threes_and_twos_count_as_printed() -> None:
    evaluator = JuegoEvaluator(RankingPolicy(kings_are_threes=False, aces_are_twos=False))
    assert evaluator.classify(cards_from_codes("3O 12C 12E 2B")).total == 25
    assert evaluator.classify(cards_from_codes("3O 3C 12E 12B")).total == 26


def test_invalid_hands() -> None:
    with pytest.raises(InvalidCardError):
        JUEGO.classify(cards_from_codes("12O 12C 12E"))
    with pytest.raises(InvalidCardError):
        PUNTO.strength(cards_from_codes("12O 12O 1E 1B"))
