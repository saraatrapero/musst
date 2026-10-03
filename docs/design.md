# Diseño del motor de Mus — `mus_engine`

> Estado: **APROBADO** (2026-10-03). Implementación por fases.
> Las referencias `[D-xx]` remiten a decisiones aprobadas en `docs/rules.md` §4.

---

## 0. Fuente de verdad

Reglamento de Juego de la FEM: `docs/reglamento/reglamento-fem.pdf`.
El análisis artículo por artículo está en **`docs/rules.md`**:
reglas confirmadas (`R-xx`, con cita), temas fuera de alcance y decisiones
adoptadas (`D-xx`). Las referencias `[D-xx]` de este documento remiten allí.

Hallazgo principal: el reglamento FEM es de **competición y conducta** y no define
varios elementos básicos (valores en tantos, valor de las cartas para juego, orden
completo del juego, desempate por la mano, rotación del reparto, límites del
descarte). Esos puntos se resolvieron como decisiones aprobadas y están aislados en
`GameConfig`/`RankingPolicy`.

---

## 1. Arquitectura propuesta

```text
 PLAYER / BOT / UI / IA            (fuera del motor: sólo producen Action)
        │  Action (objeto tipado, inmutable)
        ▼
 ┌──────────────────────────── Game (fachada pública) ─────────────────────────┐
 │  apply_action(pid, action)                                                   │
 │     1. guardas: partida terminada, jugador válido            → errores       │
 │     2. Validator: ¿turno?, ¿fase?, ¿legal según reglas?      → errores       │
 │     3. Transition (función pura): (State, Action) → (State', [Event])        │
 │     4. Auto-avance: fases sin decisión (repartir, declarar, puntuar…)        │
 │     5. Invariantes (siempre o en modo DEBUG)                                 │
 │     6. Commit: state = State'; log.append(events)                            │
 │                                                                              │
 │  get_legal_actions(pid) ─ get_observation(pid) ─ get_state() (copia)         │
 └──────────────────────────────────────────────────────────────────────────────┘
        │ usa (todo puro, sin estado propio)
        ├── rules/     evaluadores de lances (Grande, Chica, Pares, Juego, Punto)
        ├── betting/   BetState + máquina de envites (paso, envite, quiero, órdago)
        ├── scoring/   ScoringEngine: LanceScore → HandScore → GameScore
        ├── cards/     Card, Deck, Rank, Suit (value objects inmutables)
        ├── players/   Seat, Team, orden de turnos
        └── events/    eventos públicos/privados, log, replay
```

Principios:

1. **Un único objeto mutable**: `Game` guarda una referencia al `GameState` actual.
   Todo lo demás (estado, cartas, apuestas, eventos, observaciones) son
   `@dataclass(frozen=True, slots=True)` con `tuple`/`frozenset`, nunca `list`/`dict`
   expuestos. Cada transición produce un estado **nuevo**; el anterior no se toca.
   Consecuencia: ninguna referencia entregada al exterior puede alterar el motor.
2. **Validación y generación de acciones legales comparten la misma lógica.**
   `get_legal_actions()` y `validate()` se derivan de la misma función de reglas
   (`legal_action_space(state, pid)`), y `validate()` además comprueba parámetros
   (importe, cartas). Un test de propiedad garantiza que *toda* acción devuelta por
   `get_legal_actions` es aceptada y que acciones fuera de ese espacio son rechazadas.
3. **Transiciones puras**: `transition(state, pid, action) -> (state, events)` no
   tiene efectos secundarios ni aleatoriedad salvo el `RandomSource` determinista
   que vive *dentro* del estado (semilla + contador). Esto da determinismo y replay.
4. **Sin sobre-ingeniería**: no hay buses de eventos, plugins, ni inyección de
   dependencias. Hay enums, dataclasses, funciones puras y una tabla de fases.

---

## 2. Modelo de datos

### 2.1 Cartas (`cards/`)

