"""Observación de un jugador (PLAYER_OBSERVATION).

Se construye **por lista blanca** a partir del estado completo: sólo se copian los
datos que el jugador puede conocer legítimamente. Nunca se parte del estado completo
para "borrar" lo secreto.

Puede conocer: sus naipes; el marcador; la fase, el turno, la mano y el postre; las
decisiones de mus y cuántos naipes pide cada uno; las declaraciones de pares y juego;
los envites; los resultados de los lances; las manos enseñadas al final de la jugada o
en un órdago (C.VII-9, C.VI-6); los eventos públicos y sus propios eventos privados.

No puede conocer: los naipes de los demás antes de enseñarse, el mazo ni cuántos
naipes quedan en él (C.III-16), los naipes descartados por otros, la semilla ni el
orden de la baraja.

Todo es inmutable (dataclasses congeladas y tuplas): modificar una observación no
puede afectar a la partida.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from mus_engine.betting.bets import BetState, BetStatus
from mus_engine.cards.card import Card
from mus_engine.events.events import EventEnvelope
from mus_engine.game.legal import LegalActions
from mus_engine.game.phases import Phase
from mus_engine.game.state import GameState
from mus_engine.players.seating import SeatId, TeamId
from mus_engine.rules.lance import LanceType
from mus_engine.scoring.score import GameScore
from mus_engine.scoring.scoring import LanceOutcome


@dataclass(frozen=True, slots=True)
class PublicBetView:
    """Envite en curso tal y como lo ve la mesa."""

    lance: LanceType
    status: BetStatus
    participants: tuple[SeatId, ...]
    to_act: tuple[SeatId, ...]
    accepted: int
    pending: int
    proposer: SeatId | None
    is_ordago: bool

    @classmethod
    def of(cls, bet: BetState) -> PublicBetView:
        return cls(
            bet.lance,
            bet.status,
            bet.participants,
            bet.to_act,
            bet.accepted,
            bet.pending,
            bet.proposer,
            bet.is_ordago,
        )


@dataclass(frozen=True, slots=True)
class Observation:
    seat: SeatId
    player_names: tuple[str, str, str, str]
    phase: Phase
    score: GameScore
    target_score: int
    games_to_win: int
    winner: TeamId | None
    hand_number: int
    my_hand: tuple[Card, ...]
    mano: SeatId | None
    dealer: SeatId | None
    to_act: tuple[SeatId, ...]
    mus_round: int | None
    mus_requested: tuple[SeatId, ...]
    mus_cut_by: SeatId | None
    discard_counts: tuple[int | None, ...]  # cuántos naipes ha pedido cada uno en la ronda
    lance: LanceType | None
    bet: PublicBetView | None
    pares_holders: tuple[bool, ...] | None
    juego_holders: tuple[bool, ...] | None
    outcomes: tuple[LanceOutcome, ...]
    revealed_hands: tuple[tuple[Card, ...], ...] | None
    legal_actions: LegalActions
    events: tuple[EventEnvelope, ...]

    @property
    def is_my_turn(self) -> bool:
        return self.seat in self.to_act


def build_observation(
    state: GameState,
    seat: SeatId,
    events: Sequence[EventEnvelope],
    to_act: tuple[SeatId, ...],
    legal_actions: LegalActions,
) -> Observation:
    """Construye la observación de ``seat`` copiando sólo información permitida."""
    hand = state.hand
    mus = None if hand is None else hand.mus
    return Observation(
        seat=seat,
        player_names=state.table.names,
        phase=state.phase,
        score=state.score,
        target_score=state.config.target_score,
        games_to_win=state.config.games_to_win,
        winner=state.winner,
        hand_number=0 if hand is None else hand.number,
        my_hand=() if hand is None else hand.hand_of(seat),
        mano=None if hand is None else hand.mano,
        dealer=None if hand is None else hand.dealer,
        to_act=to_act,
        mus_round=None if mus is None else mus.round,
        mus_requested=() if mus is None else mus.requested,
        mus_cut_by=None if mus is None else mus.cut_by,
        discard_counts=(
            (None, None, None, None)
            if mus is None
            else tuple(None if cards is None else len(cards) for cards in mus.discards)
        ),
        lance=None if hand is None else hand.lance,
        bet=None if hand is None or hand.bet is None else PublicBetView.of(hand.bet),
        pares_holders=None if hand is None else hand.pares_holders,
        juego_holders=None if hand is None else hand.juego_holders,
        outcomes=() if hand is None else hand.outcomes,
        revealed_hands=hand.hands if hand is not None and hand.revealed else None,
        legal_actions=legal_actions,
        events=tuple(e for e in events if e.visible_to(seat)),
    )
