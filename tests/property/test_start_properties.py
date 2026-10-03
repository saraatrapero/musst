"""Propiedades del inicio de partida para semillas arbitrarias."""

from hypothesis import given, settings
from hypothesis import strategies as st

from mus_engine import Game, Phase
from mus_engine.game import invariants

seeds = st.integers(min_value=0, max_value=2**63 - 1)


@settings(max_examples=100)
@given(seeds)
def test_start_always_reaches_mus_with_valid_state(seed: int) -> None:
    game = Game(seed=seed)
    game.start()
    state = game.get_state()
    assert state.phase is Phase.MUS_DECISION
    invariants.check_state(state)


@settings(max_examples=50)
@given(seeds)
def test_start_is_deterministic(seed: int) -> None:
    a, b = Game(seed=seed), Game(seed=seed)
    a.start()
    b.start()
    assert a.event_log == b.event_log
