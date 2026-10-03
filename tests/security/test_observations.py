"""Seguridad de las observaciones: sin información ajena e inmutables."""

import dataclasses

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from tests.factories import game_at_lance, started_game
from tests.play import all_mus, discard_all, pass_lance
from tests.strategies import play_seeded
from tests.visibility import cards_in, cards_known

from mus_engine import Game, Observation, Phase
from mus_engine.cards import Deck
from mus_engine.errors import PrivateInformationError
from mus_engine.events import Visibility
from mus_engine.players import ALL_SEATS

HANDS = ("12O 12C 12E 1B", "1C 1E 4O 5O", "7O 7C 6E 5B", "11O 10C 2B 4B")


def test_observation_contains_own_hand_only() -> None:
    game = started_game(first_dealer=3)
    state = game.get_state().current_hand
    for seat in ALL_SEATS:
        obs = game.get_observation(seat)
        assert obs.my_hand == state.hand_of(seat)
        assert obs.revealed_hands is None
        others = {c for p in ALL_SEATS if p != seat for c in state.hand_of(p)}
        assert not (cards_in(obs) & others)
        assert not (cards_in(obs) & set(state.stock.cards))


def test_observation_has_no_engine_or_foreign_private_events() -> None:
    game = started_game()
    all_mus(game)
    discard_all(game, 2)
    for seat in ALL_SEATS:
        for env in game.get_observation(seat).events:
            assert env.visibility is not Visibility.ENGINE
            assert env.visibility is Visibility.PUBLIC or env.audience == seat


def test_observation_does_not_expose_deck_or_seed() -> None:
    game = started_game(seed=987654321)
    obs = game.get_observation(0)
    stack: list[object] = [obs]
    while stack:
        item = stack.pop()
        assert not isinstance(item, Deck)
        assert item != 987654321
        if dataclasses.is_dataclass(item) and not isinstance(item, type):
            stack.extend(getattr(item, f.name) for f in dataclasses.fields(item))
        elif isinstance(item, (tuple, list, frozenset, set)):
            stack.extend(item)
    assert not hasattr(obs, "stock")


def test_discard_counts_are_public_but_cards_are_not() -> None:
    game = started_game(first_dealer=3)
    all_mus(game)
    from tests.play import actor, hand_of

    from mus_engine import DiscardAction

    first = actor(game)  # el que reparte
    game.apply_action(first, DiscardAction(hand_of(game, first)[:3]))
    for seat in ALL_SEATS:
        obs = game.get_observation(seat)
        assert obs.discard_counts[first] == 3
        if seat != first:
            assert not (cards_in(obs) & set(hand_of(game, first)[:3]) - set(obs.my_hand))


def test_observation_is_immutable() -> None:
    game = started_game()
    obs = game.get_observation(0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        obs.my_hand = ()  # type: ignore[misc]
    with pytest.raises(AttributeError):
        obs.my_hand.append(obs.my_hand[0])  # type: ignore[attr-defined]
    with pytest.raises(dataclasses.FrozenInstanceError):
        obs.score.tantos = (40, 0)  # type: ignore[misc]


def test_modifying_a_copy_does_not_affect_the_game() -> None:
    game = started_game()
    before = game.get_state()
    obs = game.get_observation(0)
    hacked = dataclasses.replace(obs, my_hand=())
    assert hacked.my_hand == ()
    assert game.get_state() is before
    assert game.get_observation(0).my_hand == before.current_hand.hand_of(0)  # type: ignore[arg-type]


def test_revealed_hands_after_scoring() -> None:
    game = game_at_lance(HANDS)
    for _ in range(3):
        pass_lance(game)
    # Nueva jugada: la observación vuelve a ocultar las manos ajenas.
    assert game.get_observation(1).revealed_hands is None
    revealed = [
        e for e in game.get_observation(1).events if type(e.event).__name__ == "HandsRevealed"
    ]
    assert len(revealed) == 1


def test_observation_of_lance() -> None:
    game = game_at_lance(HANDS)
    obs = game.get_observation(0)
    assert isinstance(obs, Observation)
    assert obs.phase is Phase.LANCE
    assert obs.is_my_turn
    assert obs.bet is not None
    assert obs.bet.participants == (0, 1, 2, 3)
    assert obs.legal_actions == game.get_legal_actions(0)
    assert not game.get_observation(1).is_my_turn
    assert not game.get_observation(1).legal_actions


def test_get_hand_respects_privacy() -> None:
    game = started_game()
    assert game.get_hand(0, 0) == game.get_observation(0).my_hand
    with pytest.raises(PrivateInformationError):
        game.get_hand(1, 0)


def test_get_hand_before_start() -> None:
    from mus_engine.errors import GameNotStartedError

    with pytest.raises(GameNotStartedError):
        Game(seed=1).get_hand(0, 0)


def test_observation_before_start() -> None:
    obs = Game(seed=1).get_observation(2)
    assert obs.phase is Phase.NOT_STARTED
    assert obs.my_hand == ()
    assert obs.mano is None


@settings(max_examples=40, deadline=None)
@given(st.integers(0, 2**32), st.integers(0, 2**32), st.integers(0, 300))
def test_observations_never_leak_during_random_games(seed: int, choices: int, steps: int) -> None:
    game = Game(seed=seed)
    game.start()
    play_seeded(game, choices, steps)
    for seat in ALL_SEATS:
        assert cards_in(game.get_observation(seat)) <= cards_known(game, seat)
