"""Bot de nivel "sencillo": heurísticas claras de fuerza de mano.

Comprensible y con errores razonables, como pide el nivel sencillo del diseño
(`docs/ai-design.md` §4). No cuenta cartas, no perfila rivales ni aprende.

- Mus: corta si tiene una jugada buena en algún lance; si no, pide mus y tira las
  cartas que no son reyes ni forman pareja.
- Envites: envida con jugadas fuertes, acepta según la fuerza y lo que se juega,
  revoca con jugadas muy fuertes y sólo echa órdago si el rival está a punto de ganar.
- Señas: seña su jugada sólo cuando su compañero le mira y ningún rival lo hace.
"""

from __future__ import annotations

from collections import Counter

from mus_engine.betting.bets import BetStatus
from mus_engine.bots.base import Bot
from mus_engine.cards.card import Card, Rank
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.game.actions import (
    AcceptAction,
    Action,
    BetAction,
    CutMusAction,
    DiscardAction,
    MusAction,
    OrdagoAction,
    PassAction,
    RaiseAction,
    RejectAction,
    SignalAction,
)
from mus_engine.game.observations import Observation
from mus_engine.game.phases import Phase
from mus_engine.players.seating import opponent, partner, team_of
from mus_engine.rules.juego import JuegoEvaluator
from mus_engine.rules.lance import LanceType
from mus_engine.rules.pares import ParesCategory, ParesEvaluator
from mus_engine.rules.signals import Signal

_COUNT_STRENGTH = {0: 0.1, 1: 0.4, 2: 0.7, 3: 0.9, 4: 1.0}
_PARES_STRENGTH = {
    ParesCategory.NONE: 0.0,
    ParesCategory.PAREJA: 0.45,
    ParesCategory.MEDIAS: 0.75,
    ParesCategory.DUPLES: 0.92,
}
_JUEGO_STRENGTH = {31: 1.0, 32: 0.85, 40: 0.65}
_SIGNAL_PRIORITY = (
    Signal.DUPLES,
    Signal.TREINTA_Y_UNA,
    Signal.MEDIAS_REYES,
    Signal.MEDIAS_ASES,
    Signal.MEDIAS,
    Signal.DOS_REYES,
    Signal.DOS_ASES,
    Signal.PARES,
    Signal.JUEGO,
    Signal.TREINTA,
    Signal.VEINTINUEVE,
    Signal.CIEGO,
)

CUT_THRESHOLD = 0.7
BET_THRESHOLD = 0.85
RAISE_THRESHOLD = 0.95
ORDAGO_THRESHOLD = 0.97
ACCEPT_ORDAGO_THRESHOLD = 0.6
ACCEPT_BASE = 0.3
ACCEPT_PER_TANTO = 0.03
PUNTO_FLOOR = 20
DANGER_MARGIN = 5  # tantos que le faltan al rival para ganar: entonces arriesga más


def lance_strength(lance: LanceType, cards: tuple[Card, ...], policy: RankingPolicy) -> float:
    """Fuerza aproximada (0–1) de una mano en un lance. Heurística, no exacta."""
    ranks = [policy.effective_rank(c) for c in cards]
    if lance is LanceType.GRANDE:
        return _COUNT_STRENGTH[ranks.count(Rank.REY)]
    if lance is LanceType.CHICA:
        return _COUNT_STRENGTH[ranks.count(Rank.AS)]
    if lance is LanceType.PARES:
        return _PARES_STRENGTH[ParesEvaluator(policy).classify(cards).category]
    total = JuegoEvaluator(policy).classify(cards).total
    if lance is LanceType.JUEGO:
        return _JUEGO_STRENGTH.get(total, 0.45) if total >= 31 else 0.0
    # Punto: sólo los totales altos son buenos (30 es la máxima, C.VI-7); 20 o menos, nada.
    return max(0.0, (total - PUNTO_FLOOR) / (30 - PUNTO_FLOOR))


class SimpleBot(Bot):
    name = "sencillo"
    description = "Heurísticas de fuerza de mano; no cuenta cartas ni aprende."

    @property
    def _policy(self) -> RankingPolicy:
        return RankingPolicy.from_config(self.context.config)

    def decide(self, observation: Observation) -> Action:
        if observation.phase is Phase.MUS_DECISION:
            return self._mus(observation)
        if observation.phase is Phase.DISCARD:
            return self._discard(observation)
        return self._bet(observation)

    # --- Mus ---------------------------------------------------------------------------

    def _mus(self, observation: Observation) -> Action:
        cards = observation.my_hand
        best = max(lance_strength(lance, cards, self._policy) for lance in LanceType)
        return CutMusAction() if best >= CUT_THRESHOLD else MusAction()

    def _discard(self, observation: Observation) -> Action:
        policy = self._policy
        cards = observation.my_hand
        counts = Counter(policy.effective_rank(c) for c in cards)
        toss = [
            c
            for c in cards
            if policy.effective_rank(c) is not Rank.REY and counts[policy.effective_rank(c)] < 2
        ]
        if not toss:  # todo vale: tira la carta más baja para cumplir el mínimo
            toss = [min(cards, key=lambda c: int(policy.effective_rank(c)))]
        wanted = DiscardAction(toss)
        legal = observation.legal_actions
        return wanted if legal.contains(wanted) else legal.actions[0]

    # --- Envites -----------------------------------------------------------------------

    def _bet(self, observation: Observation) -> Action:
        bet = observation.bet
        lance = observation.lance
        legal = observation.legal_actions
        if bet is None or lance is None:  # pragma: no cover - sólo se decide en un lance
            return next(iter(legal))
        strength = lance_strength(lance, observation.my_hand, self._policy)
        my_team = team_of(observation.seat)
        rival_missing = observation.target_score - observation.score.tantos_of(opponent(my_team))
        boost = 0.1 if rival_missing <= DANGER_MARGIN else 0.0  # va a perder: arriesga más
        if bet.status is BetStatus.OPEN:
            if strength + boost >= ORDAGO_THRESHOLD and rival_missing <= DANGER_MARGIN:
                return OrdagoAction()
            if strength + boost >= BET_THRESHOLD and legal.bet is not None:
                return BetAction(legal.bet.minimum)
            return PassAction()
        if bet.is_ordago:
            return AcceptAction() if strength + boost >= ACCEPT_ORDAGO_THRESHOLD else RejectAction()
        my_missing = observation.target_score - observation.score.tantos_of(my_team)
        # Subir más de lo que falta para ganar no sirve de nada (y dos bots con 31 se
        # subirían sin fin): con tanto en juego, basta con querer.
        if strength >= RAISE_THRESHOLD and legal.raise_ is not None and bet.pending < my_missing:
            return RaiseAction(legal.raise_.minimum)
        # Rechazar regala la negada (y en pares/juego, el valor de la jugada del rival):
        # se acepta con manos medianas y se exige más cuanto más se juega.
        needed = min(0.8, ACCEPT_BASE + ACCEPT_PER_TANTO * bet.pending) - boost
        return AcceptAction() if strength >= needed else RejectAction()

    # --- Señas -------------------------------------------------------------------------

    def signal(self, observation: Observation) -> SignalAction | None:
        gaze = observation.gaze
        if gaze is None:
            return None
        me = observation.seat
        mate = partner(me)
        rivals_watching = any(gaze[p] == me for p in range(4) if p not in (me, mate))
        if gaze[mate] != me or rivals_watching:
            return None
        available = {
            a.signal: a for a in observation.legal_actions.actions if isinstance(a, SignalAction)
        }
        for signal in _SIGNAL_PRIORITY:
            if signal in available:
                return available[signal]
        return None
