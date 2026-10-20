"""Señas del Reglamento FEM (capítulo VIII): cuáles existen y cuándo son verdaderas.

- C.VIII-1/2: sólo las señas oficiales. "Cortar el mus" y "envidar más" no se
  implementan porque C.VIII-4 prohíbe señar para tomar decisiones (S-1).
- C.VIII-4: sólo se seña la jugada que se tiene → **sólo señas verdaderas** (IA-1).
- C.VIII-6: nada de señas parciales (con duples no se seña "dos reyes").
- C.VIII-3 / S-2: sólo después del corte del mus.
- C.VIII-2, C.VIII-5: medias que no sean de reyes, después de grande; treinta (y
  veintinueve, S-4) cuando todos han dicho "juego no".
- C.VIII-2: "juego" no vale para la treinta y una; "ciego" no se pasa si hay jugada con
  seña establecida.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from mus_engine.cards.card import Card, Rank
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.rules.juego import JuegoEvaluator
from mus_engine.rules.pares import ParesCategory, ParesEvaluator


class Signal(Enum):
    DOS_REYES = "dos_reyes"
    DOS_ASES = "dos_ases"
    PARES = "pares"
    MEDIAS_REYES = "medias_reyes"
    MEDIAS_ASES = "medias_ases"
    MEDIAS = "medias"
    DUPLES = "duples"
    JUEGO = "juego"
    TREINTA_Y_UNA = "treinta_y_una"
    TREINTA = "treinta"
    VEINTINUEVE = "veintinueve"
    CIEGO = "ciego"


@dataclass(frozen=True, slots=True)
class SignalContext:
    """Momento de la jugada que condiciona algunas señas."""

    grande_finished: bool  # C.VIII-5: medias que no sean de reyes, tras grande
    everyone_said_no_juego: bool  # C.VIII-2/5: treinta (y veintinueve, S-4)


def true_signals(cards: Sequence[Card], policy: RankingPolicy) -> frozenset[Signal]:
    """Señas que describen con verdad la jugada ``cards`` (sin tener en cuenta el momento)."""
    pares = ParesEvaluator(policy).classify(cards)
    total = JuegoEvaluator(policy).classify(cards).total
    found: set[Signal] = set()
    if pares.category is ParesCategory.PAREJA:
        found.add(Signal.PARES)
        if pares.ranks == (Rank.REY,):
            found.add(Signal.DOS_REYES)
        if pares.ranks == (Rank.AS,):
            found.add(Signal.DOS_ASES)
    elif pares.category is ParesCategory.MEDIAS:
        found.add(Signal.MEDIAS)
        if pares.ranks == (Rank.REY,):
            found.add(Signal.MEDIAS_REYES)
        if pares.ranks == (Rank.AS,):
            found.add(Signal.MEDIAS_ASES)
    elif pares.category is ParesCategory.DUPLES:
        found.add(Signal.DUPLES)
    if total == 31:
        found.add(Signal.TREINTA_Y_UNA)
    elif total > 31:
        found.add(Signal.JUEGO)
    elif total == 30:
        found.add(Signal.TREINTA)
    elif total == 29:
        found.add(Signal.VEINTINUEVE)
    if not found:
        found.add(Signal.CIEGO)
    return frozenset(found)


def timing_allows(signal: Signal, context: SignalContext) -> bool:
    """Restricciones de momento del reglamento (además de "tras el corte")."""
    if signal in (Signal.MEDIAS, Signal.MEDIAS_ASES):
        return context.grande_finished
    if signal in (Signal.TREINTA, Signal.VEINTINUEVE):
        return context.everyone_said_no_juego
    return True


def legal_signals(
    cards: Sequence[Card],
    policy: RankingPolicy,
    context: SignalContext,
    already_made: frozenset[Signal],
    allow_false: bool = False,
) -> tuple[Signal, ...]:
    """Señas que el jugador puede hacer ahora, en orden estable (con ``allow_false``,
    también las que no corresponden a su mano)."""
    allowed = frozenset(Signal) if allow_false else true_signals(cards, policy)
    return tuple(
        s for s in Signal if s in allowed and s not in already_made and timing_allows(s, context)
    )
