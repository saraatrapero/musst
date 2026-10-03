"""Utilidades de test para construir estados concretos.

Sólo para tests: permiten colocar una partida en un estado preciso (p. ej. terminada o
con un marcador dado) sin recorrer todas las jugadas. El código de producción nunca
expone esta posibilidad.
"""

from __future__ import annotations

from mus_engine import Game, GameState


def game_with_state(state: GameState) -> Game:
    game = Game(players=state.table, config=state.config, seed=state.rng.seed)
    game._state = state
    return game


def started_game(seed: int = 12345, **config: object) -> Game:
    from mus_engine import GameConfig

    game = Game(players=("Ana", "Bea", "Carlos", "Dani"), config=GameConfig(**config), seed=seed)  # type: ignore[arg-type]
    game.start()
    return game
