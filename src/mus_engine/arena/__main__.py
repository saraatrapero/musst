"""Torneo desde la línea de comandos.

    python -m mus_engine.arena --games 10 --seed 1 --out resultados/

Escribe ``leaderboard.md`` y ``leaderboard.json`` en ``--out`` y muestra la tabla.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mus_engine.arena.seats import DEFAULT_TIMEOUT
from mus_engine.arena.tournament import run_tournament
from mus_engine.bots.registry import all_bots
from mus_engine.config import GameConfig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mus_engine.arena", description=__doc__)
    parser.add_argument("--games", type=int, default=10, help="partidas por pareja de bots")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--signals", action="store_true", help="activar señas y miradas")
    parser.add_argument(
        "--in-process", action="store_true", help="sin aislar procesos (más rápido)"
    )
    parser.add_argument(
        "--timeout", type=float, default=DEFAULT_TIMEOUT, help="segundos por decisión"
    )
    parser.add_argument("--out", type=Path, default=None, help="carpeta para la clasificación")
    args = parser.parse_args(argv)
    result = run_tournament(
        all_bots(),
        games_per_pair=args.games,
        seed=args.seed,
        config=GameConfig(signals_enabled=args.signals),
        isolated=not args.in_process,
        timeout=args.timeout,
    )
    table = result.to_markdown()
    print(table)
    if args.out is not None:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "leaderboard.md").write_text(table, encoding="utf-8")
        (args.out / "leaderboard.json").write_text(result.to_json(), encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
