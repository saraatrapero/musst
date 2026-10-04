"""Bordes del marcador: 0, 1, 39, 40 y llegadas al tanteo durante la jugada."""

import pytest
from tests.factories import game_at_lance
from tests.play import act, pass_lance, points_events

from mus_engine import AcceptAction, BetAction, GameScore, Phase, RejectAction
from mus_engine.players import TeamId

# Todos pasan: grande A+1, chica B+1, pares A+3, juego A+3.
HANDS = ("12O 12C 12E 1B", "1C 1E 4O 5O", "7O 7C 6E 5B", "11O 10C 2B 4B")


def play_all_pass(tantos: tuple[int, int]):  # type: ignore[no-untyped-def]
    game = game_at_lance(HANDS, tantos=tantos)
    while game.phase is Phase.LANCE and game.get_state().current_hand.number == 1:
        pass_lance(game)
    return game


@pytest.mark.parametrize(
    ("tantos", "winner", "final"),
    [
        ((0, 0), None, (7, 1)),
        ((1, 1), None, (8, 2)),
        ((39, 0), TeamId.A, (40, 0)),  # la grande en paso basta
        ((0, 39), TeamId.B, (1, 40)),  # A suma la grande; B gana con la chica
        ((39, 39), TeamId.A, (40, 39)),  # la grande se cuenta antes que la chica
        ((38, 39), TeamId.B, (39, 40)),  # A llega a 39 con la grande; B gana con la chica
        ((39, 38), TeamId.A, (40, 38)),
        ((37, 39), TeamId.B, (38, 40)),
        ((36, 39), TeamId.B, (37, 40)),
        ((34, 38), TeamId.A, (41, 39)),  # 35, B 39, pares 38, el juego (3) lleva a A a 41
    ],
)
def test_end_of_hand_counting(tantos, winner, final) -> None:  # type: ignore[no-untyped-def]
    game = play_all_pass(tantos)
    assert game.winner is winner
    if winner is None:
        assert game.get_state().score.tantos == final
    else:
        assert game.get_state().score.tantos == final


def test_counting_stops_when_target_reached() -> None:
    game = play_all_pass((0, 39))
    reasons = [(p.team, p.lance) for p in points_events(game)]
    assert reasons == [("A", "grande"), ("B", "chica")]  # pares y juego ya no se cuentan


@pytest.mark.parametrize(("tantos", "final"), [((39, 39), (40, 39)), ((39, 0), (40, 0))])
def test_negada_ends_the_game_mid_hand(tantos, final) -> None:  # type: ignore[no-untyped-def]
    game = game_at_lance(HANDS, tantos=tantos)
    act(game, BetAction(2), RejectAction(), RejectAction())
    assert game.winner is TeamId.A
    assert game.get_state().score.tantos == final
    assert game.phase is Phase.GAME_OVER


def test_rival_at_39_cannot_score_after_game_ends() -> None:
    game = game_at_lance(HANDS, tantos=(39, 39))
    act(game, BetAction(2), RejectAction(), RejectAction())
    assert game.get_state().score.tantos_of(TeamId.B) == 39


def test_accepted_bet_can_exceed_target() -> None:
    """C.VI-6: los envites se cuentan aunque pasen del tanteo del juego."""
    game = game_at_lance(HANDS, tantos=(35, 0))
    act(game, BetAction(30), AcceptAction())
    pass_lance(game)
    pass_lance(game)
    assert game.winner is TeamId.A
    assert game.get_state().score.tantos == (65, 0)


def test_score_never_decreases_during_a_hand() -> None:
    game = game_at_lance(HANDS, tantos=(10, 20))
    previous = game.get_state().score.tantos
    while game.phase is Phase.LANCE:
        pass_lance(game)
        current = game.get_state().score.tantos
        assert all(c >= p for c, p in zip(current, previous, strict=True))
        previous = current


def _finish_hand(game) -> None:  # type: ignore[no-untyped-def]
    number = game.get_state().current_hand.number
    while game.phase is Phase.LANCE and game.get_state().current_hand.number == number:
        pass_lance(game)


def test_several_games_reset_tantos() -> None:
    game = game_at_lance(HANDS, tantos=(39, 20), games_to_win=3)
    _finish_hand(game)  # la grande en paso se anota al final: A llega a 40
    assert game.get_state().score == GameScore((0, 0), (1, 0))
    assert not game.is_finished


def test_last_game_of_the_match() -> None:
    game = game_at_lance(HANDS, tantos=(39, 20), games=(2, 1), games_to_win=3)
    _finish_hand(game)
    assert game.is_finished
    assert game.winner is TeamId.A
    assert game.get_state().score == GameScore((40, 20), (3, 1))