```python
class Suit(Enum):  OROS, COPAS, ESPADAS, BASTOS
class Rank(IntEnum): AS=1, DOS=2, TRES=3, CUATRO=4, CINCO=5, SEIS=6, SIETE=7,
                     SOTA=10, CABALLO=11, REY=12          # baraja española de 40

@dataclass(frozen=True, slots=True, order=False)
class Card:
    rank: Rank
    suit: Suit
    def __str__(self) -> str            # "Rey de Oros" / código corto "12O"
```

La **equivalencia de Mus** NO vive en `Card` (la carta es física); vive en una
`RankingPolicy` derivada de `GameConfig`:

```python
@dataclass(frozen=True)
class RankingPolicy:
    kings_are_threes: bool   # el TRES cuenta como REY
    aces_are_twos: bool      # el DOS cuenta como AS
    def effective_rank(card) -> Rank     # 3→REY, 2→AS en ocho reyes
    def game_points(card) -> int          # figuras y (3) = 10; (2) = 1; resto valor
    def grande_order(card) -> int         # mayor = mejor
    def chica_order(card) -> int          # menor = mejor
```

Así `Card(TRES, OROS)` sigue siendo un tres (para invariantes de baraja y
visualización) pero para todos los lances es un rey.

### 2.2 Baraja (`cards/deck.py`)

```python
@dataclass(frozen=True)
class Deck:
    cards: tuple[Card, ...]                      # orden = orden de robo
    @staticmethod
    def standard(config) -> Deck                 # exactamente 40 cartas
    def shuffled(rng) -> Deck
    def draw(n) -> tuple[tuple[Card, ...], Deck]
    def validate() -> None                       # sin duplicados, composición exacta
```

### 2.3 Jugadores y parejas (`players/`)

```python
SeatId = NewType("SeatId", int)      # 0..3 ; el orden numérico ES el orden de juego

@dataclass(frozen=True)
class Player:            # identidad: no contiene cartas ni estrategia
    id: SeatId
    name: str

class TeamId(Enum): A = 0, B = 1     # A = asientos {0,2}, B = {1,3}

@dataclass(frozen=True)
class Team:
    id: TeamId
    seats: tuple[SeatId, SeatId]
```

Las **cartas de cada jugador** no viven en `Player` sino en `HandState.hands`
(`tuple[tuple[Card, ...], ...]` indexado por asiento). Motivo: `Player` es identidad
estable de toda la partida; la mano cambia en cada transición inmutable. La petición
pide "mano" dentro de `Player`: se ofrece como vista `PlayerView` construida bajo
demanda (`game.get_player(pid)`), nunca como estado mutable.

Funciones de orden (`players/seating.py`, puras):

```python
next_player(seat) -> SeatId          # (seat + 1) % 4, sentido de juego
previous_player(seat) -> SeatId
partner(seat) -> SeatId              # (seat + 2) % 4
team_of(seat) -> TeamId              # seat % 2
are_teammates(a, b) -> bool
order_from(mano) -> tuple[SeatId, ...]   # mano, siguiente, siguiente, postre
distance_from_mano(seat, mano) -> int    # 0 = mano … 3 = postre; usado en empates
```

`Game` expone `get_partner`, `get_team`, `are_teammates`, `is_hand` (= es mano),
`next_player`, `previous_player`.

### 2.4 Estado (`game/state.py`)

