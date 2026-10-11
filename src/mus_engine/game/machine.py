"""Fases de decisión: quién puede actuar, qué es legal y cómo se valida.

Cada fase de decisión registra un :class:`PhaseHandler`. La validación es única y
común: ``get_legal_actions`` y ``apply_action`` usan exactamente la misma función
(:func:`legal_actions`), de modo que una acción es aceptada si y sólo si figura en
las acciones legales.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from mus_engine.errors import (
    IllegalActionError,
    InvalidStateError,
    NotYourTurnError,
)
from mus_engine.game.actions import Action, SignalAction
from mus_engine.game.flow import run_automatic
from mus_engine.game.handlers.lance import LanceHandler
from mus_engine.game.handlers.mus import DiscardHandler, MusDecisionHandler
from mus_engine.game.legal import NO_ACTIONS, LegalActions
from mus_engine.game.phases import Phase
from mus_engine.game.signals import apply_signal, explain_illegal_signal, signal_actions, tick
from mus_engine.game.state import GameState
from mus_engine.game.transition import Step
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


HANDLERS: dict[Phase, PhaseHandler] = {
    Phase.MUS_DECISION: MusDecisionHandler(),
    Phase.DISCARD: DiscardHandler(),
    Phase.LANCE: LanceHandler(),
}


def actors(state: GameState) -> tuple[SeatId, ...]:
    handler = HANDLERS.get(state.phase)
    return () if handler is None else handler.actors(state)


def legal_actions(state: GameState, player: SeatId) -> LegalActions:
    """Acciones legales de ``player``: las de su turno (si lo tiene) y sus señas."""
    handler = HANDLERS.get(state.phase)
    turn = (
        NO_ACTIONS
        if handler is None or player not in handler.actors(state)
        else handler.legal_actions(state, player)
    )
    signals = signal_actions(state, player)
    if not signals:
        return turn
    return replace(turn, actions=(*turn.actions, *signals))


def validate(state: GameState, player: SeatId, action: Action) -> PhaseHandler | _SignalHandler:
    """Lanza un :class:`IllegalActionError` específico si la acción no es legal."""
    if not isinstance(action, Action):
        raise IllegalActionError(f"No es una acción del motor: {action!r}")
    if isinstance(action, SignalAction):
        if action not in signal_actions(state, player):
            raise explain_illegal_signal(state, player, action)
        return SIGNAL_HANDLER
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


class _SignalHandler:
    """Adaptador para aplicar señas por la misma vía que el resto de acciones."""

    def apply(self, state: GameState, player: SeatId, action: Action) -> Step:
        if not isinstance(action, SignalAction):  # pragma: no cover - ya validado
            raise IllegalActionError(f"No es una seña: {action!r}")
        return apply_signal(state, player, action)


SIGNAL_HANDLER = _SignalHandler()


def apply(state: GameState, player: SeatId, action: Action) -> Step:
    """Valida, aplica, avanza las fases automáticas y pasa un momento (miradas)."""
    handler = validate(state, player, action)
    state, emitted = handler.apply(state, player, action)
    state, automatic = run_automatic(state)
    state, gazes = tick(state)
    return state, emitted + automatic + gazes
