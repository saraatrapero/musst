"""Propiedades del orden de la mesa."""

import itertools

from hypothesis import given
from hypothesis import strategies as st

from mus_engine.players import (
    ALL_SEATS,
    SeatId,
    are_teammates,
    closest_to_mano,
    discard_order,
    distance_from_mano,
    mus_order,
    order_from,
)

seats = st.sampled_from(ALL_SEATS)


@given(seats)
def test_orders_are_permutations(mano: SeatId) -> None:
    for order in (order_from(mano), mus_order(mano), discard_order(mano)):
        assert sorted(order) == list(ALL_SEATS)


@given(seats)
def test_orders_alternate_teams(mano: SeatId) -> None:
    order = order_from(mano)
    for a, b in itertools.pairwise(order):
        assert not are_teammates(a, b)


@given(seats, st.sets(seats, min_size=1))
def test_closest_to_mano_minimises_distance(mano: SeatId, group: set[SeatId]) -> None:
    winner = closest_to_mano(group, mano)
    assert winner in group
    assert all(distance_from_mano(winner, mano) <= distance_from_mano(p, mano) for p in group)


@given(seats)
def test_distances_are_unique(mano: SeatId) -> None:
    assert sorted(distance_from_mano(s, mano) for s in ALL_SEATS) == [0, 1, 2, 3]