```python
@dataclass(frozen=True)
class GameState:                        # FULL_GAME_STATE (contiene secretos)
    config: GameConfig
    players: tuple[Player, ...]
    score: GameScore                    # tantos por pareja
    hand_number: int
    dealer: SeatId                      # postre
    mano: SeatId                        # next_player(dealer)
    phase: Phase
    hand: HandState | None              # None antes de empezar / tras terminar
    rng: RngState                       # semilla + contador → determinismo
    winner: TeamId | None

@dataclass(frozen=True)
class HandState:
    hands: tuple[tuple[Card, ...], ...] # 4 manos de 4 cartas
    stock: Deck                         # mazo restante (orden de robo)
    discard_pile: tuple[Card, ...]      # descartes acumulados
    mus: MusState
    lance: LanceType | None
    bet: BetState | None
    declarations: Declarations          # pares/juego declarados (públicos)
    lance_outcomes: tuple[LanceOutcome, ...]   # resultado de cada lance jugado
    pending_score: HandScore            # tantos a anotar al final de la mano
    turn: SeatId | None
    revealed: frozenset[SeatId]         # manos mostradas (tras órdago/recuento)

@dataclass(frozen=True)
class MusState:
    round: int                          # nº de rondas de mus en esta mano
    speaker: SeatId | None              # quién decide mus ahora
    requested_by: frozenset[SeatId]     # quién ha pedido mus en esta ronda
    cut_by: SeatId | None               # quién cortó (≠ mano, ≠ último que envidó)
    pending_discards: frozenset[SeatId] # quién falta por descartarse
    discards: tuple[tuple[Card, ...] | None, ...]   # privado hasta resolverse
```

### 2.5 Apuestas (`betting/`)

```python
class BetStatus(Enum):
    OPEN            # nadie ha envidado aún; se habla por turno
    PENDING         # hay envite/reenvite/órdago esperando respuesta
    ACCEPTED        # "quiero": se juega a las cartas al final de la mano
    REJECTED        # "no quiero": el proponente cobra el deje
    ALL_PASSED      # "en paso"
    ORDAGO_ACCEPTED # se resuelve inmediatamente

@dataclass(frozen=True)
class BetState:
    lance: LanceType
    status: BetStatus
    accepted_amount: int       # lo ya querido en firme (0 si nada)
    pending_amount: int        # total propuesto si se acepta lo pendiente
    is_ordago: bool
    proposer: SeatId | None    # quien hizo el último envite/reenvite
    proposing_team: TeamId | None
    to_act: tuple[SeatId, ...] # cola ordenada de quién debe hablar
    passed: frozenset[SeatId]  # quién ya pasó / dijo no quiero
    eligible: frozenset[SeatId]# quién puede hablar en este lance (pares/juego)
```

El deje de un "no quiero" es **una regla, no un caso**:
`rejection_value(bet, lance)`: primera apuesta ⇒ negada = 1 (Voc. "Negada");
revoque ⇒ lo ya querido, + 1 de deje en pares/juego/punto (C.VII-1) `[D-16]`.
No hay cientos de `if`: un envite es "subir `pending_amount`, invertir el equipo
proponente, rehacer la cola `to_act` con los rivales elegibles en orden desde la
mano". Un reenvite implica querer lo anterior: fija
`accepted_amount = pending_amount` anterior antes de subir. Aceptar fija
`accepted_amount = pending_amount`. Rechazar requiere que
todos los rivales elegibles de la cola rechacen (C.VI-4: "valdrá el quiero").

### 2.6 Puntuación (`scoring/`)

Tres niveles estrictamente separados:

| Nivel | Tipo | Contenido |
|---|---|---|
| **Bet score** | `BetResult` | lo que produce la apuesta del lance: deje, envite querido, paso, órdago |
| **Lance score** | `LanceOutcome` | ganador por cartas + bet result + valor intrínseco (pares, juego, punto) |
| **Hand score** | `HandScore` | lista ordenada de `ScoreEntry(team, tantos, lance, reason)` |
| **Game score** | `GameScore` | marcador acumulado por pareja; sólo crece |

`ScoringEngine.apply(game_score, hand_score) -> (GameScore, winner | None, entries_applied)`
anota entrada a entrada **en orden reglamentario** y se detiene en cuanto una
pareja alcanza `target_score` (`[D-22]`). Amarracos son una vista:
`amarracos = tantos // 5`, `sueltos = tantos % 5` (`tantos_per_amarraco` en config).

### 2.7 Configuración

