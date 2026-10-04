"""Reglas del Reglamento FEM y decisiones sobre juego y punto."""

import itertools

from mus_engine.cards import Deck, cards_from_codes
from mus_engine.players import ALL_SEATS, SeatId
from mus_engine.rules import (
    JuegoEvaluator,
    LanceType,
    Participation,
    PuntoEvaluator,
    juego_or_punto,
    resolve,
)

JUEGO = JuegoEvaluator()
PUNTO = PuntoEvaluator()
ALL_HANDS = list(itertools.combinations(Deck.standard().cards, 4))
TOTALS = [JUEGO.classify(h).total for h in ALL_HANDS]


def test_r15_hay_juego_con_31_o_mas() -> None:
    """Voc. "No Juego": sin juego cuando los cuatro naipes suman menos de 31."""
    assert JUEGO.has_juego(cards_from_codes("12O 12C 12E 1B"))  # 31
    assert not JUEGO.has_juego(cards_from_codes("12O 12C 5E 5B"))  # 30


def test_c_vi_7_treinta_y_una_es_la_jugada_maxima_de_juego() -> None:
    """C.VI-7: la jugada máxima del juego es treinta y una."""
    best = max(JUEGO.strength(h) for h in ALL_HANDS)
    assert best == JUEGO.strength(cards_from_codes("12O 12C 12E 1B"))


def test_c_vi_8_treinta_y_tres_es_la_jugada_minima_de_juego() -> None:
    """C.VI-8 / C.VI-9: la jugada mínima del juego es treinta y tres."""
    worst = min(JUEGO.strength(h) for h in ALL_HANDS if JUEGO.has_juego(h))
    assert worst == JUEGO.strength(cards_from_codes("12O 11C 7E 6B"))


def test_c_vi_7_treinta_es_la_jugada_maxima_de_punto() -> None:
    """C.VI-7: la jugada máxima del punto es treinta."""
    assert max(t for t in TOTALS if t < 31) == 30


def test_totales_posibles() -> None:
    """Los totales van de 4 (cuatro ases) a 40. 38 y 39 son imposibles: tres naipes de 10
    suman 30 y no hay naipe que valga 8 ni 9."""
    assert min(TOTALS) == 4
    assert max(TOTALS) == 40
    assert {t for t in TOTALS if t >= 31} == {31, 32, 33, 34, 35, 36, 37, 40}


def test_d08_orden_del_juego() -> None:
    """D-08: 31, 32, 40, (39, 38,) 37, 36, 35, 34, 33. 38 y 39 no se pueden dar."""
    by_total: dict[int, tuple[int, ...]] = {}
    for hand, t in zip(ALL_HANDS, TOTALS, strict=True):
        if t >= 31:
            by_total.setdefault(t, JUEGO.strength(hand))
    order = sorted(by_total, key=lambda t: by_total[t], reverse=True)
    assert order == [31, 32, 40, 37, 36, 35, 34, 33]


def test_d20_se_juega_punto_solo_si_nadie_tiene_juego() -> None:
    """Voc. "No Juego" / D-20: si alguien tiene juego se juega juego; si no, punto."""
    hands = [
        cards_from_codes(c) for c in ("12O 11C 5E 5B", "7O 6C 5E 4B", "1O 1C 1E 1B", "4O 4C 4E 4B")
    ]
    assert juego_or_punto(hands, JUEGO) is LanceType.PUNTO
    hands[2] = cards_from_codes("12O 11C 7E 6B")  # 33
    assert juego_or_punto(hands, JUEGO) is LanceType.JUEGO


def test_r19_en_juego_solo_participan_los_que_tienen_juego() -> None:
    """R-19 / Voc. "Mano": la mano del lance de juego es el primero que lo tiene."""
    hands = {
        SeatId(0): cards_from_codes("12O 11C 5E 5B"),  # 30
        SeatId(1): cards_from_codes("12C 12E 11O 2C"),  # 31
        SeatId(2): cards_from_codes("7O 6C 5C 4B"),  # 22
        SeatId(3): cards_from_codes("12B 11B 7E 6B"),  # 33
    }
    holders = [p for p in ALL_SEATS if JUEGO.has_juego(hands[p])]
    participation = Participation.from_holders(holders, mano=SeatId(2))
    assert participation.players == (3, 1)
    assert participation.lance_mano == 3
    assert participation.single_team is not None  # 1 y 3 son pareja
    result = resolve(JUEGO, {p: hands[p] for p in participation.players}, mano=SeatId(2))
    assert result.winner == 1  # 31 gana a 33 aunque 3 esté más cerca de la mano
