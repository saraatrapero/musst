from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ActionType(StrEnum):
    MUS = "mus"
    NO_MUS = "no_mus"
    DISCARD = "discard"
    PASS = "pass"
    BET = "bet"
    ACCEPT = "accept"
    REJECT = "reject"
    RAISE = "raise"
    ORDAGO = "ordago"


@dataclass(frozen=True)
class GameAction:
    actor_id: str
    action_type: ActionType
    amount: int | None = None
    metadata: dict[str, str] = field(default_factory=dict)
