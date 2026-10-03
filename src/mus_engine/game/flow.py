"""Transiciones automáticas de la máquina de estados.

Cada función recibe un estado en una fase automática y devuelve el estado siguiente y
los eventos emitidos. Son funciones puras.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from mus_engine.cards.deck import Deck
from mus_engine.errors import InvariantViolationError
from mus_engine.events.events import (
    CardsDealt,
    CardsDiscarded,
    DeckShuffled,
    DiscardPileReshuffled,
    Emission,
    FirstDealerDrawn,
    FirstDealerFixed,
    HandStarted,
)
from mus_engine.game import lance_flow
from mus_engine.game.phases import Phase
from mus_engine.game.state import GameState, HandState, MusState
from mus_engine.game.transition import Step, enter
from mus_engine.players.seating import ALL_SEATS, SeatId, discard_order, mano_for_dealer
from mus_engine.rules.dealing import deal_hands, draw_first_dealer
from mus_engine.rules.mus import serve_discards, sorted_by_hand

MAX_AUTOMATIC_STEPS = 64


def choose_first_dealer(state: GameState) -> Step:
    """C.III-1 / D-03: sorteo del primer reparto, o repartidor fijado por config."""
    config = state.config
    if config.first_dealer is not None:
        dealer = SeatId(config.first_dealer)
        emitted: tuple[Emission, ...] = (Emission.public(FirstDealerFixed(dealer)),)
        rng = state.rng
    else:
        draw, rng = draw_first_dealer(
            Deck.standard(config.deck_type), SeatId(config.first_shuffler), state.rng
        )
        dealer = draw.dealer
        emitted = (
            Emission.public(FirstDealerDrawn(draw.shuffler, draw.cutter, draw.card_shown, dealer)),
        )
    new_state, entered = enter(state.evolve(rng=rng, pending_dealer=dealer), Phase.DEAL)
    return new_state, emitted + entered


def deal(state: GameState) -> Step:
    """C.III-2: baraja completa barajada y reparto de uno en uno desde la mano."""
    if state.pending_dealer is None:
        raise InvariantViolationError("DEAL sin repartidor asignado")
    config = state.config
    dealer = state.pending_dealer
    deck, rng = Deck.standard(config.deck_type).shuffled(state.rng)
    hands, stock = deal_hands(deck, dealer, config.cards_per_hand)
    number = 1 if state.hand is None else state.hand.number + 1
    hand = HandState(
        number=number, dealer=dealer, mano=mano_for_dealer(dealer), hands=hands, stock=stock
    )
    emitted = (
        Emission.public(HandStarted(number, dealer, hand.mano, config.cards_per_hand)),
        Emission.engine(DeckShuffled(deck.cards)),
        *(Emission.private(p, CardsDealt(p, hands[p])) for p in ALL_SEATS),
    )
    new_state, entered = enter(
        state.evolve(rng=rng, hand=hand, pending_dealer=None), Phase.MUS_DECISION
    )
    return new_state, emitted + entered


def redeal(state: GameState) -> Step:
    """Sirve los descartes de una ronda de mus y vuelve a decidir el mus (C.III-2, C.III-15)."""
    hand = state.current_hand
    mus = hand.mus
    order = discard_order(hand.mano)
    if any(cards is None for cards in mus.discards):
        raise InvariantViolationError("REDEAL con descartes pendientes")
    discards = tuple(cards or frozenset() for cards in mus.discards)
    served = serve_discards(hand.hands, hand.stock, hand.discard_pile, discards, order, state.rng)
    emitted: list[Emission] = []
    for deck in served.reshuffles:
        emitted.append(Emission.public(DiscardPileReshuffled(len(deck))))
        emitted.append(Emission.engine(DeckShuffled(deck.cards)))
    for player in order:
        emitted.append(
            Emission.private(
                player,
                CardsDiscarded(
                    player,
                    sorted_by_hand(hand.hands[player], discards[player]),
                    served.received[player],
                ),
            )
        )
    new_hand = replace(
        hand,
        hands=served.hands,
        stock=served.stock,
        discard_pile=served.discard_pile,
        mus=MusState(round=mus.round + 1),
    )
    new_state, entered = enter(state.evolve(hand=new_hand, rng=served.rng), Phase.MUS_DECISION)
    return new_state, (*emitted, *entered)


AUTOMATIC_STEPS: dict[Phase, Callable[[GameState], Step]] = {
    Phase.CHOOSE_FIRST_DEALER: choose_first_dealer,
    Phase.DEAL: deal,
    Phase.REDEAL: redeal,
    Phase.LANCE_START: lance_flow.lance_start,
    Phase.ORDAGO_SHOWDOWN: lance_flow.ordago_showdown,
    Phase.HAND_SCORING: lance_flow.hand_scoring,
    Phase.NEW_HAND: lance_flow.new_hand,
}


def run_automatic(state: GameState) -> Step:
    """Atraviesa fases automáticas hasta llegar a una fase de reposo."""
    emitted: list[Emission] = []
    for _ in range(MAX_AUTOMATIC_STEPS):
        if state.phase.is_resting:
            return state, tuple(emitted)
        step = AUTOMATIC_STEPS.get(state.phase)
        if step is None:
            raise InvariantViolationError(f"Fase automática sin transición: {state.phase}")
        state, new = step(state)
        emitted.extend(new)
    raise InvariantViolationError("Demasiadas transiciones automáticas seguidas")
