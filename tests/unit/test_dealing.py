"""Tests del reparto y del sorteo del primer reparto."""

from mus_engine.cards import SPANISH_40_CARDS, Deck, validate_complete
from mus_engine.players import ALL_SEATS, SeatId, deal_order
from mus_engine.rng import Rng
from mus_engine.rules.dealing import MIN_CUT, deal_hands, draw_first_dealer


def test_deal_hands_one_by_one_from_mano() -> None:
    deck = Deck.standard()
    dealer = SeatId(3)
    hands, stock = deal_hands(deck, dealer, 4)
    order = deal_order(dealer)  # mano primero: 0, 1, 2, 3
    for round_index in range(4):
        for position, player in enumerate(order):
            assert hands[player][round_index] == SPANISH_40_CARDS[round_index * 4 + position]
    assert len(stock) == 24
    assert stock.cards == SPANISH_40_CARDS[16:]


def test_deal_conserves_cards() -> None:
    deck, _ = Deck.standard().shuffled(Rng(3))
    for dealer in ALL_SEATS:
        hands, stock = deal_hands(deck, dealer, 4)
        validate_complete([c for hand in hands for c in hand] + list(stock))
        assert all(len(hand) == 4 for hand in hands)


def test_draw_first_dealer_is_deterministic_and_consistent() -> None:
    draw_a, rng_a = draw_first_dealer(Deck.standard(), SeatId(0), Rng(10))
    draw_b, rng_b = draw_first_dealer(Deck.standard(), SeatId(0), Rng(10))
    assert draw_a == draw_b
    assert rng_a == rng_b
    assert draw_a.cutter == 3  # a la izquierda del que baraja


def test_draw_first_dealer_cut_respects_minimum() -> None:
    # El naipe mostrado nunca es de los 2 primeros ni de los 3 últimos del mazo barajado.
    for seed in range(300):
        rng = Rng(seed)
        shuffled, _ = Deck.standard().shuffled(rng)
        draw, _ = draw_first_dealer(Deck.standard(), SeatId(0), rng)
        index = shuffled.cards.index(draw.card_shown)
        assert MIN_CUT - 1 <= index <= 40 - MIN_CUT - 1


def test_draw_first_dealer_reaches_every_seat() -> None:
    dealers = {draw_first_dealer(Deck.standard(), SeatId(1), Rng(s))[0].dealer for s in range(60)}
    assert dealers == set(ALL_SEATS)
