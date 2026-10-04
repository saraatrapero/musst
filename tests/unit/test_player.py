"""Tests unitarios de Player, Team y Table."""

import dataclasses

import pytest

from mus_engine.errors import InvalidPlayerError
from mus_engine.players import Player, SeatId, Table, Team, TeamId

NAMES = ("Ana", "Bea", "Carlos", "Dani")


def test_player_identity() -> None:
    player = Player(SeatId(2), "Carlos")
    assert player.id == 2
    assert player.name == "Carlos"
    assert player.team is TeamId.A
    assert player.partner == 0


def test_player_is_immutable_and_has_no_hand() -> None:
    player = Player(SeatId(0), "Ana")
    with pytest.raises(dataclasses.FrozenInstanceError):
        player.name = "Otra"  # type: ignore[misc]
    assert not hasattr(player, "hand")
    with pytest.raises((AttributeError, TypeError)):
        player.hand = []  # type: ignore[attr-defined]


@pytest.mark.parametrize("name", ["", "   ", None, 3])
def test_player_rejects_invalid_names(name: object) -> None:
    with pytest.raises(InvalidPlayerError):
        Player(SeatId(0), name)  # type: ignore[arg-type]


@pytest.mark.parametrize("pid", [-1, 4, "1"])
def test_player_rejects_invalid_ids(pid: object) -> None:
    with pytest.raises(InvalidPlayerError):
        Player(pid, "X")  # type: ignore[arg-type]


def test_team() -> None:
    team = Team.of(TeamId.B)
    assert team.seats == (1, 3)
    assert 1 in team
    assert 0 not in team


def test_table_from_names() -> None:
    table = Table.from_names(NAMES)
    assert [p.name for p in table.players] == list(NAMES)
    assert [p.id for p in table.players] == [0, 1, 2, 3]


def test_table_queries() -> None:
    table = Table.from_names(NAMES)
    assert table.player(1).name == "Bea"
    assert table.get_partner(0).name == "Carlos"
    assert table.get_partner(3).name == "Bea"
    assert table.get_team(3).id is TeamId.B
    assert table.are_teammates(0, 2)
    assert not table.are_teammates(0, 1)
    assert [t.id for t in table.teams] == [TeamId.A, TeamId.B]


@pytest.mark.parametrize("pid", [-1, 4, "0", None])
def test_table_rejects_unknown_players(pid: object) -> None:
    table = Table.from_names(NAMES)
    with pytest.raises(InvalidPlayerError):
        table.player(pid)
    with pytest.raises(InvalidPlayerError):
        table.get_partner(pid)


def test_table_requires_four_players() -> None:
    with pytest.raises(InvalidPlayerError):
        Table.from_names(("A", "B", "C"))  # type: ignore[arg-type]
    with pytest.raises(InvalidPlayerError):
        Table((Player(SeatId(0), "A"),))  # type: ignore[arg-type]


def test_table_requires_ordered_ids() -> None:
    players = (
        Player(SeatId(1), "A"),
        Player(SeatId(0), "B"),
        Player(SeatId(2), "C"),
        Player(SeatId(3), "D"),
    )
    with pytest.raises(InvalidPlayerError, match="se esperaba"):
        Table(players)


def test_table_rejects_non_players() -> None:
    with pytest.raises(InvalidPlayerError):
        Table(("A", "B", "C", "D"))  # type: ignore[arg-type]


def test_table_is_immutable() -> None:
    table = Table.from_names(NAMES)
    with pytest.raises(dataclasses.FrozenInstanceError):
        table.players = ()  # type: ignore[misc, assignment]
