"""Bots defectuosos para probar la robustez del torneo."""

from __future__ import annotations

import os
import time

from mus_engine import Action, PassAction
from mus_engine.bots import Bot, BotContext, RandomBot
from mus_engine.game.actions import SignalAction
from mus_engine.game.observations import Observation
from mus_engine.rules.signals import Signal


class RaisingBot(Bot):
    name = "explota"

    def decide(self, observation: Observation) -> Action:
        raise RuntimeError("fallo deliberado")


class SleepingBot(Bot):
    name = "dormido"

    def decide(self, observation: Observation) -> Action:
        time.sleep(30)
        return PassAction()  # pragma: no cover


class SlowBot(Bot):
    name = "lento"

    def decide(self, observation: Observation) -> Action:
        time.sleep(0.05)
        return PassAction()


class GarbageBot(Bot):
    name = "basura"

    def decide(self, observation: Observation) -> Action:
        return "mus"  # type: ignore[return-value]


class IllegalBot(Bot):
    name = "ilegal"

    def decide(self, observation: Observation) -> Action:
        return PassAction()  # ilegal mientras se decide el mus


class CrashingBot(Bot):
    name = "muere"

    def decide(self, observation: Observation) -> Action:
        os._exit(1)


class BadSignalBot(RandomBot):
    name = "senas-falsas"

    def signal(self, observation: Observation) -> SignalAction | None:
        return SignalAction(Signal.DUPLES) if observation.lance is not None else None


class SignalGarbageBot(RandomBot):
    name = "senas-basura"

    def signal(self, observation: Observation) -> SignalAction | None:
        return PassAction()  # type: ignore[return-value]


class BrokenStartBot(RandomBot):
    name = "no-arranca"

    def on_game_start(self, context: BotContext) -> None:
        raise ValueError("no arranco")


class BrokenEndBot(RandomBot):
    name = "falla-al-final"

    def on_game_end(self, observation: Observation) -> None:
        raise ValueError("fallo al terminar")
