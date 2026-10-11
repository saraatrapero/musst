"""Señas y miradas dentro de la partida (C.VIII; IA-1, IA-2)."""

import dataclasses

import pytest
from tests.factories import game_at_lance, game_with_state, started_game
from tests.play import act, pass_lance

from mus_engine import AcceptAction, BetAction, Game, GameConfig, PassAction, Phase, RejectAction
from mus_engine.errors import IllegalActionError, InvalidStateError, NotYourTurnError
from mus_engine.events import EventEnvelope, GazeChanged, SignalMade, SignalSeen, Visibility
from mus_engine.game.actions import ClockTick, SignalAction
from mus_engine.game.gaze import GazeState
from mus_engine.players import SeatId
from mus_engine.rules.signals import Signal

S = Signal
# 0: R R R A (medias de reyes, 31) · 1: A A 4 5 (pareja de ases) · 2: 7 7 6 5 · 3: C S 2 4
HANDS = ("12O 12C 12E 1B", "1C 1E 4O 5O", "7O 7C 6E 5B", "11O 10C 2B 4B")


def with_gaze(game: Game, *targets: int | None) -> Game:
    """Fija las miradas (y que duren) para poder razonar el caso."""
    gaze = GazeState(tuple(None if t is None else SeatId(t) for t in targets), (3, 3, 3, 3))
    return game_with_state(game.get_state().evolve(gaze=gaze))


def lance_game() -> Game:
    return game_at_lance(HANDS, signals_enabled=True)


def test_disabled_by_default() -> None:
    game = game_at_lance(HANDS)
    assert game.get_state().gaze is None
    assert not any(isinstance(a, SignalAction) for a in game.get_legal_actions(2).actions)
    with pytest.raises(InvalidStateError, match="no están activadas"):
        game.apply_action(0, SignalAction(S.MEDIAS_REYES))
    with pytest.raises(InvalidStateError, match="reloj"):
        game.tick()
    assert game.get_observation(0).gaze is None


def test_no_signals_before_the_cut() -> None:
    """C.VIII-3 / S-2: no se pasan señas hasta que se haya cortado el mus."""
    game = started_game(signals_enabled=True)
    assert game.phase is Phase.MUS_DECISION
    assert game.get_observation(0).gaze is not None
    for seat in range(4):
        assert not any(isinstance(a, SignalAction) for a in game.get_legal_actions(seat).actions)
    with pytest.raises(InvalidStateError, match="cortar el mus"):
        game.apply_action(0, SignalAction(S.CIEGO))


def test_any_player_can_signal_without_taking_the_turn() -> None:
    game = with_gaze(lance_game(), 2, None, 0, None)  # 0 y 2 se miran
    assert game.current_actors() == (0,)
    legal_2 = game.get_legal_actions(2)
    assert SignalAction(S.PARES) in legal_2.actions
    assert PassAction() not in legal_2.actions  # no es su turno
    game.apply_action(2, SignalAction(S.PARES))
    assert game.current_actors() == (0,)  # el turno no cambia
    with pytest.raises(NotYourTurnError):
        game.apply_action(2, PassAction())


def test_partner_looking_sees_the_signal() -> None:
    game = with_gaze(lance_game(), 2, None, 0, None)
    game.apply_action(0, SignalAction(S.MEDIAS_REYES))
    assert game.get_observation(2).signals_seen == ((0, S.MEDIAS_REYES),)
    assert game.get_observation(0).my_signals == ((S.MEDIAS_REYES, (2,)),)
    for rival in (1, 3):
        assert game.get_observation(rival).signals_seen == ()


def test_rival_looking_intercepts_the_signal() -> None:
    game = with_gaze(lance_game(), None, 0, None, None)  # sólo el rival 1 mira a 0
    game.apply_action(0, SignalAction(S.TREINTA_Y_UNA))
    assert game.get_observation(1).signals_seen == ((0, S.TREINTA_Y_UNA),)
    assert game.get_observation(2).signals_seen == ()  # el compañero no la vio
    assert game.get_observation(0).my_signals == ((S.TREINTA_Y_UNA, (1,)),)


