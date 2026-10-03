"""Jugadores, parejas y mesa.

Un :class:`Player` es una **identidad** estable durante toda la partida: asiento y
nombre. No contiene cartas (pertenecen al estado de cada jugada), ni estrategia, ni
interfaz, ni estadísticas. Los puestos no pueden cambiar durante la partida (C.II-1).
"""

from __future__ import annotations

from dataclasses import dataclass

from mus_engine.errors import InvalidPlayerError
from mus_engine.players.seating import (
    ALL_SEATS,
    NUM_SEATS,
    SeatId,
    TeamId,
    are_teammates,
    partner,
    seat,
    team_of,
    team_seats,
)


@dataclass(frozen=True, slots=True)
class Player:
    id: SeatId
    name: str

    def __post_init__(self) -> None:
        seat(self.id)
        if not isinstance(self.name, str) or not self.name.strip():
            raise InvalidPlayerError(f"Nombre de jugador inválido: {self.name!r}")

    @property
    def team(self) -> TeamId:
        return team_of(self.id)

    @property
    def partner(self) -> SeatId:
        return partner(self.id)


@dataclass(frozen=True, slots=True)
class Team:
    id: TeamId
    seats: tuple[SeatId, SeatId]

    @classmethod
    def of(cls, team: TeamId) -> Team:
        return cls(team, team_seats(team))

    def __contains__(self, item: object) -> bool:
        return item in self.seats


@dataclass(frozen=True, slots=True)
class Table:
    """Los cuatro jugadores sentados. ``players[i].id == i`` siempre."""

    players: tuple[Player, Player, Player, Player]

    def __post_init__(self) -> None:
        if not isinstance(self.players, tuple) or len(self.players) != NUM_SEATS:
            raise InvalidPlayerError(f"Se necesitan exactamente {NUM_SEATS} jugadores")
        for expected, player in zip(ALL_SEATS, self.players, strict=True):
            if not isinstance(player, Player):
                raise InvalidPlayerError(f"No es un jugador: {player!r}")
            if player.id != expected:
                raise InvalidPlayerError(
                    f"El jugador {player.name!r} tiene id {player.id}; se esperaba {expected}"
                )

    @classmethod
    def from_names(cls, names: tuple[str, str, str, str]) -> Table:
        """Sienta a los jugadores en orden de habla: ``names[i]`` ocupa el asiento ``i``."""
        if len(names) != NUM_SEATS:
            raise InvalidPlayerError(f"Se necesitan exactamente {NUM_SEATS} nombres")
        return cls(
            (
                Player(SeatId(0), names[0]),
                Player(SeatId(1), names[1]),
                Player(SeatId(2), names[2]),
                Player(SeatId(3), names[3]),
            )
        )

    @property
    def names(self) -> tuple[str, str, str, str]:
        a, b, c, d = self.players
        return a.name, b.name, c.name, d.name

    def player(self, player_id: object) -> Player:
        return self.players[seat(player_id)]

    @property
    def teams(self) -> tuple[Team, Team]:
        return Team.of(TeamId.A), Team.of(TeamId.B)

    def get_partner(self, player_id: object) -> Player:
        return self.players[partner(seat(player_id))]

    def get_team(self, player_id: object) -> Team:
        return Team.of(team_of(seat(player_id)))

    def are_teammates(self, a: object, b: object) -> bool:
        return are_teammates(seat(a), seat(b))
