"""Tests de la resolución genérica de lances."""

from collections.abc import Sequence

import pytest

from mus_engine.cards import Card, cards_from_codes
from mus_engine.errors import InvalidCardError
from mus_engine.players import SeatId, TeamId
from mus_engine.rules import LanceType, resolve
from mus_engine.rules.evaluation import check_hand

S0, S1, S2, S3 = map(SeatId, range(4))


class ByFirstCard:
    """Evaluador de prueba: fuerza = número impreso de la primera carta."""

    lance = LanceType.GRANDE

    def strength(self, cards: Sequence[Card]) -> tuple[int, ...]:
        return (int(cards[0].rank),)


def test_highest_strength_wins() -> None:
    hands = {S0: cards_from_codes("5O"), S1: cards_from_codes("7O"), S2: cards_from_codes("6O")}
    result = resolve(ByFirstCard(), hands, mano=S0)
    assert result.winner == S1
    assert result.strength == (7,)
    assert result.tied == (S1,)
    assert not result.decided_by_mano
    assert result.winning_team is TeamId.B
    assert result.lance is LanceType.GRANDE


@pytest.mark.parametrize(("mano", "winner"), [(S0, S0), (S1, S1), (S2, S2), (S3, S3)])
def test_full_tie_goes_to_mano(mano: SeatId, winner: SeatId) -> None:
    hands = {p: cards_from_codes(f"7{s}") for p, s in zip((S0, S1, S2, S3), "OCEB", strict=True)}
    result = resolve(ByFirstCard(), hands, mano=mano)
    assert result.winner == winner
    assert result.decided_by_mano
    assert result.tied[0] == winner
    assert set(result.tied) == {S0, S1, S2, S3}


@pytest.mark.parametrize(("mano", "winner"), [(S0, S1), (S1, S1), (S2, S3), (S3, S3)])
def test_partial_tie_closest_to_mano(mano: SeatId, winner: SeatId) -> None:
    hands = {
        S0: cards_from_codes("5O"),
        S1: cards_from_codes("7O"),
        S2: cards_from_codes("5C"),
        S3: cards_from_codes("7C"),
    }
    assert resolve(ByFirstCard(), hands, mano=mano).winner == winner


def test_result_does_not_depend_on_mapping_order() -> None:
    a = {S3: cards_from_codes("7C"), S1: cards_from_codes("7O")}
    b = {S1: cards_from_codes("7O"), S3: cards_from_codes("7C")}
    assert resolve(ByFirstCard(), a, mano=S2) == resolve(ByFirstCard(), b, mano=S2)


def test_subset_of_players() -> None:
    hands = {S2: cards_from_codes("5O")}
    assert resolve(ByFirstCard(), hands, mano=S0).winner == S2


def test_empty_lance_is_an_error() -> None:
    with pytest.raises(ValueError, match="al menos"):
        resolve(ByFirstCard(), {}, mano=S0)


@pytest.mark.parametrize(
    "cards",
    [
        cards_from_codes("1O 2O 3O"),
        cards_from_codes("1O 2O 3O 4O 5O"),
        cards_from_codes("1O 1O 3O 4O"),
        (*cards_from_codes("1O 2O 3O"), "4O"),
    ],
)
def test_check_hand_rejects_invalid_hands(cards: Sequence[Card]) -> None:
    with pytest.raises(InvalidCardError):
        check_hand(cards)
