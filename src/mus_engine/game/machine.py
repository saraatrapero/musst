"""Fases de decisión: quién puede actuar, qué es legal y cómo se valida.

Cada fase de decisión registra un :class:`PhaseHandler`. La validación es única y
común: ``get_legal_actions`` y ``apply_action`` usan exactamente la misma función
(:func:`legal_actions`), de modo que una acción es aceptada si y sólo si figura en
las acciones legales.
"""

from __future__ import annotations

from typing import Protocol

from mus_engine.errors import (
    IllegalActionError,
    InvalidStateError,
    NotYourTurnError,
)
from mus_engine.game.actions import Action
from mus_engine.game.flow import Step, run_automatic
from mus_engine.game.legal import NO_ACTIONS, LegalActions
from mus_engine.game.phases import Phase
from mus_engine.game.state import GameState
from mus_engine.players.seating import SeatId


class PhaseHandler(Protocol):
    def actors(self, state: GameState) -> tuple[SeatId, ...]:
        """Jugadores que pueden actuar ahora (normalmente uno)."""
        ...

    def legal_actions(self, state: GameState, player: SeatId) -> LegalActions:
        """Acciones legales de ``player`` (que está en ``actors``)."""
        ...

    def explain_illegal(
        self, state: GameState, player: SeatId, action: Action
    ) -> IllegalActionError:
        """Error específico para una acción que no está en ``legal_actions``."""
        ...

    def apply(self, state: GameState, player: SeatId, action: Action) -> Step:
        """Aplica una acción ya validada como legal."""
        ...


HANDLERS: dict[Phase, PhaseHandler] = {}


def actors(state: GameState) -> tuple[SeatId, ...]:
    handler = HANDLERS.get(state.phase)
    return () if handler is None else handler.actors(state)


def legal_actions(state: GameState, player: SeatId) -> LegalActions:
    handler = HANDLERS.get(state.phase)
    if handler is None or player not in handler.actors(state):
        return NO_ACTIONS
    return handler.legal_actions(state, player)


def validate(state: GameState, player: SeatId, action: Action) -> PhaseHandler:
    """Lanza un :class:`IllegalActionError` específico si la acción no es legal."""
    if not isinstance(action, Action):
        raise IllegalActionError(f"No es una acción del motor: {action!r}")
    handler = HANDLERS.get(state.phase)
    if handler is None:
        raise InvalidStateError(
            f"No se admiten acciones en la fase {state.phase.value} "
            f"(acción {type(action).__name__} del jugador {player})"
        )
    current = handler.actors(state)
    if player not in current:
        raise NotYourTurnError(
            f"No es el turno del jugador {player} en la fase {state.phase.value}; "
            f"puede actuar: {list(current)}"
        )
    if not handler.legal_actions(state, player).contains(action):
        raise handler.explain_illegal(state, player, action)
    return handler


def apply(state: GameState, player: SeatId, action: Action) -> Step:
    """Valida, aplica y avanza las fases automáticas."""
    handler = validate(state, player, action)
    state, emitted = handler.apply(state, player, action)
    state, automatic = run_automatic(state)
    return state, emitted + automatic
