"""Invariantes del motor.

Se comprueban tras cada llamada pública si ``config.debug_invariants`` está activo.
Un fallo lanza :class:`InvariantViolationError`: es un bug del motor, no del usuario.
"""

from __future__ import annotations

from mus_engine.betting.bets import BetStatus
from mus_engine.cards.deck import validate_complete
from mus_engine.errors import InvalidDeckError, InvariantViolationError
from mus_engine.game.phases import Phase
from mus_engine.game.state import GameState
from mus_engine.players.seating import NUM_SEATS, TeamId, are_teammates, mano_for_dealer, team_of


def check_state(state: GameState) -> None:
    _check_cards(state)
    _check_positions(state)
    _check_mus(state)
    _check_bet(state)
    _check_score(state)


def check_resting(state: GameState) -> None:
    if not state.phase.is_resting:
        raise InvariantViolationError(f"El estado quedó en una fase automática: {state.phase}")


def check_transition(before: GameState, after: GameState) -> None:
    """Propiedades entre dos estados consecutivos."""
    if after.score.games != before.score.games:
        gained = [a - b for a, b in zip(after.score.games, before.score.games, strict=True)]
        if any(g < 0 for g in gained) or sum(gained) != 1:
            raise InvariantViolationError(f"Juegos incoherentes: {before.score} -> {after.score}")
    elif any(a < b for a, b in zip(after.score.tantos, before.score.tantos, strict=True)):
        raise InvariantViolationError(f"El tanteo ha disminuido: {before.score} -> {after.score}")
    if before.hand is not None and (after.hand is None or after.hand.number < before.hand.number):
        raise InvariantViolationError("El número de jugada no puede retroceder")
    if before.phase is Phase.GAME_OVER and after != before:
        raise InvariantViolationError("Una partida terminada no puede cambiar")


def _check_cards(state: GameState) -> None:
    hand = state.hand
    if hand is None:
        return
    try:
        validate_complete(hand.all_cards(), state.config.deck_type)
    except InvalidDeckError as exc:
        raise InvariantViolationError(f"Naipes incoherentes: {exc}") from exc
    for player, cards in enumerate(hand.hands):
        if len(cards) != state.config.cards_per_hand:
            raise InvariantViolationError(f"El jugador {player} tiene {len(cards)} naipes")


def _check_positions(state: GameState) -> None:
    hand = state.hand
    if hand is not None and hand.mano != mano_for_dealer(hand.dealer):
        raise InvariantViolationError("La mano no es el jugador a la derecha del que reparte")


def _check_mus(state: GameState) -> None:
    hand = state.hand
    if hand is None:
        return
    mus = hand.mus
    if not 0 <= mus.speaker_index < NUM_SEATS:
        raise InvariantViolationError(f"Turno de mus fuera de rango: {mus.speaker_index}")
    if state.phase in (Phase.MUS_DECISION, Phase.DISCARD) and mus.is_cut:
        raise InvariantViolationError("No puede haber mus ni descartes tras cortarse el mus")
    if state.phase is Phase.LANCE and not mus.is_cut:
        raise InvariantViolationError("No se juegan lances sin cortar el mus")
    if state.phase is not Phase.DISCARD and any(d is not None for d in mus.discards):
        raise InvariantViolationError("Descartes pendientes fuera de la fase de descarte")
    for player, cards in enumerate(mus.discards):
        if cards is not None and not cards <= set(hand.hands[player]):
            raise InvariantViolationError(f"El descarte del jugador {player} no es de su mano")


def _check_bet(state: GameState) -> None:
    hand = state.hand
    if state.phase is not Phase.LANCE:
        return
    bet = None if hand is None else hand.bet
    if hand is None or bet is None:
        raise InvariantViolationError("Fase LANCE sin envite")
    if bet.lance is not hand.lance:
        raise InvariantViolationError("El envite no corresponde al lance en curso")
    if bet.status.is_closed or not bet.to_act:
        raise InvariantViolationError(f"Envite cerrado o sin turno en fase LANCE: {bet}")
    if not set(bet.to_act) <= set(bet.participants):
        raise InvariantViolationError("Habla un jugador que no participa en el lance")
    if len({team_of(p) for p in bet.participants}) != 2:
        raise InvariantViolationError("Hay envites sin que participen las dos parejas")
    if bet.status is BetStatus.PENDING:
        if bet.proposer is None or any(are_teammates(p, bet.proposer) for p in bet.to_act):
            raise InvariantViolationError("Con un envite pendiente sólo contestan los rivales")
        if not bet.is_ordago and not 0 <= bet.accepted < bet.pending:
            raise InvariantViolationError(f"Importes de envite incoherentes: {bet}")
    elif bet.proposer is not None or bet.accepted or bet.pending:
        raise InvariantViolationError(f"Lance abierto con envite registrado: {bet}")


def _check_score(state: GameState) -> None:
    target = state.config.target_score
    finished = state.phase is Phase.GAME_OVER
    if finished != (state.winner is not None):
        raise InvariantViolationError("Hay ganador si y sólo si la partida ha terminado")
    if state.winner is None:
        for team in TeamId:
            if state.score.tantos_of(team) >= target:
                raise InvariantViolationError(f"La pareja {team.name} alcanzó {target} sin ganar")
