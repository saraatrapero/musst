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


def play_seeded_without_ordago(
    game: Game, choice_seed: int, max_steps: int
) -> list[tuple[SeatId, Action]]:
    """Como :func:`play_seeded` pero sin órdagos: partidas largas, de muchas jugadas."""
    import random

    from mus_engine import OrdagoAction

    rng = random.Random(choice_seed)
    played: list[tuple[SeatId, Action]] = []
    while len(played) < max_steps and game.current_actors():
        player = rng.choice(game.current_actors())
        legal = game.get_legal_actions(player)
        options: list[Action] = [a for a in legal.actions if not isinstance(a, OrdagoAction)]
        if legal.bet is not None:
            options.append(BetAction(rng.randint(legal.bet.minimum, legal.bet.minimum + 4)))
        if legal.raise_ is not None:
            options.append(RaiseAction(rng.randint(legal.raise_.minimum, legal.raise_.minimum + 2)))
        action = rng.choice(options)
        game.apply_action(player, action)
        played.append((player, action))
    return played


def play_seeded_with_signals(game: Game, choice_seed: int, max_steps: int) -> int:
    """Juego aleatorio con señas de cualquier asiento y pasos del reloj. Devuelve los pasos."""
    import random

    from mus_engine.game.actions import SignalAction

    rng = random.Random(choice_seed)
    steps = 0
    while steps < max_steps and not game.is_finished:
        steps += 1
        roll = rng.random()
        if roll < 0.15:
            game.tick()
            continue
        if roll < 0.35:
            seat = SeatId(rng.randrange(4))
            signals = [
                a for a in game.get_legal_actions(seat).actions if isinstance(a, SignalAction)
            ]
            if signals:
                game.apply_action(seat, rng.choice(signals))
                continue
        (player,) = game.current_actors()
        legal = game.get_legal_actions(player)
        options: list[Action] = [a for a in legal.actions if not isinstance(a, SignalAction)]
        if legal.bet is not None:
            options.append(BetAction(rng.randint(legal.bet.minimum, legal.bet.minimum + 6)))
        if legal.raise_ is not None:
            options.append(RaiseAction(rng.randint(legal.raise_.minimum, legal.raise_.minimum + 4)))
        game.apply_action(player, rng.choice(options))
    return steps
