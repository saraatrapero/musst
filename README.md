# MUS.ST

> El Mus que aprende cómo juegas.

Este repositorio implementa la **base técnica inicial** de MUS.ST con foco en los requisitos de la práctica:

- motor de reglas independiente de la interfaz;
- baraja española de 40 cartas con modalidad de ocho reyes y ocho ases;
- validación server-side de acciones legales;
- arquitectura de observaciones por jugador (privacidad);
- API pública de bots en Python;
- event sourcing básico para historial/replay;
- tests unitarios focalizados.

## Estado del proyecto

Se ha implementado una **Fase 1/MVP del motor** para permitir crecimiento incremental hacia el alcance completo descrito en la propuesta universitaria.

## Estructura

- `src/musst/`: núcleo del motor y contratos
- `tests/`: tests unitarios iniciales
- `docs/`: documentación de arquitectura, reglas, bots, agentes, pruebas y despliegue
