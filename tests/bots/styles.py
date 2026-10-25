"""Bots de prueba con estilos marcados, para comprobar que los perfiles se adaptan."""

from __future__ import annotations

import random

from mus_engine.betting.bets import BetStatus
from mus_engine.bots.base import BotContext
from mus_engine.bots.simple_bot import SimpleBot, lance_strength
from mus_engine.game.actions import Action, BetAction, OrdagoAction, PassAction, RejectAction
from mus_engine.game.observations import Observation

BLUFF_RATE = 0.6
FEARLESS = 0.85  # el miedoso sólo juega con manos de este percentil o más


class FaroleroBot(SimpleBot):
    """Juega como el sencillo pero envida en abierto el 60 % de las veces, tenga lo que
    tenga, y a veces echa órdago de farol."""

    name = "farolero"

    def on_game_start(self, context: BotContext) -> None:
        super().on_game_start(context)
        self._rng = random.Random(context.seed * 7 + context.seat)

    def _bet(self, observation: Observation) -> Action:
        bet = observation.bet
        legal = observation.legal_actions
        if bet is not None and bet.status is BetStatus.OPEN and legal.bet is not None:
            roll = self._rng.random()
            if roll < 0.05:
                return OrdagoAction()
            if roll < BLUFF_RATE:
                return BetAction(legal.bet.minimum + self._rng.choice((0, 0, 2)))
        return super()._bet(observation)


class MiedosoBot(SimpleBot):
    """Juega como el sencillo pero sólo envida o quiere con manos muy buenas: abandona
    casi todos los envites (el estilo «cauto» que un bot puede explotar faroleando)."""

    name = "miedoso"

    def _bet(self, observation: Observation) -> Action:
        bet, lance, legal = observation.bet, observation.lance, observation.legal_actions
        if bet is None or lance is None:  # pragma: no cover - sólo se decide en un lance
            return next(iter(legal))
        strength = lance_strength(lance, observation.my_hand, self._policy)
        if strength >= FEARLESS:
            return super()._bet(observation)
        if bet.status is BetStatus.OPEN:
            return PassAction()
        return RejectAction()
