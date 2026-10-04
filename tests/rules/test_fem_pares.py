"""Reglas del Reglamento FEM y decisiones sobre pares."""

import itertools

from mus_engine.cards import Deck, cards_from_codes
from mus_engine.players import ALL_SEATS, SeatId
from mus_engine.rules import ParesCategory, ParesEvaluator, Participation, resolve

PARES = ParesEvaluator()
ALL_HANDS = list(itertools.combinations(Deck.standard().cards, 4))


def test_r17_cuatro_reyes_es_la_jugada_maxima_de_pares() -> None:
    """C.VI-7 / R-17: cuatro reyes (duples de reyes) es la máxima en pares."""
    best = max(PARES.strength(h) for h in ALL_HANDS)
    assert best == PARES.strength(cards_from_codes("12O 3C 12E 3B"))
    assert PARES.classify(cards_from_codes("12O 3C 12E 3B")).category is ParesCategory.DUPLES


def test_c_vi_8_dos_ases_es_la_jugada_minima_de_pares() -> None:
    """C.VI-8: la jugada mínima en pares son dos ases."""
    with_pares = [PARES.strength(h) for h in ALL_HANDS if PARES.has_pares(h)]
    assert min(with_pares) == PARES.strength(cards_from_codes("1O 2C 4E 5B")) == (1, 1)


def test_r18_categorias_pareja_medias_duples() -> None:
    """C.VI-17, C.VIII-2: existen pares, medias y duples, en ese orden de valor."""
    found = {PARES.classify(h).category for h in ALL_HANDS}
    assert found == set(ParesCategory)
    assert ParesCategory.PAREJA < ParesCategory.MEDIAS < ParesCategory.DUPLES


def test_c_ii_3_los_pares_se_forman_con_rangos_efectivos() -> None:
    """C.II-3: tres con rey forman pareja de reyes; dos con as, pareja de ases."""
    assert PARES.classify(cards_from_codes("3O 12C 5E 6B")).category is ParesCategory.PAREJA
    assert PARES.classify(cards_from_codes("2O 1C 5E 6B")).category is ParesCategory.PAREJA


def test_d11_los_naipes_sueltos_no_cuentan() -> None:
    """D-11: con la misma pareja empatan; gana el más cercano a la mano (D-09)."""
    hands = {
        SeatId(0): cards_from_codes("7O 7C 1E 4B"),
        SeatId(1): cards_from_codes("7E 7B 11E 10B"),
    }
    assert PARES.strength(hands[SeatId(0)]) == PARES.strength(hands[SeatId(1)])
    assert resolve(PARES, hands, mano=SeatId(1)).winner == 1


def test_r19_mano_del_lance_es_el_primero_con_pares() -> None:
    """Voc. "Mano" / R-04: en pares el primero (desde la mano) que los tiene es mano del lance."""
    hands = {
        SeatId(0): cards_from_codes("12O 11C 7E 1B"),  # sin pares
        SeatId(1): cards_from_codes("4O 5C 6E 7B"),  # sin pares
        SeatId(2): cards_from_codes("5O 5C 6C 7C"),
        SeatId(3): cards_from_codes("1C 2E 4C 4E"),
    }
    holders = [p for p in ALL_SEATS if PARES.has_pares(hands[p])]
    participation = Participation.from_holders(holders, mano=SeatId(0))
    assert participation.lance_mano == 2
    assert participation.is_contested


def test_cantidad_de_manos_por_categoria() -> None:
    """Recuento de control sobre las 91 390 manos (ocho reyes): suman el total."""
    counts = {c: 0 for c in ParesCategory}
    for hand in ALL_HANDS:
        counts[PARES.classify(hand).category] += 1
    assert sum(counts.values()) == len(ALL_HANDS) == 91390
    assert all(counts[c] > 0 for c in ParesCategory)
