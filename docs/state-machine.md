# Máquina de estados

Implementación: `src/mus_engine/game/` — `phases.py` (fases), `flow.py` (transiciones
automáticas), `machine.py` (fases de decisión y validación), `invariants.py`.

## Tipos de fase

| Tipo | Significado | Dónde se define |
|---|---|---|
| **Decisión** | el motor espera la acción de uno o varios jugadores concretos | `machine.HANDLERS[fase]` (un `PhaseHandler`) |
| **Automática** | el motor la atraviesa sola, emitiendo eventos | `flow.AUTOMATIC_STEPS[fase]` |
| **Terminal** | `GAME_OVER`: no admite acciones | — |

Invariante: tras `start()` o `apply_action()` el estado está siempre en una fase de
decisión, en `NOT_STARTED` o en `GAME_OVER` (`Phase.is_resting`). Cada cambio de fase
emite el evento público `PhaseChanged`.

## Estado actual (fase 3)

```text
NOT_STARTED ──start()──► [CHOOSE_FIRST_DEALER]* ──► [DEAL]* ──► MUS_DECISION
                          C.III-1 / D-03             C.III-2
(*) automática
```

| Fase | Tipo | Quién actúa | Acciones | Eventos | Siguiente |
|---|---|---|---|---|---|
| `NOT_STARTED` | reposo | nadie (sólo `start()`) | — | `RngSeeded` (motor), `GameStarted` | `CHOOSE_FIRST_DEALER` |
| `CHOOSE_FIRST_DEALER` | automática | — | — | `FirstDealerDrawn` o `FirstDealerFixed` | `DEAL` |
| `DEAL` | automática | — | — | `HandStarted`, `DeckShuffled` (motor), `CardsDealt` (privado ×4) | `MUS_DECISION` |
| `MUS_DECISION` | decisión | *(fase 4)* | *(fase 4)* | — | — |
| `GAME_OVER` | terminal | nadie | ninguna (`GameFinishedError`) | — | — |

`MUS_DECISION` todavía no tiene manejador: cualquier acción se rechaza con
`InvalidStateError` y `get_legal_actions` devuelve un conjunto vacío. Es la frontera
de la fase 3 y está cubierta por un test explícito.

El diagrama objetivo completo está en `docs/design.md` §3.

## Cadena de validación de `apply_action`

1. Partida no iniciada → `GameNotStartedError`; terminada → `GameFinishedError`.
2. Jugador fuera de `0..3` (o no entero) → `InvalidPlayerError`.
3. Objeto que no es `Action` → `IllegalActionError`.
4. Fase sin acciones → `InvalidStateError`.
5. Jugador que no está en `actors(state)` → `NotYourTurnError`.
6. Acción fuera de `legal_actions(state, jugador)` → error específico del manejador
   (`InvalidStateError`, `InvalidBetError`, `InvalidDiscardError`…).
7. `handler.apply` → fases automáticas → invariantes → se confirma el nuevo estado y
   se registran los eventos.

Si cualquier paso falla, **el estado no cambia** (todo es inmutable y sólo se asigna
al final). `get_legal_actions` usa la misma función que el paso 6, de modo que una
acción es aceptada si y sólo si es legal.

## Cómo se añade una fase

1. Añadir el valor a `Phase` (y a `_AUTOMATIC` si es automática).
2. Automática: una función pura `GameState -> (GameState, Emission...)` en
   `flow.AUTOMATIC_STEPS`. Decisión: un `PhaseHandler` registrado en `machine.HANDLERS`.
3. Tests: transiciones, acciones ilegales, eventos y su visibilidad.
