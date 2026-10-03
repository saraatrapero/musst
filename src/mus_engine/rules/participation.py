"""Quién participa en los lances de pares y juego.

- C.VI-5, C.VI-22, C.VI-23 (R-19): en pares y juego sólo hablan los que los tienen.
- Voc. "Mano": en pares o juego, el primer jugador que los tiene es mano del lance.
- D-20: si sólo una pareja tiene la jugada no hay envites y cobra al final; si nadie
  la tiene el lance no se juega.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from mus_engine.players.seating import SeatId, TeamId, eligible_in_order, team_of


@dataclass(frozen=True, slots=True)
class Participation:
    """Jugadores con la jugada del lance, en orden de habla desde la mano."""

    players: tuple[SeatId, ...]

    @classmethod
    def from_holders(cls, holders: Iterable[SeatId], mano: SeatId) -> Participation:
        return cls(eligible_in_order(mano, holders))

    @property
    def teams(self) -> frozenset[TeamId]:
        return frozenset(team_of(player) for player in self.players)

    @property
    def lance_mano(self) -> SeatId | None:
        return self.players[0] if self.players else None

    @property
    def is_contested(self) -> bool:
        """Las dos parejas tienen la jugada: hay envites."""
        return len(self.teams) == 2

    @property
    def single_team(self) -> TeamId | None:
        """La única pareja con la jugada (cobra sin envites, D-20), o ``None``."""
        return next(iter(self.teams)) if len(self.teams) == 1 else None

    @property
    def is_void(self) -> bool:
        """Nadie tiene la jugada: el lance no se juega."""
        return not self.players
