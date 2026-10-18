from __future__ import annotations

import random

from mus_engine.cards.card import Card
from mus_engine.events.events import (
    BetPlaced,
    CardsDealt,
    EventEnvelope,
    GameFinished,
    HandsRevealed,
    LanceResolved,
    MusRequested,
    OrdagoDeclared,
    Visibility,
)
from mus_engine.players.seating import SeatId
from mus_web.avatars_pack import avatars_by_id
from mus_web.phrases import MAX_PER_BATCH, PhraseMaker, moments


def env(event: object, visibility: Visibility = Visibility.PUBLIC) -> EventEnvelope:
    audience = SeatId(0) if visibility is Visibility.PRIVATE else None
    return EventEnvelope(1, 1, visibility, event, audience)  # type: ignore[arg-type]


def cards(*codes: str) -> tuple[Card, ...]:
    return tuple(Card.from_code(c) for c in codes)


def test_moments_from_public_events() -> None:
    s = SeatId
    events = [
        env(MusRequested(s(1))),
        env(BetPlaced(s(2), "grande", 2)),
        env(LanceResolved("grande", s(1), ())),
        env(
            HandsRevealed((cards("12O", "12C", "11O", "1B"), (), cards("1O", "1C", "2O", "3O"), ()))
        ),
        env(GameFinished("B", (0, 1))),
        env(CardsDealt(s(0), cards("1O")), Visibility.PRIVATE),
    ]
    found = list(moments(events))
    assert (1, "pide_mus") in found
    assert (2, "envida") in found
    assert {(1, "gana_lance"), (3, "gana_lance"), (0, "pierde_lance"), (2, "pierde_lance")} <= set(
        found
    )
    assert (0, "revela_31") in found
    assert (2, "revela_31") not in found
    assert {(1, "gana_partida"), (0, "pierde_partida")} <= set(found)
    assert all(moment != "reparte" for _, moment in found)


def test_only_bots_with_that_moment_speak() -> None:
    avatars = avatars_by_id()
    maker = PhraseMaker({SeatId(1): avatars["superviviente"]}, random.Random(0))
    said = maker.react([env(GameFinished("B", (0, 1))), env(OrdagoDeclared(SeatId(0), "grande"))])
    assert [p.seat for p in said] == [1]
    assert said[0].text in avatars["superviviente"].phrases["gana_partida"]
    # La Superviviente no tiene frase para "pide_mus": calla.
    assert maker.react([env(MusRequested(SeatId(1)))]) == []


def test_phrases_are_limited_per_batch() -> None:
    avatars = avatars_by_id()
    speakers = {SeatId(i): a for i, a in zip(range(4), avatars.values(), strict=False)}
    said = PhraseMaker(speakers, random.Random(0)).react([env(GameFinished("A", (1, 0)))])
    assert len(said) == MAX_PER_BATCH
    assert len({p.seat for p in said}) == len(said)
