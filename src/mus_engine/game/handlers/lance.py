"""Fase de decisión ``LANCE``: envites, revoques, quiero, no quiero y órdago."""

from __future__ import annotations

from dataclasses import replace

from mus_engine.betting import bets
from mus_engine.betting.bets import BetState, BetStatus
from mus_engine.errors import (
    IllegalActionError,
    InvalidBetError,
    InvalidStateError,
    InvariantViolationError,
)
from mus_engine.events.events import (
    BetAccepted,
    BetPlaced,
    BetRaised,
    BetRejected,
    Emission,
    Event,
    OrdagoAccepted,
    OrdagoDeclared,
    Passed,
)
from mus_engine.game.actions import (
    AcceptAction,
    Action,
    BetAction,
    OrdagoAction,
    PassAction,
    RaiseAction,
    RejectAction,
)
from mus_engine.game.lance_flow import close_bet
from mus_engine.game.legal import AmountRange, LegalActions
from mus_engine.game.state import GameState
from mus_engine.game.transition import Step
from mus_engine.players.seating import SeatId

_BET_ACTIONS = (PassAction, BetAction, RaiseAction, AcceptAction, RejectAction, OrdagoAction)


def _bet(state: GameState) -> BetState:
    bet = state.current_hand.bet
    if bet is None:
        raise InvariantViolationError("Fase LANCE sin envite")
    return bet


class LanceHandler:
    def actors(self, state: GameState) -> tuple[SeatId, ...]:
        return (_bet(state).to_act[0],)

    def legal_actions(self, state: GameState, player: SeatId) -> LegalActions:
        bet = _bet(state)
        config = state.config
        if bet.status is BetStatus.OPEN:
            return LegalActions(
                actions=(PassAction(), OrdagoAction()), bet=AmountRange(config.min_bet)
            )
        if bet.is_ordago:
            return LegalActions(actions=(AcceptAction(), RejectAction()))
        return LegalActions(
            actions=(AcceptAction(), RejectAction(), OrdagoAction()),
            raise_=AmountRange(config.min_raise),
        )

    def explain_illegal(
        self, state: GameState, player: SeatId, action: Action
    ) -> IllegalActionError:
        bet = _bet(state)
        lance = bet.lance.value
        if not isinstance(action, _BET_ACTIONS):
            return InvalidStateError(
                f"{type(action).__name__} no es válida durante los envites de {lance}"
            )
        if bet.status is BetStatus.OPEN:
            if isinstance(action, (AcceptAction, RejectAction, RaiseAction)):
                return InvalidBetError(f"No hay ningún envite pendiente en {lance}")
            return InvalidBetError(f"El envite mínimo es {state.config.min_bet}")
        if bet.is_ordago:
            return InvalidBetError(f"Hay un órdago pendiente en {lance}: sólo quiero o no quiero")
        if isinstance(action, (PassAction, BetAction)):
            return InvalidBetError(
                f"Hay un envite pendiente en {lance}: quiero, no quiero, revoque u órdago"
            )
        return InvalidBetError(f"El revoque mínimo es {state.config.min_raise} más")

    def apply(self, state: GameState, player: SeatId, action: Action) -> Step:
        bet = _bet(state)
        lance = bet.lance.value
        config = state.config
        event: Event
        if isinstance(action, PassAction):
            new_bet, event = bets.apply_pass(bet, player), Passed(player, lance)
        elif isinstance(action, BetAction):
            new_bet = bets.apply_bet(bet, player, action.amount, config)
            event = BetPlaced(player, lance, action.amount)
        elif isinstance(action, RaiseAction):
            new_bet = bets.apply_raise(bet, player, action.amount, config)
            event = BetRaised(player, lance, action.amount, new_bet.pending)
        elif isinstance(action, OrdagoAction):
            new_bet, event = bets.apply_ordago(bet, player), OrdagoDeclared(player, lance)
        elif isinstance(action, AcceptAction):
            new_bet = bets.apply_accept(bet, player)
            event = (
                OrdagoAccepted(player, lance)
                if bet.is_ordago
                else BetAccepted(player, lance, new_bet.accepted)
            )
        elif isinstance(action, RejectAction):
            new_bet, event = bets.apply_reject(bet, player), BetRejected(player, lance)
        else:  # pragma: no cover - ya validado
            raise InvariantViolationError(f"Acción no prevista en LANCE: {action}")
        emitted = (Emission.public(event),)
        if not new_bet.status.is_closed:
            return state.evolve(hand=replace(state.current_hand, bet=new_bet)), emitted
        new_state, closing = close_bet(state, new_bet)
        return new_state, emitted + closing
