"""Tests del ScoringEngine."""

import pytest

from mus_engine import GameConfig, GameScore
from mus_engine.cards import cards_from_codes
from mus_engine.errors import InvariantViolationError
from mus_engine.players import SeatId, TeamId
from mus_engine.rules import LanceType
from mus_engine.scoring import LanceOutcome, Resolution, ScoreEntry, ScoreReason, ScoringEngine

ENGINE = ScoringEngine(GameConfig())
ALL = tuple(map(SeatId, range(4)))
# mano = 0. A = {0, 2}, B = {1, 3}
HANDS = (
    cards_from_codes("12O 12C 12E 1B"),  # 0: grande; medias de reyes; 31
    cards_from_codes("1C 1E 4O 5O"),  # 1: chica; pareja de ases; 11
    cards_from_codes("7O 7C 6E 5B"),  # 2: pareja de sietes; 25
    cards_from_codes("11O 10C 2B 4B"),  # 3: sin pares; 25
)
MANO = SeatId(0)


def entries(*outcomes: LanceOutcome) -> tuple[ScoreEntry, ...]:
    return ENGINE.end_of_hand_entries(outcomes, HANDS, MANO)


def test_grande_passed_gives_one_to_card_winner() -> None:
    (entry,) = entries(LanceOutcome(LanceType.GRANDE, Resolution.PASSED, ALL))
    assert entry == ScoreEntry(TeamId.A, 1, LanceType.GRANDE, ScoreReason.PASO, SeatId(0))


def test_chica_accepted_gives_envite_only() -> None:
    (entry,) = entries(LanceOutcome(LanceType.CHICA, Resolution.ACCEPTED, ALL, amount=5))
    assert entry == ScoreEntry(TeamId.B, 5, LanceType.CHICA, ScoreReason.ENVITE, SeatId(1))


def test_grande_rejected_scores_nothing_at_end() -> None:
    outcome = LanceOutcome(
        LanceType.GRANDE, Resolution.REJECTED, ALL, team=TeamId.B, immediate_points=1
    )
    assert entries(outcome) == ()


def test_pares_accepted_gives_envite_and_team_values() -> None:
    participants = (SeatId(0), SeatId(1), SeatId(2))
    result = entries(LanceOutcome(LanceType.PARES, Resolution.ACCEPTED, participants, amount=2))
    assert result == (
        ScoreEntry(TeamId.A, 2, LanceType.PARES, ScoreReason.ENVITE, SeatId(0)),
        ScoreEntry(
            TeamId.A, 3, LanceType.PARES, ScoreReason.PARES, SeatId(0)
        ),  # medias 2 + pareja 1
    )


def test_pares_rejected_gives_proposer_team_its_own_values() -> None:
    participants = (SeatId(0), SeatId(1), SeatId(2))
    outcome = LanceOutcome(
        LanceType.PARES, Resolution.REJECTED, participants, team=TeamId.B, immediate_points=1
    )
    assert entries(outcome) == (ScoreEntry(TeamId.B, 1, LanceType.PARES, ScoreReason.PARES),)


def test_juego_uncontested() -> None:
    outcome = LanceOutcome(LanceType.JUEGO, Resolution.UNCONTESTED, (SeatId(0),), team=TeamId.A)
    assert entries(outcome) == (ScoreEntry(TeamId.A, 3, LanceType.JUEGO, ScoreReason.JUEGO),)


def test_punto_values() -> None:
    hands = (
        cards_from_codes("12O 11C 5E 5B"),  # 30
        cards_from_codes("1C 1E 4O 5O"),
        cards_from_codes("7O 7C 6E 5B"),
        cards_from_codes("11O 10C 2B 4B"),
    )
    accepted = LanceOutcome(LanceType.PUNTO, Resolution.ACCEPTED, ALL, amount=2)
    assert ENGINE.end_of_hand_entries((accepted,), hands, MANO) == (
        ScoreEntry(TeamId.A, 2, LanceType.PUNTO, ScoreReason.ENVITE, SeatId(0)),
        ScoreEntry(TeamId.A, 1, LanceType.PUNTO, ScoreReason.PUNTO, SeatId(0)),
    )
    rejected = LanceOutcome(
        LanceType.PUNTO, Resolution.REJECTED, ALL, team=TeamId.B, immediate_points=1
    )
    assert ENGINE.end_of_hand_entries((rejected,), hands, MANO) == (
        ScoreEntry(TeamId.B, 1, LanceType.PUNTO, ScoreReason.PUNTO),
    )


def test_not_played_and_ordago_score_nothing() -> None:
    assert entries(LanceOutcome(LanceType.PARES, Resolution.NOT_PLAYED)) == ()
    assert entries(LanceOutcome(LanceType.GRANDE, Resolution.ORDAGO_ACCEPTED, ALL)) == ()


def test_entries_follow_lance_order_regardless_of_input_order() -> None:
    result = entries(
        LanceOutcome(LanceType.JUEGO, Resolution.UNCONTESTED, (SeatId(0),), team=TeamId.A),
        LanceOutcome(LanceType.CHICA, Resolution.PASSED, ALL),
        LanceOutcome(LanceType.GRANDE, Resolution.PASSED, ALL),
    )
    assert [e.lance for e in result] == [LanceType.GRANDE, LanceType.CHICA, LanceType.JUEGO]


def test_apply_stops_when_target_reached() -> None:
    score = GameScore((39, 39))
    pending = (
        ScoreEntry(TeamId.B, 1, LanceType.CHICA, ScoreReason.PASO),
        ScoreEntry(TeamId.A, 3, LanceType.PARES, ScoreReason.PARES),
    )
    result = ENGINE.apply(score, pending)
    assert result.game_winner is TeamId.B
    assert result.score == GameScore((39, 40))
    assert result.applied == pending[:1]


def test_apply_without_reaching_target() -> None:
    result = ENGINE.apply(
        GameScore((10, 0)), (ScoreEntry(TeamId.A, 5, LanceType.GRANDE, ScoreReason.ENVITE),)
    )
    assert result.game_winner is None
    assert result.score == GameScore((15, 0))


def test_bets_can_exceed_target() -> None:
    result = ENGINE.apply(
        GameScore((35, 0)), (ScoreEntry(TeamId.A, 30, LanceType.GRANDE, ScoreReason.ENVITE),)
    )
    assert result.score.tantos == (65, 0)
    assert result.game_winner is TeamId.A


@pytest.mark.parametrize(("tantos", "missing"), [((0, 0), 40), ((39, 12), 1), ((17, 39), 23)])
def test_ordago_entry_completes_the_game(tantos: tuple[int, int], missing: int) -> None:
    entry = ENGINE.ordago_entry(GameScore(tantos), TeamId.A, LanceType.CHICA)
    assert entry == ScoreEntry(TeamId.A, missing, LanceType.CHICA, ScoreReason.ORDAGO)


def test_rejection_entry() -> None:
    outcome = LanceOutcome(
        LanceType.GRANDE, Resolution.REJECTED, ALL, team=TeamId.A, immediate_points=1
    )
    assert ENGINE.rejection_entry(outcome, raised=False).reason is ScoreReason.NEGADA
    assert ENGINE.rejection_entry(outcome, raised=True).reason is ScoreReason.ENVITE_NO_QUERIDO
    with pytest.raises(InvariantViolationError):
        ENGINE.rejection_entry(LanceOutcome(LanceType.GRANDE, Resolution.PASSED, ALL), raised=False)
