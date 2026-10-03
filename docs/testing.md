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
- Tests acumulados: fase 1: 114; fase 2: 183; fase 3: 290. Cobertura 100 %.

## Construir estados concretos

`tests/factories.py` ofrece `started_game(seed, **config)` y `game_with_state(state)`
para colocar una partida en un estado preciso (p. ej. terminada o con marcador
39–39). Es sólo para tests: la API pública no permite fijar el estado.
