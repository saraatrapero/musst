"""Tests de GrandeEvaluator y ChicaEvaluator con tablas de casos."""

import pytest

from mus_engine.cards import RankingPolicy, cards_from_codes
from mus_engine.errors import InvalidCardError
from mus_engine.players import SeatId
from mus_engine.rules import ChicaEvaluator, GrandeEvaluator, LanceType, resolve

GRANDE = GrandeEvaluator()
CHICA = ChicaEvaluator()
NO_EIGHT = RankingPolicy(kings_are_threes=False, aces_are_twos=False)


def g(codes: str) -> tuple[int, ...]:
    return GRANDE.strength(cards_from_codes(codes))


def c(codes: str) -> tuple[int, ...]:
    return CHICA.strength(cards_from_codes(codes))


def test_lance_types() -> None:
    assert GRANDE.lance is LanceType.GRANDE
    assert CHICA.lance is LanceType.CHICA


def test_grande_strength_is_sorted_descending() -> None:
    assert g("1O 12C 5E 11B") == (12, 11, 5, 1)


def test_chica_strength_is_sorted_ascending_negated() -> None:
    assert c("12C 1O 5E 11B") == (-1, -5, -11, -12)


@pytest.mark.parametrize(
    ("better", "worse"),
    [
        ("12O 12C 12E 12B", "12O 12C 12E 11B"),  # cuatro reyes es la máxima
        ("12O 3C 3E 12B", "12C 12E 3O 11B"),  # cuatro "reyes" en ocho reyes
        ("12O 11C 1E 1B", "12C 10E 7O 7B"),  # decide la segunda carta
        ("12O 11C 7E 1B", "12C 11E 6O 4B"),  # decide la tercera
        ("12O 11C 7E 4B", "12C 11E 7O 1B"),  # decide la cuarta
        ("12O 1C 1E 1B", "11O 11C 11E 11B"),  # basta una carta mayor en primera posición
        ("7O 6C 5E 4B", "7C 6E 5O 2B"),  # el dos vale como as
        ("10O 1C 1E 1B", "7O 7C 7E 7B"),
    ],
)
def test_grande_ordering(better: str, worse: str) -> None:
    assert g(better) > g(worse)


@pytest.mark.parametrize(
    ("better", "worse"),
    [
        ("1O 1C 1E 1B", "1O 1C 1E 4B"),  # cuatro ases es la máxima
        ("1O 2C 2E 1B", "1C 1E 2O 4B"),  # cuatro "ases" en ocho reyes
        ("1O 4C 12E 12B", "1C 5E 5O 6B"),  # decide la segunda carta
        ("1O 4C 5E 12B", "1C 4E 6O 6B"),  # decide la tercera
        ("1O 4C 5E 6B", "1C 4E 5O 7B"),  # decide la cuarta
        ("4O 4C 4E 4B", "4O 4C 4E 5B"),  # sin ases, decide la carta más alta
        ("7O 6C 5E 4B", "7C 6E 5O 3B"),  # el tres vale como rey
    ],
)
def test_chica_ordering(better: str, worse: str) -> None:
    assert c(better) > c(worse)


def test_chica_with_ace_beats_any_without() -> None:
    assert c("1O 12C 12E 12B") > c("4O 4C 4E 4B")


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("12O 12C 11E 1B", "3O 12E 11C 2C"),  # 3 = rey, 2 = as
        ("12O 11C 7E 4B", "12E 11E 7C 4C"),  # sólo cambian los palos
        ("1O 1C 1E 1B", "2O 2C 2E 2B"),
    ],
)
def test_equivalent_hands_tie(a: str, b: str) -> None:
    assert g(a) == g(b)
    assert c(a) == c(b)


def test_without_eight_kings_three_and_two_are_themselves() -> None:
    grande = GrandeEvaluator(NO_EIGHT)
    chica = ChicaEvaluator(NO_EIGHT)
    assert grande.strength(cards_from_codes("3O 1C 1E 1B")) == (3, 1, 1, 1)
    assert grande.strength(cards_from_codes("12O 1C 1E 1B")) > grande.strength(
        cards_from_codes("3O 1C 1E 1B")
    )
    assert chica.strength(cards_from_codes("1O 1C 1E 2B")) < chica.strength(
        cards_from_codes("1O 1C 1E 1B")
    )


def test_evaluators_reject_invalid_hands() -> None:
    with pytest.raises(InvalidCardError):
        GRANDE.strength(cards_from_codes("12O 12C 12E"))
    with pytest.raises(InvalidCardError):
        CHICA.strength(cards_from_codes("1O 1O 4E 5E"))


def test_grande_and_chica_winners_in_a_full_table() -> None:
    hands = {
        SeatId(0): cards_from_codes("12O 3C 11E 1B"),
        SeatId(1): cards_from_codes("12C 12E 11O 2C"),
        SeatId(2): cards_from_codes("1O 2O 4C 5C"),
        SeatId(3): cards_from_codes("1C 1E 4E 5E"),
    }
    grande = resolve(GRANDE, hands, mano=SeatId(1))
    assert grande.winner == 1  # empata con 0, pero 1 es mano
    assert set(grande.tied) == {0, 1}
    chica = resolve(CHICA, hands, mano=SeatId(0))
    assert chica.winner == 2  # empata con 3; 2 está más cerca de la mano 0
    chica_mano_3 = resolve(CHICA, hands, mano=SeatId(3))
    assert chica_mano_3.winner == 3
