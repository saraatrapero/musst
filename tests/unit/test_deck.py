"""Tests unitarios de la baraja (Reglamento FEM C.II-3: baraja española de 40)."""

import dataclasses
from collections import Counter

import pytest

from mus_engine.cards import SPANISH_40_CARDS, Card, Deck, Rank, Suit, validate_complete
from mus_engine.errors import InvalidDeckError
from mus_engine.rng import Rng


def test_standard_deck_has_40_cards() -> None:
    deck = Deck.standard()
    assert len(deck) == 40


def test_standard_deck_has_40_distinct_cards() -> None:
    deck = Deck.standard()
    assert len(set(deck)) == 40


def test_standard_deck_exact_composition() -> None:
    deck = Deck.standard()
    assert set(deck) == {Card(rank, suit) for suit in Suit for rank in Rank}
    assert Counter(card.suit for card in deck) == {suit: 10 for suit in Suit}
    assert Counter(card.rank for card in deck) == {rank: 4 for rank in Rank}


def test_standard_deck_validates_as_complete() -> None:
    Deck.standard().validate_complete()


def test_canonical_order_is_stable() -> None:
    assert Deck.standard().cards == SPANISH_40_CARDS
    assert SPANISH_40_CARDS[0] == Card(Rank.AS, Suit.OROS)
    assert SPANISH_40_CARDS[-1] == Card(Rank.REY, Suit.BASTOS)


def test_deck_is_immutable() -> None:
    deck = Deck.standard()
    with pytest.raises(dataclasses.FrozenInstanceError):
        deck.cards = ()  # type: ignore[misc]
    assert not hasattr(deck.cards, "append")


def test_deck_rejects_duplicates() -> None:
    card = Card(Rank.REY, Suit.OROS)
    with pytest.raises(InvalidDeckError, match="duplicados"):
        Deck((card, card))


def test_deck_rejects_non_cards() -> None:
    with pytest.raises(InvalidDeckError):
        Deck(("12O",))  # type: ignore[arg-type]


def test_deck_requires_tuple() -> None:
    with pytest.raises(InvalidDeckError):
        Deck(list(SPANISH_40_CARDS))  # type: ignore[arg-type]


def test_partial_deck_is_valid_but_not_complete() -> None:
    partial = Deck(SPANISH_40_CARDS[:24])
    assert len(partial) == 24
    with pytest.raises(InvalidDeckError, match="Faltan"):
        partial.validate_complete()


def test_validate_complete_reports_duplicates() -> None:
    cards = (*SPANISH_40_CARDS[:39], SPANISH_40_CARDS[0])
    with pytest.raises(InvalidDeckError, match="duplicados"):
        validate_complete(cards)


def test_validate_complete_rejects_41_cards() -> None:
    with pytest.raises(InvalidDeckError):
        validate_complete((*SPANISH_40_CARDS, SPANISH_40_CARDS[5]))


def test_draw_takes_from_the_top() -> None:
    deck = Deck.standard()
    drawn, rest = deck.draw(4)
    assert drawn == SPANISH_40_CARDS[:4]
    assert rest.cards == SPANISH_40_CARDS[4:]
    assert len(deck) == 40, "draw no debe modificar la baraja original"


def test_draw_zero_and_all() -> None:
    deck = Deck.standard()
    drawn, rest = deck.draw(0)
    assert drawn == ()
    assert rest == deck
    drawn, rest = deck.draw(40)
    assert drawn == SPANISH_40_CARDS
    assert len(rest) == 0


@pytest.mark.parametrize("count", [-1, 41])
def test_draw_rejects_invalid_counts(count: int) -> None:
    with pytest.raises(InvalidDeckError):
        Deck.standard().draw(count)


def test_dealing_16_leaves_24() -> None:
    deck, _ = Deck.standard().shuffled(Rng(1))
    hands = []
    for _ in range(4):
        hand, deck = deck.draw(4)
        hands.append(hand)
    assert len(deck) == 24
    validate_complete([c for hand in hands for c in hand] + list(deck))


def test_shuffle_preserves_composition() -> None:
    shuffled, _ = Deck.standard().shuffled(Rng(42))
    shuffled.validate_complete()
    assert shuffled.cards != SPANISH_40_CARDS


def test_shuffle_is_reproducible_with_seed() -> None:
    a, rng_a = Deck.standard().shuffled(Rng(12345))
    b, rng_b = Deck.standard().shuffled(Rng(12345))
    assert a == b
    assert rng_a == rng_b


def test_different_seeds_give_different_orders() -> None:
    orders = {Deck.standard().shuffled(Rng(seed))[0].cards for seed in range(50)}
    assert len(orders) == 50


def test_consecutive_shuffles_differ() -> None:
    rng = Rng(7)
    first, rng = Deck.standard().shuffled(rng)
    second, rng = Deck.standard().shuffled(rng)
    assert first != second


def test_contains_and_iter() -> None:
    deck = Deck(SPANISH_40_CARDS[:2])
    assert SPANISH_40_CARDS[0] in deck
    assert SPANISH_40_CARDS[3] not in deck
    assert list(deck) == list(SPANISH_40_CARDS[:2])
