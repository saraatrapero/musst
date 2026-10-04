"""Tests de propiedad de la baraja y el generador."""

from hypothesis import given
from hypothesis import strategies as st

from mus_engine.cards import Deck
from mus_engine.rng import Rng

seeds = st.integers(min_value=-(2**63), max_value=2**63)


@given(seeds)
def test_shuffle_is_always_a_permutation(seed: int) -> None:
    deck, _ = Deck.standard().shuffled(Rng(seed))
    deck.validate_complete()


@given(seeds, st.integers(min_value=0, max_value=1000))
def test_same_seed_same_order(seed: int, stream: int) -> None:
    assert Deck.standard().shuffled(Rng(seed, stream)) == Deck.standard().shuffled(
        Rng(seed, stream)
    )


@given(seeds, st.lists(st.integers(min_value=0, max_value=40), max_size=10))
def test_successive_draws_never_duplicate(seed: int, counts: list[int]) -> None:
    deck, _ = Deck.standard().shuffled(Rng(seed))
    drawn: list[object] = []
    for count in counts:
        if count > len(deck):
            break
        cards, deck = deck.draw(count)
        drawn.extend(cards)
    assert len(drawn) == len(set(drawn))
    assert len(drawn) + len(deck) == 40


@given(st.integers(min_value=1, max_value=10**6), seeds)
def test_choice_index_in_range(size: int, seed: int) -> None:
    index, _ = Rng(seed).choice_index(size)
    assert 0 <= index < size
