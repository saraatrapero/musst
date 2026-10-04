"""Tests de la participación en pares y juego."""

from mus_engine.players import SeatId, TeamId
from mus_engine.rules import Participation

S0, S1, S2, S3 = map(SeatId, range(4))


def test_order_from_mano_and_lance_mano() -> None:
    p = Participation.from_holders([S0, S3, S1], mano=S2)
    assert p.players == (S3, S0, S1)
    assert p.lance_mano == S3


def test_contested() -> None:
    p = Participation.from_holders([S0, S1], mano=S0)
    assert p.is_contested
    assert p.single_team is None
    assert not p.is_void
    assert p.teams == {TeamId.A, TeamId.B}


def test_single_team() -> None:
    p = Participation.from_holders([S1, S3], mano=S0)
    assert not p.is_contested
    assert p.single_team is TeamId.B
    assert p.lance_mano == S1


def test_void() -> None:
    p = Participation.from_holders([], mano=S0)
    assert p.is_void
    assert p.lance_mano is None
    assert p.single_team is None
    assert not p.is_contested
