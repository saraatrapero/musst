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
