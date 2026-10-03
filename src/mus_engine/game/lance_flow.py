"""Transiciones de los lances, el órdago, el tanteo y el final de juego.

Orden de una jugada tras cortar el mus (C.VII-2):

    LANCE_START(grande) → LANCE → LANCE_START(chica) → LANCE → LANCE_START(pares)
    → [LANCE] → LANCE_START(juego | punto) → [LANCE] → HAND_SCORING → NEW_HAND

- Pares y juego: el motor declara quién los tiene (público y veraz; C.VI-17, C.VI-20).
  Si las dos parejas tienen la jugada hay envites entre quienes la tienen (R-19); si
  sólo una, cobra al final sin envites; si nadie, el lance no se juega (D-20).
- Si nadie tiene juego se juega al punto (Voc. "No Juego", D-20).
- Un envite no querido se anota en el acto (C.VII-2) y puede terminar el juego (D-22).
- Un órdago aceptado se resuelve en el acto enseñando las cartas (C.VI-6) y da el juego
  completo al ganador (Voc. "Órdago"); anula los envites aceptados antes (C.VII-12).
"""

from __future__ import annotations

from dataclasses import replace

from mus_engine.betting.bets import BetState, BetStatus, open_bet, rejection_points
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.errors import InvariantViolationError
from mus_engine.events.events import (
    Emission,
    GameFinished,
    GameWon,
    HandsRevealed,
    JuegoDeclared,
    LanceClosed,
    LanceNotPlayed,
    LanceResolved,
    LanceStarted,
    LanceUncontested,
    ParesDeclared,
    PointsAwarded,
)
from mus_engine.game.phases import Phase
from mus_engine.game.state import GameState, HandState
from mus_engine.game.transition import Step, enter
from mus_engine.players.seating import ALL_SEATS, SeatId, TeamId, next_dealer, order_from
from mus_engine.rules.evaluation import resolve
from mus_engine.rules.juego import JuegoEvaluator
from mus_engine.rules.lance import LanceType
from mus_engine.rules.lances import evaluator_for
from mus_engine.rules.pares import ParesEvaluator
from mus_engine.rules.participation import Participation
from mus_engine.scoring.score import GameScore
from mus_engine.scoring.scoring import LanceOutcome, Resolution, ScoreEntry, ScoringEngine

_NEXT_LANCE: dict[LanceType, LanceType | None] = {
    LanceType.GRANDE: LanceType.CHICA,
    LanceType.CHICA: LanceType.PARES,
    LanceType.PARES: LanceType.JUEGO,  # juego o punto se decide al empezar
    LanceType.JUEGO: None,
    LanceType.PUNTO: None,
}


def _hand(state: GameState, **changes: object) -> GameState:
    return state.evolve(hand=replace(state.current_hand, **changes))  # type: ignore[arg-type]


def _holders(hand: HandState, has: tuple[bool, ...]) -> tuple[SeatId, ...]:
    return tuple(p for p in ALL_SEATS if has[p])


# --- Inicio de lance ----------------------------------------------------------------


def lance_start(state: GameState) -> Step:
    hand = state.current_hand
    lance = hand.lance
    if lance is None:
        raise InvariantViolationError("LANCE_START sin lance")
    if lance in (LanceType.GRANDE, LanceType.CHICA, LanceType.PUNTO):
        return _open(state, lance, order_from(hand.mano), ())
    policy = RankingPolicy.from_config(state.config)
    if lance is LanceType.PARES:
        evaluator = ParesEvaluator(policy)
        has = tuple(evaluator.has_pares(hand.hand_of(p)) for p in ALL_SEATS)
        declared: tuple[Emission, ...] = (Emission.public(ParesDeclared(_four(has))),)
        state = _hand(state, pares_holders=has)
    else:
        juego = JuegoEvaluator(policy)
        has = tuple(juego.has_juego(hand.hand_of(p)) for p in ALL_SEATS)
        declared = (Emission.public(JuegoDeclared(_four(has))),)
        state = _hand(state, juego_holders=has)
        if not any(has):
            # Voc. "No Juego" / D-20: nadie tiene juego, se juega al punto.
            state = _hand(state, lance=LanceType.PUNTO)
            new_state, emitted = _open(state, LanceType.PUNTO, order_from(hand.mano), ())
            return new_state, declared + emitted
    participation = Participation.from_holders(_holders(hand, has), hand.mano)
    if participation.is_contested:
        new_state, emitted = _open(state, lance, participation.players, ())
        return new_state, declared + emitted
    if participation.single_team is not None:
        outcome = LanceOutcome(
            lance,
            Resolution.UNCONTESTED,
            participation.players,
            team=participation.single_team,
        )
        event: Emission = Emission.public(
            LanceUncontested(lance.value, participation.single_team.name)
        )
    else:
        outcome = LanceOutcome(lance, Resolution.NOT_PLAYED)
        event = Emission.public(LanceNotPlayed(lance.value))
    new_state, emitted = advance(state, outcome)
    return new_state, (*declared, event, *emitted)


