"""Tests de reglas del Reglamento FEM relativas a cartas y baraja.

Cada test cita el artículo (C.<capítulo>-<artículo>) o la decisión aprobada (D-xx,
ver docs/rules.md) que verifica.
"""

from collections import Counter

from mus_engine.cards import Deck, Rank, RankingPolicy, Suit
from mus_engine.config import GameConfig


def test_r01_baraja_espanola_de_cuarenta_naipes() -> None:
    """C.II-3, C.III-1: baraja española de cuarenta naipes."""
    deck = Deck.standard(GameConfig().deck_type)
    assert len(deck) == 40
    assert len(set(deck)) == 40
    assert {card.suit for card in deck} == {Suit.OROS, Suit.COPAS, Suit.ESPADAS, Suit.BASTOS}


def test_r02_ocho_reyes_y_ocho_ases() -> None:
    """C.II-3: modalidad de ocho reyes y ocho ases (treses = reyes, doses = ases)."""
    policy = RankingPolicy.from_config(GameConfig())
    effective = Counter(policy.effective_rank(card) for card in Deck.standard())
    assert effective[Rank.REY] == 8
    assert effective[Rank.AS] == 8
    assert effective[Rank.TRES] == 0
    assert effective[Rank.DOS] == 0


def test_d01_valor_de_los_naipes_para_juego() -> None:
    """D-01: figuras (y treses) valen 10, ases (y doses) 1, resto su número."""
    policy = RankingPolicy.from_config(GameConfig())
    total = sum(policy.game_points(card) for card in Deck.standard())
    # Por palo: tres, sota, caballo y rey = 4 x 10 = 40; as y dos = 2 x 1 = 2;
    # cuatro a siete = 4 + 5 + 6 + 7 = 22. Total por palo: 64.
    assert total == 64 * 4
