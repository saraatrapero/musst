"""Bot de nivel "medio": conteo, probabilidad exacta por lance y marcador.

Nivel medio del diseño (``docs/ai-design.md`` §4): usa los agentes de la Fase D.

- :class:`~mus_engine.ai.counting.CardCounter`: quita de lo posible mis naipes y mis
  descartes, y aplica las declaraciones de pares y juego de cada uno.
- :func:`~mus_engine.ai.equity.team_equity`: probabilidad **exacta** de que mi pareja
  gane el lance (cuenta con la mano posible de mi compañero).
- :class:`~mus_engine.ai.score.ScoreAgent`: cada resultado se valora por cómo cambia la
  probabilidad de ganar la partida. De ahí sale la agresividad: con el rival a punto de
  ganar, arriesga (órdagos, querer más); con la partida encarrilada, no regala nada.

En cada envite compara el valor esperado de pasar, envidar, subir, querer, no querer y
echar órdago, y elige el mayor. Como todavía no perfila a los rivales (Fase E), supone
que se retiran con una frecuencia fija. Las señas, como el bot sencillo.
"""

from __future__ import annotations

from collections import Counter
from itertools import combinations, combinations_with_replacement
from math import comb

from mus_engine.ai.classes import classes_by_ranks
from mus_engine.ai.counting import CardCounter, Knowledge
from mus_engine.ai.equity import lance_equity, team_equity
from mus_engine.ai.score import ScoreAgent
from mus_engine.betting.bets import BetStatus
from mus_engine.bots.simple_bot import SimpleBot
from mus_engine.cards.card import Card
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
)
from mus_engine.game.observations import Observation, PublicBetView
from mus_engine.game.phases import Phase
from mus_engine.players.seating import ALL_SEATS, SeatId, opponent, team_of
from mus_engine.rules.lance import LanceType
from mus_engine.rules.lances import jugada_points

# Suposiciones sobre los rivales mientras no haya perfiles (Fase E): qué fracción de
# sus manos (las mejores) usan para querer o para envidar.
ACCEPT_BET = 0.6  # un rival quiere un envite con su 60 % mejor
ACCEPT_ORDAGO = 0.2
BETS_WITH = 0.45  # quien envida tiene una mano de su 45 % mejor
RAISES_WITH = 0.3
ORDAGOS_WITH = 0.15
# Quien ya ha envidado tiene buena mano: casi siempre quiere si le subo.
PROPOSER_ACCEPTS_RAISE = 0.85
PROPOSER_ACCEPTS_ORDAGO = 0.5
RIVAL_JUGADA = {LanceType.PARES: 2, LanceType.JUEGO: 2}  # valor medio de su jugada
BIG_BET_EQUITY = 0.8  # con más de esto, se envida más fuerte
BIG_BET_EXTRA = 2

# Mus: ventaja esperada en tantos para cortar, y peso de cada lance.
CUT_EDGE = 0.5
LANCE_WEIGHTS = {
    LanceType.GRANDE: 1.5,
    LanceType.CHICA: 1.0,
    LanceType.PARES: 2.0,
    LanceType.JUEGO: 2.5,
    LanceType.PUNTO: 0.5,
}