def _four(values: tuple[bool, ...]) -> tuple[bool, bool, bool, bool]:
    a, b, c, d = values
    return a, b, c, d


def _open(
    state: GameState,
    lance: LanceType,
    participants: tuple[SeatId, ...],
    prefix: tuple[Emission, ...],
) -> Step:
    bet = open_bet(lance, participants)
    new_state, entered = enter(_hand(state, bet=bet), Phase.LANCE)
    return new_state, (*prefix, Emission.public(LanceStarted(lance.value, participants)), *entered)


# --- Cierre de lance ------------------------------------------------------------------


def advance(state: GameState, outcome: LanceOutcome) -> Step:
    """Registra el resultado del lance y pasa al siguiente lance o al tanteo."""
    hand = state.current_hand
    following = _NEXT_LANCE[outcome.lance]
    state = _hand(state, outcomes=(*hand.outcomes, outcome), bet=None, lance=following)
    return enter(state, Phase.LANCE_START if following is not None else Phase.HAND_SCORING)


def close_bet(state: GameState, bet: BetState) -> Step:
    """Cierra los envites de un lance según su estado final."""
    lance = bet.lance
    if bet.status is BetStatus.PASSED:
        outcome = LanceOutcome(lance, Resolution.PASSED, bet.participants)
    elif bet.status is BetStatus.ACCEPTED:
        outcome = LanceOutcome(lance, Resolution.ACCEPTED, bet.participants, amount=bet.accepted)
    elif bet.status is BetStatus.REJECTED:
        outcome = LanceOutcome(
            lance,
            Resolution.REJECTED,
            bet.participants,
            team=bet.proposing_team,
            immediate_points=rejection_points(bet, state.config),
        )
    elif bet.status is BetStatus.ORDAGO_ACCEPTED:
        outcome = LanceOutcome(lance, Resolution.ORDAGO_ACCEPTED, bet.participants)
    else:
        raise InvariantViolationError(f"Envite sin cerrar: {bet}")
    closed = Emission.public(
        LanceClosed(
            lance.value,
            outcome.resolution.value,
            outcome.amount,
            None if outcome.team is None else outcome.team.name,
        )
    )
    if outcome.resolution is Resolution.ORDAGO_ACCEPTED:
        hand = state.current_hand
        state = _hand(state, outcomes=(*hand.outcomes, outcome), bet=bet)
        new_state, entered = enter(state, Phase.ORDAGO_SHOWDOWN)
        return new_state, (closed, *entered)
    if outcome.resolution is Resolution.REJECTED:
        # C.VII-2: la negada o el envite no querido se apunta en el acto.
        engine = ScoringEngine(state.config)
        entry = engine.rejection_entry(outcome, raised=bet.raised)
        state, awarded, ended = award(state, (entry,))
        if ended:
            return state, (closed, *awarded)
        new_state, emitted = advance(state, outcome)
        return new_state, (closed, *awarded, *emitted)
    new_state, emitted = advance(state, outcome)
    return new_state, (closed, *emitted)


# --- Anotación y final de juego -----------------------------------------------------


