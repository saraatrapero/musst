"""Tests de las transiciones puras de envites."""

import pytest

from mus_engine import GameConfig
from mus_engine.betting import (
    LANCES_WITH_DEJE,
    BetStatus,
    apply_accept,
    apply_bet,
    apply_ordago,
    apply_pass,
    apply_raise,
    apply_reject,
    open_bet,
    rejection_points,
    rivals_after,
)
from mus_engine.errors import InvalidBetError
from mus_engine.players import SeatId, TeamId
from mus_engine.rules import LanceType

S0, S1, S2, S3 = map(SeatId, range(4))
ALL = (S0, S1, S2, S3)
CONFIG = GameConfig()


def _open(lance: LanceType = LanceType.GRANDE, participants: tuple[SeatId, ...] = ALL):  # type: ignore[no-untyped-def]
    return open_bet(lance, participants)


def test_open_bet() -> None:
    bet = _open()
    assert bet.status is BetStatus.OPEN
    assert bet.to_act == ALL
    assert bet.proposer is None
    assert bet.proposing_team is None


def test_open_bet_requires_both_teams() -> None:
    with pytest.raises(InvalidBetError):
        open_bet(LanceType.PARES, (S0, S2))


def test_all_pass() -> None:
    bet = _open()
    for p in ALL[:-1]:
        bet = apply_pass(bet, p)
        assert bet.status is BetStatus.OPEN
    bet = apply_pass(bet, S3)
    assert bet.status is BetStatus.PASSED
    assert bet.status.is_closed


def test_bet_queues_rivals_in_order() -> None:
    bet = apply_bet(_open(), S0, 2, CONFIG)
    assert bet.status is BetStatus.PENDING
    assert bet.pending == 2
    assert bet.accepted == 0
    assert bet.to_act == (S1, S3)
    assert bet.proposing_team is TeamId.A


def test_passer_can_answer_later_bet() -> None:
    bet = apply_pass(_open(), S0)
    bet = apply_bet(bet, S1, 2, CONFIG)
    assert bet.to_act == (S2, S0)


def test_rivals_after_respects_participants() -> None:
    bet = _open(LanceType.PARES, (S0, S1, S2))
    assert rivals_after(bet, S0) == (S1,)
    assert rivals_after(bet, S1) == (S2, S0)


def test_accept_fixes_amount() -> None:
    bet = apply_accept(apply_bet(_open(), S0, 5, CONFIG), S1)
    assert bet.status is BetStatus.ACCEPTED
    assert bet.accepted == 5
    assert bet.to_act == ()


def test_partner_can_accept_after_first_rejection() -> None:
    bet = apply_reject(apply_bet(_open(), S0, 2, CONFIG), S1)
    assert bet.status is BetStatus.PENDING
    assert bet.to_act == (S3,)
    assert apply_accept(bet, S3).status is BetStatus.ACCEPTED


def test_all_rivals_reject() -> None:
    bet = apply_reject(apply_reject(apply_bet(_open(), S0, 2, CONFIG), S1), S3)
    assert bet.status is BetStatus.REJECTED
    assert rejection_points(bet, CONFIG) == 1  # negada


def test_raise_implies_accepting_previous() -> None:
    bet = apply_raise(apply_bet(_open(), S0, 2, CONFIG), S1, 3, CONFIG)
    assert bet.accepted == 2
    assert bet.pending == 5
    assert bet.proposer == S1
    assert bet.raised
    assert bet.to_act == (S2, S0)


@pytest.mark.parametrize(
    ("lance", "points"),
    [
        (LanceType.GRANDE, 2),
        (LanceType.CHICA, 2),
        (LanceType.PARES, 3),
        (LanceType.JUEGO, 3),
        (LanceType.PUNTO, 3),
    ],
)
def test_rejected_raise_points_with_deje(lance: LanceType, points: int) -> None:
    bet = apply_raise(apply_bet(_open(lance), S0, 2, CONFIG), S1, 3, CONFIG)
    bet = apply_reject(apply_reject(bet, S2), S0)
    assert bet.status is BetStatus.REJECTED
    assert rejection_points(bet, CONFIG) == points


def test_lances_with_deje() -> None:
    assert {LanceType.PARES, LanceType.JUEGO, LanceType.PUNTO} == LANCES_WITH_DEJE


def test_ordago_open_and_accept() -> None:
    bet = apply_ordago(_open(), S0)
    assert bet.is_ordago
    assert bet.accepted == 0
    assert bet.to_act == (S1, S3)
    assert apply_accept(bet, S1).status is BetStatus.ORDAGO_ACCEPTED


def test_ordago_over_bet() -> None:
    bet = apply_ordago(apply_bet(_open(), S0, 4, CONFIG), S1)
    assert bet.is_ordago
    assert bet.accepted == 4
    assert bet.raised
    rejected = apply_reject(apply_reject(bet, S2), S0)
    assert rejection_points(rejected, CONFIG) == 4


def test_ordago_rejected_as_first_bet_is_negada() -> None:
    bet = apply_reject(apply_reject(apply_ordago(_open(LanceType.PARES), S0), S1), S3)
    assert rejection_points(bet, CONFIG) == 1


def test_ordago_cannot_be_raised_or_reordagoed() -> None:
    bet = apply_ordago(_open(), S0)
    with pytest.raises(InvalidBetError, match="órdago"):
        apply_raise(bet, S1, 2, CONFIG)
    with pytest.raises(InvalidBetError, match="órdago"):
        apply_ordago(bet, S1)


@pytest.mark.parametrize(
    "transition",
    [
        lambda b: apply_pass(b, S1),  # fuera de turno
        lambda b: apply_bet(b, S0, 1, CONFIG),  # por debajo del mínimo
        lambda b: apply_accept(b, S0),  # sin envite
        lambda b: apply_reject(b, S0),
        lambda b: apply_raise(b, S0, 2, CONFIG),
    ],
)
def test_invalid_transitions_from_open(transition) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(InvalidBetError):
        transition(_open())


@pytest.mark.parametrize(
    "transition",
    [
        lambda b: apply_pass(b, S1),  # no se puede pasar con un envite pendiente
        lambda b: apply_bet(b, S1, 2, CONFIG),
        lambda b: apply_accept(b, S2),  # el compañero del que envidó no contesta
        lambda b: apply_raise(b, S2, 2, CONFIG),  # C.VI-2
        lambda b: apply_raise(b, S1, 1, CONFIG),  # revoque por debajo del mínimo
    ],
)
def test_invalid_transitions_from_pending(transition) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(InvalidBetError):
        transition(apply_bet(_open(), S0, 2, CONFIG))


def test_rejection_points_requires_rejected_bet() -> None:
    with pytest.raises(InvalidBetError):
        rejection_points(_open(), CONFIG)


def test_closed_bet_rejects_everything() -> None:
    closed = apply_accept(apply_bet(_open(), S0, 2, CONFIG), S1)
    with pytest.raises(InvalidBetError):
        apply_pass(closed, S1)
