"""Tests de eventos y visibilidad."""

import dataclasses

import pytest

from mus_engine.cards import cards_from_codes
from mus_engine.events import (
    CardsDealt,
    Emission,
    EventEnvelope,
    PhaseChanged,
    RngSeeded,
    Visibility,
)
from mus_engine.players import SeatId

S0, S1 = SeatId(0), SeatId(1)


def test_public_event_is_visible_to_everyone() -> None:
    env = EventEnvelope(0, 0, Visibility.PUBLIC, PhaseChanged("deal"))
    assert all(env.visible_to(SeatId(i)) for i in range(4))


def test_private_event_only_to_audience() -> None:
    env = EventEnvelope(0, 1, Visibility.PRIVATE, CardsDealt(S0, cards_from_codes("1O")), S0)
    assert env.visible_to(S0)
    assert not env.visible_to(S1)


def test_engine_event_is_visible_to_nobody() -> None:
    env = EventEnvelope(0, 0, Visibility.ENGINE, RngSeeded(1))
    assert not any(env.visible_to(SeatId(i)) for i in range(4))


@pytest.mark.parametrize(
    ("visibility", "audience"),
    [(Visibility.PRIVATE, None), (Visibility.PUBLIC, S0), (Visibility.ENGINE, S1)],
)
def test_audience_consistency(visibility: Visibility, audience: SeatId | None) -> None:
    with pytest.raises(ValueError, match="audiencia"):
        EventEnvelope(0, 0, visibility, PhaseChanged("x"), audience)


def test_emission_constructors() -> None:
    event = PhaseChanged("x")
    assert Emission.public(event) == Emission(event, Visibility.PUBLIC, None)
    assert Emission.private(S1, event) == Emission(event, Visibility.PRIVATE, S1)
    assert Emission.engine(event) == Emission(event, Visibility.ENGINE, None)


def test_events_are_immutable() -> None:
    event = CardsDealt(S0, cards_from_codes("1O 2O"))
    with pytest.raises(dataclasses.FrozenInstanceError):
        event.cards = ()  # type: ignore[misc]