def award(
    state: GameState, entries: tuple[ScoreEntry, ...]
) -> tuple[GameState, tuple[Emission, ...], bool]:
    """Anota ``entries`` en orden. Si una pareja alcanza el tanteo, termina el juego."""
    engine = ScoringEngine(state.config)
    result = engine.apply(state.score, entries)
    emitted = tuple(
        Emission.public(
            PointsAwarded(
                entry.team.name,
                entry.points,
                entry.lance.value,
                entry.reason.value,
                _tantos_after(state.score, result.applied[: i + 1]),
            )
        )
        for i, entry in enumerate(result.applied)
    )
    state = state.evolve(score=result.score)
    if result.game_winner is None:
        return state, emitted, False
    state, finished = finish_game(state, result.game_winner)
    return state, emitted + finished, True


def _tantos_after(start: GameScore, entries: tuple[ScoreEntry, ...]) -> tuple[int, int]:
    tantos = list(start.tantos)
    for entry in entries:
        tantos[entry.team.value] += entry.points
    return tantos[0], tantos[1]


def finish_game(state: GameState, team: TeamId) -> Step:
    """Una pareja gana el juego en curso; termina la partida o empieza otro juego."""
    games = list(state.score.games)
    games[team.value] += 1
    games_tuple = (games[0], games[1])
    won = Emission.public(GameWon(team.name, games_tuple, state.score.tantos))
    if games[team.value] >= state.config.games_to_win:
        final = state.evolve(score=GameScore(state.score.tantos, games_tuple), winner=team)
        new_state, entered = enter(final, Phase.GAME_OVER)
        return new_state, (won, Emission.public(GameFinished(team.name, games_tuple)), *entered)
    reset = state.evolve(score=GameScore((0, 0), games_tuple))
    new_state, entered = enter(reset, Phase.NEW_HAND)
    return new_state, (won, *entered)


# --- Órdago, tanteo y nueva jugada ----------------------------------------------------


def _reveal(state: GameState) -> tuple[GameState, Emission]:
    hand = state.current_hand
    return _hand(state, revealed=True), Emission.public(HandsRevealed(hand.hands))


def ordago_showdown(state: GameState) -> Step:
    """C.VI-6: el órdago aceptado se resuelve enseñando las cartas."""
    hand = state.current_hand
    bet = hand.bet
    if bet is None or bet.status is not BetStatus.ORDAGO_ACCEPTED:
        raise InvariantViolationError("ORDAGO_SHOWDOWN sin órdago aceptado")
    state, revealed = _reveal(state)
    evaluator = evaluator_for(bet.lance, RankingPolicy.from_config(state.config))
    result = resolve(evaluator, {p: hand.hand_of(p) for p in bet.participants}, hand.mano)
    resolved = Emission.public(LanceResolved(bet.lance.value, result.winner, result.tied))
    entry = ScoringEngine(state.config).ordago_entry(state.score, result.winning_team, bet.lance)
    state, awarded, ended = award(state, (entry,))
    if not ended:  # pragma: no cover - el órdago siempre alcanza el tanteo
        raise InvariantViolationError("Un órdago aceptado debe terminar el juego")
    return state, (revealed, resolved, *awarded)


def hand_scoring(state: GameState) -> Step:
    """C.VII-9: se enseñan las cartas; C.VII-2: recuento final en orden de lances."""
    state, revealed = _reveal(state)
    hand = state.current_hand
    policy = RankingPolicy.from_config(state.config)
    emitted: list[Emission] = [revealed]
    for outcome in hand.outcomes:
        if outcome.resolution in (Resolution.ACCEPTED, Resolution.PASSED):
            evaluator = evaluator_for(outcome.lance, policy)
            result = resolve(
                evaluator, {p: hand.hand_of(p) for p in outcome.participants}, hand.mano
            )
            emitted.append(
                Emission.public(LanceResolved(outcome.lance.value, result.winner, result.tied))
            )
    entries = ScoringEngine(state.config).end_of_hand_entries(hand.outcomes, hand.hands, hand.mano)
    state, awarded, ended = award(state, entries)
    emitted.extend(awarded)
    if ended:
        return state, tuple(emitted)
    new_state, entered = enter(state, Phase.NEW_HAND)
    return new_state, (*emitted, *entered)


def new_hand(state: GameState) -> Step:
    """D-15: reparte el que fue mano en la jugada anterior."""
    return enter(state.evolve(pending_dealer=next_dealer(state.current_hand.dealer)), Phase.DEAL)
