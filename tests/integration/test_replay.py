"""Registro y replay de partidas."""

import dataclasses

import pytest
from tests.factories import started_game
from tests.play import act, actor, all_mus, cut, discard_all
from tests.strategies import play_seeded_without_ordago

from mus_engine import (
    AcceptAction,
    BetAction,
    DiscardAction,
    Game,
    GameConfig,
    GameRecord,
    GameReplay,
    MusAction,
    OrdagoAction,
    PassAction,
)
from mus_engine.errors import IllegalActionError, InvariantViolationError
from mus_engine.events import CardsDealt
from mus_engine.game.legal import NO_ACTIONS
from mus_engine.players import ALL_SEATS


def long_game(seed: int = 2024, games_to_win: int = 1) -> Game:
    game = Game(
        players=("Ana", "Bea", "Carlos", "Dani"),
        seed=seed,
        config=GameConfig(games_to_win=games_to_win),
    )
    game.start()
    play_seeded_without_ordago(game, seed + 1, 100000)
    return game


def test_long_game_finishes_with_many_hands() -> None:
    game = long_game()
    assert game.is_finished
    assert game.get_state().current_hand.number > 3


def test_record_reconstructed_from_events() -> None:
    game = long_game()
    assert GameRecord.from_events(game.event_log) == game.record


def test_replay_from_events_reproduces_every_state() -> None:
    game = long_game(seed=7, games_to_win=2)
    replay = GameReplay.from_events(game.event_log)
    assert len(replay) == len(game.record.actions)
    assert replay.jump_to(len(replay)) == game.get_state()
    assert replay.event_log == game.event_log


def test_replay_from_game() -> None:
    game = long_game(seed=3)
    replay = GameReplay.from_game(game)
    assert replay.record == game.record


def test_navigation() -> None:
    game = long_game(seed=11)
    replay = GameReplay(game.record)
    assert replay.position == 0
    assert replay.at_start
    assert replay.last_action is None
    first = replay.state
    second = replay.next()
    assert replay.position == 1
    assert replay.last_action == game.record.actions[0]
    assert replay.previous() == first
    assert replay.jump_to(len(replay)) == game.get_state()
    assert replay.at_end
    assert replay.jump_to(1) == second
    with pytest.raises(IndexError):
        replay.jump_to(len(replay) + 1)
    with pytest.raises(IndexError):
        replay.jump_to(-1)
    replay.jump_to(0)
    with pytest.raises(IndexError):
        replay.previous()
    replay.jump_to(len(replay))
    with pytest.raises(IndexError):
        replay.next()


def test_events_and_observations_match_the_live_game() -> None:
    game = Game(seed=99)
    game.start()
    snapshots = [{seat: game.get_observation(seat) for seat in ALL_SEATS}]
    for _ in range(25):
        if not game.current_actors():
            break
        player = actor(game)
        action = next(iter(game.get_legal_actions(player)))
        game.apply_action(player, action)
        snapshots.append({seat: game.get_observation(seat) for seat in ALL_SEATS})
    replay = GameReplay.from_game(game)
    for position, observed in enumerate(snapshots):
        replay.jump_to(position)
        for seat in ALL_SEATS:
            live = dataclasses.replace(observed[seat], to_act=(), legal_actions=NO_ACTIONS)
            assert replay.observation(seat) == live
            assert replay.events(seat) == live.events
    assert replay.events() == game.event_log[: len(replay.events())]


def test_public_events_are_not_enough_to_rebuild() -> None:
    game = started_game()
    with pytest.raises(InvariantViolationError, match="completo"):
        GameRecord.from_events(game.get_events())


def test_unserved_discards_cannot_be_rebuilt() -> None:
    game = started_game()
    all_mus(game)
    player = actor(game)
    game.apply_action(player, DiscardAction(game.get_hand(player, player)[:1]))
    with pytest.raises(InvariantViolationError, match="sin servir"):
        GameRecord.from_events(game.event_log)


def test_tampered_record_is_rejected_by_the_engine() -> None:
    game = started_game()
    game.apply_action(game.mano, MusAction())
    record = game.record
    tampered = dataclasses.replace(record, actions=((record.actions[0][0], PassAction()),))
    with pytest.raises(IllegalActionError):
        GameReplay(tampered)


def test_replay_detects_divergence() -> None:
    game = started_game()
    game.apply_action(game.mano, MusAction())
    game._log.pop()  # corrupción deliberada del registro
    with pytest.raises(InvariantViolationError, match="mismos eventos"):
        GameReplay.from_game(game)


def test_from_events_detects_inconsistent_log() -> None:
    game = started_game()
    log = list(game.event_log)
    for i, env in enumerate(log):
        if isinstance(env.event, CardsDealt):
            fake = CardsDealt(env.event.seat, tuple(reversed(env.event.cards)))
            log[i] = dataclasses.replace(env, event=fake)
            break
    with pytest.raises(InvariantViolationError, match="no coinciden"):
        GameReplay.from_events(tuple(log))


def test_replay_with_discards_and_ordago() -> None:
    game = started_game(seed=31)
    all_mus(game)
    discard_all(game, 2)
    all_mus(game)
    discard_all(game, 4)
    cut(game)
    act(game, BetAction(2), OrdagoAction(), AcceptAction())
    assert game.is_finished
    record = GameRecord.from_events(game.event_log)
    assert record == game.record
    discards = [a for _, a in record.actions if isinstance(a, DiscardAction)]
    assert [len(d.cards) for d in discards] == [2] * 4 + [4] * 4
    assert GameReplay.from_events(game.event_log).jump_to(len(record.actions)) == game.get_state()
