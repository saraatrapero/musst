"""Decisiones de los bots incluidos."""

import dataclasses

import pytest

from mus_engine import (
    AcceptAction,
    BetAction,
    CutMusAction,
    DiscardAction,
    Game,
    GameConfig,
    GameScore,
    MusAction,
    OrdagoAction,
    PassAction,
    RaiseAction,
    RejectAction,
)
from mus_engine.bots import BotContext, RandomBot, SimpleBot
from mus_engine.bots.simple_bot import lance_strength
from mus_engine.cards import RankingPolicy, cards_from_codes
from mus_engine.game.actions import SignalAction
from mus_engine.game.gaze import GazeState
from mus_engine.players import SeatId
from mus_engine.rules import LanceType
from mus_engine.rules.signals import Signal
from tests.factories import game_at_lance, game_with_state, started_game
from tests.play import act, actor, all_mus

POLICY = RankingPolicy()


def simple(seat: int, config: GameConfig | None = None) -> SimpleBot:
    bot = SimpleBot()
    bot.on_game_start(BotContext(SeatId(seat), config or GameConfig(), 1))
    return bot


def with_hand(game: Game, seat: int, codes: str) -> Game:
    """Cambia la mano de ``seat`` intercambiando naipes con el mazo (mantiene la baraja)."""
    state = game.get_state()
    hand = state.current_hand
    wanted = cards_from_codes(codes)
    old = hand.hand_of(SeatId(seat))
    hands = list(hand.hands)
    stock = list(hand.stock.cards)
    freed = [c for c in old if c not in wanted]  # naipes que salen de la mano
    for new_card, old_card in zip([c for c in wanted if c not in old], freed, strict=True):
        holder = next((p for p, h in enumerate(hands) if new_card in h), None)
        if holder is None:
            stock[stock.index(new_card)] = old_card
        else:
            hands[holder] = tuple(old_card if c == new_card else c for c in hands[holder])
    hands[seat] = wanted
    from mus_engine.cards import Deck

    new_hand = dataclasses.replace(hand, hands=tuple(hands), stock=Deck(tuple(stock)))
    return game_with_state(state.evolve(hand=new_hand))


@pytest.mark.parametrize(
    ("lance", "codes", "strength"),
    [
        (LanceType.GRANDE, "12O 3C 12E 1B", 0.9),
        (LanceType.CHICA, "1O 2C 4E 12B", 0.7),
        (LanceType.PARES, "7O 7C 7E 1B", 0.75),
        (LanceType.PARES, "7O 6C 5E 4B", 0.0),
        (LanceType.JUEGO, "12O 12C 12E 1B", 1.0),
        (LanceType.JUEGO, "12O 11C 7E 6B", 0.45),
        (LanceType.JUEGO, "7O 6C 5E 4B", 0.0),
        (LanceType.PUNTO, "12O 11C 5E 5B", 1.0),
        (LanceType.PUNTO, "12O 11C 4E 2B", 0.5),
        (LanceType.PUNTO, "7O 6C 5E 4B", 0.2),
    ],
)
def test_lance_strength(lance: LanceType, codes: str, strength: float) -> None:
    assert lance_strength(lance, cards_from_codes(codes), POLICY) == pytest.approx(strength)


def test_cuts_with_good_hand_and_asks_mus_with_bad() -> None:
    game = started_game(first_dealer=3)  # mano 0
    good = with_hand(game, 0, "12O 3C 12E 1B")
    assert simple(0).decide(good.get_observation(0)) == CutMusAction()
    bad = with_hand(game, 0, "4O 5C 6E 7B")
    assert simple(0).decide(bad.get_observation(0)) == MusAction()


def test_discards_keep_kings_and_pairs() -> None:
    game = with_hand(started_game(first_dealer=3), 3, "12O 7C 7E 4B")
    all_mus(game)
    assert actor(game) == 3  # el que reparte se descarta primero
    action = simple(3).decide(game.get_observation(3))
    assert action == DiscardAction(cards_from_codes("4B"))


def test_discards_lowest_when_everything_is_worth_keeping() -> None:
    game = with_hand(started_game(first_dealer=3), 3, "12O 3C 12E 3B")
    all_mus(game)
    action = simple(3).decide(game.get_observation(3))
    assert isinstance(action, DiscardAction)
    assert len(action.cards) == 1


HANDS = ("12O 12C 12E 1B", "1C 1E 4O 5O", "7O 7C 6E 5B", "11O 10C 2B 4B")


def test_bets_with_strong_hand_and_passes_with_weak() -> None:
    game = game_at_lance(HANDS)  # grande: 0 tiene tres reyes
    assert simple(0).decide(game.get_observation(0)) == BetAction(2)
    act(game, PassAction())
    assert simple(1).decide(game.get_observation(1)) == PassAction()


