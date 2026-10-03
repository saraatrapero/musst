# Arquitectura

> El motor sabe jugar al Mus. La interfaz sólo muestra el estado. Jugadores, bots e IA
> sólo solicitan acciones. El motor tiene la última palabra.

## Flujo de una acción

```text
JUGADOR / BOT / IA ──Action (inmutable, tipada)──► Game.apply_action(player, action)
                                                    │
     1. ¿partida empezada / terminada?               │  GameNotStartedError / GameFinishedError
     2. ¿jugador 0..3?                               │  InvalidPlayerError
     3. machine.validate: ¿Action? ¿fase con acciones? ¿su turno? ¿legal?
                                                    │  IllegalActionError y subclases
     4. handler.apply  (función pura)               │  → (GameState', eventos)
     5. flow.run_automatic: fases automáticas       │  reparto, lances, tanteo…
     6. invariantes                                 │  InvariantViolationError (bug)
     7. commit: estado nuevo + eventos numerados    ▼
```

Si cualquier paso falla el estado no cambia: todo es inmutable y sólo se asigna al
final. `get_legal_actions` usa la misma función que el paso 3, así que **una acción es
aceptada si y sólo si es legal** (propiedad verificada en
`tests/property/test_double_validation.py`).

## Módulos

| Paquete | Responsabilidad | Depende de |
|---|---|---|
| `cards/` | `Card`, `Rank`, `Suit`, `Deck` (40 naipes), `RankingPolicy` (ocho reyes, valores de juego) | `config`, `rng` |
| `rng.py` | generador determinista (SHA-256 en modo contador), estable entre versiones de Python | — |
| `config.py` | `GameConfig`: todos los valores de reglas, validados, con su origen | — |
| `players/` | `Player`, `Team`, `Table`; orden de mesa puro (mano, postre, turnos, sorteo) | `cards` |
| `rules/` | reglas puras: reparto, mus y descartes, evaluadores de grande/chica/pares/juego/punto, participación | `cards`, `players` |
| `betting/` | `BetState` y transiciones de envites (paso, envite, revoque, quiero, no quiero, órdago) | `rules` |
| `scoring/` | `GameScore`, `LanceOutcome`, `ScoreEntry`, `ScoringEngine` | `rules` |
| `events/` | eventos y su visibilidad (`PUBLIC`, `PRIVATE`, `ENGINE`) | `cards`, `players` |
| `game/` | estado, fases, acciones, validación, transiciones, invariantes, observaciones, `Game`, `RulesEngine`, `GameRecord` | todo lo anterior |
| `replay/` | `GameReplay` | `game` |

Las reglas (`rules/`, `betting/`, `scoring/`) no conocen la partida: son funciones puras
sobre naipes y valores, testeables por separado.

## Estado

`GameState` (inmutable) es el único estado; `Game` guarda la referencia al actual, el
registro de eventos y las acciones aceptadas. Nada más es mutable.

```text
GameState
├── config: GameConfig          ├── score: GameScore (tantos, juegos)
├── table: Table                ├── winner: TeamId | None
├── rng: Rng (semilla, flujo)   ├── pending_dealer
├── phase: Phase                └── hand: HandState | None
                                    ├── number, dealer, mano
                                    ├── hands, stock: Deck, discard_pile
                                    ├── mus: MusState (ronda, turno, quién pidió, corte, descartes)
                                    ├── lance, bet: BetState
                                    ├── outcomes: LanceOutcome…
                                    ├── pares_holders, juego_holders
                                    └── revealed
```

## Máquina de estados

Fases de decisión (`MUS_DECISION`, `DISCARD`, `LANCE`) con un `PhaseHandler` cada una
(`actors`, `legal_actions`, `explain_illegal`, `apply`), y fases automáticas
(`CHOOSE_FIRST_DEALER`, `DEAL`, `REDEAL`, `LANCE_START`, `ORDAGO_SHOWDOWN`,
`HAND_SCORING`, `NEW_HAND`) como funciones puras. Detalle en `docs/state-machine.md`.

## Información privada

- `GameState` contiene secretos y sólo debe usarlo el motor (o herramientas de confianza).
- `Game.get_observation(player)` construye una `Observation` por lista blanca.
- Los eventos llevan visibilidad explícita; `get_events(viewer)` filtra.
- `Game.get_hand(player, viewer)` lanza `PrivateInformationError` si no corresponde.
- Tests: `tests/security/` y propiedades sobre partidas aleatorias.

## Determinismo y replay

Misma semilla + mismas acciones ⇒ mismos estados y eventos, en cualquier proceso y
versión de Python (`tests/regression/`). `GameRecord` (jugadores, config, semilla,
acciones) se obtiene de `Game.record` o **sólo a partir del registro completo de
eventos** (`GameRecord.from_events`). `GameReplay` re-ejecuta el registro y navega por
los estados (`next`, `previous`, `jump_to`).

## Diferencias con el diseño inicial (`docs/design.md`)

- `Phase.LANCE` único con `HandState.lance`, en lugar de una fase por lance.
- Las declaraciones de pares y juego se hacen dentro de `LANCE_START`.
- `CHECK_GAME_END` no es una fase: lo resuelve `lance_flow.award` en el momento en que
  una pareja alcanza el tanteo (puede ser a mitad de jugada, D-22).
- `Game` representa la partida completa (N juegos, `games_to_win`).
- `GameRecord` vive en `game/` para evitar un ciclo de importación con `replay/`.
- Se añadió `RulesEngine`, fachada pura para bots y simulaciones.

## Desviaciones conocidas respecto al reglamento

- D-24a: no se modelan las penalizaciones del postre que acepta un órdago con la
  jugada mínima (C.VI-9…12, C.VI-24). Ver `docs/rules.md` §4.
- No se modelan errores físicos ni de comunicación (mus visto, naipes de más, señas,
  boquilla, enseñar naipes): son imposibles por construcción o ajenos al motor
  (`docs/rules.md` §3).
