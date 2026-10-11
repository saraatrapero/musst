"""Torneo todos contra todos y clasificación (requisitos 4.1 y 4.2).

Cada par de bots juega ``games_per_pair`` partidas, alternando qué pareja ocupa los
asientos 0 y 2 para que nadie tenga ventaja de posición. Cada pareja son dos
instancias del mismo bot. Las semillas se derivan de ``seed``: el torneo es
reproducible.
"""

from __future__ import annotations

import itertools
import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from functools import partial

from mus_engine.arena.match import GameResult, play_game
from mus_engine.arena.seats import DEFAULT_TIMEOUT, InProcessSeat, IsolatedSeat, SeatController
from mus_engine.bots.base import Bot
from mus_engine.config import GameConfig
from mus_engine.players.seating import TeamId

ELO_START = 1500.0
ELO_K = 24.0


@dataclass
class Standing:
    name: str
    played: int = 0
    won: int = 0
    lost: int = 0
    drawn: int = 0
    forfeits: int = 0  # partidas perdidas por fallo del propio bot
    elo: float = ELO_START

    @property
    def win_rate(self) -> float:
        return self.won / self.played if self.played else 0.0


@dataclass
class TournamentResult:
    standings: list[Standing]
    games: list[dict[str, object]] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [
            "| # | Bot | Partidas | Ganadas | Perdidas | Tablas | Abandonos | % victorias | Elo |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for position, s in enumerate(self.standings, start=1):
            lines.append(
                f"| {position} | {s.name} | {s.played} | {s.won} | {s.lost} | {s.drawn} | "
                f"{s.forfeits} | {100 * s.win_rate:.1f} | {s.elo:.0f} |"
            )
        return "\n".join(lines) + "\n"

    def to_json(self) -> str:
        data = {
            "standings": [asdict(s) | {"win_rate": round(s.win_rate, 4)} for s in self.standings],
            "games": self.games,
        }
        return json.dumps(data, ensure_ascii=False, indent=2)


def game_seed(seed: int, pair_index: int, game_index: int) -> int:
    return seed * 1_000_003 + pair_index * 10_007 + game_index


def run_tournament(
    bots: Mapping[str, type[Bot]],
    games_per_pair: int = 10,
    seed: int = 0,
    config: GameConfig | None = None,
    isolated: bool = True,
    timeout: float = DEFAULT_TIMEOUT,
) -> TournamentResult:
    config = config or GameConfig()
    standings = {name: Standing(name) for name in bots}
    games: list[dict[str, object]] = []
    seat_type: Callable[..., SeatController] = IsolatedSeat if isolated else InProcessSeat
    for pair_index, (a, b) in enumerate(itertools.combinations(sorted(bots), 2)):
        for game_index in range(games_per_pair):
            team_a, team_b = (a, b) if game_index % 2 == 0 else (b, a)
            factories = (bots[team_a], bots[team_b], bots[team_a], bots[team_b])
            seats = [seat_type(partial(cls), timeout=timeout) for cls in factories]
            current = game_seed(seed, pair_index, game_index)
            result = play_game(seats, config, current)
            _update(standings, team_a, team_b, result)
            games.append(_summary(team_a, team_b, current, result))
    ordered = sorted(standings.values(), key=lambda s: (-s.win_rate, -s.elo, s.name))
    return TournamentResult(ordered, games)


def _update(standings: dict[str, Standing], team_a: str, team_b: str, result: GameResult) -> None:
    a, b = standings[team_a], standings[team_b]
    a.played += 1
    b.played += 1
    if result.winner is None:
        a.drawn += 1
        b.drawn += 1
        score_a = 0.5
    elif result.winner is TeamId.A:
        a.won += 1
        b.lost += 1
        score_a = 1.0
    else:
        b.won += 1
        a.lost += 1
        score_a = 0.0
    if result.forfeit is not None:
        loser = team_a if result.forfeit.seat % 2 == 0 else team_b
        standings[loser].forfeits += 1
    expected_a = 1 / (1 + 10 ** ((b.elo - a.elo) / 400))
    a.elo += ELO_K * (score_a - expected_a)
    b.elo -= ELO_K * (score_a - expected_a)


def _summary(team_a: str, team_b: str, seed: int, result: GameResult) -> dict[str, object]:
    return {
        "team_a": team_a,
        "team_b": team_b,
        "seed": seed,
        "winner": None
        if result.winner is None
        else (team_a if result.winner is TeamId.A else team_b),
        "score": list(result.score.tantos),
        "games": list(result.score.games),
        "steps": result.steps,
        "forfeit": None
        if result.forfeit is None
        else {
            "seat": result.forfeit.seat,
            "kind": result.forfeit.kind.value,
            "detail": result.forfeit.detail,
        },
    }
