"""Tests unitarios de RankingPolicy."""

import pytest

from mus_engine.cards import Card, Rank, RankingPolicy, Suit, cards_from_codes
from mus_engine.config import GameConfig

EIGHT_KINGS = RankingPolicy()
FOUR_KINGS = RankingPolicy(kings_are_threes=False, aces_are_twos=False)


def test_from_config() -> None:
    assert RankingPolicy.from_config(GameConfig()) == EIGHT_KINGS
    config = GameConfig(kings_are_threes=False, aces_are_twos=False)
    assert RankingPolicy.from_config(config) == FOUR_KINGS


@pytest.mark.parametrize("suit", list(Suit))
def test_effective_rank_eight_kings(suit: Suit) -> None:
    assert EIGHT_KINGS.effective_rank(Card(Rank.TRES, suit)) is Rank.REY
    assert EIGHT_KINGS.effective_rank(Card(Rank.DOS, suit)) is Rank.AS
    for rank in Rank:
        if rank not in (Rank.TRES, Rank.DOS):
            assert EIGHT_KINGS.effective_rank(Card(rank, suit)) is rank


def test_effective_rank_without_eight_kings() -> None:
    for rank in Rank:
        assert FOUR_KINGS.effective_rank(Card(rank, Suit.OROS)) is rank


@pytest.mark.parametrize(
    ("rank", "points"),
    [
        (Rank.AS, 1),
        (Rank.DOS, 1),
        (Rank.TRES, 10),
        (Rank.CUATRO, 4),
        (Rank.CINCO, 5),
        (Rank.SEIS, 6),
        (Rank.SIETE, 7),
        (Rank.SOTA, 10),
        (Rank.CABALLO, 10),
        (Rank.REY, 10),
    ],
)
def test_game_points_eight_kings(rank: Rank, points: int) -> None:
    assert EIGHT_KINGS.game_points(Card(rank, Suit.COPAS)) == points


def test_game_points_without_eight_kings() -> None:
    assert FOUR_KINGS.game_points(Card(Rank.TRES, Suit.OROS)) == 3
    assert FOUR_KINGS.game_points(Card(Rank.DOS, Suit.OROS)) == 2


@pytest.mark.parametrize(
    ("codes", "total"),
    [
        ("12O 12C 12E 1B", 31),
        ("3O 3C 11E 1B", 31),
        ("12O 10C 7E 4B", 31),
        ("12O 12C 12E 12B", 40),
        ("1O 1C 2E 2B", 4),
        ("7O 7C 7E 6B", 27),
        ("12O 11C 5E 5B", 30),
    ],
)
def test_total_game_points(codes: str, total: int) -> None:
    assert EIGHT_KINGS.total_game_points(cards_from_codes(codes)) == total


def test_playing_ranks() -> None:
    assert Rank.TRES not in EIGHT_KINGS.playing_ranks
    assert Rank.DOS not in EIGHT_KINGS.playing_ranks
    assert len(EIGHT_KINGS.playing_ranks) == 8
    assert FOUR_KINGS.playing_ranks == tuple(Rank)
