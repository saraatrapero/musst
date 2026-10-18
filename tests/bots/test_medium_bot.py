"""Decisiones del bot ``medio`` (Fase D): conteo, probabilidad exacta y marcador."""

from __future__ import annotations

import pytest

from mus_engine import (
    AcceptAction,
    BetAction,
    CutMusAction,
    DiscardAction,
    GameConfig,
    MusAction,
    OrdagoAction,
    PassAction,
    RejectAction,
)
from mus_engine.arena.match import play_game
from mus_engine.arena.seats import InProcessSeat
from mus_engine.bots import BotContext, MediumBot, RandomBot, SimpleBot
from mus_engine.bots.base import Bot
from mus_engine.cards import cards_from_codes
from mus_engine.game.phases import Phase
from mus_engine.players import SeatId, TeamId
from tests.bots.test_builtin_bots import with_hand
from tests.factories import game_at_lance, started_game
from tests.play import act, actor, all_mus

ONE_KING = ("12O 11C 7E 5B", "1C 1E 4O 5O", "7O 7C 6E 4B", "11O 10C 2B 4C")


def medio(seat: int) -> MediumBot:
    bot = MediumBot()
    bot.on_game_start(BotContext(SeatId(seat), GameConfig(), 1))
    return bot


@pytest.mark.parametrize(
    ("tantos", "expected"),
    [((20, 37), AcceptAction()), ((37, 20), RejectAction()), ((0, 0), RejectAction())],
)
def test_ordago_response_depends_on_the_score(tantos: tuple[int, int], expected: object) -> None:
    game = game_at_lance(ONE_KING, tantos=tantos)
    act(game, PassAction(), OrdagoAction())
    assert medio(2).decide(game.get_observation(2)) == expected


def test_more_aggressive_when_losing() -> None:
    losing = game_at_lance(ONE_KING, tantos=(20, 37))
    winning = game_at_lance(ONE_KING, tantos=(37, 20))
    assert medio(0).decide(losing.get_observation(0)) == OrdagoAction()
    assert medio(0).decide(winning.get_observation(0)) == BetAction(2)


def test_bets_bigger_with_a_great_hand() -> None:
    hands = ("12O 12C 3E 3B", "1C 1E 4O 5O", "7O 7C 6E 4B", "11O 10C 2B 4C")  # 4 reyes
    game = game_at_lance(hands, tantos=(37, 20))
    decision = medio(0).decide(game.get_observation(0))
    assert decision == BetAction(4)


def test_passes_with_nothing() -> None:
    hands = ("4O 5C 6E 7B", "12O 12C 3E 3B", "7O 7C 6E 4B", "11O 10C 2B 4C")
    game = game_at_lance(hands, tantos=(30, 10))
    assert medio(0).decide(game.get_observation(0)) == PassAction()


def test_mus_decision() -> None:
    game = started_game(seed=3, first_dealer=3)
    assert game.phase is Phase.MUS_DECISION
    seat = actor(game)
    great = with_hand(game, seat, "12O 12C 3E 3B")
    assert medio(seat).decide(great.get_observation(seat)) == CutMusAction()
    poor = with_hand(game, seat, "4O 5C 6E 7B")
    assert medio(seat).decide(poor.get_observation(seat)) == MusAction()


def test_discard_keeps_the_kings() -> None:
    game = started_game(seed=3, first_dealer=3)
    all_mus(game)
    assert game.phase is Phase.DISCARD
    seat = actor(game)
    game = with_hand(game, seat, "12O 12C 4E 5B")
    decision = medio(seat).decide(game.get_observation(seat))
    assert decision == DiscardAction(cards_from_codes("4E 5B"))


def _match(bot: type[Bot], rival: type[Bot], seeds: range) -> float:
    wins = 0
    for seed in seeds:
        bot_is_a = seed % 2 == 0
        kinds = [bot, rival] * 2 if bot_is_a else [rival, bot] * 2
        result = play_game([InProcessSeat(k, timeout=30) for k in kinds], GameConfig(), seed)
        assert result.forfeit is None
        wins += result.winner is not None and (result.winner is TeamId.A) == bot_is_a
    return wins / len(seeds)


def test_medium_beats_simple() -> None:
    """Nivel medio > nivel sencillo (requisito del diseño, §4). 65 % en 600 partidas."""
    assert _match(MediumBot, SimpleBot, range(5000, 5100)) >= 0.58


def test_medium_beats_random() -> None:
    assert _match(MediumBot, RandomBot, range(5000, 5040)) >= 0.75
