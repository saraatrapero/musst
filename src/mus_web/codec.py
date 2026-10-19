"""Traducción entre el motor y JSON (navegador y base de datos).

- **Hacia el navegador** sólo sale una ``Observation`` (lo que el jugador puede saber)
  y eventos ya filtrados por visibilidad. Nunca el ``GameState``.
- **Desde el navegador** entran acciones que se validan estrictamente: cualquier campo
  desconocido, tipo incorrecto o valor imposible lanza :class:`CodecError`. Aun así,
  la última palabra la tiene el motor, que vuelve a validar la acción.
"""

from __future__ import annotations

import dataclasses
from enum import Enum
from typing import Any

from mus_engine.cards.card import Card
from mus_engine.config import GameConfig
from mus_engine.errors import MusEngineError
from mus_engine.events.events import EventEnvelope
from mus_engine.game.actions import (
    AcceptAction,
    Action,
    BetAction,
    ClockTick,
    CutMusAction,
    DiscardAction,
    MusAction,
    OrdagoAction,
    PassAction,
    RaiseAction,
    RejectAction,
    SignalAction,
)
from mus_engine.game.legal import LegalActions
from mus_engine.game.observations import Observation
from mus_engine.game.record import GameRecord, RecordEntry
from mus_engine.players.seating import seat
from mus_engine.rules.signals import Signal

JSON = dict[str, Any]

MAX_AMOUNT = 1000  # tope razonable para un envite pedido desde el navegador


class CodecError(ValueError):
    """Mensaje del navegador mal formado."""


_SIMPLE: dict[str, type[Action]] = {
    "mus": MusAction,
    "cut": CutMusAction,
    "pass": PassAction,
    "accept": AcceptAction,
    "reject": RejectAction,
    "ordago": OrdagoAction,
}
_SIMPLE_NAMES = {cls: name for name, cls in _SIMPLE.items()}


# --- Valores genéricos ------------------------------------------------------------------


def to_json(value: object) -> Any:
    """Convierte naipes, enums, dataclasses y tuplas en tipos JSON."""
    if isinstance(value, Card):
        return value.code
    if isinstance(value, Enum):
        return (
            value.value
            if not isinstance(value.value, int) or isinstance(value, bool)
            else value.name
        )
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_json(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, (tuple, list, frozenset, set)):
        items = [to_json(v) for v in value]
        return sorted(items) if isinstance(value, (frozenset, set)) else items
    return value


# --- Acciones ----------------------------------------------------------------------------


def action_to_json(action: Action) -> JSON:
    if isinstance(action, BetAction):
        return {"type": "bet", "amount": action.amount}
    if isinstance(action, RaiseAction):
        return {"type": "raise", "amount": action.amount}
    if isinstance(action, DiscardAction):
        return {"type": "discard", "cards": sorted(c.code for c in action.cards)}
    if isinstance(action, SignalAction):
        return {"type": "signal", "signal": action.signal.value}
    return {"type": _SIMPLE_NAMES[type(action)]}


def action_from_json(data: object) -> Action:
    """Acción pedida por el navegador. Estricto: rechaza cualquier cosa rara."""
    if not isinstance(data, dict):
        raise CodecError("La acción debe ser un objeto JSON")
    kind = data.get("type")
    allowed: dict[str, set[str]] = {
        "bet": {"type", "amount"},
        "raise": {"type", "amount"},
        "discard": {"type", "cards"},
        "signal": {"type", "signal"},
    }
    if not isinstance(kind, str) or (kind not in _SIMPLE and kind not in allowed):
        raise CodecError(f"Tipo de acción desconocido: {kind!r}")
    extra = set(data) - allowed.get(kind, {"type"})
    if extra:
        raise CodecError(f"Campos no permitidos: {sorted(extra)}")
    try:
        if kind in _SIMPLE:
            return _SIMPLE[kind]()
        if kind in ("bet", "raise"):
            amount = data.get("amount")
            if (
                not isinstance(amount, int)
                or isinstance(amount, bool)
                or not 1 <= amount <= MAX_AMOUNT
            ):
                raise CodecError(f"Importe no válido: {amount!r}")
            return BetAction(amount) if kind == "bet" else RaiseAction(amount)
        if kind == "discard":
            cards = data.get("cards")
            if (
                not isinstance(cards, list)
                or not all(isinstance(c, str) for c in cards)
                or len(cards) > 4
            ):
                raise CodecError("'cards' debe ser una lista de hasta 4 códigos de naipe")
            return DiscardAction(Card.from_code(c) for c in cards)
        signal = data.get("signal")
        if not isinstance(signal, str):
            raise CodecError("'signal' debe ser texto")
        return SignalAction(Signal(signal))
    except CodecError:
        raise
    except (MusEngineError, ValueError) as error:
        raise CodecError(str(error)) from error


