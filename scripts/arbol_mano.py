"""Árbol de una jugada y detección de faroles: mide al bot medio con partidas simuladas.

    PYTHONPATH=src python scripts/arbol_mano.py --json docs/arbol_mano.json

1. **Árbol de la jugada** (bot medio y su compañero contra dos sencillos). Para cada
   jugada, desde el asiento del bot: ¿hay mus? Si no, ¿quién lo corta? Si lo hay,
   ¿cuántas cartas pide el bot en el primer descarte y cuántas rondas de mus hay? En
   cada rama: cuántas jugadas caen ahí, P(ganar la jugada), tantos de ventaja y
   P(ganar cada lance).
2. **Experiencia: ¿lleva cartas o va de farol?** El bot medio juega series de partidas
   contra los mismos rivales faroleros y guarda su perfil de una partida a la
   siguiente. Cada vez que un rival envida, el perfil estima P(farol) (envidar con una
   mano del 30 % peor); al enseñar las cartas se ve si lo era. Se compara la
   estimación con la realidad según cuántas partidas lleva observadas.
3. **¿Sirve la experiencia para ganar?** El bot medio usando perfiles contra el mismo
   bot sin usarlos, ambos contra faroleros.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from collections.abc import Callable
from multiprocessing import Pool
from pathlib import Path
from typing import Any

from mus_engine.ai.profiles import (
    BIN_NAMES,
    TIER_WIDTHS,
    PlayerProfile,
    ProfileTracker,
    hand_percentile,
    tier,
)
from mus_engine.bots.base import Bot, BotContext
from mus_engine.bots.medium_bot import MediumBot
from mus_engine.bots.simple_bot import SimpleBot
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.config import GameConfig
from mus_engine.events.events import (
    BetPlaced,
    DiscardDeclared,
    HandsRevealed,
    MusCut,
    PointsAwarded,
)
from mus_engine.game.game import Game
from mus_engine.players.seating import ALL_SEATS, SeatId
from mus_engine.rules.lance import LanceType

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.bots.styles import FaroleroBot  # bot de prueba que farolea el 60 %

POLICY = RankingPolicy()
CONFIG = GameConfig(negadas_at_end=True)
LANCES = ("grande", "chica", "pares", "juego", "punto")


class ProfiledMediumBot(MediumBot):
    use_profiles = True


def wilson(wins: int, n: int) -> dict[str, float]:
    if n == 0:
        return {"p": 0.0, "low": 0.0, "high": 0.0, "n": 0}
    z, p = 1.96, wins / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return {
        "p": round(p, 4),
        "low": round(max(0.0, centre - half), 4),
        "high": round(min(1.0, centre + half), 4),
        "n": n,
    }


def play_game(
    bots: list[Bot], seed: int, profiles: dict[SeatId, PlayerProfile] | None = None
) -> Game:
    for seat, bot in enumerate(bots):
        bot.on_game_start(BotContext(SeatId(seat), CONFIG, seed + seat, profiles or {}))
    game = Game(config=CONFIG, seed=seed)
    game.start()
    while not game.is_finished:
        (seat,) = game.current_actors()
        game.apply_action(seat, bots[seat].decide(game.get_observation(seat)))
    return game


# --- 1. Árbol de la jugada ------------------------------------------------------------


def tree_game(seed: int) -> list[dict[str, Any]]:
    side = seed % 2
    bots: list[Bot] = [MediumBot() if s % 2 == side else SimpleBot() for s in ALL_SEATS]
    game = play_game(bots, seed)
    me = SeatId(side)  # el asiento del bot que seguimos (su compañero es me + 2)
    hands: dict[int, dict[str, Any]] = {}
    for env in game.event_log:
        if env.hand_number == 0:
            continue
        h = hands.setdefault(
            env.hand_number,
            {"cut_by": None, "rounds": 0, "discard": None, "ours": 0, "theirs": 0, "lances": {}},
        )
        event = env.event
        if isinstance(event, MusCut) and h["cut_by"] is None:
            h["cut_by"] = "nosotros" if event.seat % 2 == side else "ellos"
        elif isinstance(event, DiscardDeclared):
            if event.seat == me:
                h["rounds"] += 1
                if h["discard"] is None:
                    h["discard"] = event.count
        elif isinstance(event, PointsAwarded):
            mine = (event.team == "A") == (side == 0)
            h["ours" if mine else "theirs"] += event.points
            if event.reason != "ordago":
                h["lances"].setdefault(event.lance, mine)
    return list(hands.values())


def branch(hand: dict[str, Any]) -> tuple[str, str]:
    if hand["rounds"] == 0:
        return "no_hay_mus", f"corta_{hand['cut_by']}"
    rounds = "1_ronda" if hand["rounds"] == 1 else "2_o_mas_rondas"
    return f"mus_pide_{hand['discard']}", rounds


def summarize_hands(hands: list[dict[str, Any]], total: int) -> dict[str, Any]:
    diffs = [h["ours"] - h["theirs"] for h in hands]
    n = len(diffs)
    mean = sum(diffs) / n if n else 0.0
    sd = math.sqrt(sum((d - mean) ** 2 for d in diffs) / (n - 1)) if n > 1 else 0.0
    lances = {}
    for lance in LANCES:
        played = [h["lances"][lance] for h in hands if lance in h["lances"]]
        if played:
            lances[lance] = wilson(sum(played), len(played))
    return {
        "jugadas": n,
        "proporcion": round(n / total, 4) if total else 0.0,
        "gana_jugada": wilson(sum(d > 0 for d in diffs), n),
        "tantos": round(mean, 2),
        "tantos_low": round(mean - 1.96 * sd / math.sqrt(n), 2) if n > 1 else 0.0,
        "tantos_high": round(mean + 1.96 * sd / math.sqrt(n), 2) if n > 1 else 0.0,
        "lances": lances,
    }


def tree_report(hands: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(hands)
    out: dict[str, Any] = {"todas": summarize_hands(hands, total)}
    no_mus = [h for h in hands if h["rounds"] == 0]
    mus = [h for h in hands if h["rounds"] > 0]
    out["no_hay_mus"] = summarize_hands(no_mus, total)
    out["hay_mus"] = summarize_hands(mus, total)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for h in hands:
        first, second = branch(h)
        groups[(first, "todas")].append(h)
        groups[(first, second)].append(h)
    out["ramas"] = {
        f"{a}/{b}": summarize_hands(rows, total) for (a, b), rows in sorted(groups.items())
    }
    return out


# --- 2. Experiencia: ¿farol o cartas? ---------------------------------------------------


def p_bluff(profile: PlayerProfile) -> float:
    """P(su mano está en el 30 % peor | ha envidado), por la regla de Bayes."""
    weights = [profile.bet_given(b) * w for b, w in enumerate(TIER_WIDTHS)]
    return weights[0] / sum(weights)


def experience_series(args: tuple[int, int, str]) -> list[dict[str, Any]]:
    """Una serie de partidas contra los mismos rivales; el perfil se guarda entre partidas."""
    series, games, rival = args
    stored: dict[SeatId, PlayerProfile] = {SeatId(1): PlayerProfile(), SeatId(3): PlayerProfile()}
    rows: list[dict[str, Any]] = []
    for g in range(games):
        seed = 100_000 * (series + 1) + g
        rival_bot: Callable[[], Bot] = FaroleroBot if rival == "farolero" else SimpleBot
        bots: list[Bot] = [ProfiledMediumBot() if s % 2 == 0 else rival_bot() for s in ALL_SEATS]
        estimates = {s: p_bluff(stored[s]) for s in stored}
        game = play_game(bots, seed, dict(stored))
        revealed: dict[int, tuple[Any, ...]] = {}
        for env in game.event_log:
            if isinstance(env.event, HandsRevealed):
                revealed[env.hand_number] = env.event.hands
        for env in game.event_log:
            event = env.event
            if isinstance(event, BetPlaced) and event.seat in stored:
                cards = revealed.get(env.hand_number)
                if cards is None:
                    continue
                pct = hand_percentile(cards[event.seat], LanceType(event.lance), POLICY)
                rows.append(
                    {
                        "partidas_vistas": g,
                        "estimado": estimates[event.seat],
                        "farol": tier(pct) == 0,
                    }
                )
        tracker = ProfileTracker(POLICY)
        tracker.observe(game.event_log)
        for s in stored:
            stored[s] = stored[s] + tracker.profile(s)
    return rows


def experience_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets = [(0, 0, "0 partidas"), (1, 4, "1-4"), (5, 14, "5-14"), (15, 10**9, "15 o más")]
    out = {}
    for low, high, name in buckets:
        chosen = [r for r in rows if low <= r["partidas_vistas"] <= high]
        if not chosen:
            continue
        real = wilson(sum(r["farol"] for r in chosen), len(chosen))
        out[name] = {
            "envites": len(chosen),
            "farol_estimado": round(sum(r["estimado"] for r in chosen) / len(chosen), 4),
            "farol_real": real,
        }
    return out


# --- 3. ¿Sirve la experiencia para ganar? ----------------------------------------------


def profiles_game(args: tuple[str, int]) -> bool:
    """Bot medio (con o sin perfiles) contra faroleros, con el perfil de 20 partidas previas."""
    mode, seed = args
    side = seed % 2
    medium: Callable[[], Bot] = ProfiledMediumBot if mode == "con_perfiles" else MediumBot
    rivals = {SeatId(s) for s in ALL_SEATS if s % 2 != side}
    stored = {s: PlayerProfile() for s in rivals}
    warmup = [medium() if s % 2 == side else FaroleroBot() for s in ALL_SEATS]
    for g in range(20):  # 20 partidas para conocerles
        game = play_game(warmup, 500_000 + seed * 50 + g, dict(stored))
        tracker = ProfileTracker(POLICY)
        tracker.observe(game.event_log)
        for s in stored:
            stored[s] = stored[s] + tracker.profile(s)
    bots: list[Bot] = [medium() if s % 2 == side else FaroleroBot() for s in ALL_SEATS]
    game = play_game(bots, seed, dict(stored))
    return game.winner is not None and game.winner.value == side


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partidas-arbol", type=int, default=3000)
    parser.add_argument("--partidas", type=int, default=500)
    parser.add_argument("--series", type=int, default=24)
    parser.add_argument("--por-serie", type=int, default=30)
    parser.add_argument("--json", default=None)
    args = parser.parse_args()
    out: dict[str, Any] = {}
    with Pool() as pool:
        hands = [h for hs in pool.map(tree_game, range(args.partidas_arbol)) for h in hs]
        out["arbol"] = tree_report(hands)
        print("árbol:", out["arbol"]["todas"]["jugadas"], "jugadas")
        for rival in ("farolero", "sencillo"):
            jobs = [(s, args.por_serie, rival) for s in range(args.series)]
            rows = [r for rs in pool.map(experience_series, jobs) for r in rs]
            out[f"experiencia_{rival}"] = experience_report(rows)
            print(rival, json.dumps(out[f"experiencia_{rival}"], ensure_ascii=False))
        for mode in ("sin_perfiles", "con_perfiles"):
            wins = pool.map(profiles_game, [(mode, s) for s in range(args.partidas // 2)])
            out[f"contra_farolero_{mode}"] = wilson(sum(wins), len(wins))
            print(mode, out[f"contra_farolero_{mode}"])
    out["tramos"] = list(BIN_NAMES)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
