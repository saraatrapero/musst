"""Propiedades de pares frente a una implementación de referencia."""

from collections import Counter

from hypothesis import given
from hypothesis import strategies as st

from mus_engine.cards import Card, Deck
from mus_engine.rules import ParesCategory, ParesEvaluator

DECK = Deck.standard().cards
PARES = ParesEvaluator()
ORDER = ["AS", "CUATRO", "CINCO", "SEIS", "SIETE", "SOTA", "CABALLO", "REY"]
ALIAS = {"DOS": "AS", "TRES": "REY"}

hands = st.lists(st.sampled_from(DECK), min_size=4, max_size=4, unique=True).map(tuple)


def ref_key(hand: tuple[Card, ...]) -> tuple[int, ...]:
    """Referencia: (categoría, rangos relevantes) usando el multiconjunto de tamaños."""
    counts = Counter(ORDER.index(ALIAS.get(c.rank.name, c.rank.name)) for c in hand)
    shape = sorted(counts.values(), reverse=True)
    pairs = sorted((r for r, n in counts.items() if n >= 2), reverse=True)
    if shape == [4]:
        return (3, pairs[0], pairs[0])
    if shape == [2, 2]:
        return (3, pairs[0], pairs[1])
    if shape[0] == 3:
        return (2, pairs[0])
    if shape[0] == 2:
        return (1, pairs[0])
    return (0,)


@given(hands, hands)
def test_pares_order_matches_reference(a: tuple[Card, ...], b: tuple[Card, ...]) -> None:
    sa, sb = PARES.strength(a), PARES.strength(b)
    ra, rb = ref_key(a), ref_key(b)
    assert (sa > sb) == (ra > rb)
    assert (sa == sb) == (ra == rb)


@given(hands)
def test_category_matches_reference(hand: tuple[Card, ...]) -> None:
    assert int(PARES.classify(hand).category) == ref_key(hand)[0]
    assert PARES.has_pares(hand) == (PARES.classify(hand).category is not ParesCategory.NONE)


@given(hands, st.permutations(range(4)))
def test_card_order_is_irrelevant(hand: tuple[Card, ...], perm: list[int]) -> None:
    assert PARES.classify(tuple(hand[i] for i in perm)) == PARES.classify(hand)
