"""PlayerProfileAgent (``docs/ai-design.md`` §3.2): cómo juega cada jugador.

Sólo usa información **pública**: lo que cada uno hace (pasa, envida, quiere, órdago,
mus…) y las manos que se enseñan al final de la jugada. Cruzando las dos cosas se sabe
**con qué fuerza de mano** tomó cada decisión: en percentil entre las manos que pueden
jugar ese lance (0 = la peor, 1 = la mejor), por tramos:

======== ============ ==================================
Tramo    Percentil    Para qué
======== ============ ==================================
mala     < 30 %       faroles (envidar con el 30 % peor)
regular  30–60 %
buena    60–80 %
muy buena ≥ 80 %      ir de tapado (pasar con el 20 % mejor)
======== ============ ==================================

Las frecuencias se estiman con **priors Beta**: una persona nueva parte del
comportamiento medio (:data:`BET_PRIOR`…) y se va separando según juega. El perfil es
un contador de enteros (``counts``) que se suma entre partidas y se guarda como JSON.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import cache

from mus_engine.ai.classes import hand_class, rank_supply
from mus_engine.ai.equity import Distribution, distribution
from mus_engine.ai.inference import CUT, MUS, MUS_MEAN, beta_for_mean
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.events.events import (
    BetAccepted,
    BetPlaced,
    BetRaised,
    BetRejected,
    DiscardDeclared,
    EventEnvelope,
    GameFinished,
    GameStarted,
    HandsRevealed,
    HandStarted,
    LanceStarted,
    MusCut,
    MusRequested,
    OrdagoAccepted,
    OrdagoDeclared,
    Passed,
    PointsAwarded,
    Visibility,
)
from mus_engine.players.seating import ALL_SEATS, SeatId, opponent, team_of
from mus_engine.rules.lance import LanceType

BINS = (0.3, 0.6, 0.8)  # límites de los tramos de fuerza
BIN_NAMES = ("mala", "regular", "buena", "muy buena")
TIER_WIDTHS = (0.3, 0.3, 0.2, 0.2)  # fracción de manos en cada tramo

# Comportamiento medio por tramo (prior). Calibrado con el bot medio de la Fase D.
BET_PRIOR = (0.06, 0.25, 0.6, 0.9)  # envidar en abierto
ORDAGO_PRIOR = (0.0, 0.01, 0.05, 0.4)  # órdago en abierto
ACCEPT_PRIOR = (0.25, 0.6, 0.9, 1.0)  # querer (o subir) un envite
ACCEPT_ORDAGO_PRIOR = (0.0, 0.05, 0.25, 0.7)
# Modelo para decidir (bot medio): cada jugador actúa con su ``top`` de manos mejores
# (sin datos, los valores ajustados en la Fase D) más una «fuga» con manos malas.
DEFAULT_TOP = {"bet": 0.45, "raise": 0.3, "ordago": 0.15, "accept": 0.6, "accept_ordago": 0.2}
TIER_WEIGHT = 4.0  # cuánto pesa el prior frente a las decisiones con mano enseñada
RATE_WEIGHT = 8.0  # ídem para las frecuencias globales
MIN_DECISIONS = 8  # por debajo, el perfil es «por conocer»
CONFIDENCE_SCALE = 30.0
PCT_SCALE = 1000  # los percentiles se guardan como enteros (por mil)
MUS_WEIGHT = 10.0  # cuánto pesa la media de la población frente a sus manos enseñadas
LOSING_GAP = 10  # se considera que va perdiendo con 10 tantos menos...
LOSING_NEAR_END = 8  # ...o con el rival a 8 de ganar


def tier(percentile: float) -> int:
    return sum(percentile >= b for b in BINS)


def _mean(prior: tuple[float, ...]) -> float:
    return sum(p * w for p, w in zip(prior, TIER_WIDTHS, strict=True))


def _beta(hits: float, total: float, prior: float, weight: float) -> float:
    return (hits + prior * weight) / (total + weight)


@dataclass(frozen=True, slots=True)
class PlayerProfile:
    """Perfil de un jugador: contadores sumables y estimaciones con prior."""

    counts: Mapping[str, int] = field(default_factory=dict)

    def __add__(self, other: PlayerProfile) -> PlayerProfile:
        return PlayerProfile(dict(Counter(self.counts) + Counter(other.counts)))

    def to_json(self) -> dict[str, int]:
        return dict(sorted(self.counts.items()))

    @classmethod
    def from_json(cls, data: Mapping[str, object]) -> PlayerProfile:
        return cls({k: int(v) for k, v in data.items() if isinstance(v, int) and v > 0})

    def _c(self, key: str) -> int:
        return self.counts.get(key, 0)

    # --- Frecuencias globales ----------------------------------------------------------

    @property
    def decisions(self) -> int:
        return self._c("open.n") + self._c("face.n") + self._c("ordago.n")

    @property
    def bet_rate(self) -> float:
        return _beta(self._c("open.bet"), self._c("open.n"), _mean(BET_PRIOR), RATE_WEIGHT)

    @property
    def ordago_rate(self) -> float:
        return _beta(self._c("open.ordago"), self._c("open.n"), _mean(ORDAGO_PRIOR), RATE_WEIGHT)

    @property
    def accept_rate(self) -> float:
        stay = self._c("face.accept") + self._c("face.raise") + self._c("face.ordago")
        return _beta(stay, self._c("face.n"), _mean(ACCEPT_PRIOR), RATE_WEIGHT)

    @property
    def accept_ordago_rate(self) -> float:
        return _beta(
            self._c("ordago.accept"), self._c("ordago.n"), _mean(ACCEPT_ORDAGO_PRIOR), RATE_WEIGHT
        )

    @property
    def cut_rate(self) -> float:
        return _beta(self._c("mus.cut"), self._c("mus.n"), 0.3, RATE_WEIGHT)

    def losing_bet_rate(self, losing: bool) -> float:
        key = "losing" if losing else "even"
        return _beta(
            self._c(f"{key}.open.bet"), self._c(f"{key}.open.n"), self.bet_rate, RATE_WEIGHT
        )

    # --- Por tramo de fuerza (manos enseñadas) --------------------------------------------

    def _given(self, kind: str, hit: str, prior: tuple[float, ...], rate: float, b: int) -> float:
        scale = rate / _mean(prior) if _mean(prior) > 0 else 1.0
        base = min(0.99, max(0.005, prior[b] * scale))
        return _beta(self._c(f"t.{kind}.{b}.{hit}"), self._c(f"t.{kind}.{b}.n"), base, TIER_WEIGHT)

    def bet_given(self, b: int) -> float:
        """P(envida en abierto | su mano está en el tramo ``b``)."""
        return self._given("open", "bet", BET_PRIOR, self.bet_rate, b)

    def ordago_given(self, b: int) -> float:
        return self._given("open", "ordago", ORDAGO_PRIOR, self.ordago_rate, b)

    def accept_given(self, b: int) -> float:
        """P(quiere o sube un envite | tramo ``b``)."""
        return self._given("face", "accept", ACCEPT_PRIOR, self.accept_rate, b)

    def accept_ordago_given(self, b: int) -> float:
        return self._given("ordago", "accept", ACCEPT_ORDAGO_PRIOR, self.accept_ordago_rate, b)

    def average_bet(self, b: int) -> float | None:
        """Tantos que envida de media con manos del tramo ``b`` (sus «piedras»)."""
        n = self._c(f"t.amount.{b}.n")
        return self._c(f"t.amount.{b}.sum") / n if n else None

    def behaviour(self, kind: str) -> tuple[float, float]:
        """``(top, fuga)`` para ``kind`` en ``DEFAULT_TOP``.

        ``top``: fracción de sus mejores manos con la que hace esa acción; se escala con
        su frecuencia observada respecto a la media (quien envida el doble que la media,
        envida con el doble de manos). ``fuga``: probabilidad de hacerla con una mano
        mala (farol), sólo a partir de manos enseñadas: sin datos es 0.
        """
        rate, prior, group, hit = {
            "bet": (self.bet_rate, BET_PRIOR, "open", "bet"),
            "raise": (self.bet_rate, BET_PRIOR, "open", "bet"),
            "ordago": (self.ordago_rate, ORDAGO_PRIOR, "open", "ordago"),
            "accept": (self.accept_rate, ACCEPT_PRIOR, "face", "accept"),
            "accept_ordago": (self.accept_ordago_rate, ACCEPT_ORDAGO_PRIOR, "ordago", "accept"),
        }[kind]
        top = min(0.98, max(0.02, DEFAULT_TOP[kind] * rate / _mean(prior)))
        leak = self._c(f"t.{group}.0.{hit}") / (self._c(f"t.{group}.0.n") + TIER_WEIGHT)
        return top, leak

    def mus_beta(self, signal: str, lance: LanceType) -> float:
        """Inclinación de su mano en ``lance`` tras ``signal`` (cortar o pedir mus).

        Parte de la media de la población (:data:`MUS_MEAN`) y se ajusta con las manos
        que ha enseñado después de esa decisión.
        """
        n = self._c(f"m.{signal}.{lance.value}.n")
        total = self._c(f"m.{signal}.{lance.value}.pct") / PCT_SCALE
        mean = (total + MUS_MEAN[(signal, lance)] * MUS_WEIGHT) / (n + MUS_WEIGHT)
        return beta_for_mean(round(mean, 3))

    # --- Etiqueta -----------------------------------------------------------------------

    @property
    def confidence(self) -> float:
        return self.decisions / (self.decisions + CONFIDENCE_SCALE)

    def style(self) -> str:
        """Etiqueta legible del perfil (§3.2)."""
        if self.decisions < MIN_DECISIONS:
            return "por conocer"
        both_ends = min(self._c("t.open.0.n"), self._c("t.open.3.n"))
        if both_ends >= 3 and self.bet_given(3) - self.bet_given(0) < 0.2:
            return "imprevisible"  # envida igual con buenas que con malas
        if self.bet_given(0) >= 0.25:
            return "farolero"
        if self.bet_rate >= 0.5 or self.ordago_rate >= 0.1:
            return "arriesgado"
        if self.bet_rate <= 0.2 and self.ordago_rate <= 0.02:
            return "conservador"
        if self.accept_rate <= 0.45:
            return "cauto"
        if 1 - self.bet_given(3) >= 0.45 and self._c("t.open.3.n") >= 3:
            return "de tapado"
        return "equilibrado"

    def summary(self) -> dict[str, object]:
        """Resumen para mostrar a la persona (y a la defensa de la práctica)."""
        return {
            "style": self.style(),
            "confidence": round(self.confidence, 2),
            "decisions": self.decisions,
            "games": self._c("games"),
            "bet_rate": round(self.bet_rate, 2),
            "ordago_rate": round(self.ordago_rate, 2),
            "accept_rate": round(self.accept_rate, 2),
            "accept_ordago_rate": round(self.accept_ordago_rate, 2),
            "cut_rate": round(self.cut_rate, 2),
            "bluff_rate": round(self.bet_given(0), 2),
            "slowplay_rate": round(1 - self.bet_given(3), 2),
            "bet_by_strength": {n: round(self.bet_given(b), 2) for b, n in enumerate(BIN_NAMES)},
            "ordago_by_strength": {
                n: round(self.ordago_given(b), 2) for b, n in enumerate(BIN_NAMES)
            },
            "accept_by_strength": {
                n: round(self.accept_given(b), 2) for b, n in enumerate(BIN_NAMES)
            },
            "accept_ordago_by_strength": {
                n: round(self.accept_ordago_given(b), 2) for b, n in enumerate(BIN_NAMES)
            },
            "average_bet": {
                n: None if (a := self.average_bet(b)) is None else round(a, 1)
                for b, n in enumerate(BIN_NAMES)
            },
            "bet_rate_losing": round(self.losing_bet_rate(True), 2),
            "bet_rate_even": round(self.losing_bet_rate(False), 2),
        }


@cache
def _reference(policy: RankingPolicy, lance: LanceType) -> Distribution:
    """Manos posibles de un jugador que puede jugar ``lance`` (baraja completa)."""
    pares = True if lance is LanceType.PARES else None
    juego = {LanceType.JUEGO: True, LanceType.PUNTO: False}.get(lance)
    return distribution(lance, rank_supply(policy), policy, pares, juego)


def hand_percentile(cards: Iterable[object], lance: LanceType, policy: RankingPolicy) -> float:
    strength = hand_class(tuple(cards), policy).strengths[lance]  # type: ignore[arg-type]
    if strength is None:
        return 0.0
    return _reference(policy, lance).percentile(strength)


@dataclass(slots=True)
class _Decision:
    hand: int
    seat: SeatId
    lance: LanceType
    group: str  # open | face | ordago
    choice: str  # bet | pass | ordago | accept | reject | raise
    amount: int = 0


class ProfileTracker:
    """Construye los perfiles de los cuatro asientos a partir de eventos públicos.

    Se puede alimentar poco a poco (``observe`` ignora lo ya visto) desde la
    observación de un bot, o de una vez con el registro de una partida terminada.
    """

    def __init__(self, policy: RankingPolicy | None = None) -> None:
        self.policy = policy or RankingPolicy()
        self._counts: dict[SeatId, Counter[str]] = {s: Counter() for s in ALL_SEATS}
        self._last_seq = -1
        self._pending: list[_Decision] = []
        self._state: dict[LanceType, str] = {}
        self._tantos = [0, 0]
        self._target = 40
        self._mus: dict[SeatId, str] = {}

    def profile(self, seat: SeatId) -> PlayerProfile:
        return PlayerProfile(dict(self._counts[seat]))

    def observe(self, envelopes: Iterable[EventEnvelope]) -> None:
        for envelope in envelopes:
            if envelope.seq <= self._last_seq:
                continue
            self._last_seq = envelope.seq
            if envelope.visibility is Visibility.PUBLIC:
                self._event(envelope)

    def _event(self, envelope: EventEnvelope) -> None:
        event = envelope.event
        hand = envelope.hand_number
        if isinstance(event, GameStarted):
            self._target = event.config.target_score
        elif isinstance(event, HandStarted):
            self._mus = {}
        elif isinstance(event, LanceStarted):
            self._state[LanceType(event.lance)] = "open"
            self._pending = [d for d in self._pending if d.hand == hand]
        elif isinstance(event, MusRequested):
            self._counts[event.seat]["mus.n"] += 1
            self._mus[event.seat] = MUS
        elif isinstance(event, MusCut):
            self._counts[event.seat].update({"mus.n": 1, "mus.cut": 1})
            self._mus[event.seat] = CUT
        elif isinstance(event, DiscardDeclared):
            self._counts[event.seat].update({"discard.n": 1, "discard.cards": event.count})
            self._mus = {}
        elif isinstance(event, Passed):
            self._decide(hand, event.seat, LanceType(event.lance), "open", "pass")
        elif isinstance(event, BetPlaced):
            group = "open" if self._open(event.lance) else "face"
            self._decide(hand, event.seat, LanceType(event.lance), group, "bet", event.amount)
            self._state[LanceType(event.lance)] = "bet"
        elif isinstance(event, BetRaised):
            self._decide(hand, event.seat, LanceType(event.lance), "face", "raise")
        elif isinstance(event, OrdagoDeclared):
            group = "open" if self._open(event.lance) else "face"
            self._decide(hand, event.seat, LanceType(event.lance), group, "ordago")
            self._state[LanceType(event.lance)] = "ordago"
        elif isinstance(event, BetAccepted):
            self._decide(hand, event.seat, LanceType(event.lance), "face", "accept")
        elif isinstance(event, OrdagoAccepted):
            self._decide(hand, event.seat, LanceType(event.lance), "ordago", "accept")
        elif isinstance(event, BetRejected):
            lance = LanceType(event.lance)
            group = "ordago" if self._state.get(lance) == "ordago" else "face"
            self._decide(hand, event.seat, lance, group, "reject")
        elif isinstance(event, PointsAwarded):
            self._tantos = list(event.tantos_after)
        elif isinstance(event, HandsRevealed):
            self._reveal(hand, event.hands)
        elif isinstance(event, GameFinished):
            for seat in ALL_SEATS:
                self._counts[seat]["games"] += 1

    def _open(self, lance: str) -> bool:
        return self._state.get(LanceType(lance), "open") == "open"

    def _decide(
        self, hand: int, seat: SeatId, lance: LanceType, group: str, choice: str, amount: int = 0
    ) -> None:
        counts = self._counts[seat]
        counts[f"{group}.n"] += 1
        counts[f"{group}.{choice}"] += 1
        if group == "open":
            mine = self._tantos[team_of(seat).value]
            theirs = self._tantos[opponent(team_of(seat)).value]
            losing = theirs - mine >= LOSING_GAP or theirs >= self._target - LOSING_NEAR_END
            key = "losing" if losing else "even"
            counts[f"{key}.open.n"] += 1
            counts[f"{key}.open.{choice}"] += 1
        self._pending.append(_Decision(hand, seat, lance, group, choice, amount))

    def _reveal(self, hand: int, hands: tuple[tuple[object, ...], ...]) -> None:
        # HandsRevealed enseña siempre las cuatro manos completas.
        for seat, signal in self._mus.items():
            cards = hands[seat]
            cls = hand_class(tuple(cards), self.policy)  # type: ignore[arg-type]
            for lance in LanceType:
                if cls.strengths[lance] is None:
                    continue
                pct = hand_percentile(cards, lance, self.policy)
                counts = self._counts[seat]
                counts[f"m.{signal}.{lance.value}.n"] += 1
                counts[f"m.{signal}.{lance.value}.pct"] += round(pct * PCT_SCALE)
        self._mus = {}
        for d in [d for d in self._pending if d.hand == hand]:
            cards = hands[d.seat]
            b = tier(hand_percentile(cards, d.lance, self.policy))
            counts = self._counts[d.seat]
            counts[f"t.{d.group}.{b}.n"] += 1
            if d.choice in ("bet", "ordago") and d.group == "open":
                counts[f"t.open.{b}.{d.choice}"] += 1
            if d.group == "face" and d.choice != "reject":
                counts[f"t.face.{b}.accept"] += 1
            if d.group == "ordago" and d.choice == "accept":
                counts[f"t.ordago.{b}.accept"] += 1
            if d.choice == "bet" and d.amount:
                counts.update({f"t.amount.{b}.n": 1, f"t.amount.{b}.sum": d.amount})
        self._pending = [d for d in self._pending if d.hand != hand]
