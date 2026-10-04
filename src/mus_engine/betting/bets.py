"""Estado y transiciones de los envites de un lance (BET SCORE).

Un único modelo genérico cubre paso, envite, revoque (reenvite), quiero, no quiero y
órdago, sin casos especiales por lance:

- ``OPEN``: nadie ha envidado; hablan por turno los participantes desde la mano.
- ``PENDING``: hay un envite (o revoque u órdago) esperando respuesta de los rivales.
- Cierres: ``PASSED`` (todos pasan), ``ACCEPTED`` (quiero), ``REJECTED`` (no quiero de
  todos los rivales), ``ORDAGO_ACCEPTED``.

Reglas aplicadas:

- C.VI-2 (R-24): con un envite pendiente sólo contestan los rivales; el compañero del
  que envidó no puede subir.
- C.VI-4 (R-25): basta con que un rival quiera; "no quiero" exige que rechacen todos los
  rivales que pueden hablar, en orden.
- D-25: quien pasó antes puede contestar a un envite posterior si es rival.
- Un revoque implica querer lo anterior: ``accepted`` pasa a ser el envite previo.
- Voc. "Envido" / D-18: envite mínimo ``min_bet``; revoque "N más" con N >= ``min_raise``.
- D-21: se puede responder con órdago; un órdago no se puede revocar.
- C.IV-6 (R-23): el órdago es siempre del lance en curso.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from mus_engine.config import GameConfig
from mus_engine.errors import InvalidBetError
from mus_engine.players.seating import SeatId, TeamId, are_teammates, order_from, team_of
from mus_engine.rules.lance import LanceType

LANCES_WITH_DEJE = frozenset({LanceType.PARES, LanceType.JUEGO, LanceType.PUNTO})
"""C.VII-1: los pares, el juego y el punto tienen deje."""


class BetStatus(Enum):
    OPEN = "open"
    PENDING = "pending"
    PASSED = "passed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ORDAGO_ACCEPTED = "ordago_accepted"

    @property
    def is_closed(self) -> bool:
        return self not in (BetStatus.OPEN, BetStatus.PENDING)


@dataclass(frozen=True, slots=True)
class BetState:
    """Envites de un lance.

    ``accepted``: tantos ya queridos en firme (0 si ninguno).
    ``pending``: total que se juega si se acepta lo pendiente (sin uso si es órdago).
    ``to_act``: cola ordenada de quién debe hablar.
    ``raised``: el envite pendiente es un revoque (no la primera apuesta del lance).
    """

    lance: LanceType
    participants: tuple[SeatId, ...]
    status: BetStatus = BetStatus.OPEN
    to_act: tuple[SeatId, ...] = ()
    accepted: int = 0
    pending: int = 0
    proposer: SeatId | None = None
    is_ordago: bool = False
    raised: bool = False

    @property
    def proposing_team(self) -> TeamId | None:
        return None if self.proposer is None else team_of(self.proposer)


def open_bet(lance: LanceType, participants: tuple[SeatId, ...]) -> BetState:
    """Lance abierto: hablan los participantes en el orden dado (desde la mano)."""
    if len({team_of(p) for p in participants}) != 2:
        raise InvalidBetError("Sólo hay envites si participan las dos parejas")
    return BetState(lance, participants, BetStatus.OPEN, to_act=participants)


def rivals_after(bet: BetState, player: SeatId) -> tuple[SeatId, ...]:
    """Rivales participantes de ``player`` en orden de habla a partir de él."""
    return tuple(
        p for p in order_from(player)[1:] if p in bet.participants and not are_teammates(p, player)
    )


def _require(bet: BetState, status: BetStatus, player: SeatId) -> None:
    if bet.status is not status or not bet.to_act or bet.to_act[0] != player:
        raise InvalidBetError(f"Transición de envite no válida para el jugador {player}: {bet}")


def apply_pass(bet: BetState, player: SeatId) -> BetState:
    _require(bet, BetStatus.OPEN, player)
    rest = bet.to_act[1:]
    return replace(bet, to_act=rest, status=BetStatus.OPEN if rest else BetStatus.PASSED)


def apply_bet(bet: BetState, player: SeatId, amount: int, config: GameConfig) -> BetState:
    _require(bet, BetStatus.OPEN, player)
    if amount < config.min_bet:
        raise InvalidBetError(f"El envite mínimo es {config.min_bet}")
    return replace(
        bet,
        status=BetStatus.PENDING,
        pending=amount,
        proposer=player,
        to_act=rivals_after(bet, player),
    )


def apply_raise(bet: BetState, player: SeatId, increment: int, config: GameConfig) -> BetState:
    _require(bet, BetStatus.PENDING, player)
    if bet.is_ordago:
        raise InvalidBetError("No se puede revocar un órdago")
    if increment < config.min_raise:
        raise InvalidBetError(f"El revoque mínimo es {config.min_raise} más")
    return replace(
        bet,
        accepted=bet.pending,
        pending=bet.pending + increment,
        proposer=player,
        raised=True,
        to_act=rivals_after(bet, player),
    )


def apply_ordago(bet: BetState, player: SeatId) -> BetState:
    if bet.status is BetStatus.OPEN:
        _require(bet, BetStatus.OPEN, player)
        accepted, raised = 0, False
    else:
        _require(bet, BetStatus.PENDING, player)
        if bet.is_ordago:
            raise InvalidBetError("Ya hay un órdago pendiente")
        accepted, raised = bet.pending, True
    return replace(
        bet,
        status=BetStatus.PENDING,
        accepted=accepted,
        pending=0,
        proposer=player,
        is_ordago=True,
        raised=raised,
        to_act=rivals_after(bet, player),
    )


def apply_accept(bet: BetState, player: SeatId) -> BetState:
    _require(bet, BetStatus.PENDING, player)
    if bet.is_ordago:
        return replace(bet, status=BetStatus.ORDAGO_ACCEPTED, to_act=())
    return replace(bet, status=BetStatus.ACCEPTED, accepted=bet.pending, to_act=())


def apply_reject(bet: BetState, player: SeatId) -> BetState:
    _require(bet, BetStatus.PENDING, player)
    rest = bet.to_act[1:]
    if rest:
        return replace(bet, to_act=rest)
    return replace(bet, status=BetStatus.REJECTED, to_act=())


def rejection_points(bet: BetState, config: GameConfig) -> int:
    """Tantos que gana el proponente cuando no se le quiere (se anotan en el acto, C.VII-2).

    - Primera apuesta del lance: negada (Voc. "Negada").
    - Revoque: lo ya querido (C.VII-2) y, en pares, juego y punto, más el deje
      (C.VII-1, Voc. "Deje"; D-16).
    """
    if bet.status is not BetStatus.REJECTED:
        raise InvalidBetError("Sólo un envite rechazado da tantos de negada o deje")
    if not bet.raised:
        return config.points_negada
    deje = config.points_deje if bet.lance in LANCES_WITH_DEJE else 0
    return bet.accepted + deje