def legal_to_json(legal: LegalActions) -> JSON:
    return {
        "actions": [action_to_json(a) for a in legal.actions],
        "bet": None if legal.bet is None else {"min": legal.bet.minimum, "max": legal.bet.maximum},
        "raise": None
        if legal.raise_ is None
        else {"min": legal.raise_.minimum, "max": legal.raise_.maximum},
    }


# --- Observación y eventos ----------------------------------------------------------------


def event_to_json(envelope: EventEnvelope) -> JSON:
    return {
        "seq": envelope.seq,
        "hand": envelope.hand_number,
        "type": type(envelope.event).__name__,
        "data": to_json(envelope.event),
    }


def observation_to_json(obs: Observation, events_tail: int = 150) -> JSON:
    """Lo que se envía a un jugador. Sólo campos de la observación (lista blanca)."""
    return {
        "seat": obs.seat,
        "names": list(obs.player_names),
        "phase": obs.phase.value,
        "score": {"tantos": list(obs.score.tantos), "games": list(obs.score.games)},
        "target_score": obs.target_score,
        "games_to_win": obs.games_to_win,
        "winner": None if obs.winner is None else obs.winner.name,
        "hand_number": obs.hand_number,
        "my_hand": [c.code for c in obs.my_hand],
        "mano": obs.mano,
        "dealer": obs.dealer,
        "to_act": list(obs.to_act),
        "mus_round": obs.mus_round,
        "mus_requested": list(obs.mus_requested),
        "mus_cut_by": obs.mus_cut_by,
        "discard_counts": list(obs.discard_counts),
        "lance": None if obs.lance is None else obs.lance.value,
        "bet": to_json(obs.bet),
        "pares_holders": None if obs.pares_holders is None else list(obs.pares_holders),
        "juego_holders": None if obs.juego_holders is None else list(obs.juego_holders),
        "outcomes": to_json(obs.outcomes),
        "revealed_hands": to_json(obs.revealed_hands),
        "legal": legal_to_json(obs.legal_actions),
        "gaze": None if obs.gaze is None else list(obs.gaze),
        "signals_seen": [{"sender": s, "signal": sig.value} for s, sig in obs.signals_seen],
        "my_signals": [{"signal": sig.value, "seen_by": list(by)} for sig, by in obs.my_signals],
        "events": [event_to_json(e) for e in obs.events[-events_tail:]],
    }


# --- Registro de partida (base de datos) ---------------------------------------------------


def config_to_json(config: GameConfig) -> JSON:
    return {f.name: getattr(config, f.name) for f in dataclasses.fields(config)} | {
        "deck_type": config.deck_type.value
    }


def config_from_json(data: JSON) -> GameConfig:
    from mus_engine.config import DeckType

    values = dict(data)
    values["deck_type"] = DeckType(values["deck_type"])
    return GameConfig(**values)


def record_to_json(record: GameRecord) -> JSON:
    def entry(e: RecordEntry) -> JSON:
        if isinstance(e, ClockTick):
            return {"tick": True}
        player, action = e
        return {"seat": player, "action": action_to_json(action)}

    return {
        "player_names": list(record.player_names),
        "config": config_to_json(record.config),
        "seed": record.seed,
        "actions": [entry(e) for e in record.actions],
    }


def record_from_json(data: JSON) -> GameRecord:
    entries: list[RecordEntry] = []
    for item in data["actions"]:
        if item.get("tick"):
            entries.append(ClockTick())
        else:
            entries.append((seat(item["seat"]), action_from_json(item["action"])))
    a, b, c, d = data["player_names"]
    return GameRecord((a, b, c, d), config_from_json(data["config"]), data["seed"], tuple(entries))
