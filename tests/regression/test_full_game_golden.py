"""Partidas de referencia: semilla + política de juego fija → resultado fijo.

Si cambian, el motor ha dejado de ser compatible con partidas ya jugadas (o ha
cambiado una regla). Cualquier cambio intencionado debe justificarse y actualizar
estos valores.
"""

import hashlib

from tests.strategies import play_seeded_without_ordago

from mus_engine import Game, GameConfig, GameScore
from mus_engine.players import TeamId


def _digest(game: Game) -> str:
    return hashlib.sha256(repr(game.event_log).encode()).hexdigest()[:16]


def test_golden_game_2024() -> None:
    game = Game(
        players=("Ana", "Bea", "Carlos", "Dani"), seed=2024, config=GameConfig(games_to_win=2)
    )
    game.start()
    play_seeded_without_ordago(game, 2025, 100000)
    summary = (
        game.winner,
        game.get_state().score,
        game.get_state().current_hand.number,
        len(game.record.actions),
        len(game.event_log),
        _digest(game),
    )
    assert summary == GOLDEN_2024


GOLDEN_2024 = (TeamId.A, GameScore((45, 31), (2, 0)), 9, 123, 442, "5a1d245828d6bf61")
