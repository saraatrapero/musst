"""Inferencia de manos a partir de lo que cada uno hace (primer paso del
HandInferenceAgent, ``docs/ai-design.md`` §3.3).

Cortar el mus es una señal fuerte: quien corta suele tener buena grande y a menudo
pares y juego; quien pide mus, rara vez tiene juego. Medido en 400 partidas entre bots
(percentil medio de las manos enseñadas, en cada lance):

======== ========= ======= ======= ======= =======
Señal    grande    chica   pares   juego   punto
======== ========= ======= ======= ======= =======
corta    0,70      0,35    0,64    0,52    0,57
pide mus 0,37      0,59    0,32    0,15    0,49
======== ========= ======= ======= ======= =======

Cada percentil medio ``m`` se convierte en una inclinación ``exp(β·(percentil − ½))``
sobre las manos posibles (:func:`beta_for_mean`). El perfil de cada jugador ajusta esos
valores con sus propias manos enseñadas (:meth:`PlayerProfile.mus_beta`).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from functools import cache

from mus_engine.events.events import (
    DiscardDeclared,
    EventEnvelope,
    HandStarted,
    MusCut,
    MusRequested,
    Visibility,
)
from mus_engine.players.seating import SeatId
from mus_engine.rules.lance import LanceType

CUT = "corta"
MUS = "mus"
MUS_SIGNALS = (CUT, MUS)

# Percentil medio de la mano enseñada según la última decisión de mus (población).
MUS_MEAN: dict[tuple[str, LanceType], float] = {
    (CUT, LanceType.GRANDE): 0.697,
    (CUT, LanceType.CHICA): 0.354,
    (CUT, LanceType.PARES): 0.642,
    (CUT, LanceType.JUEGO): 0.517,
    (CUT, LanceType.PUNTO): 0.568,
    (MUS, LanceType.GRANDE): 0.372,
    (MUS, LanceType.CHICA): 0.594,
    (MUS, LanceType.PARES): 0.318,
    (MUS, LanceType.JUEGO): 0.153,
    (MUS, LanceType.PUNTO): 0.489,
}
MAX_BETA = 12.0


@cache
def beta_for_mean(mean: float) -> float:
    """β tal que la media de ``x`` en [0, 1] con densidad ∝ ``exp(β·x)`` es ``mean``."""
    lo, hi = -MAX_BETA, MAX_BETA
    for _ in range(60):
        mid = (lo + hi) / 2
        if _tilted_mean(mid) < mean:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 3)


def _tilted_mean(beta: float) -> float:
    if abs(beta) < 1e-9:
        return 0.5
    return (math.exp(beta) * (beta - 1) + 1) / (beta * (math.exp(beta) - 1))


def inclination(beta: float) -> Callable[[float], float]:
    """Peso por percentil ``exp(β·(percentil − ½))``."""
    return lambda percentile: math.exp(beta * (percentile - 0.5))


def mus_signals(events: Iterable[EventEnvelope], hand_number: int) -> dict[SeatId, str]:
    """Última decisión de mus de cada asiento en la jugada ``hand_number``.

    Sólo cuenta la última ronda (tras descartar, las manos cambian). Quien no llegó a
    hablar porque otro cortó antes no aparece.
    """
    signals: dict[SeatId, str] = {}
    for envelope in events:
        if envelope.visibility is not Visibility.PUBLIC or envelope.hand_number != hand_number:
            continue
        event = envelope.event
        if isinstance(event, HandStarted | DiscardDeclared):
            signals = {}
        elif isinstance(event, MusCut):
            signals[event.seat] = CUT
        elif isinstance(event, MusRequested):
            signals[event.seat] = MUS
    return signals
