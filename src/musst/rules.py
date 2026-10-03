from __future__ import annotations

from musst.actions import ActionType, GameAction
from musst.state import GamePhase, GameState


class RulesEngine:
    """Server-side authority for legal actions."""

    def legal_actions(self, state: GameState, player_id: str) -> set[ActionType]:
        if player_id not in state.player_order:
            return set()

        if state.phase == GamePhase.MUS:
            return {ActionType.MUS, ActionType.NO_MUS}

        if state.phase == GamePhase.DISCARD:
            return {ActionType.DISCARD}

        if state.phase in {
            GamePhase.GRANDE,
            GamePhase.CHICA,
            GamePhase.PARES,
            GamePhase.JUEGO_OR_PUNTO,
        }:
            actions = {ActionType.PASS, ActionType.BET, ActionType.ORDAGO}
            if state.pending_bet is not None and state.pending_bet.bettor_id != player_id:
                actions |= {ActionType.ACCEPT, ActionType.REJECT, ActionType.RAISE}
            return actions

        return set()

    def validate_action(self, state: GameState, action: GameAction) -> None:
        legal = self.legal_actions(state, action.actor_id)
        if action.action_type not in legal:
            raise ValueError(f"Illegal action '{action.action_type}' for phase '{state.phase}'")

        if action.action_type in {ActionType.BET, ActionType.RAISE}:
            if action.amount is None or action.amount <= 0:
                raise ValueError("Bet and raise actions require amount > 0")
