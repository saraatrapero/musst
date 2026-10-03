# API pública

Todo lo que se documenta aquí se importa desde `mus_engine`. El resto de módulos
son internos y pueden cambiar.

## Fase 1 — Cartas, baraja y configuración

### `Suit`, `Rank`, `Card`

```python
Suit.OROS | Suit.COPAS | Suit.ESPADAS | Suit.BASTOS
Rank.AS (1) … Rank.SIETE (7), Rank.SOTA (10), Rank.CABALLO (11), Rank.REY (12)

card = Card(Rank.REY, Suit.OROS)
card.code            # "12O"   (número impreso + inicial del palo)
str(card)            # "Rey de Oros"
Card.from_code("1B") # Card(1B); lanza InvalidCardError si no existe (p. ej. "8O")
```

- Inmutable y hashable; igualdad por valor.
- **No** tiene orden (`<` lanza `TypeError`): el orden depende del lance.
- Rangos y palos se validan al construir: `Card(8, Suit.OROS)` → `InvalidCardError`.

### `Deck`

```python
Deck.standard()                 # 40 naipes en orden canónico
deck, rng = deck.shuffled(rng)  # nueva baraja barajada + siguiente estado del RNG
cards, rest = deck.draw(4)      # roba de arriba; no modifica `deck`
deck.validate_complete()        # exactamente las 40, sin duplicados
len(deck), card in deck, iter(deck)
```

Un `Deck` nunca puede contener duplicados ni objetos que no sean cartas
(`InvalidDeckError`). `validate_complete(cards)` comprueba una colección arbitraria
(se usará como invariante: manos + mazo + descartes = baraja completa).

### `Rng`

```python
rng = Rng(seed=12345)                 # valor inmutable (seed, stream)
items, rng = rng.shuffle(sequence)    # Fisher–Yates, no modifica la entrada
index, rng = rng.choice_index(4)      # entero uniforme en [0, 4)
```

Basado en SHA-256 en modo contador: la misma semilla produce el mismo resultado
en cualquier versión de Python y plataforma (test de regresión
`tests/regression/test_rng_golden.py`).

### `RankingPolicy`

```python
policy = RankingPolicy.from_config(config)
policy.effective_rank(card)       # 3 -> REY, 2 -> AS en ocho reyes (C.II-3)
policy.game_points(card)          # figuras 10, as 1, resto su número (D-01)
policy.total_game_points(cards)
policy.playing_ranks              # rangos efectivos posibles, de menor a mayor
```

### `GameConfig`

Inmutable; valida al construir (`InvalidConfigError`). Campos y su origen
(artículo del reglamento o decisión `D-xx`) documentados en `src/mus_engine/config.py`.

```python
GameConfig(target_score=40, games_to_win=1, deck_type=DeckType.SPANISH_40,
           kings_are_threes=True, aces_are_twos=True, ...)
```

### Excepciones

```text
MusEngineError
├── InvalidConfigError · InvalidCardError · InvalidDeckError
├── IllegalActionError
│   ├── NotYourTurnError · InvalidStateError · InvalidBetError · InvalidDiscardError
├── InvalidPlayerError · GameNotStartedError · GameFinishedError
├── PrivateInformationError
└── InvariantViolationError   (bug del motor; nunca capturar para continuar)
```

## Fase 2 — Jugadores, parejas y orden de la mesa

### `Player`, `Team`, `Table`

```python
table = Table.from_names(("Ana", "Bea", "Carlos", "Dani"))   # asientos 0..3 en orden de habla
table.player(1)               # Player(id=1, name="Bea")
table.get_partner(0)          # Player(id=2, name="Carlos")
table.get_team(3)             # Team(id=TeamId.B, seats=(1, 3))
table.are_teammates(0, 2)     # True
```

- `Player` es sólo identidad (asiento + nombre): **no** tiene mano, estrategia ni
  estadísticas. Inmutable.
- Parejas fijas: `TeamId.A` = asientos 0 y 2, `TeamId.B` = 1 y 3 (los puestos no cambian
  durante la partida, C.II-1).
- Cualquier id fuera de `0..3` (o que no sea `int`) lanza `InvalidPlayerError`.

### Orden de la mesa (`mus_engine.players`)

| Función | Significado |
|---|---|
| `next_player(s)` / `previous_player(s)` | quien habla después / antes de `s` |
| `partner(s)`, `team_of(s)`, `are_teammates(a, b)` | parejas |
| `mano_for_dealer(d)` | mano = jugador a la derecha del que reparte (Voc. "Mano") |
| `dealer_for_mano(m)` | postre = quien reparte |
| `next_dealer(d)` | quien reparte la jugada siguiente (D-15) |
| `is_mano(s, mano)`, `is_postre(s, mano)` | posición en la jugada |
| `order_from(s)` | los 4 asientos en orden de habla desde `s` |
| `distance_from_mano(s, mano)` | 0 (mano) … 3 (postre); base de desempates (D-09) |
| `closest_to_mano(seats, mano)` | quien gana un empate entre `seats` |
| `lance_mano(mano, eligible)` / `lance_postre(...)` | mano/postre del lance en pares o juego |
| `mus_order(mano)` | orden para dar o cortar mus (C.IV-4) |
| `discard_order(mano)` | postre → mano (C.III-11) |
| `deal_order(dealer)` | reparto desde la mano (C.III-2) |
| `cutter_for(shuffler)`, `first_dealer_by_suit(cutter, suit)` | sorteo del primer reparto (C.III-1, C.III-3) |

**Mano ≠ turno ≠ último que envida ≠ quien corta el mus.** La mano es una posición fija
durante la jugada; el turno lo decide la máquina de estados (fase 3+).
