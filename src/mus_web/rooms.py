"""Salas de juego: quién se sienta dónde y cómo avanza la partida.

La lógica es síncrona y determinista (fácil de probar); :mod:`mus_web.app` la mueve con
un bucle ``asyncio`` por sala que hace jugar a los bots y da los «momentos» del reloj de
miradas cuando hay señas.

Modos (``docs/ai-design.md`` §5ter):

- ``con_bot``: tú y un bot de compañero contra dos bots.
- ``dos_humanos``: dos personas (pareja) contra dos bots.
- ``cuatro``: cuatro personas, sin bots.
"""

from __future__ import annotations

import random
import string
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from mus_engine.bots.base import Bot, BotContext
from mus_engine.bots.medium_bot import MediumBot
from mus_engine.bots.simple_bot import SimpleBot
from mus_engine.config import GameConfig
from mus_engine.errors import MusEngineError
from mus_engine.events.events import EventEnvelope
from mus_engine.game.game import Game
from mus_engine.players.seating import ALL_SEATS, SeatId, team_of
from mus_web.avatars_pack import Avatar
from mus_web.codec import CodecError, action_from_json, observation_to_json
from mus_web.phrases import Phrase, PhraseMaker


class Mode(Enum):
    CON_BOT = "con_bot"
    DOS_HUMANOS = "dos_humanos"
    CUATRO = "cuatro"


HUMAN_SEATS: dict[Mode, tuple[SeatId, ...]] = {
    Mode.CON_BOT: (SeatId(0),),
    Mode.DOS_HUMANOS: (SeatId(0), SeatId(2)),  # compañeros: asientos enfrentados
    Mode.CUATRO: ALL_SEATS,
}

# Nivel de los bots de la sala (docs/ai-design.md §4).
BOT_LEVELS: dict[str, Callable[[], Bot]] = {"sencillo": SimpleBot, "medio": MediumBot}
DEFAULT_LEVEL = "medio"

CODE_ALPHABET = "".join(c for c in string.ascii_uppercase + string.digits if c not in "O0I1")
CODE_LENGTH = 6
PHRASE_HISTORY = 6


class RoomError(Exception):
    """Petición imposible en el estado actual de la sala (se le explica al jugador)."""


@dataclass(slots=True)
class Occupant:
    name: str
    avatar: Avatar
    user_id: int | None = None
    bot: Bot | None = None

    @property
    def is_bot(self) -> bool:
        return self.bot is not None

    def public(self) -> dict[str, Any]:
        return {"name": self.name, "avatar": self.avatar.public(), "bot": self.is_bot}


