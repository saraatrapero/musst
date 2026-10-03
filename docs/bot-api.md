# Bot API pública (Python)

Contrato base:

```python
class Bot(Protocol):
    def decide(self, observation: dict[str, object]) -> BotDecision:
        ...
```

- El bot recibe una **observación parcial** (nunca estado secreto global).
- El bot devuelve una acción propuesta con confianza y evidencia.
- La acción siempre es revalidada por `RulesEngine`.

Esto permite integrar bots externos sin modificar el motor.
