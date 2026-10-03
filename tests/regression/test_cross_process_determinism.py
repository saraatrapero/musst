"""La misma semilla produce la misma partida en procesos distintos.

El hash de los enums (y por tanto de los naipes) cambia entre procesos según
``PYTHONHASHSEED``. Este test garantiza que ningún orden del motor depende de iterar
conjuntos o diccionarios indexados por naipes.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SCRIPT = """
import hashlib, sys
sys.path.insert(0, {root!r})
sys.path.insert(0, {src!r})
from mus_engine import Game, GameConfig
from tests.strategies import play_seeded, play_seeded_without_ordago
digests = []
for seed in (1, 2024):
    game = Game(seed=seed, config=GameConfig(games_to_win=2))
    game.start()
    play_seeded_without_ordago(game, seed + 1, 100000)
    digests.append(hashlib.sha256(repr(game.event_log).encode()).hexdigest())
game = Game(seed=77)
game.start()
play_seeded(game, 78, 400)
digests.append(hashlib.sha256(repr(game.event_log).encode()).hexdigest())
print(",".join(digests))
"""


def _run(hash_seed: str) -> str:
    env = {**os.environ, "PYTHONHASHSEED": hash_seed}
    code = SCRIPT.format(root=str(ROOT), src=str(ROOT / "src"))
    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def test_same_result_with_different_hash_seeds() -> None:
    outputs = {_run(seed) for seed in ("0", "1", "12345", "random")}
    assert len(outputs) == 1
