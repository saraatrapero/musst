# MUS.ST — `mus_engine`

Motor de Mus en Python, determinista y sin dependencias, que sigue el
**Reglamento de Juego de la Federación Española de Mus**
(`docs/reglamento/reglamento-fem.pdf`). Es el núcleo de la aplicación MUS.ST, que
incluye además una web para jugar en el navegador (`mus_web`).

> Principio: *si el motor acepta una acción, esa acción es legal según las reglas
> implementadas.*

## Estado

Motor completo: todas las fases del plan están implementadas y probadas.

| Área | Contenido |
|---|---|
| Cartas y baraja | 40 naipes, ocho reyes y ocho ases, barajado reproducible |
| Mesa | jugadores, parejas, mano, postre, turnos, sorteo del primer reparto |
| Máquina de estados | fases de decisión y automáticas, validación única, invariantes |
| Mus | dar/cortar mus, descartes, reposición, rebarajado del descarte |
| Lances | grande, chica, pares, juego y punto con desempate por la mano |
| Envites | paso, envite, revoque, quiero, no quiero, negada, deje, órdago |
| Tanteo | orden reglamentario, final de juego a mitad de jugada, partida a N juegos |
| Información privada | observaciones por lista blanca, eventos con visibilidad |
| Replay | registro reconstruible desde los eventos, navegación por estados |
| Señas | señas oficiales de la FEM, siempre verdaderas; sólo las ve quien mira al que las hace (opcional) |
| Bots | API pública (`Bot.decide`), bots `aleatorio`, `sencillo` y `medio`, comprobación automática de bots nuevos |
| IA | conteo de cartas, probabilidad exacta de cada lance (330 clases de mano), valor de los tantos según el marcador (`docs/ai.md`) |
| Web | cuentas, salas para 1, 2 o 4 personas, mesa en el navegador con avatares, miradas, señas y frases (`docs/web.md`) |
| Torneo | todos contra todos, robusto ante bots que fallan, clasificación en Markdown y JSON |
| Calidad | 950 tests (unitarios, reglas, integración, seguridad, propiedades, regresión), cobertura 100 %, ruff y mypy estricto |

Desviación conocida respecto al reglamento: no se modelan las penalizaciones del
postre que acepta un órdago con la jugada mínima (D-24a, `docs/rules.md`).

## Instalación

```bash
python -m pip install -e ".[dev]"       # motor y bots (Python >= 3.11, sin dependencias)
python -m pip install -e ".[dev,web]"   # además, la web
```

## Uso

```python
from mus_engine import BetAction, CutMusAction, Game, GameConfig, GameReplay

game = Game(players=("Ana", "Bea", "Carlos", "Dani"), config=GameConfig(), seed=12345)
game.start()  # sorteo del primer reparto (C.III-1) y reparto (C.III-2)

(player,) = game.current_actors()  # la mano
obs = game.get_observation(player)  # sus naipes, el marcador, la fase... nada ajeno
game.apply_action(player, CutMusAction())
game.apply_action(player, BetAction(2))  # envido en grande
# ... cada jugador, en su turno, pide acciones; el motor valida, aplica y puntúa.

game.is_finished, game.winner, game.get_state().score
replay = GameReplay.from_events(game.event_log)
```

Cartas y baraja:

```python
from mus_engine import Card, Deck, GameConfig, Rank, RankingPolicy, Rng, Suit

config = GameConfig()  # 40 tantos, ocho reyes y ocho ases
deck, rng = Deck.standard().shuffled(Rng(seed=12345))  # misma semilla => mismo orden
hand, deck = deck.draw(4)

policy = RankingPolicy.from_config(config)
policy.effective_rank(Card(Rank.TRES, Suit.OROS))  # Rank.REY  (C.II-3)
policy.total_game_points(hand)  # suma para juego/punto (D-01)
```

## Calidad

```bash
python -m pytest                 # tests (unit, rules, property, regression)
python -m pytest --cov=mus_engine
ruff check . && ruff format --check .
python -m mypy                   # modo estricto sobre src/ y tests/
```

## Bots y torneo

```bash
python -m mus_engine.arena --games 20 --seed 1   # torneo entre todos los bots registrados
```

Para escribir un bot, ver [`docs/bots.md`](docs/bots.md).

## Web

```bash
python -m mus_web     # http://127.0.0.1:8000 (SQLite en ./musst.db)
```

Registro, elección de avatar, salas con código de invitación y partidas en tiempo real.
El servidor ejecuta el motor y envía a cada jugador sólo su observación. Detalles,
seguridad en [`docs/web.md`](docs/web.md); publicarla en Internet, en
[`docs/deploy.md`](docs/deploy.md).

## Integración continua

`.github/workflows/ci.yml` ejecuta en cada push a `main` y en cada pull request, con
Python 3.11, 3.12 y 3.13 (con las dependencias de la web): `ruff check`, `ruff format --check`, `mypy --strict` y la
batería de tests exigiendo cobertura del 100 %. La versión de `ruff` está fijada en
`pyproject.toml` para que el formato no cambie entre entornos.

## Documentación

- [`docs/architecture.md`](docs/architecture.md) — arquitectura final, módulos, flujo de una acción.
- [`docs/design.md`](docs/design.md) — diseño inicial aprobado y plan por fases.
- [`docs/ai-design.md`](docs/ai-design.md) — diseño de la IA multiagente y plan por fases.
- [`docs/ai.md`](docs/ai.md) — agentes ya implementados, bot medio y resultados.
- [`docs/rules.md`](docs/rules.md) — trazabilidad con el reglamento y decisiones aprobadas.
- [`docs/state-machine.md`](docs/state-machine.md) — fases, validación y cómo añadir fases.
- [`docs/scoring.md`](docs/scoring.md) — cuándo y cuánto se anota.
- [`docs/api.md`](docs/api.md) — API pública.
- [`docs/bots.md`](docs/bots.md) — tutorial: crear, probar y enviar un bot; torneo.
- [`docs/web.md`](docs/web.md) — la web: arquitectura, protocolo, seguridad y datos.
- [`docs/deploy.md`](docs/deploy.md) — publicar la web en Internet (Render), paso a paso.
- [`docs/testing.md`](docs/testing.md) — estrategia de tests y cómo añadir tests.

## Licencia

[MIT](LICENSE).
