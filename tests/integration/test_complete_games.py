"""Partidas completas reproducibles por semilla, de principio a fin."""

import itertools

from tests.play import actor

from mus_engine import CutMusAction, Game, GameConfig, PassAction, Phase
from mus_engine.events import GameFinished, GameWon, HandStarted, PointsAwarded
from mus_engine.game import invariants


def play_always_pass(game: Game) -> None:
    """Política fija: la mano corta el mus y todos pasan en todos los lances."""
    while not game.is_finished:
        player = actor(game)
        action = CutMusAction() if game.phase is Phase.MUS_DECISION else PassAction()
        game.apply_action(player, action)


def test_always_pass_game_is_reproducible() -> None:
    a = Game(seed=123)
    a.start()
    play_always_pass(a)
    b = Game(seed=123)
    b.start()
    play_always_pass(b)
    assert a.event_log == b.event_log
    assert a.winner == b.winner
    assert a.winner is not None


def test_always_pass_game_scores_every_hand() -> None:
    game = Game(seed=123, config=GameConfig(games_to_win=2))
    game.start()
    play_always_pass(game)
    invariants.check_state(game.get_state())
    hands = [e.event for e in game.event_log if isinstance(e.event, HandStarted)]
    awarded = [e.event for e in game.event_log if isinstance(e.event, PointsAwarded)]
    won = [e.event for e in game.event_log if isinstance(e.event, GameWon)]
    finished = [e.event for e in game.event_log if isinstance(e.event, GameFinished)]
    assert len(hands) >= 2 * 40 // 9  # en paso se anotan como mucho 9 tantos por jugada
    # En cada jugada se anotan grande y chica en paso (1 + 1) como mínimo.
    assert len(awarded) >= 2 * len(hands) - 2
    assert len(won) in (2, 3)
    assert len(finished) == 1
    assert game.get_state().score.games_of(game.winner) == 2  # type: ignore[arg-type]
    # Los repartidores rotan (D-15).
    dealers = [h.dealer for h in hands]
    assert all((b - a) % 4 == 1 for a, b in itertools.pairwise(dealers))
