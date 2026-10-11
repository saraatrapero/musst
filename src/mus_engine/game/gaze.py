"""Miradas de los jugadores (IA-2).

Cada jugador mira, en cada momento, a otro jugador o a la mesa (``None``). La mirada
dura unos instantes (``remaining``) y después cambia al azar con los pesos de
``GameConfig``. Hacia dónde mira cada uno es **público**. Una seña sólo la ven los
jugadores que, en ese momento, están mirando al que la hace.
"""

from __future__ import annotations

from dataclasses import dataclass

from mus_engine.config import GameConfig
from mus_engine.players.seating import ALL_SEATS, SeatId, next_player, partner, previous_player
from mus_engine.rng import Rng


@dataclass(frozen=True, slots=True)
class GazeState:
    targets: tuple[SeatId | None, ...]  # a quién mira cada asiento (None = la mesa)
    remaining: tuple[int, ...]  # momentos que le quedan a cada mirada

    def watchers_of(self, player: SeatId) -> tuple[SeatId, ...]:
        """Jugadores que están mirando a ``player``."""
        return tuple(p for p in ALL_SEATS if self.targets[p] == player)


def _options(player: SeatId, config: GameConfig) -> tuple[tuple[SeatId | None, int], ...]:
    return (
        (partner(player), config.gaze_partner_weight),
        (next_player(player), config.gaze_rival_weight),
        (previous_player(player), config.gaze_rival_weight),
        (None, config.gaze_table_weight),
    )


def _draw(player: SeatId, config: GameConfig, rng: Rng) -> tuple[SeatId | None, int, Rng]:
    options = _options(player, config)
    total = sum(weight for _, weight in options)
    pick, rng = rng.choice_index(total)
    target: SeatId | None = None
    for candidate, weight in options:
        if pick < weight:
            target = candidate
            break
        pick -= weight
    span = config.gaze_max_ticks - config.gaze_min_ticks + 1
    extra, rng = rng.choice_index(span)
    return target, config.gaze_min_ticks + extra, rng


def initial_gaze(config: GameConfig, rng: Rng) -> tuple[GazeState, Rng]:
    targets: list[SeatId | None] = []
    remaining: list[int] = []
    for player in ALL_SEATS:
        target, duration, rng = _draw(player, config, rng)
        targets.append(target)
        remaining.append(duration)
    return GazeState(tuple(targets), tuple(remaining)), rng


def advance_gaze(gaze: GazeState, config: GameConfig, rng: Rng) -> tuple[GazeState, Rng]:
    """Pasa un momento: las miradas que terminan se renuevan al azar."""
    targets = list(gaze.targets)
    remaining = list(gaze.remaining)
    for player in ALL_SEATS:
        remaining[player] -= 1
        if remaining[player] <= 0:
            targets[player], remaining[player], rng = _draw(player, config, rng)
    return GazeState(tuple(targets), tuple(remaining)), rng
