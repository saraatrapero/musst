"""Bot aleatorio: elige al azar entre las acciones legales. Sirve de referencia."""

from __future__ import annotations

import random

from mus_engine.bots.base import Bot, BotContext
from mus_engine.game.actions import Action, BetAction, RaiseAction, SignalAction
from mus_engine.game.observations import Observation

MAX_EXTRA_BET = 6


class RandomBot(Bot):
    name = "aleatorio"
    description = "Elige al azar entre las acciones legales."

    def on_game_start(self, context: BotContext) -> None:
        super().on_game_start(context)
        self._rng = random.Random(f"{context.seed}:{context.seat}")

    def decide(self, observation: Observation) -> Action:
        legal = observation.legal_actions
        options: list[Action] = [a for a in legal.actions if not isinstance(a, SignalAction)]
        if legal.bet is not None:
            options.append(
                BetAction(self._rng.randint(legal.bet.minimum, legal.bet.minimum + MAX_EXTRA_BET))
            )
        if legal.raise_ is not None:
            options.append(
                RaiseAction(self._rng.randint(legal.raise_.minimum, legal.raise_.minimum + 2))
            )
        return self._rng.choice(options)

    def signal(self, observation: Observation) -> SignalAction | None:
        signals = [a for a in observation.legal_actions.actions if isinstance(a, SignalAction)]
        if signals and self._rng.random() < 0.1:
            return self._rng.choice(signals)
        return None
