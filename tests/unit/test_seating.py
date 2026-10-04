"""Tests unitarios del orden de la mesa."""

import pytest

from mus_engine.cards import Suit
from mus_engine.errors import InvalidPlayerError
from mus_engine.players import (
    ALL_SEATS,
    SeatId,
    TeamId,
    are_teammates,
    closest_to_mano,
    cutter_for,
    deal_order,
    dealer_for_mano,
    discard_order,
    distance_from_mano,
    eligible_in_order,
    first_dealer_by_suit,
    is_mano,
    is_postre,
    lance_mano,
    lance_postre,
    mano_for_dealer,
    mus_order,
    next_dealer,
    next_player,
    opponent,
    order_from,
    partner,
    previous_player,
    seat,
    team_of,
    team_seats,
)

S0, S1, S2, S3 = (SeatId(i) for i in range(4))


@pytest.mark.parametrize("value", [-1, 4, 10, "0", 1.0, None, True, False])
def test_seat_rejects_invalid_ids(value: object) -> None:
    with pytest.raises(InvalidPlayerError):
        seat(value)


@pytest.mark.parametrize("value", [0, 1, 2, 3])
def test_seat_accepts_valid_ids(value: int) -> None:
    assert seat(value) == value


def test_next_and_previous_cycle() -> None:
    assert [next_player(s) for s in ALL_SEATS] == [1, 2, 3, 0]
    assert [previous_player(s) for s in ALL_SEATS] == [3, 0, 1, 2]


@pytest.mark.parametrize("s", ALL_SEATS)
def test_next_and_previous_are_inverse(s: SeatId) -> None:
    assert previous_player(next_player(s)) == s
    assert next_player(previous_player(s)) == s


def test_four_steps_return_to_start() -> None:
    s = S2
    for _ in range(4):
        s = next_player(s)
    assert s == S2


def test_partners_sit_opposite() -> None:
    assert [partner(s) for s in ALL_SEATS] == [2, 3, 0, 1]
    for s in ALL_SEATS:
        assert partner(partner(s)) == s
        assert partner(s) != s


def test_teams() -> None:
    assert team_of(S0) is team_of(S2) is TeamId.A
    assert team_of(S1) is team_of(S3) is TeamId.B
    assert team_seats(TeamId.A) == (0, 2)
    assert team_seats(TeamId.B) == (1, 3)
    assert opponent(TeamId.A) is TeamId.B
    assert opponent(TeamId.B) is TeamId.A


def test_are_teammates() -> None:
    assert are_teammates(S0, S2)
    assert are_teammates(S1, S3)
    assert are_teammates(S0, S0)
    assert not are_teammates(S0, S1)
    assert not are_teammates(S0, S3)
    assert not are_teammates(S2, S1)


def test_consecutive_speakers_are_always_rivals() -> None:
    for s in ALL_SEATS:
        assert not are_teammates(s, next_player(s))


def test_teammate_functions_validate_input() -> None:
    with pytest.raises(InvalidPlayerError):
        are_teammates(S0, SeatId(7))
    with pytest.raises(InvalidPlayerError):
        next_player(SeatId(-1))


def test_mano_and_dealer() -> None:
    for dealer in ALL_SEATS:
        mano = mano_for_dealer(dealer)
        assert mano == next_player(dealer)
        assert dealer_for_mano(mano) == dealer
        assert is_postre(dealer, mano)
        assert is_mano(mano, mano)
        assert not is_mano(dealer, mano)


def test_next_dealer_is_current_mano() -> None:
    for dealer in ALL_SEATS:
        assert next_dealer(dealer) == mano_for_dealer(dealer)


def test_mano_rotates_through_all_seats() -> None:
    dealer = S3
    manos = []
    for _ in range(4):
        manos.append(mano_for_dealer(dealer))
        dealer = next_dealer(dealer)
    assert sorted(manos) == [0, 1, 2, 3]
    assert manos == [0, 1, 2, 3]


def test_order_from() -> None:
    assert order_from(S0) == (0, 1, 2, 3)
    assert order_from(S2) == (2, 3, 0, 1)


def test_distance_from_mano() -> None:
    assert [distance_from_mano(s, S1) for s in ALL_SEATS] == [3, 0, 1, 2]


def test_closest_to_mano() -> None:
    assert closest_to_mano([S3, S1], mano=S2) == S3
    assert closest_to_mano([S0, S1, S2, S3], mano=S2) == S2
    assert closest_to_mano([S1], mano=S2) == S1
    with pytest.raises(ValueError, match="al menos"):
        closest_to_mano([], mano=S0)


def test_eligible_in_order_and_lance_mano() -> None:
    assert eligible_in_order(S2, [S0, S1]) == (0, 1)
    assert eligible_in_order(S1, [S0, S3]) == (3, 0)
    assert lance_mano(S1, [S0, S3]) == S3
    assert lance_postre(S1, [S0, S3]) == S0
    assert lance_mano(S1, []) is None
    assert lance_postre(S1, []) is None


def test_mus_order_starts_with_mano() -> None:
    assert mus_order(S3) == (3, 0, 1, 2)


def test_deal_order_starts_with_mano() -> None:
    assert deal_order(dealer=S0) == (1, 2, 3, 0)


def test_discard_order_starts_with_dealer_and_ends_with_mano() -> None:
    mano = S1
    order = discard_order(mano)
    assert order == (0, 3, 2, 1)
    assert order[0] == dealer_for_mano(mano)
    assert order[-1] == mano


def test_cutter_is_left_of_shuffler() -> None:
    assert cutter_for(S0) == S3
    assert cutter_for(S2) == S1


@pytest.mark.parametrize(
    ("suit", "expected"),
    [(Suit.OROS, 1), (Suit.COPAS, 2), (Suit.ESPADAS, 3), (Suit.BASTOS, 0)],
)
def test_first_dealer_by_suit_from_cutter_0(suit: Suit, expected: int) -> None:
    assert first_dealer_by_suit(S0, suit) == expected


def test_first_dealer_by_suit_covers_every_seat() -> None:
    for cutter in ALL_SEATS:
        assert {first_dealer_by_suit(cutter, suit) for suit in Suit} == set(ALL_SEATS)
