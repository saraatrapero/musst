"""Requisito 2.2: todos los bots registrados pasan la comprobación automática.

Un bot nuevo en ``src/mus_bots/`` se prueba aquí sin tocar este archivo.
"""

import pytest

from mus_engine.bots import all_bots
from mus_engine.bots.conformance import check_bot

BOTS = all_bots()


@pytest.mark.parametrize("name", sorted(BOTS))
def test_registered_bot_is_conformant(name: str) -> None:
    assert check_bot(BOTS[name], games=4) == []


@pytest.mark.parametrize("name", sorted(BOTS))
def test_registered_bot_is_conformant_in_isolation(name: str) -> None:
    assert check_bot(BOTS[name], games=1, isolated=True) == []
