"""Información privada tras el reparto."""

from tests.factories import started_game

from mus_engine.events import CardsDealt, DeckShuffled, RngSeeded, Visibility
from mus_engine.players import ALL_SEATS


def test_public_events_reveal_no_dealt_card() -> None:
    game = started_game(first_dealer=0)  # sin sorteo: ningún naipe público legítimo
    state = game.get_state()
    assert state.hand is not None
    public = repr(game.get_events())
    for card in state.hand.all_cards():
        assert repr(card) not in public


def test_player_sees_only_own_cards() -> None:
    game = started_game(first_dealer=0)
    state = game.get_state()
    assert state.hand is not None
    for viewer in ALL_SEATS:
        visible = repr(game.get_events(viewer))
        for other in ALL_SEATS:
            for card in state.hand.hand_of(other):
                assert (repr(card) in visible) == (other == viewer)
        for card in state.hand.stock.cards:
            assert repr(card) not in visible


def test_engine_events_never_reach_players() -> None:
    game = started_game()
    for viewer in ALL_SEATS:
        for env in game.get_events(viewer):
            assert env.visibility is not Visibility.ENGINE
            assert not isinstance(env.event, (RngSeeded, DeckShuffled))
    assert any(isinstance(e.event, RngSeeded) for e in game.event_log)


def test_start_returns_only_public_events() -> None:
    from mus_engine import Game

    game = Game(seed=4)
    returned = game.start()
    assert all(e.visibility is Visibility.PUBLIC for e in returned)
    assert not any(isinstance(e.event, CardsDealt) for e in returned)


def test_private_deal_events_have_correct_audience() -> None:
    game = started_game()
    for env in game.event_log:
        if isinstance(env.event, CardsDealt):
            assert env.visibility is Visibility.PRIVATE
            assert env.audience == env.event.seat
