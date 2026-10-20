"""Señas durante la partida: legalidad, efecto y avance de las miradas.

Una seña no consume el turno: cualquier jugador puede hacerla mientras se juegan los
lances (después del corte del mus, C.VIII-3). La ven exactamente los jugadores que en
ese momento miran al que la hace (IA-2).
"""

from __future__ import annotations

from dataclasses import replace

from mus_engine.cards.ranking import RankingPolicy
from mus_engine.errors import IllegalActionError, InvalidStateError
from mus_engine.events.events import Emission, GazeChanged, SignalMade, SignalSeen
from mus_engine.game.actions import SignalAction
from mus_engine.game.gaze import advance_gaze
from mus_engine.game.phases import Phase
from mus_engine.game.state import GameState, SignalRecord
from mus_engine.game.transition import Step
from mus_engine.players.seating import SeatId
from mus_engine.rules.lance import LanceType
from mus_engine.rules.signals import SignalContext, legal_signals, timing_allows, true_signals


def signals_open(state: GameState) -> bool:
    """¿Se pueden hacer señas ahora? Sólo con señas activadas y durante los lances."""
    return state.config.signals_enabled and state.phase is Phase.LANCE


def _context(state: GameState) -> SignalContext:
    hand = state.current_hand
    holders = hand.juego_holders
    return SignalContext(
        grande_finished=hand.lance is not LanceType.GRANDE,
        everyone_said_no_juego=holders is not None and not any(holders),
    )


def _made_by(state: GameState, player: SeatId) -> frozenset[object]:
    return frozenset(r.signal for r in state.current_hand.signals if r.sender == player)


def signal_actions(state: GameState, player: SeatId) -> tuple[SignalAction, ...]:
    if not signals_open(state):
        return ()
    policy = RankingPolicy.from_config(state.config)
    cards = state.current_hand.hand_of(player)
    made = frozenset(r.signal for r in state.current_hand.signals if r.sender == player)
    allowed = legal_signals(cards, policy, _context(state), made, state.config.false_signals)
    return tuple(SignalAction(s) for s in allowed)


def explain_illegal_signal(
    state: GameState, player: SeatId, action: SignalAction
) -> IllegalActionError:
    if not state.config.signals_enabled:
        return InvalidStateError("Las señas no están activadas en esta partida")
    if state.phase is not Phase.LANCE:
        return InvalidStateError("Sólo se pueden hacer señas después de cortar el mus (C.VIII-3)")
    signal = action.signal
    if signal in _made_by(state, player):
        return IllegalActionError(f"Ya has hecho la seña {signal.value} en esta jugada")
    policy = RankingPolicy.from_config(state.config)
    honest = true_signals(state.current_hand.hand_of(player), policy)
    if not state.config.false_signals and signal not in honest:
        return IllegalActionError(
            f"La seña {signal.value} no corresponde a tu jugada: sólo se señan jugadas que "
            "se tienen y completas (C.VIII-4, C.VIII-6)"
        )
    if not timing_allows(signal, _context(state)):
        return IllegalActionError(f"La seña {signal.value} no se puede hacer todavía (C.VIII-5)")
    return IllegalActionError(f"Seña no válida: {signal.value}")  # pragma: no cover


def apply_signal(state: GameState, player: SeatId, action: SignalAction) -> Step:
    gaze = state.gaze
    if gaze is None:  # pragma: no cover - garantizado por signals_open
        raise InvalidStateError("Señas sin miradas")
    seen_by = gaze.watchers_of(player)
    hand = state.current_hand
    record = SignalRecord(player, action.signal, seen_by)
    state = state.evolve(hand=replace(hand, signals=(*hand.signals, record)))
    emitted = (
        Emission.private(player, SignalMade(player, action.signal.value, seen_by)),
        *(Emission.private(w, SignalSeen(player, action.signal.value)) for w in seen_by),
    )
    return state, emitted


def tick(state: GameState) -> Step:
    """Pasa un momento: avanzan las miradas (sólo con señas activadas)."""
    if state.gaze is None:
        return state, ()
    gaze, rng = advance_gaze(state.gaze, state.config, state.rng)
    emitted: tuple[Emission, ...] = ()
    if gaze.targets != state.gaze.targets:
        emitted = (Emission.public(GazeChanged(gaze.targets)),)
    return state.evolve(gaze=gaze, rng=rng), emitted
