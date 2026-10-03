"""Replay de una partida: navegación paso a paso por sus estados.

El replay es consecuencia directa de la arquitectura: como el motor es determinista,
re-ejecutar las acciones de un :class:`GameRecord` reproduce exactamente los mismos
estados y eventos. Cada paso guarda el estado inmutable resultante, de modo que
avanzar, retroceder o saltar es inmediato.
"""

from __future__ import annotations

from mus_engine.errors import InvariantViolationError
from mus_engine.events.events import EventEnvelope
from mus_engine.game.actions import Action
from mus_engine.game.game import Game
from mus_engine.game.legal import NO_ACTIONS
from mus_engine.game.observations import Observation, build_observation
from mus_engine.game.record import GameRecord
from mus_engine.game.state import GameState
from mus_engine.players import seating
from mus_engine.players.player import Table
from mus_engine.players.seating import SeatId


class GameReplay:
    """Reproduce un :class:`GameRecord`. La posición 0 es el estado tras ``start()``."""

    def __init__(self, record: GameRecord) -> None:
        self.record = record
        game = Game(
            players=Table.from_names(record.player_names), config=record.config, seed=record.seed
        )
        game.start()
        self._states: list[GameState] = [game.get_state()]
        self._event_counts: list[int] = [len(game.event_log)]
        for player, action in record.actions:
            game.apply_action(player, action)
            self._states.append(game.get_state())
            self._event_counts.append(len(game.event_log))
        self._log = game.event_log
        self._position = 0

    @classmethod
    def from_game(cls, game: Game) -> GameReplay:
        """Replay de una partida en curso o terminada, verificando que coincide."""
        replay = cls(game.record)
        if replay.event_log != game.event_log:
            raise InvariantViolationError("El replay no reproduce los mismos eventos")
        return replay

    @classmethod
    def from_events(cls, log: tuple[EventEnvelope, ...]) -> GameReplay:
        """Replay reconstruido únicamente a partir del registro completo de eventos."""
        replay = cls(GameRecord.from_events(log))
        if replay.event_log != tuple(log):
            raise InvariantViolationError("Los eventos reconstruidos no coinciden")
        return replay

    # --- Navegación -------------------------------------------------------------------

    def __len__(self) -> int:
        """Número de acciones de la partida."""
        return len(self.record.actions)

    @property
    def position(self) -> int:
        return self._position

    @property
    def at_start(self) -> bool:
        return self._position == 0

    @property
    def at_end(self) -> bool:
        return self._position == len(self)

    def next(self) -> GameState:
        if self.at_end:
            raise IndexError("El replay ya está al final")
        self._position += 1
        return self.state

    def previous(self) -> GameState:
        if self.at_start:
            raise IndexError("El replay ya está al principio")
        self._position -= 1
        return self.state

    def jump_to(self, position: int) -> GameState:
        if not isinstance(position, int) or not 0 <= position <= len(self):
            raise IndexError(f"Posición fuera de rango: {position} (0..{len(self)})")
        self._position = position
        return self.state

    # --- Consultas --------------------------------------------------------------------

    @property
    def state(self) -> GameState:
        return self._states[self._position]

    @property
    def last_action(self) -> tuple[SeatId, Action] | None:
        """Acción que llevó a la posición actual (``None`` en la posición 0)."""
        return None if self.at_start else self.record.actions[self._position - 1]

    @property
    def event_log(self) -> tuple[EventEnvelope, ...]:
        """Registro completo de la partida (hasta el final)."""
        return self._log

    def events(self, viewer: int | None = None) -> tuple[EventEnvelope, ...]:
        """Eventos hasta la posición actual: completos o los que ve ``viewer``."""
        upto = self._log[: self._event_counts[self._position]]
        if viewer is None:
            return upto
        player = seating.seat(viewer)
        return tuple(e for e in upto if e.visible_to(player))

    def observation(self, viewer: int) -> Observation:
        """Observación de ``viewer`` en la posición actual (sin acciones legales)."""
        player = seating.seat(viewer)
        return build_observation(self.state, player, self.events(), (), NO_ACTIONS)
