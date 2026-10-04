"""Reglas del Reglamento FEM y decisiones sobre grande y chica."""

import itertools

from mus_engine.cards import Deck, cards_from_codes
from mus_engine.players import ALL_SEATS, SeatId, distance_from_mano
from mus_engine.rules import ChicaEvaluator, GrandeEvaluator, resolve

GRANDE = GrandeEvaluator()
CHICA = ChicaEvaluator()
ALL_HANDS = list(itertools.combinations(Deck.standard().cards, 4))


def test_c_vi_7_cuatro_reyes_es_la_jugada_maxima_de_grande() -> None:
    """C.VI-7: la jugada máxima de grande son cuatro reyes (en ocho reyes, reyes o treses)."""
    best = max(GRANDE.strength(h) for h in ALL_HANDS)
    assert best == GRANDE.strength(cards_from_codes("12O 12C 3E 3B")) == (12, 12, 12, 12)


def test_c_vi_7_cuatro_ases_es_la_jugada_maxima_de_chica() -> None:
    """C.VI-7: la jugada máxima de chica son cuatro ases (en ocho reyes, ases o doses)."""
    best = max(CHICA.strength(h) for h in ALL_HANDS)
    assert best == CHICA.strength(cards_from_codes("1O 2C 1E 2B")) == (-1, -1, -1, -1)


def test_c_vi_16_se_compara_de_mayor_a_menor_en_grande() -> None:
    """C.VI-16 / D-10: en grande se cantan los naipes de mayor a menor."""
    assert GRANDE.strength(cards_from_codes("12O 1C 1E 1B")) > GRANDE.strength(
        cards_from_codes("11O 11C 11E 11B")
    )


def test_c_vi_16_se_compara_de_menor_a_mayor_en_chica() -> None:
    """C.VI-16 / D-10: en chica se cantan los naipes de menor a mayor."""
    assert CHICA.strength(cards_from_codes("1O 12C 12E 12B")) > CHICA.strength(
        cards_from_codes("4O 4C 4E 4B")
    )


def test_c_ii_3_ocho_reyes_en_grande_y_chica() -> None:
    """C.II-3: los treses valen como reyes y los doses como ases en ambos lances."""
    a, b = cards_from_codes("3O 3C 2E 2B"), cards_from_codes("12O 12C 1E 1B")
    assert GRANDE.strength(a) == GRANDE.strength(b)
    assert CHICA.strength(a) == CHICA.strength(b)


def test_d09_empate_en_grande_lo_gana_el_mas_cercano_a_la_mano() -> None:
    """D-09: con la misma jugada gana quien esté más cerca de la mano."""
    same = ["12O 11O 7O 1O", "12C 11C 7C 1C", "12E 11E 7E 1E", "12B 11B 7B 1B"]
    hands = {p: cards_from_codes(same[p]) for p in ALL_SEATS}
    for mano in ALL_SEATS:
        assert resolve(GRANDE, hands, mano).winner == mano
        assert resolve(CHICA, hands, mano).winner == mano


def test_d09_empate_entre_dos_rivales_por_detras_de_la_mano() -> None:
    """D-09: si la mano no empata, gana el empatado más cercano a ella."""
    hands = {
        SeatId(0): cards_from_codes("4O 5O 6O 7O"),
        SeatId(1): cards_from_codes("12O 12C 1O 1C"),
        SeatId(2): cards_from_codes("4C 5C 6C 7C"),
        SeatId(3): cards_from_codes("3O 3C 2O 2C"),
    }
    for mano in ALL_SEATS:
        winner = resolve(GRANDE, hands, mano).winner
        assert winner in (1, 3)
        assert distance_from_mano(winner, mano) == min(
            distance_from_mano(SeatId(1), mano), distance_from_mano(SeatId(3), mano)
        )


def test_numero_de_jugadas_distintas_en_ocho_reyes() -> None:
    """Con 8 rangos efectivos hay C(8+4-1, 4) = 330 jugadas distintas en grande y chica."""
    assert len({GRANDE.strength(h) for h in ALL_HANDS}) == 330
    assert len({CHICA.strength(h) for h in ALL_HANDS}) == 330