class MediumBot(SimpleBot):
    name = "medio"
    description = "Cuenta cartas, calcula la probabilidad exacta de cada lance y mira el marcador."

    def decide(self, observation: Observation) -> Action:
        if observation.phase is Phase.MUS_DECISION:
            return self._mus(observation)
        if observation.phase is Phase.DISCARD:
            return self._discard(observation)
        return self._bet(observation)

    def _knowledge(self, observation: Observation) -> Knowledge:
        return CardCounter(self._policy).read(observation)

    # --- Mus ---------------------------------------------------------------------------

    def _mus(self, observation: Observation) -> Action:
        knowledge = self._knowledge(observation)
        edge = sum(
            weight * (2 * team_equity(knowledge, lance, self._policy) - 1)
            for lance, weight in LANCE_WEIGHTS.items()
        )
        return CutMusAction() if edge >= CUT_EDGE else MusAction()

    def _discard(self, observation: Observation) -> Action:
        """Tira los naipes que maximizan el valor esperado de la mano resultante.

        Se enumeran **todas** las formas de quedarse con 0–3 naipes y, para cada una,
        todas las clases de naipes que pueden entrar (con su probabilidad exacta).
        """
        knowledge = self._knowledge(observation)
        hand = observation.my_hand
        legal = observation.legal_actions
        splits = [
            (kept, tuple(c for c in hand if c not in kept))
            for size in range(len(hand) - 1, -1, -1)
            for kept in combinations(hand, size)
        ]
        options = [
            (self._expected_value(kept, knowledge), toss)
            for kept, toss in splits
            if legal.contains(DiscardAction(toss))
        ]
        # Siempre se puede descartar algo (D-13); con empate, el primero (menos naipes).
        return DiscardAction(max(options, key=lambda item: item[0])[1])

    def _expected_value(self, kept: tuple[Card, ...], knowledge: Knowledge) -> float:
        policy = self._policy
        kept_ranks = [int(policy.effective_rank(c)) for c in kept]
        available = knowledge.available
        classes = classes_by_ranks(policy)
        draw = 4 - len(kept)
        total_weight = 0
        total = 0.0
        for drawn in combinations_with_replacement(sorted(available), draw):
            weight = 1
            for rank, count in Counter(drawn).items():
                weight *= comb(available[rank], count)
            if not weight:
                continue
            cls = classes[tuple(sorted((*kept_ranks, *drawn)))]
            value = sum(w * lance_equity(cls, lance, policy) for lance, w in LANCE_WEIGHTS.items())
            total += weight * value
            total_weight += weight
        return total / total_weight

    # --- Envites -----------------------------------------------------------------------

    def _bet(self, observation: Observation) -> Action:
        bet = observation.bet
        lance = observation.lance
        legal = observation.legal_actions
        if bet is None or lance is None:  # pragma: no cover - sólo se decide en un lance
            return next(iter(legal))
        knowledge = self._knowledge(observation)
        values = _Values(self, observation, lance, knowledge)
        options: list[tuple[float, Action]] = []
        if bet.status is BetStatus.OPEN:
            options.append((values.showdown(0, values.equity()), PassAction()))
            if legal.bet is not None:
                amount = legal.bet.minimum
                if values.equity() >= BIG_BET_EQUITY:
                    amount += BIG_BET_EXTRA
                options.append((values.bet(amount), BetAction(amount)))
            options.append((values.ordago(), OrdagoAction()))
        else:
            assert bet.proposer is not None
            shown = ORDAGOS_WITH if bet.is_ordago else RAISES_WITH if bet.accepted else BETS_WITH
            values.facing(bet.proposer, shown)
            options.append((values.reject(bet), RejectAction()))
            if bet.is_ordago:
                options.append((values.equity(), AcceptAction()))
            else:
                options.append((values.showdown(bet.pending, values.equity()), AcceptAction()))
                if legal.raise_ is not None and bet.pending < values.my_missing:
                    amount = legal.raise_.minimum
                    options.append((values.raise_(bet, amount), RaiseAction(amount)))
                options.append((values.counter_ordago(bet), OrdagoAction()))
        choices = [(v, a) for v, a in options if legal.contains(a)]
        return max(choices, key=lambda item: item[0])[1]