```python
@dataclass(frozen=True)
class GameConfig:
    target_score: int = 40
    deck_type: DeckType = DeckType.SPANISH_40
    kings_are_threes: bool = True
    aces_are_twos: bool = True
    cards_per_hand: int = 4
    min_discard: int = 1                 # [D-13]
    max_discard: int = 4
    min_bet: int = 2                     # Voc. "Envido" = 2  [D-18]
    min_raise: int = 2                   # [D-18]
    points_pareja: int = 1
    points_medias: int = 2
    points_duples: int = 3
    points_juego_31: int = 3
    points_juego_other: int = 2
    points_punto: int = 1
    points_passed_lance: int = 1         # grande/chica/punto "en paso"
    tantos_per_amarraco: int = 5
    games_to_win: int = 1                # Intro-E: partida a N juegos (capa Match)
    first_shuffler: SeatId = 0           # C.III-1 sorteo del primer reparto [D-03]
    initial_dealer: SeatId | None = None # None = sorteo con la semilla
    debug_invariants: bool = True
```

`GameConfig.validate()` rechaza combinaciones imposibles (p. ej. `min_discard > 4`).
Ningún literal de reglas aparece fuera de `GameConfig` y `RankingPolicy`.

---

## 3. Máquina de estados

Se distingue entre **fases de decisión** (esperan una acción de un jugador) y
**fases automáticas** (el motor las atraviesa solo, emitiendo eventos).
`Game.apply_action` siempre deja el estado en una fase de decisión o en `GAME_OVER`.

```text
NOT_STARTED ──start()──► [DEAL]* ──► MUS_DECISION ◄────────────┐
                                        │  todos "mus"           │
                                        ├──────► DISCARD ──► [REDEAL]* ──┘
                                        │  alguien corta
                                        ▼
                                  LANCE(GRANDE) ──► LANCE(CHICA)
                                        │
                                  [DECLARE_PARES]* ──┬─ ambos equipos tienen ─► LANCE(PARES)
                                        │            └─ 0 ó 1 equipo: sin envite
                                  [DECLARE_JUEGO]* ──┬─ alguien tiene juego ──► LANCE(JUEGO) o sin envite
                                        │            └─ nadie: LANCE(PUNTO)
                                        ▼
                                  [HAND_SCORING]* ──► [CHECK_GAME_END]* ──┬─► GAME_OVER
                                                                         └─► [NEW_HAND]* ─► [DEAL]*
  Desde cualquier LANCE: órdago aceptado ──► [ORDAGO_SHOWDOWN]* ──► GAME_OVER
  (*) = fase automática
```

Tabla de fases de decisión:

| Fase | Quién actúa | Acciones legales | Evento(s) | Transición |
|---|---|---|---|---|
| `MUS_DECISION` | `mus.speaker` (empezando por la mano) | `MusAction`, `CutMusAction` | `MusRequested` / `MusCut` | siguiente orador; 4 mus → `DISCARD`; corte → `LANCE(GRANDE)` |
| `DISCARD` | `mus.speaker`, en orden postre → mano (C.III-11) | `DiscardAction(cards)` | `DiscardDeclared` (público: nº) | cuando todos: `[REDEAL]` → `CardsDiscarded`+`CardsDealt` → `MUS_DECISION` |
| `LANCE(x)` estado `OPEN` | `bet.to_act[0]` | `PassAction`, `BetAction(n)`, `OrdagoAction` | `Passed`, `BetPlaced`, `OrdagoDeclared` | último paso → `ALL_PASSED` → siguiente lance |
| `LANCE(x)` estado `PENDING` | `bet.to_act[0]` (rival) | `AcceptAction`, `RejectAction`, `RaiseAction(n)`, `OrdagoAction` (si no es ya órdago) | `BetAccepted`, `BetRejected`, `BetRaised`, `OrdagoDeclared` | aceptar → siguiente lance (u `ORDAGO_SHOWDOWN`); rechazos completos → deje → siguiente lance |
| `GAME_OVER` | nadie | ninguna | — | — (`GameFinishedError`) |

Cada fase se define en una tabla `PHASE_SPECS: dict[Phase, PhaseSpec]` con
`actors(state)`, `legal_actions(state, seat)`, `apply(state, seat, action)`. No hay
`if state == "X" and player == 2` disperso.

**Distinción de conceptos (requisito 9):**

