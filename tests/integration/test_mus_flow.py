"""Flujo completo del mus y los descartes a través de la API pública."""

import pytest
from tests.factories import started_game
from tests.play import actor, all_mus, cut, discard_all, hand_of

from mus_engine import (
    AcceptAction,
    BetAction,
    CutMusAction,
    DiscardAction,
    MusAction,
    PassAction,
    Phase,
)
from mus_engine.cards import Card, Rank, Suit
from mus_engine.errors import InvalidDiscardError, InvalidStateError, NotYourTurnError
from mus_engine.events import (
    CardsDiscarded,
    DiscardDeclared,
    DiscardPileReshuffled,
    MusCut,
    MusRequested,
)
from mus_engine.players import SeatId, discard_order, mus_order
from mus_engine.rules.lance import LanceType


@pytest.fixture
def game():  # type: ignore[no-untyped-def]
    return started_game(seed=2024, first_dealer=3)  # mano = 0


def test_mano_speaks_first(game) -> None:  # type: ignore[no-untyped-def]
    assert game.current_actors() == (0,)
    assert set(game.get_legal_actions(0)) == {MusAction(), CutMusAction()}
    for other in (1, 2, 3):
        assert not game.get_legal_actions(other)
        with pytest.raises(NotYourTurnError):
            game.apply_action(other, MusAction())


def test_mus_turn_order(game) -> None:  # type: ignore[no-untyped-def]
    speakers = []
    for _ in range(4):
        speakers.append(actor(game))
        game.apply_action(speakers[-1], MusAction())
    assert tuple(speakers) == mus_order(game.mano)
    assert game.phase is Phase.DISCARD


def test_mano_cuts(game) -> None:  # type: ignore[no-untyped-def]
    events = game.apply_action(0, CutMusAction())
    assert game.phase is Phase.LANCE
    assert game.get_state().current_hand.lance is LanceType.GRANDE
    assert game.get_state().current_hand.mus.cut_by == 0
    assert any(isinstance(e.event, MusCut) and e.event.seat == 0 for e in events)


def test_third_player_cuts_after_two_mus(game) -> None:  # type: ignore[no-untyped-def]
    game.apply_action(0, MusAction())
    game.apply_action(1, MusAction())
    game.apply_action(2, CutMusAction())
    assert game.phase is Phase.LANCE
    assert game.get_state().current_hand.mus.cut_by == 2
    assert game.get_state().current_hand.mus.requested == (0, 1)


def test_discard_order_dealer_first_mano_last(game) -> None:  # type: ignore[no-untyped-def]
    all_mus(game)
    order = []
    for _ in range(4):
        player = actor(game)
        order.append(player)
        game.apply_action(player, DiscardAction(hand_of(game, player)[:1]))
    assert tuple(order) == discard_order(game.mano) == (3, 2, 1, 0)


def test_discard_legal_actions(game) -> None:  # type: ignore[no-untyped-def]
    all_mus(game)
    player = actor(game)
    legal = game.get_legal_actions(player)
    assert len(legal.actions) == 15
    own = set(hand_of(game, player))
    assert all(isinstance(a, DiscardAction) and a.cards <= own for a in legal.actions)
    assert MusAction() not in set(legal)


def test_after_discards_hands_are_refilled_and_mus_restarts(game) -> None:  # type: ignore[no-untyped-def]
    before = {p: hand_of(game, p) for p in range(4)}
    all_mus(game)
    kept = {}
    for _ in range(4):
        player = actor(game)
        tossed = before[player][:2]
        kept[player] = before[player][2:]
        game.apply_action(player, DiscardAction(tossed))
    assert game.phase is Phase.MUS_DECISION
    state = game.get_state().current_hand
    assert state.mus.round == 2
    assert game.current_actors() == (game.mano,)
    for seat in range(4):
        assert hand_of(game, seat)[:2] == kept[SeatId(seat)]
        assert len(hand_of(game, seat)) == 4
    assert len(state.stock) == 24 - 8
    assert len(state.discard_pile) == 8
    events = game.event_log
    declared = [e.event for e in events if isinstance(e.event, DiscardDeclared)]
    assert [d.count for d in declared] == [2, 2, 2, 2]
    discarded = {e.event.seat: e.event for e in events if isinstance(e.event, CardsDiscarded)}
    for seat in map(SeatId, range(4)):
        assert discarded[seat].discarded == before[seat][:2]
        assert discarded[seat].received == hand_of(game, seat)[2:]


