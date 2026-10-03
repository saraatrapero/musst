"""Inicio de partida: sorteo, reparto, determinismo y errores de la fachada."""

import dataclasses

import pytest
from tests.factories import game_with_state, started_game

from mus_engine import (
    CutMusAction,
    Game,
    GameConfig,
    GameScore,
    MusAction,
    Phase,
    Table,
)
from mus_engine.errors import (
    GameFinishedError,
    GameNotStartedError,
    IllegalActionError,
    InvalidConfigError,
    InvalidPlayerError,
    InvalidStateError,
)
from mus_engine.events import CardsDealt, FirstDealerDrawn, FirstDealerFixed, HandStarted
from mus_engine.players import SeatId, TeamId, mano_for_dealer

NAMES = ("Ana", "Bea", "Carlos", "Dani")


def test_new_game_is_not_started() -> None:
    game = Game(players=NAMES, seed=1)
    assert game.phase is Phase.NOT_STARTED
    assert game.get_state().hand is None
    assert game.event_log == ()
    with pytest.raises(GameNotStartedError):
        game.apply_action(0, MusAction())
    with pytest.raises(GameNotStartedError):
        _ = game.mano


def test_start_deals_and_waits_for_mus() -> None:
    game = started_game()
    state = game.get_state()
    assert game.phase is Phase.MUS_DECISION
    assert state.hand is not None
    assert state.hand.number == 1
    assert all(len(h) == 4 for h in state.hand.hands)
    assert len(state.hand.stock) == 24
    assert state.hand.discard_pile == ()
    assert state.score == GameScore()
    assert game.mano == mano_for_dealer(game.dealer)
    assert game.is_hand(game.mano)
    assert not game.is_hand(game.dealer)


def test_start_twice_is_rejected() -> None:
    game = started_game()
    with pytest.raises(InvalidStateError, match="ya ha empezado"):
        game.start()


def test_same_seed_same_game() -> None:
    a, b = started_game(seed=999), started_game(seed=999)
    assert a.get_state() == b.get_state()
    assert a.event_log == b.event_log


def test_different_seeds_different_hands() -> None:
    hands = {started_game(seed=s).get_state().hand.hands for s in range(30)}  # type: ignore[union-attr]
    assert len(hands) == 30


def test_seed_is_generated_when_missing_and_reproducible() -> None:
    game = Game(players=NAMES)
    game.start()
    replay = Game(players=NAMES, seed=game.seed)
    replay.start()
    assert replay.get_state() == game.get_state()


def test_first_dealer_drawn_event_matches_hand() -> None:
    game = started_game(seed=5)
    drawn = [e.event for e in game.event_log if isinstance(e.event, FirstDealerDrawn)]
    started = [e.event for e in game.event_log if isinstance(e.event, HandStarted)]
    assert len(drawn) == 1
    assert len(started) == 1
    assert drawn[0].dealer == started[0].dealer == game.dealer


@pytest.mark.parametrize("dealer", [0, 1, 2, 3])
def test_first_dealer_can_be_fixed(dealer: int) -> None:
    game = started_game(first_dealer=dealer)
    assert game.dealer == dealer
    assert game.mano == (dealer + 1) % 4
    assert any(isinstance(e.event, FirstDealerFixed) for e in game.event_log)
    assert not any(isinstance(e.event, FirstDealerDrawn) for e in game.event_log)


def test_cards_dealt_events_match_hands() -> None:
    game = started_game()
    state = game.get_state()
    assert state.hand is not None
    dealt = {e.audience: e.event for e in game.event_log if isinstance(e.event, CardsDealt)}
    assert set(dealt) == {0, 1, 2, 3}
    for player, event in dealt.items():
        assert event.cards == state.hand.hand_of(SeatId(player))  # type: ignore[arg-type]


def test_event_sequence_numbers_are_contiguous() -> None:
    game = started_game()
    assert [e.seq for e in game.event_log] == list(range(len(game.event_log)))


def test_lance_actions_not_available_yet() -> None:
    # Frontera de la fase 4: los lances se implementan en las fases siguientes.
    game = started_game()
    game.apply_action(game.mano, CutMusAction())
    assert game.phase is Phase.LANCE
    assert game.current_actors() == ()
    with pytest.raises(InvalidStateError):
        game.apply_action(game.mano, MusAction())


@pytest.mark.parametrize("player", [-1, 4, "0", None, True, 1.0])
def test_invalid_player_ids(player: object) -> None:
    game = started_game()
    with pytest.raises(InvalidPlayerError):
        game.apply_action(player, MusAction())  # type: ignore[arg-type]
    with pytest.raises(InvalidPlayerError):
        game.get_legal_actions(player)  # type: ignore[arg-type]


def test_non_action_rejected() -> None:
    game = started_game()
    with pytest.raises(IllegalActionError):
        game.apply_action(0, "mus")  # type: ignore[arg-type]


def test_finished_game_rejects_actions() -> None:
    state = started_game().get_state()
    over = state.evolve(phase=Phase.GAME_OVER, winner=TeamId.A, score=GameScore((40, 12)))
    game = game_with_state(over)
    assert game.is_finished
    assert game.winner is TeamId.A
    with pytest.raises(GameFinishedError):
        game.apply_action(0, MusAction())
    assert not game.get_legal_actions(0)


def test_team_queries() -> None:
    game = started_game()
    assert game.get_partner(1).id == 3
    assert game.get_team(2).id is TeamId.A
    assert game.are_teammates(1, 3)
    assert not game.are_teammates(0, 1)
    assert game.next_player(3) == 0
    assert game.previous_player(0) == 3
    assert game.get_player(2).name == "Carlos"


def test_construction_errors() -> None:
    with pytest.raises(InvalidPlayerError):
        Game(players=("A", "B", "C"))
    with pytest.raises(InvalidPlayerError):
        Game(players="ABCD")
    with pytest.raises(InvalidConfigError):
        Game(config="config")  # type: ignore[arg-type]
    with pytest.raises(InvalidConfigError):
        Game(seed="123")  # type: ignore[arg-type]
    with pytest.raises(InvalidConfigError):
        Game(seed=True)
    with pytest.raises(InvalidConfigError):
        GameConfig(first_dealer=4)
    with pytest.raises(InvalidConfigError):
        GameConfig(first_shuffler=-1)


def test_accepts_table_instance() -> None:
    game = Game(players=Table.from_names(NAMES), seed=3)
    assert game.get_player(0).name == "Ana"


def test_state_cannot_be_modified_from_outside() -> None:
    game = started_game()
    state = game.get_state()
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.score = GameScore((39, 0))  # type: ignore[misc]
    assert state.hand is not None
    with pytest.raises(AttributeError):
        state.hand.hands[0].append(None)  # type: ignore[attr-defined]
