"""Reglas del Reglamento FEM sobre el reparto."""

from tests.factories import started_game

from mus_engine.events import DeckShuffled
from mus_engine.players import deal_order


def test_c_iii_2_naipes_de_uno_en_uno_empezando_por_la_mano() -> None:
    """C.III-2: los naipes se dan de uno en uno; empieza la mano (Voc. "Mano")."""
    game = started_game(seed=77)
    state = game.get_state()
    assert state.hand is not None
    (shuffle,) = [e.event for e in game.event_log if isinstance(e.event, DeckShuffled)]
    order = deal_order(state.hand.dealer)
    assert order[0] == state.hand.mano
    for i, card in enumerate(shuffle.order[:16]):
        assert state.hand.hand_of(order[i % 4])[i // 4] == card


def test_c_iii_1_primer_reparto_por_sorteo() -> None:
    """C.III-1: el primer reparto se sortea; con distintas semillas reparten todos."""
    dealers = {started_game(seed=s).dealer for s in range(80)}
    assert dealers == {0, 1, 2, 3}
