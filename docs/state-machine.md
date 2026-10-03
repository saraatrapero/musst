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

## Estado actual (fase 4)

```text
NOT_STARTED ──start()──► [CHOOSE_FIRST_DEALER]* ──► [DEAL]* ──► MUS_DECISION ◄──────────┐
                          C.III-1 / D-03             C.III-2        │                      │
                                                                    ├─ 4 × mus ─► DISCARD ─┤
                                                                    │            C.III-11  │
                                                                    │                [REDEAL]*
                                                                    │           C.III-2, C.III-15
                                                                    └─ corte ─► LANCE (grande)
(*) automática
```

| Fase | Tipo | Quién actúa | Acciones legales | Eventos | Siguiente |
|---|---|---|---|---|---|
| `NOT_STARTED` | reposo | nadie (sólo `start()`) | — | `RngSeeded` (motor), `GameStarted` | `CHOOSE_FIRST_DEALER` |
| `CHOOSE_FIRST_DEALER` | automática | — | — | `FirstDealerDrawn` o `FirstDealerFixed` | `DEAL` |
| `DEAL` | automática | — | — | `HandStarted`, `DeckShuffled` (motor), `CardsDealt` (privado ×4) | `MUS_DECISION` |
| `MUS_DECISION` | decisión | uno a uno: mano, 2º, 3º, 4º (C.IV-4) | `MusAction`, `CutMusAction` | `MusRequested` / `MusCut` | 4 × mus → `DISCARD`; corte → `LANCE` (grande) |
| `DISCARD` | decisión | uno a uno: postre, 3º, 2º, mano (C.III-11) | `DiscardAction` de 1 a 4 naipes propios (D-13) | `DiscardDeclared` (público: sólo el número) | tras el mano → `REDEAL` |
| `REDEAL` | automática | — | — | `DiscardPileReshuffled` + `DeckShuffled` (motor) si se acaba el mazo; `CardsDiscarded` (privado ×4) | `MUS_DECISION` (nueva ronda, vuelve a hablar la mano) |
| `LANCE` | decisión | *(fases siguientes)* | — | — | — |
| `GAME_OVER` | terminal | nadie | ninguna (`GameFinishedError`) | — | — |

Detalles del mus:

- El primer "no hay mus" de cualquier jugador, en su turno, corta el mus (D-04). Para
  la mano, cortar equivale a "paso" (Voc. "Paso").
- Los descartes se declaran en orden y quedan **pendientes**; al declararse el último
  (el mano), `REDEAL` los pasa todos al montón y sirve a cada jugador de una vez, en el
  mismo orden (C.III-2, D-06).
- Si el mazo no alcanza, se sirve lo que queda y después se baraja **todo** el
  descarte, incluidos los naipes tirados en esa ronda, para seguir sirviendo
  (C.III-15, D-07). Un jugador puede, por tanto, recibir un naipe que acaba de tirar.
- No hay límite de rondas de mus (D-14).

`LANCE` todavía no tiene manejador: es la frontera de la fase 4 (test explícito).

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
