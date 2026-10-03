from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from musst.actions import GameAction


@dataclass(frozen=True)
class BotDecision:
    action: GameAction
    confidence: float
    evidence: dict[str, float]
    agents_consulted: list[str]


class Bot(Protocol):
    """Public bot API required by the coursework."""

    def decide(self, observation: dict[str, object]) -> BotDecision:
        """Return one legal action proposal for current observation."""
