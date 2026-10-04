"""Fases de la máquina de estados.

Hay dos clases de fases:

- **De decisión**: el motor espera la acción de un jugador concreto.
- **Automáticas**: el motor las atraviesa sin intervención, emitiendo eventos.

Tras cada llamada pública (``start`` / ``apply_action``) el estado está siempre en una
fase de decisión o en ``GAME_OVER`` (invariante). Las fases se añaden al enum a
medida que se implementan; el diagrama completo está en ``docs/state-machine.md``.
"""

from __future__ import annotations

from enum import Enum


class Phase(Enum):
    NOT_STARTED = "not_started"
    CHOOSE_FIRST_DEALER = "choose_first_dealer"  # automática (C.III-1)
    DEAL = "deal"  # automática (C.III-2)
    MUS_DECISION = "mus_decision"  # decisión (C.IV)
    DISCARD = "discard"  # decisión (C.III-11)
    REDEAL = "redeal"  # automática (C.III-2, C.III-15)
    LANCE_START = "lance_start"  # automática: declaraciones y participantes
    LANCE = "lance"  # decisión: envites del lance en curso (HandState.lance)
    ORDAGO_SHOWDOWN = "ordago_showdown"  # automática (C.VI-6)
    HAND_SCORING = "hand_scoring"  # automática (C.VII-2, C.VII-9)
    NEW_HAND = "new_hand"  # automática (D-15)
    GAME_OVER = "game_over"

    @property
    def is_automatic(self) -> bool:
        return self in _AUTOMATIC

    @property
    def is_resting(self) -> bool:
        """Fase en la que puede quedar el estado entre llamadas públicas."""
        return not self.is_automatic


_AUTOMATIC = frozenset(
    {
        Phase.CHOOSE_FIRST_DEALER,
        Phase.DEAL,
        Phase.REDEAL,
        Phase.LANCE_START,
        Phase.ORDAGO_SHOWDOWN,
        Phase.HAND_SCORING,
        Phase.NEW_HAND,
    }
)
