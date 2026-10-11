"""El torneo es robusto: un bot que falla pierde, pero el torneo sigue (requisito 4.1)."""

import json
from functools import partial

import pytest

from mus_engine import GameConfig
from mus_engine.arena import FailureKind, InProcessSeat, IsolatedSeat, play_game, run_tournament
from mus_engine.arena.__main__ import main
from mus_engine.arena.seats import SeatError
from mus_engine.bots import Bot, RandomBot, SimpleBot
from mus_engine.players import TeamId
from tests.bots import faulty


def seats(
    team_a: type[Bot], team_b: type[Bot], isolated: bool = False, timeout: float = 2.0
) -> list:  # type: ignore[type-arg]
    kind = IsolatedSeat if isolated else InProcessSeat
    return [kind(partial(cls), timeout=timeout) for cls in (team_a, team_b, team_a, team_b)]


def test_normal_game_has_a_winner() -> None:
    result = play_game(seats(SimpleBot, RandomBot), GameConfig(), seed=3)
    assert result.forfeit is None
    assert result.winner in (TeamId.A, TeamId.B)
    assert result.steps > 0


@pytest.mark.parametrize(
    ("bot", "kind"),
    [
        (faulty.RaisingBot, FailureKind.EXCEPTION),
        (faulty.GarbageBot, FailureKind.INVALID_RETURN),
        (faulty.IllegalBot, FailureKind.ILLEGAL_ACTION),
        (faulty.BrokenStartBot, FailureKind.EXCEPTION),
    ],
)
def test_failing_bot_forfeits_in_process(bot: type[Bot], kind: FailureKind) -> None:
    result = play_game(seats(RandomBot, bot), GameConfig(), seed=1)
    assert result.forfeit is not None
    assert result.forfeit.kind is kind
    assert result.forfeit.seat % 2 == 1  # la pareja B es la del bot defectuoso
    assert result.winner is TeamId.A


@pytest.mark.parametrize(
    ("bot", "kind"),
    [
        (faulty.SleepingBot, FailureKind.TIMEOUT),
        (faulty.CrashingBot, FailureKind.CRASH),
        (faulty.RaisingBot, FailureKind.EXCEPTION),
    ],
)
def test_failing_bot_forfeits_in_isolation(bot: type[Bot], kind: FailureKind) -> None:
    result = play_game(seats(bot, RandomBot, isolated=True, timeout=0.5), GameConfig(), seed=1)
    assert result.forfeit is not None
    assert result.forfeit.kind is kind
    assert result.winner is TeamId.B


def test_in_process_timeout_is_measured() -> None:
    from mus_engine import Game

    game = Game(seed=1)
    game.start()
    seat = InProcessSeat(partial(faulty.SlowBot), timeout=0.01)
    with pytest.raises(SeatError) as info:
        seat.decide(game.get_observation(0))
    assert info.value.kind is FailureKind.TIMEOUT


def test_factory_must_return_a_bot() -> None:
    from mus_engine import Game

    game = Game(seed=1)
    game.start()
    seat = InProcessSeat(lambda: "no soy un bot")  # type: ignore[arg-type, return-value]
    with pytest.raises(SeatError) as info:
        seat.decide(game.get_observation(0))
    assert info.value.kind is FailureKind.INVALID_RETURN


@pytest.mark.parametrize(
    ("bot", "kind"),
    [
        (faulty.BadSignalBot, FailureKind.ILLEGAL_ACTION),
        (faulty.SignalGarbageBot, FailureKind.INVALID_RETURN),
    ],
)
def test_bad_signals_forfeit(bot: type[Bot], kind: FailureKind) -> None:
    hits = []
    for seed in range(10):
        result = play_game(seats(bot, RandomBot), GameConfig(signals_enabled=True), seed=seed)
        if result.forfeit is not None:
            hits.append(result.forfeit.kind)
            assert result.winner is TeamId.B
    assert kind in hits


def test_failure_at_game_end_does_not_change_result() -> None:
    result = play_game(seats(faulty.BrokenEndBot, RandomBot), GameConfig(), seed=4)
    assert result.forfeit is None
    assert result.winner is not None


