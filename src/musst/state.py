from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from musst.cards import Card


class GamePhase(StrEnum):
    DEALING = "dealing"
    MUS = "mus"
    DISCARD = "discard"
    GRANDE = "grande"
    CHICA = "chica"
    PARES = "pares"
    JUEGO_OR_PUNTO = "juego_or_punto"
    SCORING = "scoring"
    CHECK_GAME_END = "check_game_end"
    FINISHED = "finished"


@dataclass(frozen=True)
class PendingBet:
    bettor_id: str
    amount: int


@dataclass
class GameState:
    player_order: list[str]
    hands: dict[str, list[Card]]
    phase: GamePhase = GamePhase.DEALING
    human_team_points: int = 0
    bot_team_points: int = 0
    target_points: int = 40
    pending_bet: PendingBet | None = None
    metadata: dict[str, str] = field(default_factory=dict)