def test_nobody_looking_loses_the_signal() -> None:
    game = with_gaze(lance_game(), None, None, None, None)
    game.apply_action(0, SignalAction(S.MEDIAS_REYES))
    assert game.get_observation(0).my_signals == ((S.MEDIAS_REYES, ()),)
    assert all(game.get_observation(p).signals_seen == () for p in (1, 2, 3))


def test_signal_events_are_private() -> None:
    game = with_gaze(lance_game(), 2, 0, 0, None)
    game.apply_action(0, SignalAction(S.MEDIAS_REYES))
    made = [e for e in game.event_log if isinstance(e.event, SignalMade)]
    seen = [e for e in game.event_log if isinstance(e.event, SignalSeen)]
    assert [(e.visibility, e.audience) for e in made] == [(Visibility.PRIVATE, 0)]
    assert sorted(e.audience for e in seen) == [1, 2]  # type: ignore[type-var]
    assert all(e.visibility is Visibility.PRIVATE for e in seen)
    assert not [e for e in game.get_events(3) if isinstance(e.event, (SignalMade, SignalSeen))]


def test_false_signal_is_rejected() -> None:
    """C.VIII-4 / IA-1: sólo se seña la jugada que se tiene."""
    game = lance_game()
    with pytest.raises(IllegalActionError, match="no corresponde a tu jugada"):
        game.apply_action(0, SignalAction(S.DUPLES))
    with pytest.raises(IllegalActionError, match="no corresponde"):
        game.apply_action(3, SignalAction(S.PARES))


def test_partial_signal_is_rejected() -> None:
    """C.VIII-6: con medias de reyes no se seña "dos reyes"."""
    with pytest.raises(IllegalActionError, match="completas"):
        lance_game().apply_action(0, SignalAction(S.DOS_REYES))


def test_each_signal_once_per_hand() -> None:
    game = lance_game()
    game.apply_action(1, SignalAction(S.DOS_ASES))
    with pytest.raises(IllegalActionError, match="Ya has hecho"):
        game.apply_action(1, SignalAction(S.DOS_ASES))
    game.apply_action(1, SignalAction(S.PARES))  # otra seña verdadera sí


def test_medias_not_of_kings_only_after_grande() -> None:
    """C.VIII-5: las medias que no sean de reyes se pasan después del lance de grande."""
    hands = ("10O 10C 10E 7B", "1C 1E 4O 5O", "7O 7C 6E 5B", "11O 10B 2B 4B")
    game = game_at_lance(hands, signals_enabled=True)
    with pytest.raises(IllegalActionError, match="todavía"):
        game.apply_action(0, SignalAction(S.MEDIAS))
    pass_lance(game)  # termina grande
    game.apply_action(0, SignalAction(S.MEDIAS))


def test_treinta_after_everyone_says_no_juego() -> None:
    """C.VIII-2 / C.VIII-5: treinta, cuando los cuatro han dicho "juego no"."""
    hands = ("12O 11C 5E 5B", "10C 6E 4O 4C", "7O 11O 6C 1E", "12C 10O 2B 4B")  # nadie con juego
    game = game_at_lance(hands, signals_enabled=True)
    with pytest.raises(IllegalActionError, match="todavía"):
        game.apply_action(0, SignalAction(S.TREINTA))
    pass_lance(game)  # grande
    pass_lance(game)  # chica
    pass_lance(game)  # pares
    lance = game.get_state().current_hand.lance
    assert lance is not None
    assert lance.value == "punto"
    game.apply_action(0, SignalAction(S.TREINTA))


def test_signals_reset_every_hand() -> None:
    game = lance_game()
    game.apply_action(1, SignalAction(S.DOS_ASES))
    for _ in range(3):
        pass_lance(game)
    assert game.get_state().current_hand.signals == ()


