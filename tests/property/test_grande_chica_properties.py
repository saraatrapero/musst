"""Propiedades de grande y chica frente a una implementación de referencia."""

from hypothesis import given
from hypothesis import strategies as st

from mus_engine.cards import Card, Deck, Rank
from mus_engine.players import ALL_SEATS, SeatId, distance_from_mano
from mus_engine.rules import ChicaEvaluator, GrandeEvaluator, resolve

DECK = Deck.standard().cards
GRANDE = GrandeEvaluator()
CHICA = ChicaEvaluator()

# Referencia independiente: lista explícita del orden de grande en ocho reyes.
GRANDE_ORDER = ["AS", "CUATRO", "CINCO", "SEIS", "SIETE", "SOTA", "CABALLO", "REY"]
ALIAS = {"DOS": "AS", "TRES": "REY"}


def ref_value(card: Card) -> int:
    return GRANDE_ORDER.index(ALIAS.get(card.rank.name, card.rank.name))


def ref_grande_beats(a: tuple[Card, ...], b: tuple[Card, ...]) -> int:
    """1 si a gana, -1 si pierde, 0 si empata (sin considerar la mano)."""
    va = sorted((ref_value(x) for x in a), reverse=True)
    vb = sorted((ref_value(x) for x in b), reverse=True)
    for x, y in zip(va, vb, strict=True):
        if x != y:
            return 1 if x > y else -1
    return 0


def ref_chica_beats(a: tuple[Card, ...], b: tuple[Card, ...]) -> int:
    va = sorted(ref_value(x) for x in a)
    vb = sorted(ref_value(x) for x in b)
    for x, y in zip(va, vb, strict=True):
        if x != y:
            return 1 if x < y else -1
    return 0


def sign(x: tuple[int, ...], y: tuple[int, ...]) -> int:
    return (x > y) - (x < y)


hands = st.lists(st.sampled_from(DECK), min_size=4, max_size=4, unique=True).map(tuple)
tables = st.lists(st.sampled_from(DECK), min_size=16, max_size=16, unique=True)


@given(hands, hands)
def test_grande_matches_reference(a: tuple[Card, ...], b: tuple[Card, ...]) -> None:
    assert sign(GRANDE.strength(a), GRANDE.strength(b)) == ref_grande_beats(a, b)


@given(hands, hands)
def test_chica_matches_reference(a: tuple[Card, ...], b: tuple[Card, ...]) -> None:
    assert sign(CHICA.strength(a), CHICA.strength(b)) == ref_chica_beats(a, b)


@given(hands, st.permutations(range(4)))
def test_card_order_is_irrelevant(hand: tuple[Card, ...], perm: list[int]) -> None:
    shuffled = tuple(hand[i] for i in perm)
    assert GRANDE.strength(shuffled) == GRANDE.strength(hand)
    assert CHICA.strength(shuffled) == CHICA.strength(hand)


@given(tables, st.sampled_from(ALL_SEATS))
def test_winner_is_best_and_closest_to_mano(cards: list[Card], mano: SeatId) -> None:
    table = {p: tuple(cards[p * 4 : p * 4 + 4]) for p in ALL_SEATS}
    for evaluator, beats in ((GRANDE, ref_grande_beats), (CHICA, ref_chica_beats)):
        result = resolve(evaluator, table, mano)
        for other in ALL_SEATS:
            outcome = beats(table[result.winner], table[other])
            assert outcome >= 0
            if outcome == 0 and other != result.winner:
                assert distance_from_mano(result.winner, mano) < distance_from_mano(other, mano)


def test_rank_names_cover_the_deck() -> None:
    assert {r.name for r in Rank} == set(GRANDE_ORDER) | set(ALIAS)
