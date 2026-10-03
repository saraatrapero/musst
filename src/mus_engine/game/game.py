"""Fachada pública del motor: :class:`Game`.

Es el único objeto con estado mutable (el estado actual y el registro de eventos).
Todo cambio pasa por :meth:`Game.start` o :meth:`Game.apply_action`; el resto de
métodos son consultas que no pueden alterar la partida.
"""

from __future__ import annotations

import secrets
from collections.abc import Sequence

from mus_engine.cards.card import Card
from mus_engine.config import GameConfig
from mus_engine.errors import (
    GameFinishedError,
    GameNotStartedError,
    InvalidConfigError,
    InvalidPlayerError,
    InvalidStateError,
    PrivateInformationError,
)
from mus_engine.events.events import (
    Emission,
    EventEnvelope,
    GameStarted,
    HandStarted,
    RngSeeded,
    Visibility,
)
from mus_engine.game import invariants, machine
from mus_engine.game.actions import Action
from mus_engine.game.flow import run_automatic
from mus_engine.game.legal import LegalActions
from mus_engine.game.observations import Observation, build_observation
from mus_engine.game.phases import Phase
from mus_engine.game.record import GameRecord
from mus_engine.game.state import GameState
from mus_engine.game.transition import enter
from mus_engine.players import seating
from mus_engine.players.player import Player, Table, Team
from mus_engine.players.seating import SeatId, TeamId
from mus_engine.rng import Rng

DEFAULT_NAMES = ("Jugador 0", "Jugador 1", "Jugador 2", "Jugador 3")


