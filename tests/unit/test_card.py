"""Tests unitarios de Card, Rank y Suit."""

import dataclasses

import pytest

from mus_engine.cards import Card, Rank, Suit, cards_from_codes
from mus_engine.errors import InvalidCardError


def test_card_has_rank_and_suit() -> None:
    card = Card(Rank.REY, Suit.OROS)
    assert card.rank is Rank.REY
    assert card.suit is Suit.OROS


def test_card_is_immutable() -> None:
    card = Card(Rank.AS, Suit.BASTOS)
    with pytest.raises(dataclasses.FrozenInstanceError):
        card.rank = Rank.REY  # type: ignore[misc]


def test_card_equality_and_hash_by_value() -> None:
    assert Card(Rank.SOTA, Suit.COPAS) == Card(Rank.SOTA, Suit.COPAS)
    assert Card(Rank.SOTA, Suit.COPAS) != Card(Rank.SOTA, Suit.ESPADAS)
    assert len({Card(Rank.SOTA, Suit.COPAS), Card(Rank.SOTA, Suit.COPAS)}) == 1


def test_card_has_no_implicit_ordering() -> None:
    # El orden depende del lance: comparar cartas directamente debe fallar.
    with pytest.raises(TypeError):
        _ = Card(Rank.AS, Suit.OROS) < Card(Rank.REY, Suit.OROS)  # type: ignore[operator]


def test_spanish_deck_has_no_eights_or_nines() -> None:
    assert {int(r) for r in Rank} == {1, 2, 3, 4, 5, 6, 7, 10, 11, 12}


@pytest.mark.parametrize("bad_rank", [8, 9, 0, 13, "12", None])
def test_card_rejects_invalid_rank(bad_rank: object) -> None:
    with pytest.raises(InvalidCardError):
        Card(bad_rank, Suit.OROS)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad_suit", ["O", "oros", None, 0])
def test_card_rejects_invalid_suit(bad_suit: object) -> None:
    with pytest.raises(InvalidCardError):
        Card(Rank.AS, bad_suit)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("card", "code", "text"),
    [
        (Card(Rank.REY, Suit.OROS), "12O", "Rey de Oros"),
        (Card(Rank.AS, Suit.BASTOS), "1B", "As de Bastos"),
        (Card(Rank.CABALLO, Suit.COPAS), "11C", "Caballo de Copas"),
        (Card(Rank.SIETE, Suit.ESPADAS), "7E", "Siete de Espadas"),
    ],
)
def test_card_representation(card: Card, code: str, text: str) -> None:
    assert card.code == code
    assert str(card) == text
    assert repr(card) == f"Card({code})"
    assert Card.from_code(code) == card


def test_every_card_roundtrips_through_its_code() -> None:
    for suit in Suit:
        for rank in Rank:
            card = Card(rank, suit)
            assert Card.from_code(card.code) == card


@pytest.mark.parametrize("code", ["", "1", "8O", "9C", "13B", "12X", "O12", "1o", "xx", "-1O"])
def test_from_code_rejects_invalid_codes(code: str) -> None:
    with pytest.raises(InvalidCardError):
        Card.from_code(code)


def test_cards_from_codes() -> None:
    assert cards_from_codes("12O 1B") == (Card(Rank.REY, Suit.OROS), Card(Rank.AS, Suit.BASTOS))
