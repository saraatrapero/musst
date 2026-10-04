"""Reparto de naipes y sorteo del primer reparto (funciones puras).

- C.III-1: sorteo del primer reparto por el palo del naipe que sale al cortar.
- C.III-2: los naipes se dan de uno en uno, empezando por la mano.
- C.III-3: corta el jugador a la izquierda del que baraja, sin dejar ni levantar
  menos de tres naipes.
"""

from __future__ import annotations

from dataclasses import dataclass

from mus_engine.cards.card import Card
from mus_engine.cards.deck import Deck
from mus_engine.players.seating import (
    NUM_SEATS,
    SeatId,
    cutter_for,
    deal_order,
    first_dealer_by_suit,
)
from mus_engine.rng import Rng

MIN_CUT = 3  # C.III-3: "no se podrá dejar ni levantar menos de tres naipes"


@dataclass(frozen=True, slots=True)
class FirstDealerDraw:
    shuffler: SeatId
    cutter: SeatId
    card_shown: Card
    dealer: SeatId


def draw_first_dealer(deck: Deck, shuffler: SeatId, rng: Rng) -> tuple[FirstDealerDraw, Rng]:
    """Simula C.III-1: se baraja, corta el de la izquierda y el palo decide.

    El corte levanta ``k`` naipes (``MIN_CUT <= k <= len - MIN_CUT``); el naipe que
    "sale" es el de debajo del paquete levantado.
    """
    shuffled, rng = deck.shuffled(rng)
    choices = len(shuffled) - 2 * MIN_CUT + 1
    offset, rng = rng.choice_index(choices)
    lifted = MIN_CUT + offset
    card = shuffled.cards[lifted - 1]
    cutter = cutter_for(shuffler)
    dealer = first_dealer_by_suit(cutter, card.suit)
    return FirstDealerDraw(shuffler, cutter, card, dealer), rng


def deal_hands(
    deck: Deck, dealer: SeatId, cards_per_hand: int
) -> tuple[tuple[tuple[Card, ...], ...], Deck]:
    """Reparte ``cards_per_hand`` naipes de uno en uno empezando por la mano (C.III-2).

    Devuelve las manos indexadas por asiento y el mazo restante.
    """
    hands: list[list[Card]] = [[] for _ in range(NUM_SEATS)]
    stock = deck
    for _ in range(cards_per_hand):
        for player in deal_order(dealer):
            (card,), stock = stock.draw(1)
            hands[player].append(card)
    return tuple(tuple(hand) for hand in hands), stock
