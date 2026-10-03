"""Juego aleatorio con acciones legales, guiado por Hypothesis."""

from __future__ import annotations

from hypothesis import strategies as st

from mus_engine import Action, BetAction, Game, RaiseAction
from mus_engine.players import SeatId


def legal_choices(game: Game, player: SeatId, data: st.DataObject) -> list[Action]:
    """Acciones legales concretas, con importes de envite y revoque aleatorios."""
    legal = game.get_legal_actions(player)
    choices: list[Action] = list(legal.actions)
    if legal.bet is not None:
        choices.append(BetAction(data.draw(st.integers(legal.bet.minimum, legal.bet.minimum + 10))))
    if legal.raise_ is not None:
        choices.append(
            RaiseAction(data.draw(st.integers(legal.raise_.minimum, legal.raise_.minimum + 10)))
        )
    return choices


def play_random_legal(
    game: Game, data: st.DataObject, max_steps: int
) -> list[tuple[SeatId, Action]]:
    """Aplica hasta ``max_steps`` acciones legales elegidas al azar. Devuelve las aplicadas."""
    played: list[tuple[SeatId, Action]] = []
    while len(played) < max_steps and game.current_actors():
        player = data.draw(st.sampled_from(game.current_actors()))
        options = legal_choices(game, player, data)
        assert options, "un jugador con turno debe tener alguna acción legal"
        action = data.draw(st.sampled_from(options))
        game.apply_action(player, action)
        played.append((player, action))
    return played


def play_seeded(game: Game, choice_seed: int, max_steps: int) -> list[tuple[SeatId, Action]]:
    """Como :func:`play_random_legal` pero con un ``random.Random`` propio.

    Para partidas largas (completas), donde Hypothesis generaría demasiados datos.
    """
    import random

    rng = random.Random(choice_seed)
    played: list[tuple[SeatId, Action]] = []
    while len(played) < max_steps and game.current_actors():
        player = rng.choice(game.current_actors())
        legal = game.get_legal_actions(player)
        options: list[Action] = list(legal.actions)
        if legal.bet is not None:
            options.append(BetAction(rng.randint(legal.bet.minimum, legal.bet.minimum + 10)))
        if legal.raise_ is not None:
            options.append(
                RaiseAction(rng.randint(legal.raise_.minimum, legal.raise_.minimum + 10))
            )
        action = rng.choice(options)
        game.apply_action(player, action)
        played.append((player, action))
    return played
