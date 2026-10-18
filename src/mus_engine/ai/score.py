"""ScoreAgent (``docs/ai-design.md`` §3.4): cuánto vale cada tanto según el marcador.

Lo importante no son los tantos sino la **probabilidad de ganar la partida**. Se calcula
una tabla ``W(mis tantos, sus tantos)`` con un modelo de manos independientes: en cada
mano las parejas suman tantos según :data:`HAND_POINTS`, medida en 600 partidas entre
bots ``sencillo`` (unos 3,5 tantos por pareja y mano). Si las dos parejas llegan al
objetivo en la misma mano, se cuenta como medio juego para cada una.

De la tabla sale sola la agresividad que pide el diseño: con el rival a punto de ganar
cualquier tanto suyo es casi la derrota, y arriesgar sale a cuenta; con la partida
encarrilada, conviene no regalar nada.

>>> agent = ScoreAgent(target=40)
>>> agent.win(0, 0)
0.5
>>> agent.win(36, 10) > 0.9 > 0.1 > agent.win(10, 36)
True
"""

from __future__ import annotations

from functools import cache

# Tantos (pareja propia, pareja rival) en una mano: simétrica; se normaliza al cargar.
HAND_POINTS: dict[tuple[int, int], float] = {
    (1, 4): 0.054,
    (5, 1): 0.049,
    (3, 2): 0.0303,
    (3, 3): 0.029,
    (2, 2): 0.0285,
    (2, 4): 0.0283,
    (1, 6): 0.0275,
    (1, 3): 0.0233,
    (7, 1): 0.023,
    (0, 6): 0.0221,
    (1, 8): 0.0178,
    (4, 3): 0.0135,
    (1, 9): 0.0129,
    (0, 5): 0.0122,
    (3, 6): 0.0118,
    (2, 6): 0.0112,
    (0, 8): 0.0106,
    (2, 5): 0.0103,
    (0, 7): 0.0092,
    (5, 3): 0.0092,
    (4, 4): 0.0086,
    (4, 5): 0.0078,
    (0, 9): 0.0065,
    (7, 3): 0.0057,
    (4, 6): 0.0053,
    (0, 4): 0.0053,
    (0, 10): 0.005,
    (1, 11): 0.0049,
    (5, 6): 0.0046,
    (5, 5): 0.0046,
    (2, 7): 0.0045,
    (1, 10): 0.0043,
}


def _symmetric() -> tuple[tuple[int, int, float], ...]:
    both: dict[tuple[int, int], float] = {}
    for (a, b), p in HAND_POINTS.items():
        both[(a, b)] = both.get((a, b), 0.0) + p
        both[(b, a)] = both.get((b, a), 0.0) + p
    total = sum(both.values())
    return tuple((a, b, p / total) for (a, b), p in sorted(both.items()))


@cache
def _table(target: int) -> tuple[tuple[float, ...], ...]:
    """``table[a][b]`` = P(ganar | a, b) para 0 <= a, b < target."""
    outcomes = _symmetric()
    table = [[0.0] * target for _ in range(target)]
    # Cada mano suma al menos un tanto: se rellena de más tantos a menos.
    for total in range(2 * target - 2, -1, -1):
        for a in range(max(0, total - target + 1), min(target, total + 1)):
            b = total - a
            value = 0.0
            for x, y, p in outcomes:
                na, nb = a + x, b + y
                if na >= target and nb >= target:
                    value += p * 0.5
                elif na >= target:
                    value += p
                elif nb < target:
                    value += p * table[na][nb]
            table[a][b] = value
    return tuple(tuple(row) for row in table)


def win_probability(mine: int, theirs: int, target: int = 40) -> float:
    """P(ganar el juego) con ``mine`` tantos frente a ``theirs``, a ``target``."""
    if mine >= target and theirs >= target:
        return 0.5
    if mine >= target:
        return 1.0
    if theirs >= target:
        return 0.0
    return _table(target)[max(0, mine)][max(0, theirs)]


class ScoreAgent:
    """Valor de los tantos en probabilidad de ganar, desde el punto de vista de una pareja."""

    def __init__(self, target: int) -> None:
        self.target = target

    def win(self, mine: int, theirs: int) -> float:
        return round(win_probability(mine, theirs, self.target), 12)

    def outcome(self, mine: int, theirs: int, gained: int, lost: int) -> float:
        """P(ganar) si mi pareja suma ``gained`` y la rival ``lost``."""
        return win_probability(mine + gained, theirs + lost, self.target)