| Concepto | Definición | Dónde vive |
|---|---|---|
| **Mano** | jugador a la derecha (siguiente en orden) del repartidor; rota cada mano | `GameState.mano` |
| **Postre** | repartidor; último en hablar | `GameState.dealer` |
| **Turno** | quien debe actuar ahora | `HandState.turn` / `bet.to_act[0]` |
| **Iniciador de lance** | primer jugador elegible desde la mano en ese lance (en pares/juego puede no ser la mano) | derivado |
| **Último envidador** | `bet.proposer` | `BetState` |
| **Cortador del mus** | `mus.cut_by` | `MusState` |

Los empates se resuelven **siempre** por la mano (`distance_from_mano`), nunca por
quién habló último ni por quién cortó.

---

## 4. Flujo completo de una partida (ejemplo)

1. `Game(players=…, config=GameConfig(), seed=123)` → `NOT_STARTED`.
2. `start()` → sorteo del primer reparto por palo (C.III-1) con la semilla `[D-03]`, `GameStarted`,
   barajado, reparto 4×4 desde la mano, una a una (C.III-2) → `CardsDealt`
   (privado por jugador; público: "4 cartas a cada uno") → `MUS_DECISION`, habla la mano.
3. Mano: `MusAction` · J1: `MusAction` · J2: `MusAction` · J3: `MusAction` → `DISCARD`.
4. Del postre al mano (C.III-11) cada uno envía `DiscardAction` (1–4 cartas `[D-13]`);
   el motor sirve de una vez a cada jugador (C.III-2, orden `[D-06]`), rebarajando
   todo el descarte si se agota el mazo (C.III-15, `[D-07]`) → `MUS_DECISION`.
5. Mano: `CutMusAction` → `MusCut` → `LANCE(GRANDE)`.
6. Grande (mano = J0; parejas A = {J0, J2}, B = {J1, J3}): J0 `PassAction`,
   J1 `BetAction(2)`, J2 `RaiseAction(3)` (total 5), J1 `RejectAction`,
   J3 `RejectAction` → `BetRejected`; la pareja A cobra el deje = 2 (lo ya querido)
   → `PointsAwarded` (se anota en el lance: C.VII-2; deje `[D-16]`).
7. Chica: todos pasan → `ALL_PASSED`; 1 tanto al ganador de chica al final.
8. Pares: `PairsDeclared` público (sí/no por jugador). Si sólo un equipo tiene →
   sin envite, cobra al final. Si ambos → `LANCE(PARES)` sólo entre los que tienen.
9. Juego: `JuegoDeclared`. Si nadie → `LANCE(PUNTO)`.
10. `HAND_SCORING`: se muestran las cuatro manos (C.VII-9), se evalúa cada lance
    en orden Grande → Chica → Pares → Juego/Punto, `LanceResolved` + `PointsAwarded`.
11. `CHECK_GAME_END`: si una pareja llega a 40 → `GameFinished`; si no →
    `NEW_HAND`: el repartidor pasa al siguiente asiento → paso 2.

---

## 5. Acciones (`game/actions.py`)

Todas `@dataclass(frozen=True, slots=True)`, hijas de `Action` (unión cerrada):

| Acción | Datos | Fase |
|---|---|---|
| `MusAction` | — | `MUS_DECISION` |
| `CutMusAction` | — | `MUS_DECISION` |
| `DiscardAction` | `cards: frozenset[Card]` | `DISCARD` |
| `PassAction` | — | lance `OPEN` |
| `BetAction` | `amount: int` (total envidado, ≥ `min_bet`) | lance `OPEN` |
| `RaiseAction` | `increment: int` ("envido N más", ≥ `min_raise`) | lance `PENDING` |
| `AcceptAction` | — | lance `PENDING` |
| `RejectAction` | — | lance `PENDING` |
| `OrdagoAction` | — | `OPEN` o `PENDING` no-órdago |

Decisiones:
- `DiscardAction` usa `frozenset` → imposible enviar duplicados; además se valida
  que las cartas estén en la mano del jugador y el tamaño ∈ [min, max].
