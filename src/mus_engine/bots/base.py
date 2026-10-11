"""API pública para escribir bots (requisito 2.1 de la práctica).

Un bot controla **un asiento**. Sólo recibe la :class:`Observation` de ese asiento:
nunca el estado completo de la partida. Para escribir un bot basta con heredar de
:class:`Bot` e implementar :meth:`Bot.decide`; no hay que tocar el código del juego.

Ciclo de vida en una partida::

    bot.on_game_start(context)        # una vez: asiento, configuración y semilla
    bot.signal(observation)           # (si hay señas) en cada paso, tenga o no el turno
    bot.decide(observation) -> Action # cuando le toca
    bot.on_game_end(observation)      # una vez: la observación final (para aprender)

Reglas del torneo: la acción devuelta debe ser legal (``observation.legal_actions``),
cada decisión tiene un tiempo límite y un bot no puede compartir información con su
compañero salvo mediante señas. Si un bot falla, tarda demasiado o hace algo ilegal,
su pareja pierde esa partida.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from mus_engine.config import GameConfig
from mus_engine.game.actions import Action, SignalAction
from mus_engine.game.observations import Observation
from mus_engine.players.seating import SeatId


@dataclass(frozen=True, slots=True)
class BotContext:
    """Lo que un bot sabe al empezar la partida."""

    seat: SeatId
    config: GameConfig
    seed: int  # para que el bot sea reproducible si usa azar


class Bot(ABC):
    """Base de todos los bots. Una instancia por asiento y partida."""

    name: ClassVar[str] = "bot"
    description: ClassVar[str] = ""

    def on_game_start(self, context: BotContext) -> None:
        """Se llama una vez antes de la primera decisión."""
        self.context = context

    @abstractmethod
    def decide(self, observation: Observation) -> Action:
        """Devuelve una acción de ``observation.legal_actions`` (le toca jugar)."""

    def signal(self, observation: Observation) -> SignalAction | None:
        """Con señas activadas, se pregunta en cada paso. ``None`` = no hacer seña."""
        return None

    def on_game_end(self, observation: Observation) -> None:  # noqa: B027 - opcional
        """Observación final de la partida (incluye las manos enseñadas)."""
