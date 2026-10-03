from __future__ import annotations

from dataclasses import dataclass, field

from musst.actions import ActionType, GameAction
from musst.events import ActionRecorded, EventVisibility, GameEvent
from musst.rules import RulesEngine
from musst.state import GameState, PendingBet


@dataclass
class GameEngine:
    state: GameState
    rules: RulesEngine = field(default_factory=RulesEngine)
    history: list[GameEvent] = field(default_factory=list)

    def apply_action(self, action: GameAction) -> None:
        self.rules.validate_action(self.state, action)
        self._reduce(action)
        self.history.append(
            ActionRecorded(
                event_type="ActionRecorded",
                actor_id=action.actor_id,
                action_type=action.action_type,
                payload={"amount": str(action.amount) if action.amount else ""},
                visibility=EventVisibility.PUBLIC,
            )
        )

    def _reduce(self, action: GameAction) -> None:
        if action.action_type == ActionType.BET and action.amount is not None:
            self.state.pending_bet = PendingBet(bettor_id=action.actor_id, amount=action.amount)
        elif action.action_type == ActionType.RAISE and action.amount is not None:
            self.state.pending_bet = PendingBet(bettor_id=action.actor_id, amount=action.amount)
        elif action.action_type in {ActionType.ACCEPT, ActionType.REJECT}:
            self.state.pending_bet = None