- `get_legal_actions` devuelve para `BetAction`/`RaiseAction` un **rango**
  (`BetAction(2)` … hasta el máximo útil) mediante `LegalActions` con
  `bet_range: range | None` para no listar cientos de objetos; además
  `.as_list(limit)` y `.contains(action)`. `DiscardAction` igual: se exponen las
  combinaciones (máx. 15 por jugador: C(4,1)+…+C(4,4)), pequeño y enumerable.
- No existe acción para declarar pares/juego: la declaración la hace el motor
  (no se puede mentir; C.VI-17, C.IX-1).

## 6. Eventos (`events/`)

```python
@dataclass(frozen=True)
class EventEnvelope:
    seq: int
    hand_number: int
    visibility: Public | PrivateTo(seat) | EngineOnly
    event: Event
```

| Evento | Visibilidad | Contenido |
|---|---|---|
| `GameStarted` | público | config, jugadores, repartidor inicial |
| `DeckShuffled` | **solo motor** | orden de la baraja (para auditoría/replay) |
| `HandStarted` | público | nº mano, mano, postre |
| `CardsDealt` | privado(seat) | cartas recibidas |
| `CardsDealtPublic` | público | nº de cartas recibidas por asiento |
| `MusRequested` / `MusCut` | público | asiento |
| `DiscardDeclared` | público | asiento, **nº** de cartas |
| `CardsDiscarded` | privado(seat) | cartas descartadas y recibidas |
| `DeckReshuffled` | público + solo motor | hecho público; orden sólo motor |
| `LanceStarted` | público | lance, elegibles |
| `PairsDeclared` / `JuegoDeclared` | público | sí/no por asiento |
| `Passed`, `BetPlaced`, `BetRaised`, `BetAccepted`, `BetRejected`, `OrdagoDeclared`, `OrdagoAccepted` | público | asiento, importes |
| `HandsRevealed` | público | manos mostradas (sólo cuando el reglamento las muestra) |
| `LanceResolved` | público | lance, ganador, motivo |
| `PointsAwarded` | público | pareja, tantos, lance, motivo |
| `GameFinished` | público | ganador, marcador final |

## 7. Observaciones (`game/observations.py`)

```python
@dataclass(frozen=True)
class Observation:                 # PLAYER_OBSERVATION
    seat: SeatId
    phase: Phase
    my_hand: tuple[Card, ...]
    mano: SeatId; dealer: SeatId; turn: SeatId | None
    score: GameScore
    bet: PublicBetView | None      # sin campos internos
    declarations: Declarations
    discard_counts: tuple[int | None, ...]
    revealed_hands: Mapping[SeatId, tuple[Card, ...]]   # MappingProxyType
    public_events: tuple[EventEnvelope, ...]            # públicos + privados propios
    legal_actions: LegalActions
```

Garantías:
- Se construye desde cero filtrando por visibilidad: sólo `Public` y
  `PrivateTo(self.seat)`. Nunca se copia `GameState` y se "borra" lo secreto
  (whitelist, no blacklist).
- No incluye: manos ajenas no reveladas, mazo **ni su tamaño** (C.III-16), pila de descartes, semilla, contador
  RNG, descartes ajenos (sólo el número).
- Inmutable: tuplas, frozen dataclasses, `MappingProxyType`. `observation.my_hand.append`
  → `AttributeError`.
- Tests de seguridad: para cada observación de una partida aleatoria se serializa
  recursivamente todo su contenido y se comprueba que **ninguna** carta de manos
  ajenas no reveladas ni del mazo aparece (incluyendo `repr`).

## 8. Estructura de carpetas

