"""Tests de las reglas puras de mus y descartes."""

import pytest

from mus_engine.cards import SPANISH_40_CARDS, Card, Deck, cards_from_codes, validate_complete
from mus_engine.errors import InvalidDiscardError
from mus_engine.players import SeatId, discard_order
from mus_engine.rng import Rng
from mus_engine.rules.mus import check_discard, discard_options, serve_discards, sorted_by_hand

HAND = cards_from_codes("12O 1C 5E 7B")


def test_discard_options_count_and_order() -> None:
    options = discard_options(HAND, 1, 4)
    assert len(options) == 4 + 6 + 4 + 1
    assert len(set(options)) == 15
    assert options[0] == frozenset(HAND[:1])
    assert options[-1] == frozenset(HAND)
    assert [len(o) for o in options] == sorted(len(o) for o in options)


def test_discard_options_respect_limits() -> None:
    assert {len(o) for o in discard_options(HAND, 2, 3)} == {2, 3}


def test_check_discard_accepts_valid() -> None:
    check_discard(HAND, frozenset(HAND[:2]), 1, 4)


def test_check_discard_rejects_foreign_cards() -> None:
    with pytest.raises(InvalidDiscardError, match="no están en tu mano"):
        check_discard(HAND, frozenset(cards_from_codes("12O 4B")), 1, 4)


@pytest.mark.parametrize("cards", [frozenset(), frozenset(HAND)])
def test_check_discard_rejects_wrong_count(cards: frozenset) -> None:  # type: ignore[type-arg]
    with pytest.raises(InvalidDiscardError, match="entre"):
        check_discard(HAND, cards, 1, 3)


def _table() -> tuple[tuple[tuple, ...], Deck]:  # type: ignore[type-arg]
    hands = tuple(SPANISH_40_CARDS[i * 4 : i * 4 + 4] for i in range(4))
    return hands, Deck(SPANISH_40_CARDS[16:])


def test_serve_without_reshuffle() -> None:
    hands, stock = _table()
    discards: tuple[frozenset[Card], ...] = (
        frozenset(hands[0][:1]),
        frozenset(hands[1][:2]),
        frozenset(),
        frozenset(hands[3]),
    )
    order = discard_order(SeatId(0))  # 3, 2, 1, 0
    served = serve_discards(hands, stock, (), discards, order, Rng(1))
    # Se sirve de una vez a cada uno en el orden de descarte.
    assert served.received[3] == SPANISH_40_CARDS[16:20]
    assert served.received[2] == ()
    assert served.received[1] == SPANISH_40_CARDS[20:22]
    assert served.received[0] == SPANISH_40_CARDS[22:23]
    assert served.hands[0] == (*hands[0][1:], SPANISH_40_CARDS[22])
    assert served.reshuffles == ()
    assert served.rng == Rng(1)
    assert len(served.discard_pile) == 7
    validate_complete(
        [c for h in served.hands for c in h] + list(served.stock) + list(served.discard_pile)
    )


def test_serve_with_reshuffle_uses_whole_pile() -> None:
    hands, _ = _table()
    stock = Deck(SPANISH_40_CARDS[16:18])  # sólo 2 naipes en el mazo
    old_pile = SPANISH_40_CARDS[18:]
    discards = tuple(frozenset(h) for h in hands)  # todos tiran 4
    served = serve_discards(hands, stock, old_pile, discards, discard_order(SeatId(0)), Rng(5))
    assert len(served.reshuffles) == 1
    reshuffled = served.reshuffles[0]
    # "Todo el descarte": el antiguo más los descartes de esta ronda (D-07).
    assert set(reshuffled) == set(old_pile) | {c for h in hands for c in h}
    assert all(len(h) == 4 for h in served.hands)
    assert served.received[3][:2] == SPANISH_40_CARDS[16:18]
    assert served.rng == Rng(5, 1)
    validate_complete(
        [c for h in served.hands for c in h] + list(served.stock) + list(served.discard_pile)
    )


def test_sorted_by_hand() -> None:
    assert sorted_by_hand(HAND, frozenset(HAND[2:])) == HAND[2:]
