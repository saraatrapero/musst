"""Propiedades del mus con secuencias aleatorias de acciones legales."""

from hypothesis import given, settings
from hypothesis import strategies as st
from tests.strategies import play_random_legal

from mus_engine import Game, Phase
from mus_engine.game import invariants

seeds = st.integers(min_value=0, max_value=2**32)


@settings(max_examples=150)
@given(seeds, st.data())
def test_random_legal_mus_play_keeps_invariants(seed: int, data: st.DataObject) -> None:
    game = Game(seed=seed)
    game.start()
    play_random_legal(game, data, max_steps=60)
    state = game.get_state()
    invariants.check_state(state)
    assert state.phase in (Phase.MUS_DECISION, Phase.DISCARD, Phase.LANCE)


@settings(max_examples=60)
@given(seeds, st.data())
def test_every_legal_action_is_accepted(seed: int, data: st.DataObject) -> None:
    """Toda acción listada como legal es aceptada (sobre una copia del estado)."""
    from tests.factories import game_with_state

    game = Game(seed=seed)
    game.start()
    play_random_legal(game, data, max_steps=data.draw(st.integers(0, 20)))
    for player in game.current_actors():
        for action in game.get_legal_actions(player):
            probe = game_with_state(game.get_state())
            probe.apply_action(player, action)


@settings(max_examples=40)
@given(seeds, st.data())
def test_same_seed_and_actions_reproduce_game(seed: int, data: st.DataObject) -> None:
    """Determinismo: repetir semilla y acciones produce los mismos estados y eventos."""
    first = Game(seed=seed)
    first.start()
    played = play_random_legal(first, data, max_steps=40)
    second = Game(seed=seed)
    second.start()
    for player, action in played:
        second.apply_action(player, action)
    assert second.get_state() == first.get_state()
    assert second.event_log == first.event_log