```text
musst/
├── pyproject.toml            # hatchling; deps dev: pytest, hypothesis, ruff, mypy
├── README.md
├── docs/
│   ├── design.md             # este documento
│   ├── reglamento/           # PDF de la FEM (fuente de verdad)
│   ├── rules.md              # regla → artículo → test, y decisiones A-xx
│   ├── architecture.md · state-machine.md · scoring.md · testing.md · api.md
├── src/mus_engine/
│   ├── __init__.py           # API pública: Game, GameConfig, acciones, Observation…
│   ├── config.py             # GameConfig
│   ├── errors.py             # jerarquía de excepciones
│   ├── rng.py                # RNG determinista serializable
│   ├── cards/   card.py · deck.py · ranking.py (RankingPolicy)
│   ├── players/ player.py · team.py · seating.py
│   ├── rules/   lance.py (LanceType, protocolo Evaluator) · grande.py · chica.py
│   │            pares.py · juego.py · punto.py · mus.py (reparto, descartes)
│   ├── betting/ bets.py (BetState + transiciones) · ordago.py
│   ├── scoring/ scoring.py
│   ├── game/    game.py · state.py · phases.py · actions.py · validator.py
│   │            observations.py · invariants.py
│   ├── events/  events.py · log.py
│   └── replay/  replay.py
└── tests/ unit/ · rules/ · integration/ · security/ · property/ · regression/
```

Cambios respecto a la propuesta original: `config.py`, `errors.py`, `rng.py`
separados; `events/` fuera de `game/` porque replay y observaciones dependen de él;
`tests/property/` explícito; `cards/enums.py` innecesario (los enums viven en `card.py`).

## 9. Estrategia de testing

| Tipo | Qué cubre | Herramienta |
|---|---|---|
| Unit | Card, Deck (40, sin duplicados, composición exacta 10×4, barajado reproducible), RankingPolicy, cada evaluador, BetState, ScoringEngine | pytest + parametrize |
| Rules | un test por regla/decisión `A-xx`, nombrado `test_A14_deje_primer_envite_vale_1`, con cita del artículo | pytest |
| Integration | partidas completas con semilla y guion de acciones; verifican estados, cartas, eventos, marcador y ganador | pytest |
| Illegal | fuera de turno, fuera de fase, aceptar sin envite, envidar tras cerrar lance, mus tras corte, cartas ajenas/inexistentes/duplicadas/demasiadas, actuar tras el final | pytest |
| Security | ninguna observación contiene información ajena; mutar observaciones no altera el motor | pytest + hypothesis |
| Property | (1) partidas aleatorias con acciones legales siempre terminan y cumplen invariantes; (2) `legal ⊆ aceptadas` y `ilegales ⊆ rechazadas`; (3) misma semilla + mismas acciones ⇒ mismo log; (4) replay ≡ partida; (5) evaluadores: antisimetría y transitividad de comparaciones; (6) marcador monótono | hypothesis |
| Regression | cada bug → test en `tests/regression/` con descripción | pytest |
| Bordes de marcador | 0, 1, 39, 40; 39–39, 39–38, 38–39, 0–39; llegar a 40 en cada lance y en deje | pytest parametrize (estado construido con `GameState` de prueba vía fábrica de tests, no vía API pública) |

Calidad: `ruff check`, `ruff format --check`, `mypy --strict`, cobertura ≥ 95 % en
`rules/`, `betting/`, `scoring/`. Invariantes activos en todos los tests.

**Invariantes** (`game/invariants.py`, tras cada transición si `debug_invariants`):
manos + mazo + descartes = 40 cartas exactas sin duplicados; cada mano tiene 4
cartas fuera de `DISCARD`; una carta descartada sólo vuelve al juego a través de
un rebarajado del descarte (C.III-15); marcador nunca disminuye; nadie supera
`target_score` sin que la partida haya terminado; ganador ⇔ `GAME_OVER`;
`turn ∈ actores de la fase`; `0 ≤ accepted_amount ≤ pending_amount`;
`proposing_team ≠ team(to_act[0])` en `PENDING`. Fallo → `InvariantViolationError`
(es un bug del motor, nunca del usuario).

**Excepciones** (`errors.py`):

