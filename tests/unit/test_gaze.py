"""Tests del modelo de miradas."""

from mus_engine import GameConfig
from mus_engine.game.gaze import GazeState, advance_gaze, initial_gaze
from mus_engine.players import ALL_SEATS, SeatId, partner
from mus_engine.rng import Rng

CONFIG = GameConfig(signals_enabled=True)


def test_initial_gaze_is_deterministic_and_valid() -> None:
    a, rng_a = initial_gaze(CONFIG, Rng(1))
    b, rng_b = initial_gaze(CONFIG, Rng(1))
    assert a == b
    assert rng_a == rng_b
    for player in ALL_SEATS:
        assert a.targets[player] != player
        assert CONFIG.gaze_min_ticks <= a.remaining[player] <= CONFIG.gaze_max_ticks


def test_gaze_holds_until_it_expires() -> None:
    gaze = GazeState((SeatId(2), None, SeatId(0), SeatId(1)), (3, 1, 2, 1))
    after, _ = advance_gaze(gaze, CONFIG, Rng(5))
    assert after.targets[0] == 2  # le quedaban 3 momentos
    assert after.targets[2] == 0
    assert after.remaining[0] == 2
    assert after.remaining[2] == 1


def test_only_partner_weight() -> None:
    config = GameConfig(
        signals_enabled=True, gaze_partner_weight=1, gaze_rival_weight=0, gaze_table_weight=0
    )
    gaze, _ = initial_gaze(config, Rng(9))
    assert gaze.targets == tuple(partner(p) for p in ALL_SEATS)


def test_only_table_weight() -> None:
    config = GameConfig(
        signals_enabled=True, gaze_partner_weight=0, gaze_rival_weight=0, gaze_table_weight=1
    )
    gaze, _ = initial_gaze(config, Rng(9))
    assert gaze.targets == (None, None, None, None)
    assert gaze.watchers_of(SeatId(0)) == ()


def test_watchers_of() -> None:
    gaze = GazeState((SeatId(2), SeatId(2), None, SeatId(2)), (1, 1, 1, 1))
    assert gaze.watchers_of(SeatId(2)) == (0, 1, 3)
    assert gaze.watchers_of(SeatId(0)) == ()


def test_distribution_roughly_follows_weights() -> None:
    gaze, rng = initial_gaze(CONFIG, Rng(3))
    partner_looks = 0
    total = 0
    for _ in range(3000):
        gaze, rng = advance_gaze(gaze, CONFIG, rng)
        partner_looks += sum(gaze.targets[p] == partner(p) for p in ALL_SEATS)
        total += 4
    share = partner_looks / total  # peso 30 de 100
    assert 0.25 < share < 0.35
