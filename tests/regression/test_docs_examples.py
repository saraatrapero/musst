"""Los ejemplos de código de README.md y docs/api.md se ejecutan sin errores.

Regresión: el primer ejemplo de inicio rápido elegía siempre la primera acción legal
(pedir mus) y, como el reglamento no limita las rondas de mus (D-14), no terminaba.
"""

import re
import signal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _first_game_example(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"```python\n(from mus_engine import [^\n]*Game[^\n]*\n.*?)```", text, re.S)
    assert match, f"No hay ejemplo de partida en {path}"
    return match.group(1).replace("# ... cada jugador", "pass  # ... cada jugador")


@pytest.mark.parametrize("name", ["README.md", "docs/api.md"])
def test_quick_start_runs(name: str) -> None:
    def timeout(signum: int, frame: object) -> None:
        raise TimeoutError(f"El ejemplo de {name} no termina")

    previous = signal.signal(signal.SIGALRM, timeout)
    signal.alarm(30)
    try:
        exec(compile(_first_game_example(ROOT / name), name, "exec"), {})
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def test_bot_tutorial_example_is_conformant() -> None:
    from mus_engine.bots.conformance import check_bot

    text = (ROOT / "docs" / "bots.md").read_text(encoding="utf-8")
    match = re.search(r"Crea `src/mus_bots/mi_equipo.py`:\n\n```python\n(.*?)```", text, re.S)
    assert match, "No se encuentra el bot del tutorial"
    namespace: dict[str, object] = {}
    exec(compile(match.group(1), "docs/bots.md", "exec"), namespace)
    assert check_bot(namespace["Prudente"], games=2) == []  # type: ignore[arg-type]
