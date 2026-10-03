"""Reglas del Reglamento FEM sobre el mus y los descartes."""

from tests.factories import started_game
from tests.play import actor, all_mus, discard_all, hand_of

from mus_engine import CutMusAction, DiscardAction, MusAction, Phase
from mus_engine.events import CardsDiscarded, DeckShuffled, DiscardPileReshuffled
from mus_engine.players import SeatId, are_teammates, discard_order


def test_c_iv_4_orden_para_dar_o_cortar_el_mus() -> None:
    """C.IV-4: el 2º sólo habla tras dar mus el mano; el 4º tras la pareja mano."""
    game = started_game(first_dealer=1)  # mano = 2
    assert game.current_actors() == (2,)
    game.apply_action(2, MusAction())
    assert game.current_actors() == (3,)  # mano de la pareja postre
    game.apply_action(3, MusAction())
    assert game.current_actors() == (0,)  # compañero del mano
    assert are_teammates(SeatId(0), SeatId(2))
    game.apply_action(0, MusAction())
    assert game.current_actors() == (1,)  # 4º, tras la pareja mano


def test_c_iv_2_el_mus_se_corta_con_cualquier_naipe() -> None:
    """C.IV-2: cortar el mus siempre es legal en el turno, sean cuales sean los naipes."""
    for seed in range(20):
        game = started_game(seed=seed)
        assert game.get_legal_actions(game.mano).contains(CutMusAction())


def test_voc_paso_del_mano_corta_el_mus() -> None:
    """Voc. "Paso": cortar el mus si se es mano. Un solo corte termina el mus."""
    game = started_game()
    game.apply_action(game.mano, CutMusAction())
    assert game.phase is Phase.LANCE


def test_c_iii_11_descarte_del_que_reparte_al_mano() -> None:
    """C.III-11: el primero en descartarse es el que da; el mano es el último."""
    game = started_game(first_dealer=2)  # mano = 3
    all_mus(game)
    order = []
    for _ in range(4):
        order.append(actor(game))
        game.apply_action(order[-1], DiscardAction(hand_of(game, order[-1])[:1]))
    assert order == [2, 1, 0, 3]
    assert tuple(order) == discard_order(SeatId(3))


def test_c_iii_2_se_sirve_de_una_vez_y_por_el_mismo_orden() -> None:
    """C.III-2: en los descartes se sirve de una vez a cada jugador y por el mismo orden."""
    game = started_game(first_dealer=3)  # mano = 0
    stock = game.get_state().current_hand.stock.cards
    all_mus(game)
    counts = {3: 1, 2: 4, 1: 2, 0: 3}
    for _ in range(4):
        player = actor(game)
        game.apply_action(player, DiscardAction(hand_of(game, player)[: counts[player]]))
    received = {
        e.event.seat: e.event.received
        for e in game.event_log
        if isinstance(e.event, CardsDiscarded)
    }
    position = 0
    for seat in (3, 2, 1, 0):
        assert received[SeatId(seat)] == stock[position : position + counts[seat]]
        position += counts[seat]


def test_c_iii_15_se_rebaraja_todo_el_descarte() -> None:
    """C.III-15 / D-07: al acabarse el mazo se baraja todo el descarte, incluida la ronda."""
    game = started_game(first_dealer=3)
    all_mus(game)
    discard_all(game, 4)  # 16 al descarte, quedan 8 en el mazo
    all_mus(game)
    this_round = [hand_of(game, p) for p in range(4)]
    old_pile = set(game.get_state().current_hand.discard_pile)
    discard_all(game, 4)
    log = game.event_log
    reshuffled = [e.event for e in log if isinstance(e.event, DiscardPileReshuffled)]
    assert len(reshuffled) == 1
    assert reshuffled[0].cards == 16 + 16
    new_deck = [e.event for e in log if isinstance(e.event, DeckShuffled)][-1]
    assert set(new_deck.order) == old_pile | {c for h in this_round for c in h}


def test_d13_entre_uno_y_cuatro_naipes() -> None:
    """D-13: mínimo 1 y máximo 4 naipes; configurable."""
    game = started_game(min_discard=2, max_discard=3)
    all_mus(game)
    sizes = {len(a.cards) for a in game.get_legal_actions(actor(game)).actions}  # type: ignore[attr-defined]
    assert sizes == {2, 3}


def test_d14_sin_limite_de_rondas_de_mus() -> None:
    """D-14: se puede dar mus tantas veces como se quiera."""
    game = started_game()
    for _ in range(10):
        all_mus(game)
        discard_all(game, 1)
    assert game.get_state().current_hand.mus.round == 11
    assert game.phase is Phase.MUS_DECISION
