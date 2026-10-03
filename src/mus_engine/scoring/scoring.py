"""Puntuación: LANCE SCORE → entradas de tanteo → GAME SCORE.

Tres niveles separados:

- **BET SCORE** (``betting.bets``): qué produce la apuesta (negada, deje, envite querido).
- **LANCE SCORE** (:class:`LanceOutcome`, :class:`ScoreEntry`): cómo se cerró cada lance y
  qué entradas de tanteo genera.
- **GAME SCORE** (:class:`GameScore`): el marcador, que sólo crece dentro de un juego.

Orden reglamentario (C.VII-2): en cada lance se apuntan en el acto la negada o los
envites no aceptados; al final de la jugada, por orden de lances (grande, chica, pares,
juego o punto), los envites aceptados, el valor de grande y chica si quedaron en paso,
el punto y el valor de los pares y del juego. El recuento se detiene en cuanto una
pareja alcanza el tanteo (D-22).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from mus_engine.cards.card import Card
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.config import GameConfig
from mus_engine.errors import InvariantViolationError
from mus_engine.players.seating import SeatId, TeamId, team_of
from mus_engine.rules.evaluation import resolve
from mus_engine.rules.lance import LanceType
from mus_engine.rules.lances import LANCE_ORDER, evaluator_for, jugada_points, lance_value
from mus_engine.scoring.score import GameScore


class Resolution(Enum):
    """Cómo terminó un lance."""

    PASSED = "passed"  # todos pasaron ("en paso")
    ACCEPTED = "accepted"  # envite querido: se decide a cartas al final
    REJECTED = "rejected"  # no querido: el lance es de la pareja que envidó (C.VI-7)
    UNCONTESTED = "uncontested"  # sólo una pareja tiene la jugada: cobra sin envites (D-20)
    NOT_PLAYED = "not_played"  # nadie tiene la jugada
    ORDAGO_ACCEPTED = "ordago_accepted"


@dataclass(frozen=True, slots=True)
class LanceOutcome:
    """Resultado público de un lance tras cerrarse sus envites."""

    lance: LanceType
    resolution: Resolution
    participants: tuple[SeatId, ...] = ()
    amount: int = 0  # envite querido (ACCEPTED)
    team: TeamId | None = None  # pareja que gana el lance sin comparar (REJECTED, UNCONTESTED)
    immediate_points: int = 0  # negada o deje anotados en el acto (REJECTED)


class ScoreReason(Enum):
    NEGADA = "negada"  # primera apuesta no querida
    ENVITE_NO_QUERIDO = "envite_no_querido"  # revoque no querido (+ deje en pares/juego/punto)
    ENVITE = "envite"  # envite querido
    PASO = "paso"  # grande o chica en paso
    PARES = "pares"
    JUEGO = "juego"
    PUNTO = "punto"
    ORDAGO = "ordago"


@dataclass(frozen=True, slots=True)
class ScoreEntry:
    team: TeamId
    points: int
    lance: LanceType
    reason: ScoreReason
    winner: SeatId | None = None  # jugador cuya jugada decide (si se compara a cartas)


@dataclass(frozen=True, slots=True)
class Applied:
    score: GameScore
    applied: tuple[ScoreEntry, ...]
    game_winner: TeamId | None  # pareja que ha alcanzado el tanteo, si alguna


class ScoringEngine:
    """Calcula y aplica el tanteo según ``GameConfig``."""

    def __init__(self, config: GameConfig) -> None:
        self.config = config
        self.policy = RankingPolicy.from_config(config)

    # --- Entradas -----------------------------------------------------------------

    def rejection_entry(self, outcome: LanceOutcome, raised: bool) -> ScoreEntry:
        if outcome.team is None or outcome.resolution is not Resolution.REJECTED:
            raise InvariantViolationError(f"Entrada de rechazo sin pareja: {outcome}")
        reason = ScoreReason.ENVITE_NO_QUERIDO if raised else ScoreReason.NEGADA
        return ScoreEntry(outcome.team, outcome.immediate_points, outcome.lance, reason)

    def end_of_hand_entries(
        self, outcomes: Sequence[LanceOutcome], hands: Sequence[Sequence[Card]], mano: SeatId
    ) -> tuple[ScoreEntry, ...]:
        """Entradas del recuento final, en orden de lances (C.VII-2)."""
        by_lance = {outcome.lance: outcome for outcome in outcomes}
        entries: list[ScoreEntry] = []
        for lance in LANCE_ORDER:
            outcome = by_lance.get(lance)
            if outcome is not None:
                entries.extend(self._lance_entries(outcome, hands, mano))
        return tuple(entries)

    def _lance_entries(
        self, outcome: LanceOutcome, hands: Sequence[Sequence[Card]], mano: SeatId
    ) -> list[ScoreEntry]:
        lance, resolution = outcome.lance, outcome.resolution
        if resolution in (Resolution.NOT_PLAYED, Resolution.ORDAGO_ACCEPTED):
            return []
        winner: SeatId | None = None
        if resolution in (Resolution.ACCEPTED, Resolution.PASSED):
            evaluator = evaluator_for(lance, self.policy)
            contenders = {p: hands[p] for p in outcome.participants}
            winner = resolve(evaluator, contenders, mano).winner
            team = team_of(winner)
        elif outcome.team is not None:
            team = outcome.team
        else:  # pragma: no cover - defensivo
            raise InvariantViolationError(f"Lance sin ganador: {outcome}")

        entries: list[ScoreEntry] = []
        if resolution is Resolution.ACCEPTED:
            entries.append(ScoreEntry(team, outcome.amount, lance, ScoreReason.ENVITE, winner))
        if lance in (LanceType.GRANDE, LanceType.CHICA):
            if resolution is Resolution.PASSED:
                entries.append(
                    ScoreEntry(
                        team, self.config.points_passed_lance, lance, ScoreReason.PASO, winner
                    )
                )
        elif lance is LanceType.PUNTO:
            entries.append(
                ScoreEntry(team, lance_value(lance, self.config), lance, ScoreReason.PUNTO, winner)
            )
        else:
            value = sum(
                jugada_points(lance, hands[p], self.config)
                for p in outcome.participants
                if team_of(p) is team
            )
            reason = ScoreReason.PARES if lance is LanceType.PARES else ScoreReason.JUEGO
            entries.append(ScoreEntry(team, value, lance, reason, winner))
        return [entry for entry in entries if entry.points > 0]

    # --- Aplicación ----------------------------------------------------------------

    def apply(self, score: GameScore, entries: Sequence[ScoreEntry]) -> Applied:
        """Anota las entradas en orden y se detiene al alcanzar el tanteo (D-22)."""
        applied: list[ScoreEntry] = []
        for entry in entries:
            tantos = list(score.tantos)
            tantos[entry.team.value] += entry.points
            score = GameScore((tantos[0], tantos[1]), score.games)
            applied.append(entry)
            if tantos[entry.team.value] >= self.config.target_score:
                return Applied(score, tuple(applied), entry.team)
        return Applied(score, tuple(applied), None)

    def ordago_entry(self, score: GameScore, team: TeamId, lance: LanceType) -> ScoreEntry:
        """El órdago aceptado da el juego completo (Voc. "Órdago"): lo que falte hasta el tanteo."""
        missing = max(self.config.target_score - score.tantos_of(team), 1)
        return ScoreEntry(team, missing, lance, ScoreReason.ORDAGO)
