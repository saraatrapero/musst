from __future__ import annotations

from musst.rules import RulesEngine
from musst.state import GameState


def build_player_observation(
    state: GameState,
    player_id: str,
    rules_engine: RulesEngine,
) -> dict[str, object]:
    """Build a player-specific view that hides private cards from others."""
    if player_id not in state.player_order:
        raise ValueError("Unknown player")

    players_view: dict[str, dict[str, object]] = {}
    for pid in state.player_order:
        if pid == player_id:
            players_view[pid] = {
                "hand": [{"suit": c.suit, "rank": c.rank} for c in state.hands.get(pid, [])],
                "hand_size": len(state.hands.get(pid, [])),
            }
        else:
            players_view[pid] = {
                "hand_size": len(state.hands.get(pid, [])),
            }

    return {
        "you": player_id,
        "phase": state.phase,
        "score": {
            "human_team": state.human_team_points,
            "bot_team": state.bot_team_points,
            "target": state.target_points,
        },
        "players": players_view,
        "legal_actions": sorted(a.value for a in rules_engine.legal_actions(state, player_id)),
    }
