"""Propiedades de juego y punto frente a una referencia independiente."""

from hypothesis import given
from hypothesis import strategies as st

from mus_engine.cards import Card, Deck
from mus_engine.rules import JuegoEvaluator, PuntoEvaluator

DECK = Deck.standard().cards
JUEGO = JuegoEvaluator()
PUNTO = PuntoEvaluator()
VALUE = {"AS": 1, "DOS": 1, "TRES": 10, "CUATRO": 4, "CINCO": 5, "SEIS": 6, "SIETE": 7,
         "SOTA": 10, "CABALLO": 10, "REY": 10}  # fmt: skip
PREFERENCE = [31, 32, 40, 39, 38, 37, 36, 35, 34, 33]

hands = st.lists(st.sampled_from(DECK), min_size=4, max_size=4, unique=True).map(tuple)


def ref_total(hand: tuple[Card, ...]) -> int:
    return sum(VALUE[c.rank.name] for c in hand)


def ref_juego_key(hand: tuple[Card, ...]) -> int:
    t = ref_total(hand)
    return 100 - PREFERENCE.index(t) if t >= 31 else 0


@given(hands)
def test_total_matches_reference(hand: tuple[Card, ...]) -> None:
    assert JUEGO.classify(hand).total == ref_total(hand)
    assert JUEGO.has_juego(hand) == (ref_total(hand) >= 31)


@given(hands, hands)
def test_juego_order_matches_reference(a: tuple[Card, ...], b: tuple[Card, ...]) -> None:
    assert (JUEGO.strength(a) > JUEGO.strength(b)) == (ref_juego_key(a) > ref_juego_key(b))
    assert (JUEGO.strength(a) == JUEGO.strength(b)) == (ref_juego_key(a) == ref_juego_key(b))


@given(hands, hands)
def test_punto_order_matches_reference(a: tuple[Card, ...], b: tuple[Card, ...]) -> None:
    if ref_total(a) < 31 and ref_total(b) < 31:
        assert (PUNTO.strength(a) > PUNTO.strength(b)) == (ref_total(a) > ref_total(b))
