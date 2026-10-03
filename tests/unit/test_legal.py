"""Tests de LegalActions y AmountRange."""

from mus_engine import (
    AcceptAction,
    AmountRange,
    BetAction,
    LegalActions,
    PassAction,
    RaiseAction,
    RejectAction,
)
from mus_engine.game.legal import NO_ACTIONS


def test_amount_range() -> None:
    bounded = AmountRange(2, 5)
    assert 2 in bounded
    assert 5 in bounded
    assert 1 not in bounded
    assert 6 not in bounded
    unbounded = AmountRange(2)
    assert 10**9 in unbounded
    assert True not in unbounded
    assert "3" not in unbounded


def test_contains_discrete_and_ranges() -> None:
    legal = LegalActions(actions=(PassAction(),), bet=AmountRange(2))
    assert legal.contains(PassAction())
    assert legal.contains(BetAction(2))
    assert legal.contains(BetAction(30))
    assert not legal.contains(BetAction(1))
    assert not legal.contains(RaiseAction(2))
    assert not legal.contains(AcceptAction())


def test_action_types_and_iteration() -> None:
    legal = LegalActions(actions=(AcceptAction(), RejectAction()), raise_=AmountRange(2))
    assert legal.action_types() == {AcceptAction, RejectAction, RaiseAction}
    assert list(legal) == [AcceptAction(), RejectAction(), RaiseAction(2)]
    with_bet = LegalActions(bet=AmountRange(2))
    assert with_bet.action_types() == {BetAction}
    assert list(with_bet) == [BetAction(2)]


def test_empty() -> None:
    assert not NO_ACTIONS
    assert list(NO_ACTIONS) == []
    assert LegalActions(bet=AmountRange(2))
    assert LegalActions(raise_=AmountRange(2))
    assert LegalActions(actions=(PassAction(),))