def test_many_mus_rounds_exhaust_and_reshuffle(game) -> None:  # type: ignore[no-untyped-def]
    for _ in range(3):
        all_mus(game)
        discard_all(game, 4)
    reshuffles = [e for e in game.event_log if isinstance(e.event, DiscardPileReshuffled)]
    assert reshuffles
    assert game.phase is Phase.MUS_DECISION
    assert game.get_state().current_hand.mus.round == 4
    cut(game)
    assert game.get_state().phase is Phase.LANCE


@pytest.mark.parametrize("action", [DiscardAction([]), PassAction(), BetAction(2), AcceptAction()])
def test_wrong_actions_during_mus_decision(game, action) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(InvalidStateError):
        game.apply_action(0, action)


@pytest.mark.parametrize("action", [MusAction(), CutMusAction(), PassAction()])
def test_wrong_actions_during_discard(game, action) -> None:  # type: ignore[no-untyped-def]
    all_mus(game)
    with pytest.raises(InvalidStateError):
        game.apply_action(actor(game), action)


def test_discard_other_players_cards(game) -> None:  # type: ignore[no-untyped-def]
    all_mus(game)
    player = actor(game)
    other = (player + 1) % 4
    with pytest.raises(InvalidDiscardError, match="no están en tu mano"):
        game.apply_action(player, DiscardAction(hand_of(game, other)[:1]))


def test_discard_card_not_in_hand_from_stock(game) -> None:  # type: ignore[no-untyped-def]
    all_mus(game)
    player = actor(game)
    stock_card = game.get_state().current_hand.stock.cards[0]
    with pytest.raises(InvalidDiscardError):
        game.apply_action(player, DiscardAction([stock_card]))


def test_discard_zero_cards(game) -> None:  # type: ignore[no-untyped-def]
    all_mus(game)
    with pytest.raises(InvalidDiscardError, match="entre 1 y 4"):
        game.apply_action(actor(game), DiscardAction([]))


def test_discard_too_many_cards(game) -> None:  # type: ignore[no-untyped-def]
    all_mus(game)
    player = actor(game)
    five = (*hand_of(game, player), game.get_state().current_hand.stock.cards[0])
    with pytest.raises(InvalidDiscardError):
        game.apply_action(player, DiscardAction(five))


def test_discard_duplicates_rejected_before_reaching_engine(game) -> None:  # type: ignore[no-untyped-def]
    all_mus(game)
    card = hand_of(game, actor(game))[0]
    with pytest.raises(InvalidDiscardError, match="dos veces"):
        DiscardAction([card, card])


def test_nonexistent_card_cannot_be_built() -> None:
    from mus_engine.errors import InvalidCardError

    with pytest.raises(InvalidCardError):
        Card(8, Suit.OROS)  # type: ignore[arg-type]
    assert Card(Rank.REY, Suit.OROS)


def test_discard_out_of_turn(game) -> None:  # type: ignore[no-untyped-def]
    all_mus(game)
    mano = game.mano
    with pytest.raises(NotYourTurnError):
        game.apply_action(mano, DiscardAction(hand_of(game, mano)[:1]))


def test_no_mus_or_discard_after_cut(game) -> None:  # type: ignore[no-untyped-def]
    cut(game)
    player = actor(game)
    with pytest.raises(InvalidStateError):
        game.apply_action(player, MusAction())
    with pytest.raises(InvalidStateError):
        game.apply_action(player, DiscardAction(hand_of(game, player)[:1]))


def test_rejected_action_leaves_state_untouched(game) -> None:  # type: ignore[no-untyped-def]
    all_mus(game)
    before = game.get_state()
    log = game.event_log
    with pytest.raises(InvalidDiscardError):
        game.apply_action(actor(game), DiscardAction([]))
    assert game.get_state() is before
    assert game.event_log == log


def test_mus_events_are_public(game) -> None:  # type: ignore[no-untyped-def]
    all_mus(game)
    requested = [e for e in game.get_events() if isinstance(e.event, MusRequested)]
    assert [e.event.seat for e in requested] == [0, 1, 2, 3]