class _Values:
    """Valor esperado (probabilidad de ganar la partida) de cada opción de envite.

    Modelo de los rivales: quieren o envidan sólo con sus mejores manos (las fracciones
    de arriba). Así, «me quieren» y «me envidan» se traducen en condicionar sus manos a
    ese tramo y recalcular de forma exacta mi probabilidad de ganar el lance.
    """

    def __init__(self, bot: MediumBot, obs: Observation, lance: LanceType, knowledge: Knowledge):
        team = team_of(obs.seat)
        self.policy = bot._policy
        self.knowledge = knowledge
        self.rivals = tuple(s for s in ALL_SEATS if team_of(s) is not team)
        self.mine = obs.score.tantos_of(team)
        self.theirs = obs.score.tantos_of(opponent(team))
        self.score = ScoreAgent(obs.target_score)
        self.my_missing = obs.target_score - self.mine
        self.lance = lance
        self.my_jugada = jugada_points(lance, obs.my_hand, bot.context.config)
        self.rival_jugada = RIVAL_JUGADA.get(lance, 0)
        self.windows: dict[SeatId, tuple[float, float]] = {}

    def equity(self, extra: dict[SeatId, tuple[float, float]] | None = None) -> float:
        windows = dict(self.windows)
        windows.update(extra or {})
        return team_equity(self.knowledge, self.lance, self.policy, windows)

    def facing(self, proposer: SeatId, top: float) -> None:
        """El rival ``proposer`` ha envidado: tiene una mano de su ``top`` mejor."""
        self.windows[proposer] = (1.0 - top, 1.0)

    def _win_points(self, amount: int) -> int:
        if self.lance in (LanceType.GRANDE, LanceType.CHICA):
            return max(amount, 1)  # en paso, el lance vale 1
        extra = 1 if self.lance is LanceType.PUNTO else self.my_jugada
        return amount + extra

    def _lose_points(self, amount: int) -> int:
        if self.lance in (LanceType.GRANDE, LanceType.CHICA):
            return max(amount, 1)
        extra = 1 if self.lance is LanceType.PUNTO else self.rival_jugada
        return amount + extra

    def showdown(self, amount: int, p: float) -> float:
        """Se ve a cartas con ``amount`` tantos queridos y probabilidad ``p`` de ganar."""
        win = self.score.outcome(self.mine, self.theirs, self._win_points(amount), 0)
        lose = self.score.outcome(self.mine, self.theirs, 0, self._lose_points(amount))
        return p * win + (1 - p) * lose

    def _uncontested(self, points: int) -> float:
        """No me quieren: cobro ``points`` y mi jugada."""
        jugada = self.my_jugada if self.lance in (LanceType.PARES, LanceType.JUEGO) else 0
        extra = 1 if self.lance is LanceType.PUNTO else 0
        return self.score.outcome(self.mine, self.theirs, points + jugada + extra, 0)

    def _team_response(self, accept: float) -> tuple[float, float]:
        """(P(no me quieren), P(gano el lance | me quieren)) si cada rival quiere con su
        ``accept`` mejor: no quieren sólo si los dos tienen manos flojas."""
        fold = (1.0 - accept) ** 2
        p = self.equity()
        weak = self.equity({r: (0.0, 1.0 - accept) for r in self.rivals})
        return fold, (p - fold * weak) / (1.0 - fold)

    def _proposer_response(self, proposer: SeatId, accept: float) -> tuple[float, float]:
        """Lo mismo cuando responde sólo quien ya envidó (con su tramo actual)."""
        low, high = self.windows.get(proposer, (0.0, 1.0))
        cut = high - (high - low) * accept
        return 1.0 - accept, self.equity({proposer: (cut, high)})

    def bet(self, amount: int) -> float:
        fold, p = self._team_response(ACCEPT_BET)
        return fold * self._uncontested(1) + (1 - fold) * self.showdown(amount, p)

    def ordago(self) -> float:
        fold, p = self._team_response(ACCEPT_ORDAGO)
        return fold * self._uncontested(1) + (1 - fold) * p

    def raise_(self, bet: PublicBetView, amount: int) -> float:
        assert bet.proposer is not None
        fold, p = self._proposer_response(bet.proposer, PROPOSER_ACCEPTS_RAISE)
        return fold * self._uncontested(bet.pending) + (1 - fold) * self.showdown(
            bet.pending + amount, p
        )

    def counter_ordago(self, bet: PublicBetView) -> float:
        assert bet.proposer is not None
        fold, p = self._proposer_response(bet.proposer, PROPOSER_ACCEPTS_ORDAGO)
        return fold * self._uncontested(bet.pending) + (1 - fold) * p

    def reject(self, bet: PublicBetView) -> float:
        points = 1 if bet.accepted == 0 else bet.accepted + 1
        jugada = self.rival_jugada if self.lance in (LanceType.PARES, LanceType.JUEGO) else 0
        return self.score.outcome(self.mine, self.theirs, 0, points + jugada)
