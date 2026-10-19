"""Agentes de la IA (``docs/ai-design.md`` §3).

Cada agente es una pieza pequeña que **sólo lee la observación** del jugador (y, más
adelante, su memoria). Nunca mira el estado completo de la partida.

- :mod:`.classes`: las 330 clases de mano del Mus y su fuerza en cada lance.
- :mod:`.counting`: :class:`CardCounter`, qué cartas pueden tener los demás.
- :mod:`.equity`: probabilidad exacta de que mi pareja gane cada lance.
- :mod:`.score`: :class:`ScoreAgent`, probabilidad de ganar la partida según el tanteo.
"""

from mus_engine.ai.classes import HandClass, hand_class
from mus_engine.ai.counting import CardCounter, Knowledge
from mus_engine.ai.equity import lance_equity, team_equity
from mus_engine.ai.score import ScoreAgent, win_probability

__all__ = [
    "CardCounter",
    "HandClass",
    "Knowledge",
    "ScoreAgent",
    "hand_class",
    "lance_equity",
    "team_equity",
    "win_probability",
]
