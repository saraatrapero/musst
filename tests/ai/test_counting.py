from __future__ import annotations

from mus_engine import Game
from mus_engine.ai.counting import CardCounter
from mus_engine.cards.card import Card
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.events.events import CardsDiscarded, DiscardPileReshuffled
from mus_engine.game.actions import CutMusAction, DiscardAction, MusAction, PassAction
from mus_engine.game.phases import Phase
from mus_engine.players.seating import SeatId

POLICY = RankingPolicy()


def counted(game: Game, seat: int) -> int:
    return sum(CardCounter(POLICY).read(game.get_observation(seat)).available.values())


def test_my_cards_and_discards_are_out_of_play() -> None:
    game = Game(seed=5)
    game.start()
    obs = game.get_observation(0)
    knowledge = CardCounter(POLICY).read(obs)
    assert knowledge.seat == 0
    assert knowledge.mano == obs.mano
    assert sum(knowledge.available.values()) == 36
    assert knowledge.pares == (None,) * 4
    while game.phase is Phase.MUS_DECISION:
        (seat,) = game.current_actors()
        game.apply_action(seat, MusAction())
    tossed: dict[int, tuple[Card, ...]] = {}
    while game.phase is Phase.DISCARD:
        (seat,) = game.current_actors()
        toss = game.get_observation(seat).my_hand[:2]
        tossed[seat] = toss
        game.apply_action(seat, DiscardAction(toss))
    knowledge = CardCounter(POLICY).read(game.get_observation(0))
    assert set(knowledge.out_of_play) == set(tossed[0])
    assert sum(knowledge.available.values()) == 34  # 4 en mano + 2 descartados
    assert all(r == (2,) for r in knowledge.requested)


def test_declarations_are_read_and_reshuffles_reset_discards() -> None:
    game = Game(seed=5)
    game.start()
    rounds = 0
    while game.phase is not Phase.LANCE:
        (seat,) = game.current_actors()
        obs = game.get_observation(seat)
        if game.phase is Phase.MUS_DECISION:
            game.apply_action(seat, MusAction() if rounds < 3 else CutMusAction())
        else:
            game.apply_action(seat, DiscardAction(obs.my_hand))  # 4 cada vez: se rebaraja
            if game.phase is not Phase.DISCARD:
                rounds += 1
    while game.get_observation(0).pares_holders is None:
        (seat,) = game.current_actors()
        game.apply_action(seat, PassAction())
    knowledge = CardCounter(POLICY).read(game.get_observation(0))
    assert all(v is not None for v in knowledge.pares)
    log = game.get_observation(0).events
    reshuffled = [e for e in log if isinstance(e.event, DiscardPileReshuffled)]
    assert reshuffled
    last = reshuffled[-1].seq
    mine_after = [
        c
        for e in log
        if isinstance(e.event, CardsDiscarded) and e.event.seat == SeatId(0) and e.seq > last
        for c in e.event.discarded
    ]
    assert set(knowledge.out_of_play) == set(mine_after)
