"""Mide el rendimiento de los bots con partidas simuladas.

    PYTHONPATH=src python scripts/medir_bots.py --partidas 300 --json resultados.json

Juega cada enfrentamiento con y sin señas (reglas de la web: señas falsas permitidas y
recuento al final) y saca, para la pareja del primer bot:

- P(ganar la partida) con su intervalo de confianza del 95 % (Wilson);
- P(ganar la jugada) según haya habido mus o no, y según haya visto una seña de su
  compañero o los rivales le hayan pillado la suya;
- la calibración: la probabilidad que el bot calcula de ganar cada lance frente a lo
  que pasa de verdad al enseñar las cartas.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from collections.abc import Callable
from multiprocessing import Pool
from typing import Any

from mus_engine.ai.classes import hand_class
from mus_engine.ai.counting import CardCounter
from mus_engine.ai.equity import team_equity
from mus_engine.bots.base import Bot, BotContext
from mus_engine.bots.medium_bot import MediumBot
from mus_engine.bots.random_bot import RandomBot
from mus_engine.bots.simple_bot import SimpleBot
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.config import GameConfig
from mus_engine.events.events import (
    DiscardDeclared,
    HandsRevealed,
    HandStarted,
    PointsAwarded,
    SignalSeen,
)
from mus_engine.game.actions import SignalAction
from mus_engine.game.game import Game
from mus_engine.game.phases import Phase
from mus_engine.players.seating import ALL_SEATS, SeatId, partner, team_of
from mus_engine.rules.evaluation import resolve
from mus_engine.rules.lance import LanceType
from mus_engine.rules.lances import evaluator_for


class DeafMediumBot(MediumBot):
    """El bot medio sin leer las señas (para medir cuánto aportan)."""

    read_signals = False


BOTS: dict[str, Callable[[], Bot]] = {
    "medio": MediumBot,
    "medio_sordo": DeafMediumBot,
    "sencillo": SimpleBot,
    "aleatorio": RandomBot,
}
MATCHES = [
    ("medio", "sencillo"),
    ("medio", "aleatorio"),
    ("sencillo", "aleatorio"),
    ("medio", "medio_sordo"),
]
POLICY = RankingPolicy()


def play(args: tuple[str, str, bool, int]) -> dict[str, Any]:
    """Una partida; la pareja de ``first`` juega en asientos pares o impares según la semilla."""
    first, second, signals, seed = args
    config = GameConfig(signals_enabled=signals, false_signals=True, negadas_at_end=True)
    side = seed % 2
    bots = [BOTS[first if s % 2 == side else second]() for s in ALL_SEATS]
    for seat, bot in enumerate(bots):
        bot.on_game_start(BotContext(SeatId(seat), config, seed + seat))
    game = Game(config=config, seed=seed)
    game.start()
    estimates: list[tuple[int, str, SeatId, float]] = []  # (jugada, lance, asiento, P)
    asked: set[tuple[int, str, int]] = set()
    while not game.is_finished:
        if signals:
            game.tick()
            for seat in ALL_SEATS:
                action = bots[seat].signal(game.get_observation(seat))
                if isinstance(action, SignalAction):
                    game.apply_action(seat, action)
        (seat,) = game.current_actors()
        obs = game.get_observation(seat)
        key = (obs.hand_number, str(obs.lance), seat)
        if (
            obs.phase is Phase.LANCE
            and obs.lance is not None
            and seat % 2 == side
            and key not in asked
        ):
            asked.add(key)
            knowledge = CardCounter(POLICY).read(obs)
            p = team_equity(knowledge, obs.lance, POLICY)
            estimates.append((obs.hand_number, obs.lance.value, seat, p))
        game.apply_action(seat, bots[seat].decide(obs))
    return summarize(game, side, estimates)


def summarize(
    game: Game, side: int, estimates: list[tuple[int, str, SeatId, float]]
) -> dict[str, Any]:
    winner = game.winner
    hands: dict[int, dict[str, Any]] = defaultdict(
        lambda: {"mus": False, "seen": False, "caught": False, "ours": 0, "theirs": 0}
    )
    revealed: dict[int, tuple[tuple[Any, ...], ...]] = {}
    manos: dict[int, SeatId] = {}
    for env in game.event_log:
        event, info = env.event, hands[env.hand_number]
        if isinstance(event, DiscardDeclared):
            info["mus"] = True
        elif isinstance(event, SignalSeen) and env.audience is not None:
            ours = env.audience % 2 == side
            if ours and event.sender == partner(env.audience):
                info["seen"] = True  # mi pareja vio la seña de su compañero
            if not ours and event.sender % 2 == side:
                info["caught"] = True  # los rivales nos pillaron una seña
        elif isinstance(event, PointsAwarded):
            mine = (event.team == "A") == (side == 0)
            info["ours" if mine else "theirs"] += event.points
        elif isinstance(event, HandsRevealed):
            revealed[env.hand_number] = event.hands
        elif isinstance(event, HandStarted):
            manos[env.hand_number] = event.mano
    calibration = []
    for hand_number, lance_name, seat, p in estimates:
        cards = revealed.get(hand_number)
        if cards is None or hand_number not in manos:
            continue
        actual = lance_winner(lance_name, cards, manos[hand_number])
        if actual is not None:
            calibration.append((p, team_of(actual) is team_of(seat)))
    return {
        "won": winner is not None and winner.value == side,
        "hands": [h for n, h in sorted(hands.items()) if n > 0],
        "calibration": calibration,
    }


def lance_winner(
    lance_name: str, cards: tuple[tuple[Any, ...], ...], mano: SeatId
) -> SeatId | None:

    lance = LanceType(lance_name)
    players = {
        SeatId(s): cards[s]
        for s in ALL_SEATS
        if hand_class(cards[s], POLICY).strengths[lance] is not None
    }
    if not players:
        return None
    return resolve(evaluator_for(lance, POLICY), players, mano).winner


def wilson(wins: int, n: int) -> tuple[float, float, float]:
    if n == 0:
        return 0.0, 0.0, 0.0
    z, p = 1.96, wins / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return p, max(0.0, centre - half), min(1.0, centre + half)


def rate(rows: list[bool]) -> dict[str, float]:
    p, low, high = wilson(sum(rows), len(rows))
    return {"p": round(p, 4), "low": round(low, 4), "high": round(high, 4), "n": len(rows)}


def report(results: list[dict[str, Any]]) -> dict[str, Any]:
    hands = [h for r in results for h in r["hands"]]

    def hand_rate(pred: Callable[[dict[str, Any]], bool]) -> dict[str, float]:
        return rate([h["ours"] > h["theirs"] for h in hands if pred(h)])

    bins: dict[int, list[bool]] = defaultdict(list)
    for p, won in (c for r in results for c in r["calibration"]):
        bins[min(9, int(p * 10))].append(won)
    return {
        "partida": rate([r["won"] for r in results]),
        "jugada": hand_rate(lambda h: True),
        "con_mus": hand_rate(lambda h: h["mus"]),
        "sin_mus": hand_rate(lambda h: not h["mus"]),
        "vio_sena": hand_rate(lambda h: h["seen"]),
        "no_vio_sena": hand_rate(lambda h: not h["seen"]),
        "le_pillaron": hand_rate(lambda h: h["caught"]),
        "calibracion": {
            f"{b / 10:.1f}-{(b + 1) / 10:.1f}": rate(rows) for b, rows in sorted(bins.items())
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partidas", type=int, default=200)
    parser.add_argument("--json", default=None)
    args = parser.parse_args()
    out: dict[str, Any] = {}
    with Pool() as pool:
        for first, second in MATCHES:
            for signals in (False, True):
                jobs = [(first, second, signals, seed) for seed in range(args.partidas)]
                name = f"{first}_vs_{second}_{'con' if signals else 'sin'}_senas"
                out[name] = report(pool.map(play, jobs))
                part = out[name]["partida"]
                print(f"{name}: {part['p']:.1%} [{part['low']:.1%}-{part['high']:.1%}]")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
