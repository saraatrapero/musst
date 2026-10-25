from __future__ import annotations

import pytest

from mus_engine import Game, GameConfig
from mus_engine.ai.inference import CUT, MUS, MUS_MEAN, beta_for_mean, inclination, mus_signals
from mus_engine.ai.profiles import (
    BIN_NAMES,
    DEFAULT_TOP,
    MIN_DECISIONS,
    PlayerProfile,
    ProfileTracker,
    hand_percentile,
    tier,
)
from mus_engine.bots import BotContext, RandomBot, SimpleBot
from mus_engine.bots.base import Bot
from mus_engine.cards import cards_from_codes
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.players import SeatId
from mus_engine.rules.lance import LanceType
from tests.bots.styles import FaroleroBot

POLICY = RankingPolicy()


def played(kinds: list[type[Bot]], seeds: range) -> list[PlayerProfile]:
    """Perfiles de cada asiento tras jugar ``seeds`` partidas completas."""
    totals = [PlayerProfile() for _ in range(4)]
    config = GameConfig()
    for seed in seeds:
        game = Game(config=config, seed=seed)
        game.start()
        bots = [k() for k in kinds]
        for seat, bot in enumerate(bots):
            bot.on_game_start(BotContext(SeatId(seat), config, seed))
        while not game.is_finished:
            (seat,) = game.current_actors()
            game.apply_action(seat, bots[seat].decide(game.get_observation(seat)))
        tracker = ProfileTracker()
        tracker.observe(game.event_log)
        tracker.observe(game.event_log)  # lo ya visto no se cuenta dos veces
        totals = [t + tracker.profile(SeatId(s)) for s, t in enumerate(totals)]
    return totals


def test_tiers_and_percentiles() -> None:
    assert [tier(p) for p in (0.0, 0.29, 0.3, 0.6, 0.79, 0.8, 1.0)] == [0, 0, 1, 2, 2, 3, 3]
    assert hand_percentile(cards_from_codes("12O 12C 3E 3B"), LanceType.GRANDE, POLICY) > 0.99
    assert hand_percentile(cards_from_codes("4O 5C 6E 7B"), LanceType.GRANDE, POLICY) < 0.1
    assert hand_percentile(cards_from_codes("4O 5C 6E 7B"), LanceType.PARES, POLICY) == 0.0


def test_new_player_is_average() -> None:
    profile = PlayerProfile()
    assert profile.style() == "por conocer"
    assert profile.decisions == 0
    assert profile.confidence == 0.0
    for kind, top in DEFAULT_TOP.items():
        assert profile.behaviour(kind)[0] == pytest.approx(top)
        assert profile.behaviour(kind)[1] == 0.0
    assert profile.average_bet(3) is None
    for signal in (CUT, MUS):
        for lance in LanceType:
            assert profile.mus_beta(signal, lance) == beta_for_mean(MUS_MEAN[(signal, lance)])
    summary = profile.summary()
    assert summary["style"] == "por conocer"
    strengths = summary["bet_by_strength"]
    assert isinstance(strengths, dict)
    assert set(strengths) == set(BIN_NAMES)


def test_json_roundtrip_and_sum() -> None:
    a = PlayerProfile({"open.n": 3, "open.bet": 1})
    b = PlayerProfile.from_json({"open.n": 2, "basura": "x", "cero": 0})
    assert (a + b).to_json() == {"open.bet": 1, "open.n": 5}


def test_styles_of_the_builtin_bots() -> None:
    simple, rnd, *_ = played([SimpleBot, RandomBot, SimpleBot, RandomBot], range(12))
    assert simple.style() == "conservador"
    assert rnd.style() == "imprevisible"
    assert simple.bet_rate < 0.2 < rnd.bet_rate
    assert simple.bet_given(3) > simple.bet_given(0)  # el sencillo envida con buenas
    assert rnd.average_bet(0) is not None
    assert simple.confidence > 0.5
    assert simple.counts["games"] == 12
    assert simple.cut_rate > 0


def test_bluffer_is_detected() -> None:
    _, bluffer, *_ = played([SimpleBot, FaroleroBot, SimpleBot, FaroleroBot], range(15))
    assert bluffer.style() in ("farolero", "imprevisible")
    top, leak = bluffer.behaviour("bet")
    assert top > DEFAULT_TOP["bet"]
    assert leak > 0.3


def test_score_sensitivity_is_recorded() -> None:
    simple, *_ = played([SimpleBot, RandomBot, SimpleBot, RandomBot], range(12))
    assert simple.counts.get("losing.open.n", 0) + simple.counts.get("even.open.n", 0) > 0
    assert 0 <= simple.losing_bet_rate(True) <= 1


@pytest.mark.parametrize(
    ("counts", "style"),
    [
        ({"open.n": 40, "open.bet": 30}, "arriesgado"),
        ({"open.n": 40, "open.bet": 2, "face.n": 10, "face.accept": 8}, "conservador"),
        ({"open.n": 20, "open.bet": 7, "face.n": 30, "face.accept": 3}, "cauto"),
        ({"open.n": 20, "open.bet": 7, "t.open.0.n": 10, "t.open.0.bet": 8}, "farolero"),
        (
            {"open.n": 20, "open.bet": 7, "face.n": 20, "face.accept": 15, "t.open.3.n": 10},
            "de tapado",
        ),
        (
            {
                "open.n": 20,
                "open.bet": 7,
                "face.n": 20,
                "face.accept": 15,
                "t.open.3.n": 10,
                "t.open.3.bet": 9,
            },
            "equilibrado",
        ),
        ({"open.n": 4}, "por conocer"),
    ],
)
def test_style_rules(counts: dict[str, int], style: str) -> None:
    assert PlayerProfile(counts).style() == style
    assert MIN_DECISIONS == 8


def test_mus_signals_and_inclination() -> None:
    game = Game(seed=4)
    game.start()
    signals = mus_signals(game.get_observation(0).events, game.get_observation(0).hand_number)
    assert signals == {}
    assert beta_for_mean(0.5) == pytest.approx(0.0, abs=1e-3)
    assert beta_for_mean(0.7) > 0 > beta_for_mean(0.3)
    weigh = inclination(2.0)
    assert weigh(1.0) > weigh(0.5) == 1.0 > weigh(0.0)


def test_cut_signal_is_learned_per_player() -> None:
    simple, *_ = played([SimpleBot, RandomBot, SimpleBot, RandomBot], range(12))
    assert simple.counts.get(f"m.{CUT}.grande.n", 0) > 0
    assert simple.mus_beta(CUT, LanceType.GRANDE) > 0


def test_bluff_share_grows_with_shown_bluffs() -> None:
    """Parte de sus envites que son faroles: sin datos, poca; con faroles enseñados, más."""
    from mus_engine.ai.profiles import PlayerProfile

    nobody = PlayerProfile()
    bluffer = PlayerProfile({"t.open.0.n": 20, "t.open.0.bet": 12, "open.n": 40, "open.bet": 24})
    honest = PlayerProfile({"t.open.0.n": 20, "open.n": 40, "open.bet": 8})
    assert honest.bluff_share() < nobody.bluff_share() < 0.1 < bluffer.bluff_share()
