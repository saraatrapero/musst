"""¿Crece la ventaja del bot con cada persona? Experimento por parejas de partidas.

    PYTHONPATH=src python scripts/aprendizaje.py --json docs/aprendizaje.json

El bot medio juega series de partidas contra los mismos dos rivales (un estilo de
jugador) y guarda su perfil de una partida a la siguiente, como hace la web con cada
usuario. Para medir lo que aporta lo aprendido, cada partida se juega **dos veces con
la misma baraja**: una con el perfil acumulado y otra sin él. La diferencia, partida a
partida, es lo que gana el bot por conocer a ese jugador.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Callable
from multiprocessing import Pool
from pathlib import Path
from typing import Any

from mus_engine.ai.profiles import PlayerProfile, ProfileTracker
from mus_engine.bots.base import Bot, BotContext
from mus_engine.bots.medium_bot import MediumBot
from mus_engine.bots.simple_bot import SimpleBot
from mus_engine.cards.ranking import RankingPolicy
from mus_engine.config import GameConfig
from mus_engine.game.game import Game
from mus_engine.players.seating import ALL_SEATS, SeatId

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.bots.styles import FaroleroBot, MiedosoBot  # estilos de jugador de prueba

POLICY = RankingPolicy()
CONFIG = GameConfig(negadas_at_end=True)
STYLES: dict[str, Callable[[], Bot]] = {
    "farolero": FaroleroBot,
    "miedoso": MiedosoBot,
    "sencillo": SimpleBot,
}
BUCKETS = (
    (0, 0, "1.ª partida"),
    (1, 4, "2.ª a 5.ª"),
    (5, 14, "6.ª a 15.ª"),
    (15, 10**9, "16.ª o más"),
)


class ProfiledMediumBot(MediumBot):
    use_profiles = True


def play(
    medium: Callable[[], Bot],
    rival: Callable[[], Bot],
    seed: int,
    profiles: dict[SeatId, PlayerProfile],
) -> Game:
    bots = [medium() if s % 2 == 0 else rival() for s in ALL_SEATS]
    for seat, bot in enumerate(bots):
        bot.on_game_start(BotContext(SeatId(seat), CONFIG, seed + seat, profiles))
    game = Game(config=CONFIG, seed=seed)
    game.start()
    while not game.is_finished:
        (seat,) = game.current_actors()
        game.apply_action(seat, bots[seat].decide(game.get_observation(seat)))
    return game


def margin(game: Game) -> int:
    ours, theirs = game.get_state().score.tantos
    return ours - theirs


def series(args: tuple[str, int, int]) -> list[dict[str, Any]]:
    style, number, games = args
    rival = STYLES[style]
    stored = {SeatId(1): PlayerProfile(), SeatId(3): PlayerProfile()}
    rows = []
    for k in range(games):
        seed = 1_000_000 * (number + 1) + k
        learned = play(ProfiledMediumBot, rival, seed, dict(stored))
        fresh = play(MediumBot, rival, seed, {})
        rows.append(
            {
                "k": k,
                "gana_con": learned.winner is not None and learned.winner.value == 0,
                "gana_sin": fresh.winner is not None and fresh.winner.value == 0,
                "dif_tantos": margin(learned) - margin(fresh),
            }
        )
        tracker = ProfileTracker(POLICY)
        tracker.observe(learned.event_log)
        for s in stored:
            stored[s] = stored[s] + tracker.profile(s)
    return rows


def mean_ci(values: list[float]) -> dict[str, float]:
    n = len(values)
    mean = sum(values) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1)) if n > 1 else 0.0
    half = 1.96 * sd / math.sqrt(n) if n > 1 else 0.0
    return {
        "media": round(mean, 3),
        "low": round(mean - half, 3),
        "high": round(mean + half, 3),
        "n": n,
    }


def report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for low, high, name in BUCKETS:
        chosen = [r for r in rows if low <= r["k"] <= high]
        if not chosen:
            continue
        out[name] = {
            "gana_con_perfil": mean_ci([float(r["gana_con"]) for r in chosen]),
            "gana_sin_perfil": mean_ci([float(r["gana_sin"]) for r in chosen]),
            "ventaja_partidas": mean_ci(
                [float(r["gana_con"]) - float(r["gana_sin"]) for r in chosen]
            ),
            "ventaja_tantos": mean_ci([float(r["dif_tantos"]) for r in chosen]),
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--series", type=int, default=24)
    parser.add_argument("--partidas", type=int, default=30)
    parser.add_argument("--estilos", default="farolero,miedoso")
    parser.add_argument("--json", default=None)
    args = parser.parse_args()
    out: dict[str, Any] = {}
    with Pool() as pool:
        for style in args.estilos.split(","):
            jobs = [(style, s, args.partidas) for s in range(args.series)]
            rows = [r for rs in pool.map(series, jobs) for r in rs]
            out[style] = report(rows)
            print(style, json.dumps(out[style], ensure_ascii=False))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
