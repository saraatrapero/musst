"""Información privada durante el mus y los descartes."""

from tests.factories import started_game
from tests.play import actor, all_mus, discard_all, hand_of
from tests.visibility import cards_ever_held, cards_in

from mus_engine import DiscardAction
from mus_engine.events import CardsDiscarded, DiscardDeclared, Visibility
from mus_engine.players import ALL_SEATS


def test_discarded_and_received_cards_are_private() -> None:
    game = started_game(first_dealer=3)
    all_mus(game)
    discard_all(game, 3)
    for env in game.event_log:
        if isinstance(env.event, CardsDiscarded):
            assert env.visibility is Visibility.PRIVATE
            assert env.audience == env.event.seat
        if isinstance(env.event, DiscardDeclared):
            assert env.visibility is Visibility.PUBLIC


def test_players_only_know_cards_they_have_held() -> None:
    """Ningún evento visible para un jugador contiene un naipe que él no haya tenido."""
    game = started_game(first_dealer=3)
    for count in (2, 4, 4, 3):
        all_mus(game)
        discard_all(game, count)
    for viewer in ALL_SEATS:
        known = cards_ever_held(game, viewer)
        assert cards_in(game.get_events(viewer)) <= known
        assert set(hand_of(game, viewer)) <= known


def test_apply_action_returns_only_events_visible_to_actor() -> None:
    game = started_game(first_dealer=3)
    all_mus(game)
    for _ in range(4):
        player = actor(game)
        returned = game.apply_action(player, DiscardAction(hand_of(game, player)[:1]))
        assert all(e.visible_to(player) for e in returned)


def test_legal_discards_only_mention_own_cards() -> None:
    game = started_game()
    all_mus(game)
    player = actor(game)
    own = set(hand_of(game, player))
    for action in game.get_legal_actions(player).actions:
        assert action.cards <= own  # type: ignore[attr-defined]
    for other in ALL_SEATS:
        if other != player:
            assert not game.get_legal_actions(other)
