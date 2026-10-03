"""Reglas como funciones puras sobre ``GameState`` (sin estado propio).

Útil para bots, IA, simulaciones y herramientas que necesitan explorar "qué pasaría
si" sin tocar una partida real: cada llamada devuelve un estado nuevo.

Atención: ``GameState`` contiene información secreta. Un bot que juegue limpio debe
decidir sólo con su :class:`~mus_engine.game.observations.Observation`.
"""

from __future__ import annotations

from mus_engine.events.events import Emission
from mus_engine.game import machine
from mus_engine.game.actions import Action
from mus_engine.game.legal import LegalActions
from mus_engine.game.state import GameState
from mus_engine.players import seating
from mus_engine.players.seating import SeatId


class RulesEngine:
    @staticmethod
    def actors(state: GameState) -> tuple[SeatId, ...]:
        return machine.actors(state)

    @staticmethod
    def legal_actions(state: GameState, player_id: int) -> LegalActions:
        return machine.legal_actions(state, seating.seat(player_id))

    @staticmethod
    def is_legal(state: GameState, player_id: int, action: Action) -> bool:
        player = seating.seat(player_id)
        return player in machine.actors(state) and machine.legal_actions(state, player).contains(
            action
        )

    @staticmethod
    def validate(state: GameState, player_id: int, action: Action) -> None:
        """Lanza el error específico si la acción no es legal."""
        machine.validate(state, seating.seat(player_id), action)

    @staticmethod
    def apply(
        state: GameState, player_id: int, action: Action
    ) -> tuple[GameState, tuple[Emission, ...]]:
        """Valida y aplica; devuelve el estado siguiente y los eventos emitidos."""
        return machine.apply(state, seating.seat(player_id), action)
