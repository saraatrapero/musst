# MUS.ST — `mus_engine`

Motor de Mus en Python, determinista y sin dependencias, que sigue el
**Reglamento de Juego de la Federación Española de Mus**
(`docs/reglamento/reglamento-fem.pdf`). Es el núcleo de la futura aplicación
MUS.ST: no incluye interfaz, usuarios ni IA.

> Principio: *si el motor acepta una acción, esa acción es legal según las reglas
> implementadas.*

## Estado

| Fase | Contenido | Estado |
|---|---|---|
| Diseño | arquitectura, máquina de estados, análisis del reglamento | ✅ |
| 1 | cartas, baraja, equivalencias de ocho reyes, RNG determinista, configuración, errores | ✅ |
| 2 | jugadores, parejas y orden de la mesa | pendiente |
| 3+ | estado, reparto, mus, lances, envites, órdago, tanteo, eventos, observaciones, replay | pendiente |

## Instalación

```bash
python -m pip install -e ".[dev]"     # Python >= 3.11
```

## Uso (fase 1)

```python
from mus_engine import Card, Deck, GameConfig, Rank, RankingPolicy, Rng, Suit

config = GameConfig()                       # 40 tantos, ocho reyes y ocho ases
deck, rng = Deck.standard().shuffled(Rng(seed=12345))   # misma semilla => mismo orden
hand, deck = deck.draw(4)

policy = RankingPolicy.from_config(config)
policy.effective_rank(Card(Rank.TRES, Suit.OROS))       # Rank.REY  (C.II-3)
policy.total_game_points(hand)                          # suma para juego/punto (D-01)
```

## Calidad

```bash
python -m pytest                 # tests (unit, rules, property, regression)
python -m pytest --cov=mus_engine
ruff check . && ruff format --check .
python -m mypy                   # modo estricto sobre src/ y tests/
```

## Documentación

- [`docs/design.md`](docs/design.md) — arquitectura, modelo de datos, máquina de estados, plan.
- [`docs/rules.md`](docs/rules.md) — trazabilidad con el reglamento y decisiones aprobadas.
- [`docs/api.md`](docs/api.md) — API pública.
- [`docs/testing.md`](docs/testing.md) — estrategia de tests y cómo añadir tests.
