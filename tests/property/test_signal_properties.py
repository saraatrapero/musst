"""Propiedades de partidas con señas y miradas activadas."""

from hypothesis import given, settings
from hypothesis import strategies as st
from tests.factories import game_with_state
from tests.strategies import play_seeded_with_signals
from tests.visibility import cards_in, cards_known

from mus_engine import Game, GameConfig, GameRecord, GameReplay
from mus_engine.errors import MusEngineError
from mus_engine.game import invariants
from mus_engine.game.actions import SignalAction
from mus_engine.players import ALL_SEATS
from mus_engine.rules.signals import Signal

seeds = st.integers(0, 2**32)
CONFIG = GameConfig(signals_enabled=True)


@settings(max_examples=40, deadline=None)
@given(seeds, seeds, st.integers(0, 400))
def test_random_games_with_signals_keep_invariants(seed: int, choices: int, steps: int) -> None:
    game = Game(seed=seed, config=CONFIG)
    game.start()
    play_seeded_with_signals(game, choices, steps)
    invariants.check_state(game.get_state())
    for seat in ALL_SEATS:
        assert cards_in(game.get_observation(seat)) <= cards_known(game, seat)


@settings(max_examples=40, deadline=None)
@given(seeds, seeds, st.integers(0, 120))
def test_every_signal_accepted_iff_legal(seed: int, choices: int, steps: int) -> None:
    game = Game(seed=seed, config=CONFIG)
    game.start()
    play_seeded_with_signals(game, choices, steps)
    state = game.get_state()
    for seat in ALL_SEATS:
        legal = game.get_legal_actions(seat)
        for signal in Signal:
            action = SignalAction(signal)
            probe = game_with_state(state)
            try:
                probe.apply_action(seat, action)
            except MusEngineError:
                assert not legal.contains(action)
                assert probe.get_state() is state
            else:
                assert legal.contains(action)


@settings(max_examples=30, deadline=None)
@given(seeds, seeds, st.integers(0, 600))
def test_games_with_signals_replay_from_events(seed: int, choices: int, steps: int) -> None:
    game = Game(seed=seed, config=GameConfig(signals_enabled=True, games_to_win=2))
    game.start()
    play_seeded_with_signals(game, choices, steps)
    record = GameRecord.from_events(game.event_log) if _discards_served(game) else game.record
    replay = GameReplay(record)
    assert replay.jump_to(len(replay)) == game.get_state()
    assert replay.event_log == game.event_log


def _discards_served(game: Game) -> bool:
    hand = game.get_state().hand
    return hand is None or all(d is None for d in hand.mus.discards)


@settings(max_examples=20, deadline=None)
@given(seeds, seeds)
def test_signal_games_finish(seed: int, choices: int) -> None:
    game = Game(seed=seed, config=CONFIG)
    game.start()
    play_seeded_with_signals(game, choices, 50000)
    assert game.is_finished
