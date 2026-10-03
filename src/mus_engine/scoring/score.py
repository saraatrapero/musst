"""Marcador de la partida (GAME SCORE).

Sólo representa tantos y juegos por pareja. Cómo se ganan los tantos (lances,
envites) lo decide el ``ScoringEngine`` (fase de puntuación).
"""

from __future__ import annotations

from dataclasses import dataclass

from mus_engine.players.seating import TeamId


@dataclass(frozen=True, slots=True)
class GameScore:
    """Tantos del juego en curso y juegos ganados, indexados por ``TeamId.value``."""

    tantos: tuple[int, int] = (0, 0)
    games: tuple[int, int] = (0, 0)

    def __post_init__(self) -> None:
        for value in (*self.tantos, *self.games):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"Marcador inválido: {self}")

    def tantos_of(self, team: TeamId) -> int:
        return self.tantos[team.value]

    def games_of(self, team: TeamId) -> int:
        return self.games[team.value]

    def amarracos_of(self, team: TeamId, tantos_per_amarraco: int) -> tuple[int, int]:
        """(amarracos, tantos sueltos): sólo representación (D-19)."""
        return divmod(self.tantos_of(team), tantos_per_amarraco)