class Game:
    """Una partida de Mus.

    >>> game = Game(players=("Ana", "Bea", "Carlos", "Dani"), seed=12345)
    >>> _ = game.start()
    >>> game.phase
    <Phase.MUS_DECISION: 'mus_decision'>
    """

    def __init__(
        self,
        players: Sequence[str] | Table = DEFAULT_NAMES,
        config: GameConfig | None = None,
        seed: int | None = None,
    ) -> None:
        table = players if isinstance(players, Table) else _table_from(players)
        if config is None:
            config = GameConfig()
        if not isinstance(config, GameConfig):
            raise InvalidConfigError(f"Configuración inválida: {config!r}")
        if seed is None:
            seed = secrets.randbits(63)
        if not isinstance(seed, int) or isinstance(seed, bool):
            raise InvalidConfigError(f"La semilla debe ser un entero: {seed!r}")
        self._state = GameState(config=config, table=table, rng=Rng(seed))
        self._log: list[EventEnvelope] = []
        self._actions: list[tuple[SeatId, Action]] = []

    # --- Acciones -------------------------------------------------------------------

    def start(self) -> tuple[EventEnvelope, ...]:
        """Sortea el primer reparto y reparte. Devuelve los eventos públicos."""
        if self._state.phase is not Phase.NOT_STARTED:
            raise InvalidStateError("La partida ya ha empezado")
        state = self._state
        emitted: tuple[Emission, ...] = (
            Emission.engine(RngSeeded(state.rng.seed)),
            Emission.public(GameStarted(state.table.names, state.config)),
        )
        state, entered = enter(state, Phase.CHOOSE_FIRST_DEALER)
        state, automatic = run_automatic(state)
        new = self._commit(state, emitted + entered + automatic)
        return tuple(e for e in new if e.visibility is Visibility.PUBLIC)

    def apply_action(self, player_id: int, action: Action) -> tuple[EventEnvelope, ...]:
        """Solicita una acción. Devuelve los eventos producidos que ``player_id`` puede ver.

        Lanza un error específico (subclase de ``MusEngineError``) si la acción no es
        legal; en ese caso el estado no cambia.
        """
        self._require_in_progress()
        player = seating.seat(player_id)
        state, emitted = machine.apply(self._state, player, action)
        new = self._commit(state, emitted)
        self._actions.append((player, action))
        return tuple(e for e in new if e.visible_to(player))

    # --- Consultas ------------------------------------------------------------------

    def get_state(self) -> GameState:
        """Estado completo e inmutable. **Contiene información secreta**: no entregar a
        jugadores ni bots."""
        return self._state

    def get_observation(self, player_id: int) -> Observation:
        """Lo que ``player_id`` puede saber ahora. Inmutable y sin información ajena."""
        player = seating.seat(player_id)
        return build_observation(
            self._state,
            player,
            self._log,
            machine.actors(self._state),
            machine.legal_actions(self._state, player),
        )

    def get_hand(self, player_id: int, viewer_id: int) -> tuple[Card, ...]:
        """Naipes de ``player_id`` vistos por ``viewer_id``.

        Lanza :class:`PrivateInformationError` si ``viewer_id`` no puede verlos (no son
        suyos y no se han enseñado).
        """
        player, viewer = seating.seat(player_id), seating.seat(viewer_id)
        hand = self._state.hand
        if hand is None:
            raise GameNotStartedError("Todavía no se ha repartido ninguna jugada")
        if player != viewer and not hand.revealed:
            raise PrivateInformationError(
                f"El jugador {viewer} no puede ver los naipes del jugador {player}"
            )
        return hand.hand_of(player)

    def get_legal_actions(self, player_id: int) -> LegalActions:
        player = seating.seat(player_id)
        return machine.legal_actions(self._state, player)

    def current_actors(self) -> tuple[SeatId, ...]:
        """Jugadores que pueden actuar ahora."""
        return machine.actors(self._state)

    def get_events(self, viewer: int | None = None) -> tuple[EventEnvelope, ...]:
        """Eventos visibles para ``viewer`` (públicos + sus privados), o sólo públicos."""
        if viewer is None:
            return tuple(e for e in self._log if e.visibility is Visibility.PUBLIC)
        player = seating.seat(viewer)
        return tuple(e for e in self._log if e.visible_to(player))

    @property
    def event_log(self) -> tuple[EventEnvelope, ...]:
        """Registro completo, incluidos eventos privados y de motor (auditoría/replay)."""
        return tuple(self._log)

    @property
    def record(self) -> GameRecord:
        """Registro reproducible: jugadores, configuración, semilla y acciones aceptadas."""
        state = self._state
        return GameRecord(state.table.names, state.config, state.rng.seed, tuple(self._actions))

    @property
    def phase(self) -> Phase:
        return self._state.phase

    @property
    def seed(self) -> int:
        return self._state.rng.seed

    @property
    def is_finished(self) -> bool:
        return self._state.phase is Phase.GAME_OVER

    @property
    def winner(self) -> TeamId | None:
        return self._state.winner

    @property
    def mano(self) -> SeatId:
        return self._current_hand_positions()[0]

    @property
    def dealer(self) -> SeatId:
        return self._current_hand_positions()[1]

    def get_player(self, player_id: int) -> Player:
        return self._state.table.player(player_id)

    def get_partner(self, player_id: int) -> Player:
        return self._state.table.get_partner(player_id)

    def get_team(self, player_id: int) -> Team:
        return self._state.table.get_team(player_id)

    def are_teammates(self, player_a: int, player_b: int) -> bool:
        return self._state.table.are_teammates(player_a, player_b)

    def next_player(self, player_id: int) -> SeatId:
        return seating.next_player(seating.seat(player_id))

    def previous_player(self, player_id: int) -> SeatId:
        return seating.previous_player(seating.seat(player_id))

    def is_hand(self, player_id: int) -> bool:
        """``True`` si ``player_id`` es la mano de la jugada en curso."""
        return seating.seat(player_id) == self.mano

    # --- Internos -------------------------------------------------------------------

    def _require_in_progress(self) -> None:
        if self._state.phase is Phase.NOT_STARTED:
            raise GameNotStartedError("La partida no ha empezado: llama a start()")
        if self._state.phase is Phase.GAME_OVER:
            raise GameFinishedError("La partida ha terminado")

    def _current_hand_positions(self) -> tuple[SeatId, SeatId]:
        hand = self._state.hand
        if hand is None:
            raise GameNotStartedError("Todavía no se ha repartido ninguna jugada")
        return hand.mano, hand.dealer

    def _commit(self, state: GameState, emitted: tuple[Emission, ...]) -> tuple[EventEnvelope, ...]:
        if state.config.debug_invariants:
            invariants.check_resting(state)
            invariants.check_state(state)
            invariants.check_transition(self._state, state)
        hand_number = 0 if self._state.hand is None else self._state.hand.number
        envelopes: list[EventEnvelope] = []
        for emission in emitted:
            # Cada evento lleva el número de la jugada en curso cuando se produce.
            if isinstance(emission.event, HandStarted):
                hand_number = emission.event.hand_number
            envelopes.append(
                EventEnvelope(
                    seq=len(self._log) + len(envelopes),
                    hand_number=hand_number,
                    visibility=emission.visibility,
                    event=emission.event,
                    audience=emission.audience,
                )
            )
        self._state = state
        self._log.extend(envelopes)
        return tuple(envelopes)


def _table_from(names: Sequence[str]) -> Table:
    if isinstance(names, str) or len(names) != seating.NUM_SEATS:
        raise InvalidPlayerError("Se necesitan exactamente cuatro nombres de jugador")
    return Table.from_names((names[0], names[1], names[2], names[3]))
