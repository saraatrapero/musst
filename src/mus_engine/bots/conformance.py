"""Comprobación automática de un bot antes de incluirlo (requisito 2.2).

``check_bot(MiBot)`` juega varias partidas del bot (en las dos parejas, con y sin
señas) contra el bot aleatorio y devuelve la lista de problemas encontrados: acciones
ilegales, excepciones, tiempo excesivo o resultados que no son acciones. Una lista
vacía significa que el bot es apto para el torneo.

Los tests del repositorio aplican esta comprobación a todos los bots registrados.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial

from mus_engine.arena.match import play_game
from mus_engine.arena.seats import DEFAULT_TIMEOUT, InProcessSeat, IsolatedSeat, SeatController
from mus_engine.bots.base import Bot
from mus_engine.bots.random_bot import RandomBot
from mus_engine.config import GameConfig


@dataclass(frozen=True, slots=True)
class Problem:
    seed: int
    signals: bool
    seat: int
    kind: str
    detail: str


def check_bot(
    bot: type[Bot],
    games: int = 6,
    seed: int = 0,
    isolated: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[Problem]:
    """Juega ``games`` partidas por configuración y devuelve los problemas del bot."""
    problems: list[Problem] = []
    for signals in (False, True):
        config = GameConfig(signals_enabled=signals)
        for index in range(games):
            bot_seats = (0, 2) if index % 2 == 0 else (1, 3)
            classes = [bot if seat in bot_seats else RandomBot for seat in range(4)]
            seat_type = IsolatedSeat if isolated else InProcessSeat
            seats: list[SeatController] = [
                seat_type(partial(cls), timeout=timeout) for cls in classes
            ]
            current = seed + index
            result = play_game(seats, config, current)
            if result.forfeit is not None and result.forfeit.seat in bot_seats:
                problems.append(
                    Problem(
                        current,
                        signals,
                        result.forfeit.seat,
                        result.forfeit.kind.value,
                        result.forfeit.detail,
                    )
                )
    return problems
