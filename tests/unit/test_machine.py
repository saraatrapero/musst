"""Tests del mecanismo genérico de validación de la máquina de estados.

Se registra un manejador de prueba para la fase MUS_DECISION y se verifica la cadena
de validación: turno → legalidad → error específico → aplicación → fases automáticas.
"""

import pytest
from tests.factories import started_game

from mus_engine import CutMusAction, LegalActions, MusAction, PassAction, Phase
from mus_engine.errors import (
    IllegalActionError,
    InvalidBetError,
    InvalidStateError,
    NotYourTurnError,
)
from mus_engine.events import Emission, PhaseChanged
from mus_engine.game import machine
from mus_engine.game.actions import Action
from mus_engine.game.flow import Step
from mus_engine.game.state import GameState
from mus_engine.players import SeatId


class FakeHandler:
    """Sólo el jugador 0 actúa; sólo puede pedir mus."""

    def actors(self, state: GameState) -> tuple[SeatId, ...]:
        return (SeatId(0),)

    def legal_actions(self, state: GameState, player: SeatId) -> LegalActions:
        return LegalActions(actions=(MusAction(),))

    def explain_illegal(
        self, state: GameState, player: SeatId, action: Action
    ) -> IllegalActionError:
        return InvalidBetError("explicación específica")

    def apply(self, state: GameState, player: SeatId, action: Action) -> Step:
        return state.evolve(phase=Phase.DEAL, pending_dealer=SeatId(0)), (
            Emission.public(PhaseChanged("fake")),
        )


@pytest.fixture
def fake_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(machine.HANDLERS, Phase.MUS_DECISION, FakeHandler())


def test_without_handler_every_action_is_invalid_state() -> None:
    state = started_game().get_state()
    assert machine.actors(state) == ()
    assert not machine.legal_actions(state, SeatId(0))
    with pytest.raises(InvalidStateError):
        machine.validate(state, SeatId(0), MusAction())


@pytest.mark.usefixtures("fake_handler")
def test_wrong_player_is_rejected() -> None:
    state = started_game().get_state()
    with pytest.raises(NotYourTurnError, match="jugador 1"):
        machine.validate(state, SeatId(1), MusAction())
    assert not machine.legal_actions(state, SeatId(1))


@pytest.mark.usefixtures("fake_handler")
def test_illegal_action_uses_specific_error() -> None:
    state = started_game().get_state()
    with pytest.raises(InvalidBetError, match="específica"):
        machine.validate(state, SeatId(0), CutMusAction())


@pytest.mark.usefixtures("fake_handler")
def test_non_action_is_rejected() -> None:
    state = started_game().get_state()
    with pytest.raises(IllegalActionError):
        machine.validate(state, SeatId(0), "mus")  # type: ignore[arg-type]


@pytest.mark.usefixtures("fake_handler")
def test_apply_runs_automatic_phases_until_rest() -> None:
    state = started_game().get_state()
    new_state, emitted = machine.apply(state, SeatId(0), MusAction())
    # El manejador falso lleva a DEAL; el motor reparte de nuevo y vuelve a MUS_DECISION.
    assert new_state.phase is Phase.MUS_DECISION
    assert new_state.hand is not None
    assert state.hand is not None
    assert new_state.hand.number == state.hand.number + 1
    assert emitted[0].event == PhaseChanged("fake")


@pytest.mark.usefixtures("fake_handler")
def test_game_apply_action_through_facade() -> None:
    game = started_game()
    before = game.get_state()
    with pytest.raises(NotYourTurnError):
        game.apply_action(2, MusAction())
    assert game.get_state() is before, "un rechazo no debe cambiar el estado"
    visible = game.apply_action(0, MusAction())
    assert all(env.visible_to(SeatId(0)) for env in visible)
    assert game.get_legal_actions(0).contains(MusAction())
    assert not game.get_legal_actions(0).contains(PassAction())
