"""Tipos y utilidades comunes de las transiciones."""

from __future__ import annotations

from mus_engine.events.events import Emission, PhaseChanged
from mus_engine.game.phases import Phase
from mus_engine.game.state import GameState

Step = tuple[GameState, tuple[Emission, ...]]


def enter(state: GameState, phase: Phase) -> Step:
    """Cambia de fase y emite ``PhaseChanged``."""
    return state.evolve(phase=phase), (Emission.public(PhaseChanged(phase.value)),)
