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

## Diagrama completo

```text
NOT_STARTED ──start()──► [CHOOSE_FIRST_DEALER]* ──► [DEAL]* ──► MUS_DECISION ◄──────────┐
                          C.III-1 / D-03             C.III-2  ▲     │                      │
                                                              │     ├─ 4 × mus ─► DISCARD ─┤
                                                              │     │            C.III-11  │
                                                              │     │                [REDEAL]*
                                                              │     └─ corte
                                                              │          ▼
                                     ┌──────────────► [LANCE_START]* (grande, chica, pares, juego|punto)
                                     │                 │  declaraciones de pares/juego (públicas)
                                     │                 ├─ sin envites (una pareja / nadie) ──┐
                                     │                 ▼                                     │
                                     │               LANCE  (paso, envite, revoque,          │
                                     │                 │     quiero, no quiero, órdago)       │
                                     │   no quiero:    ├─ cerrado ───────────────────────────┤
                                     │   anota en el   │                                     │
                                     │   acto (puede   ├─ órdago querido ─► [ORDAGO_SHOWDOWN]* ──► fin de juego
                                     │   acabar juego) │                                     │
                                     └── siguiente ◄───┘◄────────────────────────────────────┘
                                         lance
                                           │ tras juego/punto
                                           ▼
                                    [HAND_SCORING]* ──► fin de juego ──┬─► GAME_OVER (partida ganada)
                                           │                           └─► [NEW_HAND]*
                                           └─► [NEW_HAND]* ──► [DEAL]* (reparte el que fue mano, D-15)
(*) automática
```

| Fase | Tipo | Quién actúa | Acciones legales | Eventos principales |
|---|---|---|---|---|
| `NOT_STARTED` | reposo | nadie (sólo `start()`) | — | `RngSeeded` (motor), `GameStarted` |
| `CHOOSE_FIRST_DEALER` | automática | — | — | `FirstDealerDrawn` / `FirstDealerFixed` |
| `DEAL` | automática | — | — | `HandStarted`, `DeckShuffled` (motor), `CardsDealt` (privado) |
| `MUS_DECISION` | decisión | mano, 2º, 3º, 4º (C.IV-4) | `MusAction`, `CutMusAction` | `MusRequested`, `MusCut` |
| `DISCARD` | decisión | postre → mano (C.III-11) | `DiscardAction` (1–4 naipes propios) | `DiscardDeclared` (sólo el número) |
| `REDEAL` | automática | — | — | `CardsDiscarded` (privado), `DiscardPileReshuffled` |
| `LANCE_START` | automática | — | — | `ParesDeclared`, `JuegoDeclared`, `LanceStarted`, `LanceUncontested`, `LanceNotPlayed` |
| `LANCE` abierto | decisión | participantes en orden desde la mano | `PassAction`, `BetAction(n ≥ 2)`, `OrdagoAction` | `Passed`, `BetPlaced`, `OrdagoDeclared` |
| `LANCE` con envite | decisión | rivales del que envidó, en orden | `AcceptAction`, `RejectAction`, `RaiseAction(n ≥ 2)`, `OrdagoAction` (sin revoque ni órdago si ya hay órdago) | `BetAccepted`, `BetRejected`, `BetRaised`, `OrdagoAccepted`, `LanceClosed`, `PointsAwarded` |
| `ORDAGO_SHOWDOWN` | automática | — | — | `HandsRevealed`, `LanceResolved`, `PointsAwarded`, `GameWon` |
| `HAND_SCORING` | automática | — | — | `HandsRevealed`, `LanceResolved`, `PointsAwarded`, `GameWon` |
| `NEW_HAND` | automática | — | — | — |
| `GAME_OVER` | terminal | nadie | ninguna (`GameFinishedError`) | `GameFinished` |

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
