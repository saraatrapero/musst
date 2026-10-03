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
| `tests/integration/` | partidas completas con semilla (a partir de la fase 4) |
| `tests/security/` | información privada e inmutabilidad de observaciones (fase 16) |

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
- Fase 1: 114 tests, cobertura 100 %.
