"""Tests de las acciones tipadas."""

import dataclasses

import pytest

from mus_engine import (
    AcceptAction,
    BetAction,
    CutMusAction,
    DiscardAction,
    MusAction,
    OrdagoAction,
    PassAction,
    RaiseAction,
    RejectAction,
)
from mus_engine.cards import cards_from_codes
from mus_engine.errors import InvalidBetError, InvalidDiscardError


def test_simple_actions_are_value_objects() -> None:
    for cls in (MusAction, CutMusAction, PassAction, AcceptAction, RejectAction, OrdagoAction):
        assert cls() == cls()
        assert hash(cls()) == hash(cls())


def test_different_action_types_are_not_equal() -> None:
    assert AcceptAction() != RejectAction()  # type: ignore[comparison-overlap]
    assert MusAction() != CutMusAction()  # type: ignore[comparison-overlap]


def test_bet_amounts() -> None:
    assert BetAction(2).amount == 2
    assert RaiseAction(5) == RaiseAction(5)
    assert BetAction(2) != RaiseAction(2)  # type: ignore[comparison-overlap]


@pytest.mark.parametrize("amount", [0, -2, True, 2.0, "2", None])
@pytest.mark.parametrize("cls", [BetAction, RaiseAction])
def test_invalid_bet_amounts(cls: type, amount: object) -> None:
    with pytest.raises(InvalidBetError):
        cls(amount)


def test_actions_are_immutable() -> None:
    bet = BetAction(2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        bet.amount = 40  # type: ignore[misc]


def test_discard_action_normalises_to_frozenset() -> None:
    cards = cards_from_codes("12O 1B")
    action = DiscardAction(list(cards))
    assert action.cards == frozenset(cards)
    assert action == DiscardAction(reversed(cards))
    with pytest.raises(dataclasses.FrozenInstanceError):
        action.cards = frozenset()  # type: ignore[misc]


def test_discard_action_rejects_duplicates() -> None:
    (card,) = cards_from_codes("12O")
    with pytest.raises(InvalidDiscardError, match="dos veces"):
        DiscardAction([card, card])


@pytest.mark.parametrize("bad", ["12O", b"x", 3, None, ["12O"], [None]])
def test_discard_action_rejects_non_cards(bad: object) -> None:
    with pytest.raises(InvalidDiscardError):
        DiscardAction(bad)  # type: ignore[arg-type]


def test_empty_discard_is_constructible_but_engine_decides() -> None:
    # La forma es válida; el número mínimo de naipes lo valida el motor (D-13).
    assert DiscardAction([]).cards == frozenset()
