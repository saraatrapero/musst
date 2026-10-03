"""Propiedades de partidas completas con acciones legales aleatorias."""

from hypothesis import given, settings
from hypothesis import strategies as st
from tests.factories import game_with_state
from tests.strategies import legal_choices, play_random_legal, play_seeded
from tests.visibility import cards_in, cards_known

from mus_engine import Game, GameConfig, Phase
from mus_engine.events import GameFinished, PointsAwarded
from mus_engine.game import invariants
from mus_engine.players import ALL_SEATS

seeds = st.integers(min_value=0, max_value=2**32)


@settings(max_examples=60, deadline=None)
@given(seeds, seeds, st.integers(1, 3))
def test_random_games_finish_correctly(seed: int, choice_seed: int, games_to_win: int) -> None:
    game = Game(seed=seed, config=GameConfig(games_to_win=games_to_win))
    game.start()
    play_seeded(game, choice_seed, max_steps=20000)
    state = game.get_state()
    invariants.check_state(state)
    assert state.phase is Phase.GAME_OVER, "una partida con acciones legales debe terminar"
    if state.phase is Phase.GAME_OVER:
        assert state.winner is not None
        assert state.score.tantos_of(state.winner) >= state.config.target_score
        finished = [e.event for e in game.event_log if isinstance(e.event, GameFinished)]
        assert len(finished) == 1
        assert finished[0].winner == state.winner.name
        assert state.score.games_of(state.winner) == games_to_win


@settings(max_examples=40, deadline=None)
@given(seeds, st.data())
def test_points_awarded_match_score(seed: int, data: st.DataObject) -> None:
    game = Game(seed=seed)
    game.start()
    play_random_legal(game, data, max_steps=400)
    tantos = [0, 0]
    for env in game.event_log:
        if isinstance(env.event, PointsAwarded):
            index = 0 if env.event.team == "A" else 1
            tantos[index] += env.event.points
            assert env.event.tantos_after[index] == tantos[index]
    if game.get_state().score.games == (0, 0):
        assert tuple(tantos) == game.get_state().score.tantos


@settings(max_examples=40, deadline=None)
@given(seeds, st.data())
def test_every_listed_action_is_accepted(seed: int, data: st.DataObject) -> None:
    game = Game(seed=seed)
    game.start()
    play_random_legal(game, data, max_steps=data.draw(st.integers(0, 60)))
    for player in game.current_actors():
        for action in legal_choices(game, player, data):
            game_with_state(game.get_state()).apply_action(player, action)


@settings(max_examples=30, deadline=None)
@given(seeds, st.data())
def test_replaying_actions_reproduces_the_game(seed: int, data: st.DataObject) -> None:
    config = GameConfig(games_to_win=2)
    first = Game(seed=seed, config=config)
    first.start()
    played = play_random_legal(first, data, max_steps=500)
    second = Game(seed=seed, config=config)
    second.start()
    for player, action in played:
        second.apply_action(player, action)
    assert second.get_state() == first.get_state()
    assert second.event_log == first.event_log


@settings(max_examples=40, deadline=None)
@given(seeds, st.data())
def test_players_never_see_unknown_cards(seed: int, data: st.DataObject) -> None:
    game = Game(seed=seed)
    game.start()
    play_random_legal(game, data, max_steps=200)
    for viewer in ALL_SEATS:
        assert cards_in(game.get_events(viewer)) <= cards_known(game, viewer)
