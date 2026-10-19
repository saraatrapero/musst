# Crear un bot

Tutorial de principio a fin para añadir un bot a MUS.ST sin tocar el código del juego
(requisitos 2.1–2.3 de la práctica).

## 1. Qué es un bot

Un bot controla **un asiento**. En cada decisión recibe la `Observation` de su asiento
(sus cartas, el marcador, los envites, las declaraciones, las señas que ha visto…) y
devuelve una `Action`. **Nunca** recibe el estado completo de la partida: no puede ver
las cartas de nadie más.

Una pareja son dos instancias del mismo bot. En el torneo oficial cada asiento corre en
un proceso distinto, así que dos compañeros sólo pueden comunicarse con **señas**.

## 2. Tu primer bot

Crea `src/mus_bots/mi_equipo.py`:

```python
from mus_engine import Action, CutMusAction, PassAction
from mus_engine.bots import Bot
from mus_engine.game.observations import Observation


class Prudente(Bot):
    name = "prudente"  # único en el repositorio
    description = "Corta siempre el mus y nunca envida."

    def decide(self, observation: Observation) -> Action:
        legal = observation.legal_actions
        for preferred in (CutMusAction(), PassAction()):
            if legal.contains(preferred):
                return preferred
        return next(iter(legal))  # cualquier acción legal
```

Eso es todo: el registro lo encuentra solo (`mus_engine.bots.all_bots()`).

## 3. Lo que tienes en la observación

| Campo | Contenido |
|---|---|
| `seat`, `phase`, `lance` | tu asiento, la fase y el lance en curso |
| `my_hand` | tus cuatro cartas |
| `mano`, `dealer`, `to_act`, `is_my_turn` | posiciones y turno |
| `score`, `target_score`, `games_to_win` | marcador |
| `legal_actions` | acciones legales: `actions` y los rangos `bet` / `raise_` |
| `bet` | el envite en curso (importes, quién envidó, si es órdago…) |
| `mus_requested`, `mus_cut_by`, `discard_counts` | lo que ha pasado en el mus |
| `pares_holders`, `juego_holders` | declaraciones públicas de pares y juego |
| `outcomes` | cómo se cerraron los lances de la jugada |
| `revealed_hands` | las cuatro manos, cuando se enseñan (final de jugada u órdago) |
| `gaze`, `signals_seen`, `my_signals` | miradas y señas (si están activadas) |
| `events` | historial de eventos que puedes ver |

Para envidar una cantidad concreta: `BetAction(n)` con `n` dentro de
`legal_actions.bet`; para revocar, `RaiseAction(n)` dentro de `legal_actions.raise_`.

## 4. Métodos opcionales

```python
class MiBot(Bot):
    name = "mi-bot"

    def on_game_start(self, context):  # asiento, configuración y semilla
        super().on_game_start(context)

    def signal(self, observation):  # señas: se pregunta en cada paso
        return None  # o SignalAction(Signal.DUPLES) si es verdadera y legal

    def on_game_end(self, observation):  # observación final: aprende aquí
        ...
```

Usa `context.seed` si tu bot necesita azar, para que sus partidas sean reproducibles.

## 5. Comprueba tu bot

```python
from mus_engine.bots.conformance import check_bot
from mus_bots.mi_equipo import Prudente

assert check_bot(Prudente) == []  # lista de problemas; vacía = apto
```

`check_bot` juega partidas en las dos parejas, con y sin señas, contra el bot aleatorio.
Detecta acciones ilegales, excepciones, tiempo excesivo y resultados que no son acciones.
Además, `python -m pytest tests/bots` aplica esta comprobación a **todos** los bots
registrados, también al tuyo, sin tocar ningún test.

## 6. Juega un torneo en local

```bash
python -m mus_engine.arena --games 20 --seed 1             # todos los bots registrados
python -m mus_engine.arena --games 20 --signals --out out/  # con señas; guarda la clasificación
```

Reglas del torneo:

- todos contra todos, alternando las posiciones;
- cada decisión tiene un tiempo límite (`--timeout`, 2 s por defecto);
- si un bot lanza una excepción, tarda demasiado, devuelve algo que no es una acción o
  hace una jugada ilegal, **su pareja pierde esa partida**; el torneo sigue;
- clasificación por porcentaje de victorias y Elo.

## 7. Envía tu bot

1. Haz un fork del repositorio y crea una rama.
2. Añade tu módulo en `src/mus_bots/`.
3. Ejecuta `python -m pytest tests/bots`.
4. Abre un pull request. La CI ejecuta las mismas comprobaciones.

## Referencia

| Elemento | Dónde |
|---|---|
| `Bot`, `BotContext` | `mus_engine.bots.base` |
| Acciones | `mus_engine` (`MusAction`, `CutMusAction`, `DiscardAction`, `PassAction`, `BetAction`, `RaiseAction`, `AcceptAction`, `RejectAction`, `OrdagoAction`) y `mus_engine.game.actions.SignalAction` |
| Señas | `mus_engine.rules.signals.Signal` |
| Observación | `mus_engine.game.observations.Observation` (ver también `docs/api.md`) |
| Comprobación | `mus_engine.bots.conformance.check_bot` |
| Torneo | `mus_engine.arena.run_tournament`, `python -m mus_engine.arena` |
| Bots incluidos | `aleatorio` (azar entre acciones legales), `sencillo` (heurísticas de fuerza de mano), `medio` (conteo, probabilidad exacta por lance y marcador; `docs/ai.md`) |
