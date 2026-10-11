"""Tablas de verdad de las señas (C.VIII) y restricciones de momento."""

import pytest

from mus_engine.cards import RankingPolicy, cards_from_codes
from mus_engine.rules.signals import (
    Signal,
    SignalContext,
    legal_signals,
    timing_allows,
    true_signals,
)

POLICY = RankingPolicy()
S = Signal


def truth(codes: str) -> frozenset[Signal]:
    return true_signals(cards_from_codes(codes), POLICY)


@pytest.mark.parametrize(
    ("codes", "expected"),
    [
        ("12O 3C 6E 5B", {S.PARES, S.DOS_REYES, S.TREINTA_Y_UNA}),  # reyes (3 = rey); 31
        ("1O 2C 6E 5B", {S.PARES, S.DOS_ASES}),  # pareja de ases; 13
        ("7O 7C 6E 5B", {S.PARES}),  # pareja de sietes; 25
        ("12O 12C 3E 1B", {S.MEDIAS, S.MEDIAS_REYES, S.TREINTA_Y_UNA}),  # 31
        ("1O 1C 2E 7B", {S.MEDIAS, S.MEDIAS_ASES}),  # 10
        ("10O 10C 10E 7B", {S.MEDIAS, S.JUEGO}),  # medias de sotas; 37
        ("12O 3C 1E 2B", {S.DUPLES}),  # duples reyes-ases; 22 -> sin juego ni 29/30
        ("12O 12C 3E 3B", {S.DUPLES, S.JUEGO}),  # cuatro reyes; 40
        ("12O 11C 5E 5B", {S.PARES, S.TREINTA}),  # pareja de cincos; 30
        ("12O 11C 5E 4B", {S.VEINTINUEVE}),  # 29 sin pares
        ("12O 11C 7E 4B", {S.TREINTA_Y_UNA}),  # 31 sin pares
        ("12O 11C 7E 6B", {S.JUEGO}),  # 33
        ("7O 6C 5E 4B", {S.CIEGO}),  # nada que señar
    ],
)
def test_true_signals(codes: str, expected: set[Signal]) -> None:
    assert truth(codes) == expected


def test_duples_cannot_be_signalled_partially() -> None:
    """C.VIII-6: con duples de reyes con ases no se pasan dos reyes ni dos ases."""
    signals = truth("12O 3C 1E 2B")
    assert S.DOS_REYES not in signals
    assert S.DOS_ASES not in signals
    assert S.PARES not in signals


def test_juego_signal_excludes_31() -> None:
    """C.VIII-2: la seña de juego no vale para la treinta y una."""
    assert S.JUEGO not in truth("12O 12C 12E 1B")
    assert S.TREINTA_Y_UNA in truth("12O 12C 12E 1B")


def test_ciego_only_without_any_other_signal() -> None:
    """C.VIII-2: ciego no se pasa si hay jugada con seña establecida."""
    for codes in ("7O 7C 6E 5B", "12O 11C 5E 4B", "12O 11C 7E 6B"):
        assert S.CIEGO not in truth(codes)


@pytest.mark.parametrize(
    ("signal", "grande_finished", "no_juego", "allowed"),
    [
        (S.MEDIAS_REYES, False, False, True),  # medias de reyes, en cualquier momento
        (S.MEDIAS, False, False, False),  # C.VIII-5: otras medias, tras grande
        (S.MEDIAS, True, False, True),
        (S.MEDIAS_ASES, False, False, False),
        (S.MEDIAS_ASES, True, False, True),
        (S.TREINTA, True, False, False),  # tras "juego no" de los cuatro
        (S.TREINTA, True, True, True),
        (S.VEINTINUEVE, True, False, False),  # S-4
        (S.VEINTINUEVE, True, True, True),
        (S.DUPLES, False, False, True),
        (S.JUEGO, False, False, True),
    ],
)
def test_timing(signal: Signal, grande_finished: bool, no_juego: bool, allowed: bool) -> None:
    assert timing_allows(signal, SignalContext(grande_finished, no_juego)) is allowed


def test_legal_signals_excludes_made_and_untimely() -> None:
    cards = cards_from_codes("10O 10C 10E 7B")  # medias de sotas + juego
    early = SignalContext(grande_finished=False, everyone_said_no_juego=False)
    assert legal_signals(cards, POLICY, early, frozenset()) == (S.JUEGO,)
    late = SignalContext(grande_finished=True, everyone_said_no_juego=False)
    assert legal_signals(cards, POLICY, late, frozenset({S.JUEGO})) == (S.MEDIAS,)


def test_without_eight_kings_three_is_not_a_king() -> None:
    policy = RankingPolicy(kings_are_threes=False, aces_are_twos=False)
    # 12 + 3 no forman pareja; total 10 + 3 + 6 + 5 = 24: nada que señar.
    assert true_signals(cards_from_codes("12O 3C 6E 5B"), policy) == {S.CIEGO}
