"""Juego aleatorio con acciones legales, guiado por Hypothesis."""

from __future__ import annotations

from hypothesis import strategies as st

from mus_engine import Action, Game
from mus_engine.players import SeatId


def play_random_legal(
    game: Game, data: st.DataObject, max_steps: int
) -> list[tuple[SeatId, Action]]:
    """Aplica hasta ``max_steps`` acciones legales elegidas al azar. Devuelve las aplicadas."""
    played: list[tuple[SeatId, Action]] = []
    while len(played) < max_steps and game.current_actors():
        player = data.draw(st.sampled_from(game.current_actors()))
        options = list(game.get_legal_actions(player))
        assert options, "un jugador con turno debe tener alguna acción legal"
        action = data.draw(st.sampled_from(options))
        game.apply_action(player, action)
        played.append((player, action))
    return played
