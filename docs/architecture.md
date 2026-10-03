# Arquitectura (base incremental)

## Principios

1. **RulesEngine como fuente de verdad**.
2. **GameEngine desacoplado de frontend**.
3. **Observation Builder** para evitar fugas de información privada.
4. **API de bots estable** para competición.
5. **Event sourcing** para replay, análisis y aprendizaje.

## Flujo

`GameState -> ObservationBuilder -> Bot/Human Action -> RulesEngine.validate -> GameEngine.apply -> GameEvent`

## Estado actual

La base actual cubre contratos y componentes mínimos para evolucionar en fases sin bloquear la práctica.
