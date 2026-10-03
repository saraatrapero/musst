from collections import Counter

from musst.cards import SpanishDeck40, mus_equivalent_rank


def test_spanish_deck_has_40_cards() -> None:
    deck = SpanishDeck40.create()
    assert len(deck) == 40


def test_eight_kings_eight_aces_equivalence() -> None:
    deck = SpanishDeck40.create()
    eq = Counter(mus_equivalent_rank(card.rank) for card in deck)
    assert eq[12] == 8
    assert eq[1] == 8