def test_step_limit_gives_a_draw() -> None:
    result = play_game(seats(RandomBot, RandomBot), GameConfig(), seed=2, max_steps=3)
    assert result.winner is None
    assert result.steps == 3


def test_play_game_requires_four_seats() -> None:
    with pytest.raises(ValueError, match="cuatro"):
        play_game(seats(RandomBot, RandomBot)[:3], GameConfig(), seed=1)


def test_tournament_survives_faulty_bots() -> None:
    bots = {"aleatorio": RandomBot, "sencillo": SimpleBot, "explota": faulty.RaisingBot}
    result = run_tournament(bots, games_per_pair=2, seed=1, isolated=False)
    by_name = {s.name: s for s in result.standings}
    assert by_name["explota"].lost == 4
    assert by_name["explota"].forfeits == 4
    assert by_name["explota"].won == 0
    assert sum(s.played for s in result.standings) == 2 * 3 * 2
    assert result.standings[-1].name == "explota"


def test_tournament_is_reproducible_and_balanced() -> None:
    bots = {"aleatorio": RandomBot, "sencillo": SimpleBot}
    first = run_tournament(bots, games_per_pair=4, seed=7, isolated=False)
    second = run_tournament(bots, games_per_pair=4, seed=7, isolated=False)
    assert first.to_json() == second.to_json()
    sides = [(g["team_a"], g["team_b"]) for g in first.games]
    assert sides.count(("aleatorio", "sencillo")) == sides.count(("sencillo", "aleatorio")) == 2


def test_tournament_outputs() -> None:
    result = run_tournament(
        {"aleatorio": RandomBot, "sencillo": SimpleBot}, games_per_pair=2, seed=1, isolated=False
    )
    table = result.to_markdown()
    assert table.startswith("| # | Bot |")
    assert "sencillo" in table
    data = json.loads(result.to_json())
    assert {s["name"] for s in data["standings"]} == {"aleatorio", "sencillo"}
    assert len(data["games"]) == 2


def test_draws_are_counted() -> None:
    from mus_engine.arena.match import GameResult
    from mus_engine.arena.tournament import Standing, _update
    from mus_engine.game.record import GameRecord
    from mus_engine.scoring import GameScore

    standings = {"a": Standing("a"), "b": Standing("b")}
    draw = GameResult(
        None, GameScore(), None, 1, GameRecord(("a", "b", "c", "d"), GameConfig(), 1, ())
    )
    _update(standings, "a", "b", draw)
    assert standings["a"].drawn == standings["b"].drawn == 1
    assert standings["a"].elo == standings["b"].elo


def test_cli_writes_leaderboard(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["--games", "2", "--seed", "1", "--in-process", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "leaderboard.md").read_text(encoding="utf-8").startswith("| # |")
    assert json.loads((tmp_path / "leaderboard.json").read_text(encoding="utf-8"))["standings"]
    assert "sencillo" in capsys.readouterr().out


def test_simple_bot_clearly_beats_random() -> None:
    """Regresión de calidad: el nivel sencillo debe ganar claramente al azar."""
    result = run_tournament(
        {"aleatorio": RandomBot, "sencillo": SimpleBot}, games_per_pair=100, seed=11, isolated=False
    )
    winner = result.standings[0]
    assert winner.name == "sencillo"
    assert winner.win_rate >= 0.65


def test_isolated_seat_after_crash_and_broken_pipe() -> None:
    from mus_engine import Game

    game = Game(seed=1)
    game.start()
    obs = game.get_observation(0)
    seat = IsolatedSeat(partial(faulty.CrashingBot), timeout=1.0)
    with pytest.raises(SeatError) as first:
        seat.decide(obs)
    assert first.value.kind is FailureKind.CRASH
    with pytest.raises(SeatError, match="no está vivo"):
        seat.decide(obs)
    seat.close()

    broken = IsolatedSeat(partial(RandomBot), timeout=1.0)
    broken._conn.close()
    with pytest.raises(SeatError) as second:
        broken.decide(obs)
    assert second.value.kind is FailureKind.CRASH
    broken.close()
