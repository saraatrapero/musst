"""Bot de nivel "medio": conteo, probabilidad exacta por lance y marcador.

Nivel medio del diseño (``docs/ai-design.md`` §4): usa los agentes de la Fase D.

- :class:`~mus_engine.ai.counting.CardCounter`: quita de lo posible mis naipes y mis
  descartes, y aplica las declaraciones de pares y juego de cada uno.
- :func:`~mus_engine.ai.equity.team_equity`: probabilidad **exacta** de que mi pareja
  gane el lance (cuenta con la mano posible de mi compañero).
- :class:`~mus_engine.ai.score.ScoreAgent`: cada resultado se valora por cómo cambia la
  probabilidad de ganar la partida. De ahí sale la agresividad: con el rival a punto de
  ganar, arriesga (órdagos, querer más); con la partida encarrilada, no regala nada.
- :class:`~mus_engine.ai.profiles.PlayerProfile` (Fase E): cómo juega cada rival —lo
  que trae guardado (``BotContext.profiles``) más lo que ve en esta partida—. Con
  ``use_profiles`` activado, «me ha envidado» o «me quiere» se traduce en qué manos
  son probables según ese jugador (desactivado por defecto: ver ``docs/ai.md``).

En cada envite compara el valor esperado de pasar, envidar, subir, querer, no querer y
echar órdago, y elige el mayor. Las señas, como el bot sencillo.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import replace
from itertools import combinations, combinations_with_replacement
from math import comb
from typing import ClassVar

from mus_engine.ai.classes import classes_by_ranks
from mus_engine.ai.counting import CardCounter, Knowledge
from mus_engine.ai.equity import View, lance_equity, team_equity
from mus_engine.ai.inference import inclination, mus_signals
from mus_engine.ai.profiles import BIN_NAMES, PlayerProfile, ProfileTracker, tier
from mus_engine.ai.score import ScoreAgent
from mus_engine.betting.bets import BetStatus
from mus_engine.bots.base import BotContext
from mus_engine.bots.simple_bot import SimpleBot
from mus_engine.cards.card import Card
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.events.events import LanceStarted, Passed
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

# Quien ya ha envidado tiene buena mano: casi siempre quiere si le subo.
PROPOSER_ACCEPTS_RAISE = 0.85
PROPOSER_ACCEPTS_ORDAGO = 0.5
RIVAL_JUGADA = {LanceType.PARES: 2, LanceType.JUEGO: 2}  # valor medio de su jugada
BIG_BET_EQUITY = 0.8  # con más de esto, se envida más fuerte
BIG_BET_EXTRA = 2
# Órdago sólo cuando la partida ya está avanzada y cree que, si se lo quieren, gana el
# lance; al principio, nunca (con una mano segura se envida para cobrar más). Si va a
# perder la partida de todos modos, arriesga, pero no con cualquier cosa. Medido: el
# bot gana lo mismo (74 % contra el sencillo) y echa unas 6 veces menos órdagos.
ORDAGO_MIN_WIN = 0.9
ORDAGO_LATE = 30  # tantos de la pareja que más lleva a partir de los que es «tarde»
DESPERATE = 0.15  # P(ganar la partida) por debajo de la cual arriesga más
DESPERATE_MIN_WIN = 0.5  # ... pero sólo si tiene opciones de ganar el lance

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
    # Deducir la mano de los rivales de su mus y de sus pases (``ai/inference.py``)
    # calibra mejor las probabilidades pero, en las pruebas, no gana más partidas: queda
    # desactivado hasta la inferencia completa de la Fase F (docs/ai.md).
    infer_from_mus_and_passes: ClassVar[bool] = False
    # Usar el perfil de cada rival para interpretar sus envites y prever si querrá.
    # Medido en la Fase E, no mejora frente a los valores ajustados de la Fase D (65 %
    # contra el sencillo en ambos casos; algo peor contra un farolero): desactivado
    # hasta la Fase F. Los perfiles se siguen calculando y guardando.
    use_profiles: ClassVar[bool] = False
    # Tener en cuenta las señas que ve (de su compañero y de los rivales que pilla):
    # las manos que no cuadran con la seña pesan mucho menos (docs/ai.md, Fase G).
    read_signals: ClassVar[bool] = True

    name = "medio"
    description = (
        "Cuenta cartas, calcula la probabilidad exacta de cada lance, "
        "mira el marcador y perfila a los rivales."
    )

    def on_game_start(self, context: BotContext) -> None:
        super().on_game_start(context)
        self._tracker = ProfileTracker(RankingPolicy.from_config(context.config))

    def profile_of(self, seat: SeatId, observation: Observation) -> PlayerProfile:
        """Perfil de ``seat``: lo guardado de otras partidas más lo visto en ésta."""
        self._tracker.observe(observation.events)
        if not self.use_profiles:
            return PlayerProfile()
        return self.context.profiles.get(seat, PlayerProfile()) + self._tracker.profile(seat)

    def decide(self, observation: Observation) -> Action:
        if observation.phase is Phase.MUS_DECISION:
            return self._mus(observation)
        if observation.phase is Phase.DISCARD:
            return self._discard(observation)
        return self._bet(observation)

    def _knowledge(self, observation: Observation) -> Knowledge:
        knowledge = CardCounter(self._policy).read(observation)
        if self.read_signals:
            return knowledge
        return replace(knowledge, signals=(frozenset(),) * len(knowledge.signals))

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
            if values.ordago_is_sound(values.ordago_win()):
                options.append((values.ordago(), OrdagoAction()))
        else:
            assert bet.proposer is not None
            kind = "ordago" if bet.is_ordago else "raise" if bet.accepted else "bet"
            values.facing(bet.proposer, kind)
            options.append((values.reject(bet), RejectAction()))
            if bet.is_ordago:
                options.append((values.equity(), AcceptAction()))
            else:
                options.append((values.showdown(bet.pending, values.equity()), AcceptAction()))
                if legal.raise_ is not None and bet.pending < values.my_missing:
                    amount = legal.raise_.minimum
                    options.append((values.raise_(bet, amount), RaiseAction(amount)))
                if values.ordago_is_sound(values.counter_ordago_win(bet)):
                    options.append((values.counter_ordago(bet), OrdagoAction()))
        choices = [(v, a) for v, a in options if legal.contains(a)]
        return max(choices, key=lambda item: item[0])[1]


class _Values:
    """Valor esperado (probabilidad de ganar la partida) de cada opción de envite.

    Con el perfil de cada rival, «me han envidado» y «me quieren» se traducen en
    reponderar sus manos posibles (regla de Bayes, :meth:`Distribution.tilt`) y
    recalcular de forma exacta mi probabilidad de ganar el lance.
    """

    def __init__(self, bot: MediumBot, obs: Observation, lance: LanceType, knowledge: Knowledge):
        team = team_of(obs.seat)
        self.policy = bot._policy
        self.knowledge = knowledge
        self.rivals = tuple(s for s in ALL_SEATS if team_of(s) is not team)
        self.profiles = {r: bot.profile_of(r, obs) for r in self.rivals}
        self.mine = obs.score.tantos_of(team)
        self.theirs = obs.score.tantos_of(opponent(team))
        self.score = ScoreAgent(obs.target_score)
        self.my_missing = obs.target_score - self.mine
        self.lance = lance
        self.my_jugada = jugada_points(lance, obs.my_hand, bot.context.config)
        self.rival_jugada = RIVAL_JUGADA.get(lance, 0)
        self.views: dict[SeatId, View] = {}
        if bot.infer_from_mus_and_passes:
            self._mus_signals(bot, obs)
            self._passes(bot, obs)

    def _add(self, seat: SeatId, view: View) -> None:
        base = self.views.get(seat)
        self.views[seat] = view if base is None else _compose(base, view)

    def _mus_signals(self, bot: MediumBot, obs: Observation) -> None:
        """El rival que ha cortado el mus suele llevar buena mano; el que lo ha pedido, no.

        Sólo a los rivales: a mi compañero lo trato como una mano cualquiera, que es lo
        que mejor ha funcionado en las pruebas (docs/ai.md).
        """
        for seat, signal in mus_signals(obs.events, obs.hand_number).items():
            if seat in self.rivals:
                beta = bot.profile_of(seat, obs).mus_beta(signal, self.lance)
                self._add(seat, _inclined(beta))

    def _passes(self, bot: MediumBot, obs: Observation) -> None:
        """Un rival que ya ha pasado en este lance suele tener una mano floja (regla de
        Bayes con su perfil)."""
        start = max(
            (
                e.seq
                for e in obs.events
                if isinstance(e.event, LanceStarted)
                and e.event.lance == self.lance.value
                and e.hand_number == obs.hand_number
            ),
            default=None,
        )
        if start is None:
            return
        passed = {
            e.event.seat
            for e in obs.events
            if e.seq > start and isinstance(e.event, Passed) and e.event.seat in self.rivals
        }
        for seat in passed:
            profile = bot.profile_of(seat, obs)
            self._add(seat, _passes(profile))

    def equity(self, extra: Mapping[SeatId, View] | None = None) -> float:
        views = dict(self.views)
        for seat, view in (extra or {}).items():
            base = views.get(seat)
            views[seat] = view if base is None else _compose(base, view)
        return team_equity(self.knowledge, self.lance, self.policy, views)

    def facing(self, proposer: SeatId, kind: str) -> None:
        """El rival ``proposer`` ha envidado (``bet``), subido (``raise``) u ordagado.

        Su envite sustituye a lo que se deducía de su mus y de sus pases: van muy ligados
        (quien corta suele envidar) y contarlos a la vez lo haría parecer más fuerte.
        """
        top, leak = self.profiles[proposer].behaviour(kind)
        self.views[proposer] = _does(top, leak)

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

    def _team_response(self, ordago: bool) -> tuple[float, float]:
        """(P(no me quieren), P(gano el lance | me quieren)).

        Cada rival quiere según su perfil (su ``top`` de manos más alguna mala); no me
        quieren sólo si los dos dicen que no.
        """
        kind = "accept_ordago" if ordago else "accept"
        behaviour = {r: self.profiles[r].behaviour(kind) for r in self.rivals}
        fold = 1.0
        for top, leak in behaviour.values():
            fold *= (1 - top) * (1 - leak)
        p = self.equity()
        weak = self.equity({r: _declines(top, leak) for r, (top, leak) in behaviour.items()})
        return fold, min(1.0, max(0.0, (p - fold * weak) / (1.0 - fold)))

    def _proposer_response(self, proposer: SeatId, accept: float) -> tuple[float, float]:
        """Lo mismo cuando responde sólo quien ya envidó: quiere con su ``accept`` mejor."""
        return 1.0 - accept, self.equity({proposer: lambda d: d.window(1.0 - accept, 1.0)})

    def bet(self, amount: int) -> float:
        fold, p = self._team_response(ordago=False)
        return fold * self._uncontested(1) + (1 - fold) * self.showdown(amount, p)

    def ordago_win(self) -> float:
        """P(ganar el lance) si le quieren el órdago."""
        return self._team_response(ordago=True)[1]

    def counter_ordago_win(self, bet: PublicBetView) -> float:
        assert bet.proposer is not None
        return self._proposer_response(bet.proposer, PROPOSER_ACCEPTS_ORDAGO)[1]

    def ordago_is_sound(self, win: float) -> bool:
        """Sólo se echa si cree que lo gana, salvo que la partida esté casi perdida."""
        if max(self.mine, self.theirs) < ORDAGO_LATE:
            return False
        if win >= ORDAGO_MIN_WIN:
            return True
        return win >= DESPERATE_MIN_WIN and self.score.win(self.mine, self.theirs) < DESPERATE

    def ordago(self) -> float:
        fold, p = self._team_response(ordago=True)
        return fold * self._uncontested(1) + (1 - fold) * p

    def raise_(self, bet: PublicBetView, amount: int) -> float:
        assert bet.proposer is not None
        # Quien ha envidado de farol no aguanta un revoque: con su perfil, la parte de
        # sus envites que son faroles se va (y sólo me llevo lo envidado).
        accept = min(PROPOSER_ACCEPTS_RAISE, 1.0 - self.profiles[bet.proposer].bluff_share())
        fold, p = self._proposer_response(bet.proposer, accept)
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


def _acts(top: float, leak: float) -> Callable[[float], float]:
    """P(actúa | percentil): seguro con su ``top`` mejor, con prob. ``leak`` si no."""
    return lambda percentile: 1.0 if percentile >= 1.0 - top else leak


def _does(top: float, leak: float) -> View:
    """Sus manos si ha hecho la acción (envidar, querer…)."""
    acts = _acts(top, leak)
    return lambda d: d.tilt(acts)


def _declines(top: float, leak: float) -> View:
    """Sus manos si no la ha hecho (ha pasado, no quiere…)."""
    acts = _acts(top, leak)
    return lambda d: d.tilt(lambda q: 1 - acts(q))


def _passes(profile: PlayerProfile) -> View:
    """Sus manos si ha pasado: P(pasa | fuerza) = 1 − P(envida | tramo) de su perfil.

    Más suave que :func:`_declines`: con buena mano también se pasa a veces.
    """
    weights = [1 - profile.bet_given(b) for b in range(len(BIN_NAMES))]
    return lambda d: d.tilt(lambda q: weights[tier(q)])


def _inclined(beta: float) -> View:
    weight = inclination(beta)
    return lambda d: d.tilt(weight)


def _compose(first: View, then: View) -> View:
    return lambda d: then(first(d))


class LearningMediumBot(MediumBot):
    """El bot medio que aprende de cada persona: usa el perfil que la web guarda de ella
    entre partidas (y lo que ve en la partida en curso) para interpretar sus envites y
    prever si querrá. Medido en ``scripts/aprendizaje.py``: contra quien abandona casi
    todo pasa de ganar el 78 % de las partidas al 96 %; contra quien no tiene un estilo
    marcado, gana lo mismo que sin perfil."""

    use_profiles = True
