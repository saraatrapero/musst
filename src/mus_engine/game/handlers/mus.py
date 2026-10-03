"""Fases de decisión del mus: dar/cortar mus y descartarse.

- C.IV-4 / D-04: se habla en orden mano, 2º, 3º, 4º; el primer corte termina el mus.
- C.IV-2: el mus se puede cortar con cualquier naipe.
- C.III-11: se descarta primero el que reparte; el mano es el último.
- D-13: entre ``config.min_discard`` y ``config.max_discard`` naipes propios.
"""

from __future__ import annotations

from dataclasses import replace

from mus_engine.errors import IllegalActionError, InvalidStateError, InvariantViolationError
from mus_engine.events.events import DiscardDeclared, Emission, MusCut, MusRequested
from mus_engine.game.actions import Action, CutMusAction, DiscardAction, MusAction
from mus_engine.game.flow import Step, enter
from mus_engine.game.legal import LegalActions
from mus_engine.game.phases import Phase
from mus_engine.game.state import GameState, HandState, MusState
from mus_engine.players.seating import NUM_SEATS, SeatId, discard_order, mus_order
from mus_engine.rules.lance import LanceType
from mus_engine.rules.mus import check_discard, discard_options

_MUS_CHOICES = LegalActions(actions=(MusAction(), CutMusAction()))


def _with_mus(state: GameState, hand: HandState, mus: MusState) -> GameState:
    return state.evolve(hand=replace(hand, mus=mus))


def _wrong_phase(state: GameState, action: Action, expected: str) -> InvalidStateError:
    return InvalidStateError(
        f"{type(action).__name__} no es válida en la fase {state.phase.value}: se espera {expected}"
    )


class MusDecisionHandler:
    """``MUS_DECISION``: cada jugador, en orden desde la mano, da mus o lo corta."""

    def actors(self, state: GameState) -> tuple[SeatId, ...]:
        hand = state.current_hand
        return (mus_order(hand.mano)[hand.mus.speaker_index],)

    def legal_actions(self, state: GameState, player: SeatId) -> LegalActions:
        return _MUS_CHOICES

    def explain_illegal(
        self, state: GameState, player: SeatId, action: Action
    ) -> IllegalActionError:
        return _wrong_phase(state, action, "MusAction o CutMusAction")

    def apply(self, state: GameState, player: SeatId, action: Action) -> Step:
        hand = state.current_hand
        mus = hand.mus
        if isinstance(action, CutMusAction):
            cut = _with_mus(state, hand, replace(mus, cut_by=player))
            cut = cut.evolve(hand=replace(cut.current_hand, lance=LanceType.GRANDE))
            entered_state, entered = enter(cut, Phase.LANCE)
            return entered_state, (Emission.public(MusCut(player)), *entered)
        requested = replace(
            mus, speaker_index=mus.speaker_index + 1, requested=(*mus.requested, player)
        )
        new_state = _with_mus(state, hand, requested)
        emitted: tuple[Emission, ...] = (Emission.public(MusRequested(player)),)
        if requested.speaker_index < NUM_SEATS:
            return new_state, emitted
        # Los cuatro han dado mus: empiezan los descartes (C.III-11).
        discarding = _with_mus(
            new_state, new_state.current_hand, replace(requested, speaker_index=0)
        )
        entered_state, entered = enter(discarding, Phase.DISCARD)
        return entered_state, emitted + entered


class DiscardHandler:
    """``DISCARD``: del que reparte al mano, cada uno indica los naipes que tira."""

    def actors(self, state: GameState) -> tuple[SeatId, ...]:
        hand = state.current_hand
        return (discard_order(hand.mano)[hand.mus.speaker_index],)

    def legal_actions(self, state: GameState, player: SeatId) -> LegalActions:
        config = state.config
        options = discard_options(
            state.current_hand.hand_of(player), config.min_discard, config.max_discard
        )
        return LegalActions(actions=tuple(DiscardAction(cards) for cards in options))

    def explain_illegal(
        self, state: GameState, player: SeatId, action: Action
    ) -> IllegalActionError:
        if not isinstance(action, DiscardAction):
            return _wrong_phase(state, action, "DiscardAction")
        config = state.config
        try:
            check_discard(
                state.current_hand.hand_of(player),
                action.cards,
                config.min_discard,
                config.max_discard,
            )
        except IllegalActionError as error:
            return error
        return IllegalActionError(f"Descarte no válido: {action}")  # pragma: no cover

    def apply(self, state: GameState, player: SeatId, action: Action) -> Step:
        if not isinstance(action, DiscardAction):  # pragma: no cover - ya validado
            raise InvariantViolationError("DiscardHandler.apply sin DiscardAction")
        hand = state.current_hand
        mus = hand.mus
        discards = list(mus.discards)
        discards[player] = action.cards
        updated = replace(mus, speaker_index=mus.speaker_index + 1, discards=tuple(discards))
        new_state = _with_mus(state, hand, updated)
        emitted: tuple[Emission, ...] = (
            Emission.public(DiscardDeclared(player, len(action.cards))),
        )
        if updated.speaker_index < NUM_SEATS:
            return new_state, emitted
        entered_state, entered = enter(new_state, Phase.REDEAL)
        return entered_state, emitted + entered