def test_accepts_or_rejects_by_strength() -> None:
    game = game_at_lance(HANDS)
    act(game, PassAction(), BetAction(2))  # 1 envida a grande
    assert simple(2).decide(game.get_observation(2)) == RejectAction()  # sin reyes
    act(game, RejectAction())
    assert simple(0).decide(game.get_observation(0)) == AcceptAction()  # tres reyes


def test_raises_with_four_kings() -> None:
    hands = ("12O 12C 3E 3B", "1C 1E 4O 5O", "7O 7C 6E 5B", "11O 10C 2B 4B")
    game = game_at_lance(hands)
    act(game, PassAction(), BetAction(2), RejectAction())
    assert simple(0).decide(game.get_observation(0)) == RaiseAction(2)


def test_ordago_response() -> None:
    game = game_at_lance(HANDS)
    act(game, PassAction(), OrdagoAction())
    assert simple(2).decide(game.get_observation(2)) == RejectAction()
    act(game, RejectAction())
    assert simple(0).decide(game.get_observation(0)) == AcceptAction()


def test_ordago_only_when_rival_is_about_to_win() -> None:
    hands = ("12O 12C 3E 3B", "1C 1E 4O 5O", "7O 7C 6E 5B", "11O 10C 2B 4B")  # 0: cuatro reyes
    calm = game_at_lance(hands)
    assert simple(0).decide(calm.get_observation(0)) == BetAction(2)
    danger = game_at_lance(hands, tantos=(10, 36))
    assert simple(0).decide(danger.get_observation(0)) == OrdagoAction()


def test_more_daring_when_losing() -> None:
    game = game_at_lance(HANDS, tantos=(0, 36))
    act(game, PassAction(), BetAction(2))
    bot = simple(2)
    obs = game.get_observation(2)
    calm = dataclasses.replace(obs, score=GameScore((0, 0)))
    assert bot.decide(calm) == RejectAction()
    assert bot.decide(obs) in (AcceptAction(), RejectAction())


def test_signals_only_when_partner_looks_and_no_rival() -> None:
    game = game_at_lance(HANDS, signals_enabled=True)
    bot = simple(0, GameConfig(signals_enabled=True))
    state = game.get_state()
    watched = game_with_state(
        state.evolve(gaze=GazeState((None, None, SeatId(0), None), (3, 3, 3, 3)))
    )
    assert bot.signal(watched.get_observation(0)) == SignalAction(Signal.TREINTA_Y_UNA)
    spied = game_with_state(
        state.evolve(gaze=GazeState((None, SeatId(0), SeatId(0), None), (3, 3, 3, 3)))
    )
    assert bot.signal(spied.get_observation(0)) is None
    alone = game_with_state(state.evolve(gaze=GazeState((None, None, None, None), (3, 3, 3, 3))))
    assert bot.signal(alone.get_observation(0)) is None
    assert simple(0).signal(game_at_lance(HANDS).get_observation(0)) is None


def test_random_bot_is_reproducible_and_legal() -> None:
    game = started_game()
    obs = game.get_observation(actor(game))
    a, b = RandomBot(), RandomBot()
    for bot in (a, b):
        bot.on_game_start(BotContext(SeatId(0), GameConfig(), 42))
    choices_a = [a.decide(obs) for _ in range(20)]
    choices_b = [b.decide(obs) for _ in range(20)]
    assert choices_a == choices_b
    assert all(obs.legal_actions.contains(c) for c in choices_a)


def test_random_bot_signals_sometimes() -> None:
    game = game_at_lance(HANDS, signals_enabled=True)
    bot = RandomBot()
    bot.on_game_start(BotContext(SeatId(1), GameConfig(signals_enabled=True), 3))
    made = [bot.signal(game.get_observation(1)) for _ in range(200)]
    assert any(isinstance(m, SignalAction) for m in made)
    assert any(m is None for m in made)


def test_default_bot_hooks() -> None:
    from mus_engine.bots import Bot

    class Minimal(Bot):
        name = "minimo"

        def decide(self, observation):  # type: ignore[no-untyped-def]
            return next(iter(observation.legal_actions))

    bot = Minimal()
    bot.on_game_start(BotContext(SeatId(0), GameConfig(), 1))
    game = started_game()
    assert bot.signal(game.get_observation(0)) is None
    bot.on_game_end(game.get_observation(0))


def test_conformance_reports_problems() -> None:
    from mus_engine.bots.conformance import check_bot
    from tests.bots.faulty import RaisingBot

    problems = check_bot(RaisingBot, games=2)
    assert len(problems) == 4  # 2 partidas x (sin señas, con señas)
    assert {p.kind for p in problems} == {"exception"}
    assert all(p.seat in (0, 1, 2, 3) for p in problems)
