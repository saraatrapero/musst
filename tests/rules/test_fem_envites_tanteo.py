"""Reglas del Reglamento FEM sobre envites, órdago y tanteo (y decisiones aprobadas)."""

from tests.factories import game_at_lance
from tests.play import act, pass_lance, points_events

from mus_engine import (
    AcceptAction,
    BetAction,
    OrdagoAction,
    PassAction,
    RaiseAction,
    RejectAction,
)
from mus_engine.errors import NotYourTurnError
from mus_engine.events import HandsRevealed
from mus_engine.players import TeamId

HANDS = ("12O 12C 12E 1B", "1C 1E 4O 5O", "7O 7C 6E 5B", "11O 10C 2B 4B")


def scored(game) -> list[tuple[str, int, str, str]]:  # type: ignore[no-untyped-def]
    return [(p.team, p.points, p.lance, p.reason) for p in points_events(game)]


def test_r21_envido_son_dos_tantos_o_el_numero_que_se_diga() -> None:
    """Voc. "Envido": apostar dos tantos o el número indicado."""
    game = game_at_lance(HANDS)
    legal = game.get_legal_actions(0)
    assert legal.contains(BetAction(2))
    assert legal.contains(BetAction(17))
    assert not legal.contains(BetAction(1))


def test_r24_el_companero_no_sube_con_envite_en_litigio() -> None:
    """C.VI-2: con un envite en litigio el compañero no puede subirlo."""
    game = game_at_lance(HANDS)
    act(game, BetAction(2))
    assert 2 not in game.current_actors()
    try:
        game.apply_action(2, RaiseAction(2))
    except NotYourTurnError:
        pass
    else:  # pragma: no cover
        raise AssertionError("El compañero no puede revocar")


def test_r25_vale_el_quiero_de_un_rival() -> None:
    """C.VI-4: si un jugador quiere y su compañero no, vale el quiero."""
    game = game_at_lance(HANDS)
    act(game, BetAction(2), RejectAction(), AcceptAction())
    assert game.get_state().current_hand.outcomes[0].resolution.value == "accepted"


def test_r27_negada_por_no_aceptar_la_primera_apuesta() -> None:
    """Voc. "Negada": tanto ganado por la no aceptación de la primera apuesta."""
    game = game_at_lance(HANDS)
    act(game, BetAction(5), RejectAction(), RejectAction())
    assert scored(game) == [("A", 1, "grande", "negada")]


def test_r28_d16_deje_en_pares_juego_y_punto() -> None:
    """C.VII-1 / Voc. "Deje" / D-16: revoque no querido = lo querido + 1 en pares."""
    game = game_at_lance(HANDS)
    pass_lance(game)
    pass_lance(game)
    act(game, BetAction(4), RaiseAction(3), RejectAction(), RejectAction())
    assert scored(game)[0] == ("B", 5, "pares", "envite_no_querido")


def test_r29_negadas_en_el_acto_resto_al_final() -> None:
    """C.VII-2: en cada lance la negada; al final envites aceptados y valor de jugadas."""
    game = game_at_lance(HANDS)
    act(game, BetAction(2), RejectAction(), RejectAction())  # grande: negada en el acto
    assert scored(game) == [("A", 1, "grande", "negada")]
    act(game, BetAction(2), AcceptAction())  # chica: querida, se cuenta al final
    assert len(scored(game)) == 1
    pass_lance(game)
    assert scored(game)[1] == ("B", 2, "chica", "envite")


def test_r30_envites_aunque_pasen_del_tanteo() -> None:
    """C.VI-6: los envites se cuentan al final, aunque pasen de los tantos del juego."""
    game = game_at_lance(HANDS)
    act(game, BetAction(100), AcceptAction())
    pass_lance(game)
    pass_lance(game)
    assert game.winner is TeamId.A
    assert game.get_state().score.tantos[0] == 100


def test_r31_solo_el_ordago_aceptado_resuelve_en_el_acto() -> None:
    """C.VI-6: sólo el órdago aceptado permite enseñar los naipes y resolver."""
    game = game_at_lance(HANDS)
    act(game, BetAction(2), AcceptAction())
    assert not any(isinstance(e.event, HandsRevealed) for e in game.event_log)
    act(game, OrdagoAction(), AcceptAction())
    assert any(isinstance(e.event, HandsRevealed) for e in game.event_log)
    assert game.is_finished


def test_r32_el_ordago_anula_envites_anteriores() -> None:
    """C.VII-12: el órdago aceptado anula los envites aceptados en lances anteriores."""
    game = game_at_lance(HANDS, tantos=(35, 0))
    act(game, BetAction(10), AcceptAction())  # grande querida para A (le daría el juego)
    act(game, OrdagoAction(), AcceptAction())  # órdago a chica de A; la gana B
    assert game.winner is TeamId.B


def test_r33_c_vi_7_tras_no_quiero_el_lance_es_de_los_rivales() -> None:
    """C.VI-7: aunque la mano lleve la máxima, si no acepta el lance es de sus rivales."""
    hands = ("12O 12C 3E 3B", "1C 1E 4O 5O", "7O 7C 6E 5B", "11O 10C 2B 4B")  # 0: cuatro reyes
    game = game_at_lance(hands)
    pass_lance(game)
    pass_lance(game)
    act(game, PassAction(), BetAction(2), RejectAction(), RejectAction())
    assert ("B", 1, "pares", "negada") in scored(game)
    assert ("B", 1, "pares", "pares") in scored(game)  # pareja de ases del jugador 1
    assert not [s for s in scored(game) if s[0] == "A" and s[2] == "pares"]


def test_r34_al_final_se_ensenan_las_cuatro_manos() -> None:
    """C.VII-9: terminado el juego o punto, los cuatro enseñan todos sus naipes."""
    game = game_at_lance(HANDS)
    for _ in range(3):
        pass_lance(game)
    (revealed,) = [e.event for e in game.get_events() if isinstance(e.event, HandsRevealed)]
    assert len(revealed.hands) == 4


def test_d20_una_sola_pareja_con_juego_cobra_sin_envites() -> None:
    """D-20: si sólo una pareja tiene juego no hay envites y cobra al final."""
    game = game_at_lance(HANDS)
    for _ in range(3):
        pass_lance(game)
    assert ("A", 3, "juego", "juego") in scored(game)


def test_d22_el_recuento_se_detiene_al_alcanzar_el_tanteo() -> None:
    """D-22: gana la primera pareja que llega al tanteo en el orden de lances."""
    game = game_at_lance(HANDS, tantos=(38, 39))
    for _ in range(3):
        pass_lance(game)
    assert game.winner is TeamId.B
    assert game.get_state().score.tantos == (39, 40)


def test_d23_se_gana_al_llegar_o_superar_el_tanteo() -> None:
    """D-23: se gana con tantos >= target_score. A suma 1 + 3 + 3 = 7 en la jugada."""
    game = game_at_lance(HANDS, tantos=(32, 0))
    for _ in range(3):
        pass_lance(game)
    assert game.winner is None
    assert game.get_state().score.tantos == (39, 1)
    game = game_at_lance(HANDS, tantos=(33, 0))
    for _ in range(3):
        pass_lance(game)
    assert game.winner is TeamId.A
    assert game.get_state().score.tantos == (40, 1)
