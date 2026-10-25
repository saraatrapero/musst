"""Probabilidad exacta de ganar un lance (base del EquityAgent, §3.6).

Para cada asiento ajeno se calcula la distribución de sus clases de mano posibles
(pesadas por cuántas manos concretas caben en los naipes que quedan y filtradas por sus
declaraciones). Con eso se obtiene **sin simular** la probabilidad de que la mejor mano
de mi pareja gane a las dos de los rivales, con los empates resueltos a favor del más
cercano a la mano (C.VI).

Simplificación: las manos de los demás se tratan como independientes entre sí (se
ignora que dos rivales no pueden tener el mismo naipe). El error es pequeño y se
compensa con la velocidad: unas decenas de microsegundos por lance.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache

from mus_engine.ai.classes import HandClass, all_classes, hand_class, rank_supply
from mus_engine.ai.counting import Knowledge
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.players.seating import ALL_SEATS, SeatId, distance_from_mano, partner, team_of
from mus_engine.rules.evaluation import Strength
from mus_engine.rules.lance import LanceType
from mus_engine.rules.signals import Signal


@dataclass(frozen=True, slots=True)
class Distribution:
    """Fuerzas posibles de un asiento en un lance. ``none``: prob. de no poder jugarlo."""

    strengths: tuple[Strength, ...]  # ordenadas, sin repetir
    cumulative: tuple[float, ...]  # prob. acumulada de fuerza < strengths[i]
    mass: tuple[float, ...]  # prob. de cada fuerza
    none: float

    def below(self, strength: Strength) -> tuple[float, float]:
        """(P(fuerza < strength), P(fuerza == strength))."""
        i = bisect_left(self.strengths, strength)
        if i < len(self.strengths) and self.strengths[i] == strength:
            return self.cumulative[i], self.mass[i]
        less = self.cumulative[i] if i < len(self.strengths) else 1.0 - self.none
        return less, 0.0

    def _pieces(self) -> list[tuple[Strength | None, float]]:
        """(fuerza, masa) de peor a mejor; no poder jugar el lance (None) es lo peor."""
        return [(None, self.none), *zip(self.strengths, self.mass, strict=True)]

    def window(self, low: float, high: float) -> Distribution:
        """La distribución condicionada a estar entre los cuantiles ``low`` y ``high``.

        Sirve para modelar a un rival que sólo quiere (o envida) con sus mejores manos.
        """
        kept: list[tuple[Strength | None, float]] = []
        start = 0.0
        for strength, mass in self._pieces():
            end = start + mass
            inside = max(0.0, min(end, high) - max(start, low))
            if inside > 0:
                kept.append((strength, inside))
            start = end
        return _normalized(kept) or self

    def tilt(self, weight: Callable[[float], float]) -> Distribution:
        """La distribución reponderada por ``weight(percentil)``.

        El percentil de una fuerza es su posición entre las manos que **pueden jugar** el
        lance (0 = la peor, 1 = la mejor). Con ``weight = P(envida | percentil)`` se
        obtiene la mano de alguien que acaba de envidar (regla de Bayes); las manos que
        no pueden jugar el lance usan ``weight(0)``.
        """
        playing = 1.0 - self.none
        pieces: list[tuple[Strength | None, float]] = [(None, self.none * weight(0.0))]
        for strength, cumulative, mass in zip(
            self.strengths, self.cumulative, self.mass, strict=True
        ):
            percentile = (cumulative + mass / 2) / playing
            pieces.append((strength, mass * weight(percentile)))
        return _normalized(pieces) or self

    def percentile(self, strength: Strength) -> float:
        """Percentil de ``strength`` entre las manos que pueden jugar el lance."""
        less, equal = self.below(strength)
        playing = 1.0 - self.none
        return 0.5 if playing <= 0 else min(1.0, (less + equal / 2) / playing)


def _normalized(pieces: list[tuple[Strength | None, float]]) -> Distribution | None:
    total = sum(m for _, m in pieces)
    if total <= 0:
        return None
    none = sum(m for st, m in pieces if st is None) / total
    ordered = [(st, m / total) for st, m in pieces if st is not None and m > 0]
    cumulative: list[float] = []
    running = 0.0
    for _, m in ordered:
        cumulative.append(running)
        running += m
    return Distribution(
        tuple(st for st, _ in ordered),
        tuple(cumulative),
        tuple(m for _, m in ordered),
        none,
    )


def distribution(
    lance: LanceType,
    available: dict[int, int],
    policy: RankingPolicy,
    pares: bool | None = None,
    juego: bool | None = None,
    signals: frozenset[Signal] = frozenset(),
) -> Distribution:
    """Fuerzas posibles de una mano ajena. ``signals``: señas que se le han visto; las
    manos que no las cumplen pesan :data:`SIGNAL_DOUBT` (puede ser un farol)."""
    weights: dict[Strength, float] = {}
    none = 0.0
    total = 0.0
    for cls in all_classes(policy):
        if (pares is not None and cls.has_pares != pares) or (
            juego is not None and cls.has_juego != juego
        ):
            continue
        weight: float = cls.weight(available)
        if not weight:
            continue
        if not signals <= cls.signals:
            weight *= SIGNAL_DOUBT
        total += weight
        strength = cls.strengths[lance]
        if strength is None:
            none += weight
        else:
            weights[strength] = weights.get(strength, 0.0) + weight
    if not total:  # imposible con los naipes que quedan: se supone que no juega
        return Distribution((), (), (), 1.0)
    ordered = sorted(weights)
    mass = tuple(weights[s] / total for s in ordered)
    cumulative: list[float] = []
    running = 0.0
    for m in mass:
        cumulative.append(running)
        running += m
    return Distribution(tuple(ordered), tuple(cumulative), mass, none / total)


def _beats(
    strength: Strength | None, seat: SeatId, rival: Distribution, rival_seat: SeatId, mano: SeatId
) -> float:
    """P(la mano ``strength`` de ``seat`` gana a la del rival)."""
    if strength is None:
        return 0.0
    less, equal = rival.below(strength)
    closer = distance_from_mano(seat, mano) < distance_from_mano(rival_seat, mano)
    return rival.none + less + (equal if closer else 0.0)


View = Callable[[Distribution], Distribution]

# Peso de una mano que contradice una seña vista: no cero, porque una persona puede
# farolear (regla de casa de la web); los bots sólo señan lo que tienen.
SIGNAL_DOUBT = 0.1


def team_equity(
    knowledge: Knowledge,
    lance: LanceType,
    policy: RankingPolicy,
    views: Mapping[SeatId, View] | None = None,
) -> float:
    """P(que mi pareja gane ``lance``), contando con la mano de mi compañero.

    ``views`` transforma lo que se sabe de la mano de algunos asientos: por ejemplo
    ``{rival: lambda d: d.window(0.6, 1.0)}`` si ese rival sólo envida con su 40 %
    mejor, o ``d.tilt(...)`` con lo que dice su perfil.
    """
    me = knowledge.seat
    mate = partner(me)
    rivals = [s for s in ALL_SEATS if team_of(s) is not team_of(me)]
    mine = hand_class(knowledge.my_hand, policy).strengths[lance]
    dists = {
        s: distribution(
            lance,
            knowledge.available,
            policy,
            knowledge.pares[s],
            knowledge.juego[s],
            knowledge.signals[s],
        )
        for s in (mate, *rivals)
    }
    for seat, view in (views or {}).items():
        dists[seat] = view(dists[seat])
    mano = knowledge.mano

    def win_with(best: Strength | None, best_seat: SeatId) -> float:
        result = 1.0
        for rival in rivals:
            result *= _beats(best, best_seat, dists[rival], rival, mano)
        return result

    mate_dist = dists[mate]
    total = mate_dist.none * win_with(mine, me)
    for strength, mass in zip(mate_dist.strengths, mate_dist.mass, strict=True):
        if mine is None or strength > mine:
            best, seat = strength, mate
        elif strength < mine:
            best, seat = mine, me
        else:
            seat = min((me, mate), key=lambda s: distance_from_mano(s, mano))
            best = mine
        total += mass * win_with(best, seat)
    return total


def lance_equity(cls: HandClass, lance: LanceType, policy: RankingPolicy) -> float:
    """P(que una mano de clase ``cls`` gane sola a una mano cualquiera); empate = ½."""
    return _solo_equity(policy, lance)[cls.ranks]


@cache
def _solo_equity(policy: RankingPolicy, lance: LanceType) -> dict[tuple[int, ...], float]:
    dist = distribution(lance, rank_supply(policy), policy)
    result: dict[tuple[int, ...], float] = {}
    for cls in all_classes(policy):
        strength = cls.strengths[lance]
        if strength is None:
            result[cls.ranks] = 0.0
        else:
            less, equal = dist.below(strength)
            result[cls.ranks] = dist.none + less + equal / 2
    return result
