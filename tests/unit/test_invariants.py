"""Los invariantes detectan estados corruptos."""

from typing import Any

import pytest
from tests.factories import started_game

from mus_engine import GameScore, Phase
from mus_engine.cards import Deck
from mus_engine.errors import InvariantViolationError
from mus_engine.game import invariants
from mus_engine.game.state import GameState
from mus_engine.players import SeatId, TeamId


def _state() -> GameState:
    return started_game().get_state()


def test_valid_state_passes() -> None:
    state = _state()
    invariants.check_state(state)
    invariants.check_resting(state)
    invariants.check_transition(state, state)


def test_duplicated_card_detected() -> None:
    state = _state()
    assert state.hand is not None
    hands = list(state.hand.hands)
    hands[1] = (hands[0][0], *hands[1][1:])  # duplica un naipe y pierde otro
    bad = state.evolve(hand=_replace_hand(state, hands=tuple(hands)))
    with pytest.raises(InvariantViolationError, match="Naipes"):
        invariants.check_state(bad)


def test_missing_card_detected() -> None:
    state = _state()
    assert state.hand is not None
    bad = state.evolve(hand=_replace_hand(state, stock=Deck(state.hand.stock.cards[1:])))
    with pytest.raises(InvariantViolationError):
        invariants.check_state(bad)


def test_wrong_hand_size_detected() -> None:
    state = _state()
    assert state.hand is not None
    hands = list(state.hand.hands)
    extra = state.hand.stock.cards[0]
    hands[2] = (*hands[2], extra)
    bad = state.evolve(
        hand=_replace_hand(state, hands=tuple(hands), stock=Deck(state.hand.stock.cards[1:]))
    )
    with pytest.raises(InvariantViolationError, match="5 naipes"):
        invariants.check_state(bad)


def test_wrong_mano_detected() -> None:
    state = _state()
    assert state.hand is not None
    wrong = SeatId((state.hand.mano + 1) % 4)
    with pytest.raises(InvariantViolationError, match="mano"):
        invariants.check_state(state.evolve(hand=_replace_hand(state, mano=wrong)))


def test_target_reached_without_winner_detected() -> None:
    state = _state().evolve(score=GameScore(tantos=(40, 0)))
    with pytest.raises(InvariantViolationError, match="alcanzó"):
        invariants.check_state(state)


def test_winner_requires_game_over() -> None:
    with pytest.raises(InvariantViolationError, match="ganador"):
        invariants.check_state(_state().evolve(winner=TeamId.A))
    with pytest.raises(InvariantViolationError, match="ganador"):
        invariants.check_state(_state().evolve(phase=Phase.GAME_OVER))


def test_automatic_phase_is_not_resting() -> None:
    with pytest.raises(InvariantViolationError, match="automática"):
        invariants.check_resting(_state().evolve(phase=Phase.DEAL))


def test_score_cannot_decrease() -> None:
    before = _state().evolve(score=GameScore(tantos=(10, 5)))
    after = before.evolve(score=GameScore(tantos=(9, 5)))
    with pytest.raises(InvariantViolationError, match="disminuido"):
        invariants.check_transition(before, after)


def test_games_must_increase_by_one() -> None:
    before = _state().evolve(score=GameScore(tantos=(30, 5), games=(0, 0)))
    ok = before.evolve(score=GameScore(tantos=(0, 0), games=(1, 0)))
    invariants.check_transition(before, ok)
    bad = before.evolve(score=GameScore(tantos=(0, 0), games=(1, 1)))
    with pytest.raises(InvariantViolationError, match="Juegos"):
        invariants.check_transition(before, bad)


def test_hand_number_cannot_go_back() -> None:
    state = _state()
    assert state.hand is not None
    older = state.evolve(hand=_replace_hand(state, number=0))
    with pytest.raises(InvariantViolationError, match="jugada"):
        invariants.check_transition(state, older)
    with pytest.raises(InvariantViolationError, match="jugada"):
        invariants.check_transition(state, state.evolve(hand=None))


def test_finished_game_cannot_change() -> None:
    over = _state().evolve(phase=Phase.GAME_OVER, winner=TeamId.B, score=GameScore((10, 40)))
    with pytest.raises(InvariantViolationError, match="terminada"):
        invariants.check_transition(over, over.evolve(score=GameScore((11, 40))))


def _replace_hand(state: GameState, **changes: object):  # type: ignore[no-untyped-def]
    import dataclasses

    assert state.hand is not None
    return dataclasses.replace(state.hand, **changes)  # type: ignore[arg-type]


def test_state_before_first_hand_passes() -> None:
    from mus_engine import Game

    invariants.check_state(Game(seed=1).get_state())


def _with_mus(state: GameState, **changes: Any) -> GameState:
    import dataclasses

    hand = state.current_hand
    return state.evolve(
        hand=dataclasses.replace(hand, mus=dataclasses.replace(hand.mus, **changes))
    )


def test_mus_speaker_out_of_range() -> None:
    with pytest.raises(InvariantViolationError, match="fuera de rango"):
        invariants.check_state(_with_mus(_state(), speaker_index=4))


def test_no_mus_after_cut() -> None:
    with pytest.raises(InvariantViolationError, match="cortarse"):
        invariants.check_state(_with_mus(_state(), cut_by=SeatId(0)))


def test_no_lance_without_cut() -> None:
    with pytest.raises(InvariantViolationError, match="sin cortar"):
        invariants.check_state(_state().evolve(phase=Phase.LANCE))


def test_pending_discards_only_in_discard_phase() -> None:
    state = _state()
    card = state.current_hand.hand_of(SeatId(0))[0]
    discards = (frozenset({card}), None, None, None)
    with pytest.raises(InvariantViolationError, match="pendientes"):
        invariants.check_state(_with_mus(state, discards=discards))


def test_discard_must_belong_to_hand() -> None:
    state = _state().evolve(phase=Phase.DISCARD)
    foreign = state.current_hand.hand_of(SeatId(1))[0]
    discards = (frozenset({foreign}), None, None, None)
    with pytest.raises(InvariantViolationError, match="no es de su mano"):
        invariants.check_state(_with_mus(state, discards=discards))
