from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from musst.actions import ActionType


class EventVisibility(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"


@dataclass(frozen=True)
class GameEvent:
    event_type: str
    actor_id: str | None
    payload: dict[str, str]
    visibility: EventVisibility = EventVisibility.PUBLIC
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ActionRecorded(GameEvent):
    action_type: ActionType | None = None
