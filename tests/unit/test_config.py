"""Tests de GameConfig."""

import dataclasses

import pytest

from mus_engine.config import DeckType, GameConfig
from mus_engine.errors import InvalidConfigError


def test_defaults_follow_regulation_and_decisions() -> None:
    config = GameConfig()
    assert config.target_score == 40  # Intro-E
    assert config.deck_type is DeckType.SPANISH_40  # C.II-3
    assert config.kings_are_threes
    assert config.aces_are_twos
    assert (config.min_discard, config.max_discard) == (1, 4)  # D-13
    assert config.min_bet == 2  # Voc. "Envido"
    assert (config.points_pareja, config.points_medias, config.points_duples) == (1, 2, 3)  # D-02
    assert (config.points_juego_31, config.points_juego_other) == (3, 2)  # D-02
    assert config.points_punto == 1
    assert config.points_passed_lance == 1
    assert config.points_negada == 1
    assert config.points_deje == 1


def test_config_is_immutable() -> None:
    config = GameConfig()
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.target_score = 30  # type: ignore[misc]


def test_custom_target_score() -> None:
    assert GameConfig(target_score=60).target_score == 60


@pytest.mark.parametrize(
    "kwargs",
    [
        {"target_score": 0},
        {"target_score": -40},
        {"target_score": True},
        {"target_score": 40.0},
        {"games_to_win": 0},
        {"cards_per_hand": 5},
        {"min_discard": 0},
        {"max_discard": 5},
        {"min_discard": 4, "max_discard": 3},
        {"min_bet": 0},
        {"min_raise": 0},
        {"points_medias": 1},
        {"points_duples": 2},
        {"points_juego_31": 1},
        {"tantos_per_amarraco": 0},
        {"deck_type": "spanish_40"},
    ],
)
def test_invalid_configs_are_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(InvalidConfigError):
        GameConfig(**kwargs)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"gaze_partner_weight": -1},
        {"gaze_rival_weight": True},
        {"gaze_partner_weight": 0, "gaze_rival_weight": 0, "gaze_table_weight": 0},
        {"gaze_min_ticks": 0},
        {"gaze_max_ticks": "3"},
        {"gaze_min_ticks": 4, "gaze_max_ticks": 3},
    ],
)
def test_invalid_gaze_configs(kwargs: dict[str, object]) -> None:
    with pytest.raises(InvalidConfigError):
        GameConfig(signals_enabled=True, **kwargs)  # type: ignore[arg-type]
