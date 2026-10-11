from __future__ import annotations

import json
import random
from typing import Any

import pytest

from mus_engine import Game
from mus_engine.cards.card import Card
from mus_engine.config import GameConfig
from mus_engine.game.actions import (
    AcceptAction,
    Action,
    BetAction,
    CutMusAction,
    DiscardAction,
    MusAction,
    OrdagoAction,
    PassAction,
    RaiseAction,
    RejectAction,
    SignalAction,
)
from mus_engine.game.record import GameRecord
from mus_engine.rules.signals import Signal
from mus_web.codec import (
    MAX_AMOUNT,
    CodecError,
    action_from_json,
    action_to_json,
    config_from_json,
    config_to_json,
    observation_to_json,
    record_from_json,
    record_to_json,
    to_json,
)

ACTIONS: list[Action] = [
    MusAction(),
    CutMusAction(),
    PassAction(),
    AcceptAction(),
    RejectAction(),
    OrdagoAction(),
    BetAction(2),
    RaiseAction(5),
    DiscardAction([Card.from_code("12O"), Card.from_code("1B")]),
    SignalAction(Signal.DUPLES),
]


@pytest.mark.parametrize("action", ACTIONS)
def test_actions_roundtrip(action: Action) -> None:
    data = action_to_json(action)
    assert action_from_json(json.loads(json.dumps(data))) == action


@pytest.mark.parametrize(
    "data",
    [
        "mus",
        {},
        {"type": "hack"},
        {"type": 3},
        {"type": "mus", "extra": 1},
        {"type": "bet"},
        {"type": "bet", "amount": True},
        {"type": "bet", "amount": 0},
        {"type": "raise", "amount": MAX_AMOUNT + 1},
        {"type": "bet", "amount": 2.5},
        {"type": "discard", "cards": "12O"},
        {"type": "discard", "cards": [1]},
        {"type": "discard", "cards": ["1O", "2O", "3O", "4O", "5O"]},
        {"type": "discard", "cards": ["99X"]},
        {"type": "signal", "signal": 1},
        {"type": "signal", "signal": "guiño"},
    ],
)
def test_malformed_actions_are_rejected(data: Any) -> None:
    with pytest.raises(CodecError):
        action_from_json(data)


def test_generic_values() -> None:
    assert to_json(Card.from_code("12O")) == "12O"
    assert to_json(Signal.JUEGO) == "juego"
    assert to_json(frozenset({3, 1})) == [1, 3]
    assert to_json((1, (2,))) == [1, [2]]


def _played(signals: bool) -> Game:
    game = Game(seed=3, config=GameConfig(signals_enabled=signals))
    game.start()
    rng = random.Random(1)
    for step in range(400):
        if game.is_finished:
            break
        if signals and step % 3 == 0:
            game.tick()
        (seat,) = game.current_actors()
        legal = game.get_legal_actions(seat)
        options = [a for a in legal.actions if not isinstance(a, SignalAction)]
        if legal.bet is not None:
            options.append(BetAction(legal.bet.minimum))
        game.apply_action(seat, rng.choice(options))
    return game


def test_observation_is_json_and_only_has_my_cards() -> None:
    game = _played(signals=True)
    obs = game.get_observation(0)
    data = observation_to_json(obs, events_tail=10)
    text = json.dumps(data)
    assert len(data["events"]) <= 10
    assert data["my_hand"] == [c.code for c in obs.my_hand]
    assert data["gaze"] is not None
    assert "state" not in data
    assert json.loads(text) == data


def test_observation_without_signals() -> None:
    game = Game(seed=1)
    game.start()
    data = observation_to_json(game.get_observation(1))
    assert data["gaze"] is None
    assert data["lance"] is None
    assert data["bet"] is None
    assert data["winner"] is None


def test_finished_game_observation() -> None:
    game = _played(signals=False)
    assert game.is_finished
    data = observation_to_json(game.get_observation(0))
    assert data["winner"] in ("A", "B")


def test_record_roundtrip_with_ticks() -> None:
    game = _played(signals=True)
    record = game.record
    data = json.loads(json.dumps(record_to_json(record)))
    assert any(e.get("tick") for e in data["actions"])
    again = record_from_json(data)
    assert isinstance(again, GameRecord)
    assert again == record


def test_config_roundtrip() -> None:
    config = GameConfig(signals_enabled=True, target_score=30)
    assert config_from_json(json.loads(json.dumps(config_to_json(config)))) == config
