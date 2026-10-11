"""Una partida entre dos parejas de bots, robusta frente a fallos (requisito 4.1).

Si un bot lanza una excepción, tarda demasiado, devuelve algo que no es una acción o
hace una acción ilegal, **su pareja pierde la partida** (abandono) y el resultado se
registra; nunca se interrumpe el programa que organiza el torneo.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from mus_engine.arena.seats import FailureKind, SeatController, SeatError
from mus_engine.bots.base import BotContext
from mus_engine.config import GameConfig
from mus_engine.errors import MusEngineError
from mus_engine.game.game import Game
from mus_engine.game.record import GameRecord
from mus_engine.players.seating import ALL_SEATS, SeatId, TeamId, opponent, team_of
from mus_engine.scoring.score import GameScore

DEFAULT_MAX_STEPS = 20_000  # tope por si nadie corta nunca el mus (D-14)


@dataclass(frozen=True, slots=True)
class Forfeit:
    seat: SeatId
    kind: FailureKind
    detail: str


@dataclass(frozen=True, slots=True)
class GameResult:
    winner: TeamId | None  # None = tablas por tope de pasos
    score: GameScore
    forfeit: Forfeit | None
    steps: int
    record: GameRecord


def play_game(
    seats: Sequence[SeatController],
    config: GameConfig,
    seed: int,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> GameResult:
    """Juega una partida. ``seats[i]`` controla el asiento ``i``; los cierra al acabar."""
    if len(seats) != len(ALL_SEATS):
        raise ValueError("Se necesitan cuatro asientos")
    game = Game(config=config, seed=seed)
    game.start()
    steps = 0
    forfeit: Forfeit | None = None
    try:
        for seat in ALL_SEATS:
            forfeit = _guard(seat, lambda s=seat: seats[s].start(BotContext(s, config, seed)))
            if forfeit:
                break
        while forfeit is None and not game.is_finished and steps < max_steps:
            steps += 1
            if config.signals_enabled:
                forfeit = _signals(game, seats)
                if forfeit:
                    break
            (player,) = game.current_actors()
            forfeit = _turn(game, seats, player)
        if forfeit is None:
            for seat in ALL_SEATS:
                # Un fallo al final no cambia el resultado ya decidido.
                _guard(seat, lambda s=seat: seats[s].end(game.get_observation(s)))
    finally:
        for controller in seats:
            controller.close()
    state = game.get_state()
    if forfeit is not None:
        winner: TeamId | None = opponent(team_of(forfeit.seat))
    else:
        winner = state.winner
    return GameResult(winner, state.score, forfeit, steps, game.record)


def _guard(seat: SeatId, call: object) -> Forfeit | None:
    try:
        call()  # type: ignore[operator]
    except SeatError as failure:
        return Forfeit(seat, failure.kind, failure.detail)
    return None


def _signals(game: Game, seats: Sequence[SeatController]) -> Forfeit | None:
    for seat in ALL_SEATS:
        try:
            action = seats[seat].signal(game.get_observation(seat))
        except SeatError as failure:
            return Forfeit(seat, failure.kind, failure.detail)
        if action is not None:
            try:
                game.apply_action(seat, action)
            except MusEngineError as error:
                return Forfeit(seat, FailureKind.ILLEGAL_ACTION, str(error))
    return None


def _turn(game: Game, seats: Sequence[SeatController], player: SeatId) -> Forfeit | None:
    try:
        action = seats[player].decide(game.get_observation(player))
    except SeatError as failure:
        return Forfeit(player, failure.kind, failure.detail)
    try:
        game.apply_action(player, action)
    except MusEngineError as error:
        return Forfeit(player, FailureKind.ILLEGAL_ACTION, str(error))
    return None
