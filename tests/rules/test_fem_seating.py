"""Reglas del Reglamento FEM sobre la mesa, la mano y el orden."""

from mus_engine.cards import Suit
from mus_engine.players import (
    ALL_SEATS,
    SeatId,
    are_teammates,
    cutter_for,
    dealer_for_mano,
    discard_order,
    first_dealer_by_suit,
    lance_mano,
    mano_for_dealer,
    mus_order,
    next_dealer,
    next_player,
)


def test_r03_mano_es_el_jugador_a_la_derecha_del_que_reparte() -> None:
    """Voc. "Mano": el jugador a la derecha del que reparte (habla justo después)."""
    for dealer in ALL_SEATS:
        assert mano_for_dealer(dealer) == next_player(dealer)


def test_r04_mano_del_lance_es_el_primero_que_tiene_pares_o_juego() -> None:
    """Voc. "Mano": en pares o juego el primer jugador que los tiene es mano del lance."""
    mano = SeatId(0)
    assert lance_mano(mano, eligible=[SeatId(2), SeatId(3)]) == 2
    assert lance_mano(mano, eligible=[SeatId(0), SeatId(3)]) == 0


def test_r06_sorteo_del_primer_reparto() -> None:
    """C.III-1 y C.III-3: corta el de la izquierda del que baraja; el palo decide."""
    shuffler = SeatId(0)
    cutter = cutter_for(shuffler)
    assert cutter == 3
    assert first_dealer_by_suit(cutter, Suit.OROS) == 0  # 1º a la derecha del que corta
    assert first_dealer_by_suit(cutter, Suit.COPAS) == 1
    assert first_dealer_by_suit(cutter, Suit.ESPADAS) == 2
    assert first_dealer_by_suit(cutter, Suit.BASTOS) == 3  # el que los muestra


def test_r08_orden_del_mus_respeta_c_iv_4() -> None:
    """C.IV-4: el 2º no corta antes de que el mano dé mus; el 4º tras la pareja mano."""
    mano = SeatId(1)
    order = mus_order(mano)
    assert order[0] == mano
    # El 2º (mano de la pareja postre) habla después del mano.
    assert not are_teammates(order[1], mano)
    # El 4º habla después de los dos jugadores de la pareja mano.
    assert are_teammates(order[2], mano)
    assert not are_teammates(order[3], mano)


def test_r10_descarte_del_que_reparte_al_mano() -> None:
    """C.III-11: el primero en descartarse es el que da; el mano es el último."""
    for mano in ALL_SEATS:
        order = discard_order(mano)
        assert order[0] == dealer_for_mano(mano)
        assert order[-1] == mano
        assert sorted(order) == list(ALL_SEATS)


def test_d15_reparte_el_mano_de_la_jugada_anterior() -> None:
    """D-15: reparte la jugada siguiente el que fue mano en esta."""
    dealer = SeatId(2)
    assert next_dealer(dealer) == mano_for_dealer(dealer)
