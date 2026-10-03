# Testing

```bash
python -m pytest                        # toda la batería
python -m pytest tests/rules            # sólo reglas del reglamento
python -m pytest --cov=mus_engine --cov-report=term-missing
```

## Organización

| Carpeta | Qué contiene |
|---|---|
| `tests/unit/` | una clase/módulo por fichero: comportamiento, errores, inmutabilidad |
| `tests/rules/` | un test por regla del reglamento (`R-xx`) o decisión (`D-xx`); el docstring cita el artículo |
| `tests/property/` | propiedades con Hypothesis (p. ej. todo barajado es una permutación de las 40) |
| `tests/regression/` | un test por bug encontrado o por compatibilidad que no debe romperse |
| `tests/integration/` | uso de `Game` de extremo a extremo con semilla; partidas completas cuando estén todos los lances |
| `tests/security/` | información privada (eventos visibles por jugador) e inmutabilidad |

## Cómo añadir un test

- **Regla nueva**: en `tests/rules/`, nombre `test_<id>_<descripcion>` y docstring con la
  cita (`C.VI-4`) o la decisión (`D-16`). Añade la fila correspondiente en `docs/rules.md`.
- **Bug**: primero un test en `tests/regression/` que lo reproduzca y falle; después el
  arreglo. El docstring describe el bug.
- **Propiedad**: usa estrategias de Hypothesis con semillas (`st.integers`) para que los
  fallos sean reproducibles.

## Criterios

- `mypy --strict` también sobre los tests.
- Cobertura objetivo: 100 % en `cards/`, `rules/`, `betting/`, `scoring/`.
- Tests acumulados: fase 1: 114; fase 2: 183; fase 3: 290; fase 4: 347; fase 5: 401; fase 6: 455; fase 7: 504; fases 8–10: 639. Cobertura 100 %.

## Utilidades

- `tests/play.py`: jugar por la API pública (`all_mus`, `discard_all`, `cut`, `actor`,
  `pass_lance`, `act`, `points_events`).
- `tests/factories.py`: `game_at_lance(hands, tantos=..., games=..., **config)` coloca una
  partida al empezar los lances con manos elegidas (resto de la baraja en el mazo).
- `tests/strategies.py`: `play_random_legal(game, data, max_steps)` elige acciones
  legales al azar con Hypothesis y devuelve las aplicadas (permite reproducirlas);
  `play_seeded(game, seed, max_steps)` hace lo mismo con un `random.Random` para partidas
  completas.
- `tests/visibility.py`: `cards_in(obj)` extrae recursivamente todos los naipes de un
  objeto; `cards_ever_held(game, seat)` los que un jugador ha tenido y `cards_known`
  añade los enseñados legítimamente. Base de los tests de información privada.

## Construir estados concretos

`tests/factories.py` ofrece `started_game(seed, **config)` y `game_with_state(state)`
para colocar una partida en un estado preciso (p. ej. terminada o con marcador
39–39). Es sólo para tests: la API pública no permite fijar el estado.