@dataclass(slots=True)
class Room:
    code: str
    mode: Mode
    signals: bool
    phrases_enabled: bool
    host_id: int
    avatars: tuple[Avatar, ...]
    rng: random.Random
    seats: list[Occupant | None] = field(default_factory=lambda: [None] * 4)
    game: Game | None = None
    phrases: list[dict[str, Any]] = field(default_factory=list)
    saved: bool = False
    level: str = DEFAULT_LEVEL
    _phrase_maker: PhraseMaker | None = None
    _seen: int = 0  # eventos ya comentados
    _phrase_count: int = 0

    # --- Antes de empezar ------------------------------------------------------------

    @property
    def human_seats(self) -> tuple[SeatId, ...]:
        return HUMAN_SEATS[self.mode]

    @property
    def started(self) -> bool:
        return self.game is not None

    @property
    def finished(self) -> bool:
        return self.game is not None and self.game.is_finished

    @property
    def hand_number(self) -> int:
        hand = None if self.game is None else self.game.get_state().hand
        return 0 if hand is None else hand.number

    def seat_of(self, user_id: int) -> SeatId | None:
        for seat in ALL_SEATS:
            occupant = self.seats[seat]
            if occupant is not None and occupant.user_id == user_id:
                return seat
        return None

    def join(self, user_id: int, name: str, avatar: Avatar) -> SeatId:
        current = self.seat_of(user_id)
        if current is not None:
            return current
        if self.started:
            raise RoomError("La partida ya ha empezado")
        for seat in self.human_seats:
            if self.seats[seat] is None:
                self.seats[seat] = Occupant(name, avatar, user_id=user_id)
                return seat
        raise RoomError("La sala está completa")

    def leave(self, user_id: int) -> None:
        seat = self.seat_of(user_id)
        if seat is None:
            return
        if self.started:
            raise RoomError("No se puede abandonar una partida empezada")
        self.seats[seat] = None

    def start(self, user_id: int, seed: int, bot_factory: Callable[[], Bot] | None = None) -> None:
        if user_id != self.host_id:
            raise RoomError("Sólo quien creó la sala puede empezar")
        if self.started:
            raise RoomError("La partida ya ha empezado")
        if any(self.seats[s] is None for s in self.human_seats):
            raise RoomError("Faltan jugadores por sentarse")
        taken = {o.avatar.id for o in self.seats if o is not None}
        free = [a for a in self.avatars if a.id not in taken] or list(self.avatars)
        self.rng.shuffle(free)
        config = GameConfig(signals_enabled=self.signals)
        bot_factory = bot_factory or BOT_LEVELS[self.level]
        speakers: dict[SeatId, Avatar] = {}
        for seat in ALL_SEATS:
            if self.seats[seat] is None:
                avatar = free.pop() if free else self.rng.choice(self.avatars)
                bot = bot_factory()
                bot.on_game_start(BotContext(seat, config, seed + seat))
                self.seats[seat] = Occupant(avatar.nickname, avatar, bot=bot)
                speakers[seat] = avatar
        names = tuple(o.name for o in self.seats if o is not None)
        self.game = Game(names, config=config, seed=seed)
        self.game.start()
        self._phrase_maker = PhraseMaker(speakers, self.rng)
        self._after_step()

    # --- Durante la partida -------------------------------------------------------------

    def _game(self) -> Game:
        if self.game is None:
            raise RoomError("La partida no ha empezado")
        return self.game

    def _bot(self, seat: SeatId) -> Bot | None:
        occupant = self.seats[seat]
        return None if occupant is None else occupant.bot

    def human_action(self, user_id: int, data: object) -> None:
        game = self._game()
        seat = self.seat_of(user_id)
        if seat is None:
            raise RoomError("No estás sentado en esta mesa")
        if game.is_finished:
            raise RoomError("La partida ha terminado")
        try:
            action = action_from_json(data)
            game.apply_action(seat, action)
        except (CodecError, MusEngineError) as error:
            raise RoomError(str(error)) from error
        self._after_step()

    def bot_to_act(self) -> SeatId | None:
        game = self._game()
        if game.is_finished:
            return None
        (seat,) = game.current_actors()
        return seat if self._bot(seat) is not None else None

    def bot_step(self) -> None:
        """Juega el bot al que le toca (y antes, si hay señas, deja hacer señas)."""
        seat = self.bot_to_act()
        if seat is None:
            raise RoomError("No le toca a ningún bot")
        game = self._game()
        self._bot_signals()
        bot = self._bot(seat)
        assert bot is not None
        game.apply_action(seat, bot.decide(game.get_observation(seat)))
        self._after_step()

    def clock(self) -> None:
        """Un momento del reloj de miradas (sólo con señas)."""
        game = self._game()
        if not self.signals or game.is_finished:
            return
        game.tick()
        self._bot_signals()
        self._after_step()

    def _bot_signals(self) -> None:
        game = self._game()
        if not self.signals:
            return
        for seat in ALL_SEATS:
            bot = self._bot(seat)
            if bot is None or game.is_finished:
                continue
            action = bot.signal(game.get_observation(seat))
            if action is not None:
                game.apply_action(seat, action)

    def _after_step(self) -> None:
        game = self._game()
        log = game.event_log
        new: tuple[EventEnvelope, ...] = log[self._seen :]
        self._seen = len(log)
        if game.is_finished:
            for occupant in self.seats:
                if occupant is not None and occupant.bot is not None:
                    occupant.bot.on_game_end(game.get_observation(self._seat_index(occupant)))
        if self.phrases_enabled and self._phrase_maker is not None:
            for phrase in self._phrase_maker.react(new):
                self._say(phrase)
        del self.phrases[:-PHRASE_HISTORY]

    def _seat_index(self, occupant: Occupant) -> SeatId:
        return ALL_SEATS[self.seats.index(occupant)]

    def _say(self, phrase: Phrase) -> None:
        self._phrase_count += 1
        self.phrases.append({"id": self._phrase_count, "seat": phrase.seat, "text": phrase.text})

    # --- Vistas -------------------------------------------------------------------------

    def lobby_view(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "mode": self.mode.value,
            "signals": self.signals,
            "phrases": self.phrases_enabled,
            "level": self.level,
            "host_id": self.host_id,
            "started": self.started,
            "finished": self.finished,
            "human_seats": list(self.human_seats),
            "seats": [None if o is None else o.public() for o in self.seats],
        }

    def view_for(self, user_id: int) -> dict[str, Any]:
        """Lo que recibe un jugador sentado: la sala y **su** observación."""
        seat = self.seat_of(user_id)
        if seat is None:
            raise RoomError("No estás sentado en esta mesa")
        view = {"room": self.lobby_view(), "seat": seat, "phrases": list(self.phrases)}
        if self.game is not None:
            view["game"] = observation_to_json(self.game.get_observation(seat))
        return view

    def winners(self) -> tuple[SeatId, ...]:
        game = self._game()
        winner = game.winner
        return tuple(s for s in ALL_SEATS if winner is not None and team_of(s) is winner)


def new_code(rng: random.Random) -> str:
    return "".join(rng.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