```text
MusEngineError
├── IllegalActionError
│   ├── NotYourTurnError
│   ├── InvalidStateError        (acción no válida en la fase)
│   ├── InvalidBetError          (importe, aceptar sin envite, órdago sobre órdago…)
│   └── InvalidDiscardError      (nº de cartas, cartas ajenas/inexistentes)
├── InvalidPlayerError
├── GameFinishedError
├── GameNotStartedError
├── PrivateInformationError
├── InvalidConfigError
└── InvariantViolationError      (bug interno)
```

Todas llevan `phase`, `seat` y `action` en el mensaje.

## 10. Ambigüedades del reglamento

Ver `docs/rules.md` §4 (D-01 … D-24). Resumen de lo que más afecta al diseño:
D-02 (valores en tantos), D-08/D-09 (orden del juego y desempates), D-16 (negada y
deje), D-22 (fin del juego a mitad de jugada) y D-24 (penalizaciones del postre con
jugada mínima).

## 11. Decisiones de diseño

1. **Estado inmutable + transiciones puras.** Es la forma más simple de garantizar a la
   vez inmutabilidad de observaciones, determinismo, replay e invariantes.
2. **Replay por re-ejecución.** El registro canónico es `GameRecord(config, seed,
   players, actions)`. `GameReplay` re-ejecuta las acciones con el mismo motor y guarda
   la secuencia de estados (inmutables, baratos de compartir). `next/previous/jump_to`
   navegan esa secuencia. El log de eventos se regenera y se compara con el original
   (detecta divergencias). Alternativa descartada: reconstruir el estado "plegando"
   eventos con reductores propios — duplicaría la lógica del motor y podría divergir.
3. **RNG propio** (`random.Random(seed)` encapsulado, con estado serializable dentro de
   `GameState`). Nunca `random` global.
4. **Declaraciones automáticas** de pares/juego (no hay acción "tengo pares").
5. **Avance automático** de las fases sin decisión: el cliente nunca tiene que "pulsar
   siguiente". Si la UI quiere pausas, las hace con los eventos.
6. **`Player` sin cartas**: la mano es estado de la mano, no identidad del jugador.
7. **Errores**: el motor nunca captura excepciones genéricas; un fallo de invariante es
   un bug y se propaga.
8. **Sin dependencias en tiempo de ejecución** (sólo stdlib). Dev: pytest, hypothesis,
   ruff, mypy.
9. Python ≥ 3.11 (el entorno tiene 3.11).

## 12. Plan de implementación

Cada fase termina con implementación + tests + documentación + casos límite +
revisión, y un commit. No se pasa a la siguiente sin tu visto bueno.

| Fase | Entregable | Tests clave |
|---|---|---|
| 1 | `Card`, `Rank`, `Suit`, `RankingPolicy`, `Deck`, `rng`, `GameConfig`, `errors`, tooling | 40 cartas, sin duplicados, composición, barajado reproducible, equivalencias 3/2 |
| 2 | `Player`, `Team`, `seating` | orden, pareja, mano, postre, rotación |
| 3 | `GameState`, `Phase`, `Game` esqueleto, invariantes | estado inicial, errores de fase |
| 4 | Reparto y mano | reparto determinista, rotación de mano |
| 5 | Mus, descartes, re-reparto, mazo agotado | flujo de mus, ilegales, D-04..D-07, D-13, D-14 |
| 6–9 | Evaluadores Grande, Chica, Pares, Juego/Punto | tablas exhaustivas, empates, mano |
| 10 | `BetState` y lances con envites | paso, envite, reenvite, deje |
| 11 | Órdago | aceptado/rechazado, fin de partida |
| 12 | `ScoringEngine` y final de partida | 0/1/39/40, llegar a 40 en cada lance |
| 13 | Eventos públicos/privados | contenido y visibilidad |
| 14 | Observaciones | seguridad e inmutabilidad |
| 15 | Replay | replay ≡ partida, navegación |
| 16 | Tests de propiedad y partidas completas; docs finales | ver §9 |

(La numeración agrupa algunas fases de tu lista de 18; el orden es el mismo. Las fases 3 y 4 se entregaron juntas: `start()` necesita repartir para llegar a una fase de decisión.)