def test_tick_moves_gaze_and_is_public() -> None:
    game = lance_game()
    before = game.get_state().gaze
    events: list[EventEnvelope] = []
    for _ in range(6):
        events.extend(game.tick())
    assert game.get_state().gaze != before
    assert all(e.visibility is Visibility.PUBLIC for e in events)
    assert any(isinstance(e.event, GazeChanged) for e in events)
    assert game.get_observation(3).gaze == game.get_state().gaze.targets  # type: ignore[union-attr]


def test_actions_also_advance_gaze() -> None:
    game = with_gaze(lance_game(), 2, None, 0, None)
    game.apply_action(0, PassAction())
    assert game.get_state().gaze.remaining == (2, 2, 2, 2)  # type: ignore[union-attr]


def test_signals_and_ticks_are_replayed_from_events() -> None:
    from mus_engine import GameRecord, GameReplay

    game = Game(seed=5, config=GameConfig(signals_enabled=True, first_dealer=3))
    game.start()
    game.apply_action(0, game.get_legal_actions(0).actions[1])  # corta el mus
    game.tick()
    for seat in range(4):
        options = [a for a in game.get_legal_actions(seat).actions if isinstance(a, SignalAction)]
        if options:
            game.apply_action(seat, options[0])
    game.tick()
    act(game, BetAction(2), AcceptAction())
    record = GameRecord.from_events(game.event_log)
    assert record == game.record
    assert sum(isinstance(e, ClockTick) for e in record.actions) == 2
    assert GameReplay.from_events(game.event_log).jump_to(len(record.actions)) == game.get_state()


def test_signalling_keeps_bets_intact() -> None:
    game = with_gaze(lance_game(), 2, None, 0, None)
    act(game, BetAction(2))
    game.apply_action(2, SignalAction(S.PARES))  # el compañero seña mientras se responde
    act(game, RejectAction(), RejectAction())
    assert game.get_state().score.tantos == (1, 0)


def test_state_with_false_signal_violates_invariants() -> None:
    from mus_engine.errors import InvariantViolationError
    from mus_engine.game import invariants
    from mus_engine.game.state import SignalRecord

    state = lance_game().get_state()
    hand = dataclasses.replace(state.current_hand, signals=(SignalRecord(SeatId(3), S.DUPLES, ()),))
    with pytest.raises(InvariantViolationError, match="falsa"):
        invariants.check_state(state.evolve(hand=hand))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ("gaze_without_signals", "si y sólo si"),
        ("self_gaze", "sí mismo"),
        ("long_gaze", "Duración"),
        ("signal_disabled", "desactivadas"),
        ("repeated", "repetida"),
        ("self_seen", "propia seña"),
    ],
)
def test_signal_invariants(change: str, message: str) -> None:
    from mus_engine.errors import InvariantViolationError
    from mus_engine.game import invariants
    from mus_engine.game.state import SignalRecord

    state = lance_game().get_state()
    hand = state.current_hand
    pares = SignalRecord(SeatId(1), S.PARES, ())
    if change == "gaze_without_signals":
        state = game_at_lance(HANDS).get_state().evolve(gaze=state.gaze)
    elif change == "self_gaze":
        state = state.evolve(gaze=GazeState((SeatId(0), None, None, None), (1, 1, 1, 1)))
    elif change == "long_gaze":
        state = state.evolve(gaze=GazeState((None, None, None, None), (99, 1, 1, 1)))
    elif change == "signal_disabled":
        plain = game_at_lance(HANDS).get_state()
        state = plain.evolve(hand=dataclasses.replace(plain.current_hand, signals=(pares,)))
    elif change == "repeated":
        state = state.evolve(hand=dataclasses.replace(hand, signals=(pares, pares)))
    else:
        own = SignalRecord(SeatId(1), S.PARES, (SeatId(1),))
        state = state.evolve(hand=dataclasses.replace(hand, signals=(own,)))
    with pytest.raises(InvariantViolationError, match=message):
        invariants.check_state(state)
