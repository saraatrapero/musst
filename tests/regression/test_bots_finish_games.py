"""Bug: dos bots ``sencillo`` con jugadas muy fuertes se subían el envite sin fin
(más de 5.000 tantos en juego) y la partida no terminaba nunca. Semillas 1, 4 y 7."""

from __future__ import annotations

import pytest

from mus_engine.bots.base import BotContext
from mus_engine.bots.simple_bot import SimpleBot
from mus_engine.config import GameConfig
from mus_engine.game.game import Game

MAX_STEPS = 2000


@pytest.mark.parametrize("seed", [1, 4, 7])
def test_simple_bots_do_not_raise_forever(seed: int) -> None:
    config = GameConfig()
    game = Game(config=config, seed=seed)
    game.start()
    bots = [SimpleBot() for _ in range(4)]
    for seat, bot in enumerate(bots):
        bot.on_game_start(BotContext(seat, config, seed))  # type: ignore[arg-type]
    steps = 0
    while not game.is_finished:
        steps += 1
        assert steps < MAX_STEPS
        (player,) = game.current_actors()
        game.apply_action(player, bots[player].decide(game.get_observation(player)))
