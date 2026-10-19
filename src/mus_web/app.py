"""Aplicación FastAPI: API de cuentas y salas, WebSocket de la mesa y web estática.

Seguridad:

- Contraseñas con scrypt; sesiones en cookie ``HttpOnly`` + ``SameSite=Lax`` cuyo token
  sólo se guarda cifrado con SHA-256.
- El WebSocket comprueba la sesión, que el jugador esté sentado y el ``Origin`` (evita
  que otra web abra la mesa en nombre del usuario).
- Cada jugador recibe **sólo su observación**: nunca el estado de la partida.
- Bloqueo temporal tras varios inicios de sesión fallidos.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import random
import secrets
import time
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import timedelta
from importlib import resources
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import select, text
from starlette.websockets import WebSocketDisconnect

from mus_engine.ai.profiles import PlayerProfile
from mus_web.avatars_pack import avatars_by_id, load_pack
from mus_web.codec import record_to_json
from mus_web.db import Database, GameRow, GameSeat, LoginSession, ProfileRow, User, utcnow
from mus_web.rooms import BOT_LEVELS, DEFAULT_LEVEL, Mode, Room, RoomError, new_code
from mus_web.security import (
    CredentialError,
    check_password,
    check_username,
    hash_password,
    new_token,
    token_digest,
    verify_password,
)

COOKIE = "musst_session"
DEFAULT_DATABASE_URL = "sqlite:///musst.db"
MAX_FAILED_LOGINS = 5
LOCKOUT_SECONDS = 300
MAX_ROOMS = 500
MAX_MESSAGE_BYTES = 4096
DELETED_NAME = "(cuenta borrada)"
AVATAR_POSES = frozenset(
    {"frente", "izquierda", "derecha", "enfrente", "contento", "fastidiado", "pillo"}
)


@dataclass(slots=True)
class Settings:
    database_url: str = DEFAULT_DATABASE_URL
    secure_cookies: bool = False
    session_days: int = 30
    bot_delay: float = 0.9  # segundos que «piensa» un bot (para poder seguir la mesa)
    hand_pause: float = 3.0  # pausa al acabar una mano para ver las cartas enseñadas
    tick_interval: float = 1.5  # un momento del reloj de miradas, con señas
    password_n: int = 2**14  # coste de scrypt (se reduce en los tests)
    seed_source: Callable[[], int] = field(default=lambda: secrets.randbits(63))

    @classmethod
    def from_env(cls) -> Settings:  # pragma: no cover - configuración de despliegue
        url = postgres_driver(os.environ.get("MUSST_DATABASE_URL", DEFAULT_DATABASE_URL))
        return cls(database_url=url, secure_cookies=os.environ.get("MUSST_SECURE") == "1")


def postgres_driver(url: str) -> str:
    """Usa psycopg 3 con las URL que dan los servicios (``postgres://…``)."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url.removeprefix(prefix)
    return url


# --- Esquemas de entrada ---------------------------------------------------------------


class RegisterIn(BaseModel):
    username: str
    password: str
    avatar: str
    consent: bool


class LoginIn(BaseModel):
    username: str
    password: str


class AvatarIn(BaseModel):
    avatar: str


class DeleteIn(BaseModel):
    password: str


class RoomIn(BaseModel):
    mode: str
    signals: bool = False
    phrases: bool = True
    level: str = DEFAULT_LEVEL


# --- Salas en memoria --------------------------------------------------------------------


class Hub:
    """Salas activas, conexiones abiertas y el bucle que mueve cada partida."""

    def __init__(self, settings: Settings, db: Database) -> None:
        self.settings = settings
        self.db = db
        self.rooms: dict[str, Room] = {}
        self.sockets: dict[str, dict[WebSocket, int]] = defaultdict(dict)
        self.wakeups: dict[str, asyncio.Event] = {}
        self.tasks: set[asyncio.Task[None]] = set()
        self.rng = random.Random(settings.seed_source())

    def user_from_token(self, token: str | None) -> User | None:
        if not token:
            return None
        with self.db.session() as session:
            login = session.get(LoginSession, token_digest(token))
            if login is None or login.expires_at < utcnow():
                return None
            user = login.user
            session.expunge(user)
            return user

    def create(
        self, host: User, mode: Mode, signals: bool, phrases: bool, level: str = DEFAULT_LEVEL
    ) -> Room:
        if len(self.rooms) >= MAX_ROOMS:
            self._purge()
        if len(self.rooms) >= MAX_ROOMS:
            raise RoomError("Hay demasiadas salas abiertas; prueba en un rato")
        code = new_code(self.rng)
        while code in self.rooms:  # pragma: no cover - colisión improbable
            code = new_code(self.rng)
        room = Room(
            code=code,
            mode=mode,
            signals=signals,
            phrases_enabled=phrases,
            host_id=host.id,
            avatars=load_pack()[1],
            rng=random.Random(self.rng.getrandbits(63)),
            level=level,
        )
        room.join(host.id, host.username, avatars_by_id()[host.avatar_id])
        self.rooms[code] = room
        return room

    def _purge(self) -> None:
        for code, room in list(self.rooms.items()):
            if room.finished or not self.sockets.get(code):
                self.rooms.pop(code)
                self.sockets.pop(code, None)
                self.wakeups.pop(code, None)

    def room(self, code: str) -> Room:
        room = self.rooms.get(code.upper())
        if room is None:
            raise HTTPException(404, "Esa sala no existe")
        return room

    def launch(self, room: Room) -> None:
        self.wakeups[room.code] = asyncio.Event()
        task = asyncio.create_task(self._drive(room))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def wake(self, room: Room) -> None:
        wakeup = self.wakeups.get(room.code)
        if wakeup is not None:
            wakeup.set()

    async def _drive(self, room: Room) -> None:
        """Hace jugar a los bots y avanza el reloj de miradas hasta el final."""
        s = self.settings
        wakeup = self.wakeups[room.code]
        hand = room.hand_number
        while not room.finished:
            if room.bot_to_act() is not None:
                pause = s.hand_pause if room.hand_number != hand else s.bot_delay
                hand = room.hand_number
                await asyncio.sleep(pause)
                room.bot_step()
                await self.broadcast(room)
                continue
            if room.signals:
                try:
                    await asyncio.wait_for(wakeup.wait(), s.tick_interval)
                except TimeoutError:
                    room.clock()
                    await self.broadcast(room)
            else:
                await wakeup.wait()
            wakeup.clear()
        self.save(room)
        await self.broadcast(room)

    async def broadcast(self, room: Room) -> None:
        for socket, user_id in list(self.sockets[room.code].items()):
            with contextlib.suppress(Exception):
                await socket.send_json(room.view_for(user_id))

    def load_profiles(self, room: Room) -> dict[int, PlayerProfile]:
        ids = [o.user_id for o in room.seats if o is not None and o.user_id is not None]
        with self.db.session() as session:
            rows = session.scalars(select(ProfileRow).where(ProfileRow.user_id.in_(ids))).all()
            return {row.user_id: PlayerProfile.from_json(row.counts) for row in rows}

    def save(self, room: Room) -> None:
        """Guarda la partida terminada y actualiza las estadísticas de los usuarios."""
        if room.saved or room.game is None:
            return
        room.saved = True
        state = room.game.get_state()
        winners = room.winners()
        with self.db.session() as session:
            row = GameRow(
                mode=room.mode.value,
                signals=room.signals,
                winner_team=None if state.winner is None else state.winner.name,
                final_tantos=list(state.score.tantos),
                final_games=list(state.score.games),
                record=record_to_json(room.game.record),
            )
            session.add(row)
            for seat, occupant in enumerate(room.seats):
                assert occupant is not None
                won = seat in winners
                user = None if occupant.user_id is None else session.get(User, occupant.user_id)
                if user is not None:
                    user.games_played += 1
                    user.games_won += int(won)
                row.seats.append(
                    GameSeat(
                        seat=seat,
                        user_id=None if user is None else user.id,
                        bot=None if occupant.bot is None else occupant.bot.name,
                        avatar_id=occupant.avatar.id,
                        won=won,
                    )
                )
            learned = room.profiles_learned()
            for user_id, profile in learned.items():
                if session.get(User, user_id) is None:  # borró su cuenta durante la partida
                    continue
                stored = session.get(ProfileRow, user_id)
                if stored is None:
                    session.add(ProfileRow(user_id=user_id, counts=profile.to_json()))
                else:
                    total = PlayerProfile.from_json(stored.counts) + profile
                    stored.counts = total.to_json()


def current_user(request: Request, musst_session: Annotated[str | None, Cookie()] = None) -> User:
    hub: Hub = request.app.state.hub
    user = hub.user_from_token(musst_session)
    if user is None:
        raise HTTPException(401, "Inicia sesión")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


# --- Aplicación ----------------------------------------------------------------------------


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    db = Database(settings.database_url)
    hub = Hub(settings, db)
    failed: dict[str, list[float]] = defaultdict(list)

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        for task in list(hub.tasks):
            task.cancel()

    static = resources.files("mus_web").joinpath("static")

    def avatar_images(avatar_id: str) -> list[str]:
        """Poses dibujadas que existen (``static/avatars/<id>/<pose>.png``)."""
        folder = static.joinpath("avatars", avatar_id)
        if not folder.is_dir():
            return []
        return sorted(
            f.name.removesuffix(".png")
            for f in folder.iterdir()
            if f.name.endswith(".png") and f.name.removesuffix(".png") in AVATAR_POSES
        )

    app = FastAPI(title="MUS.ST", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.hub = hub
    app.state.db = db

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    # --- Sesión ------------------------------------------------------------------------

    def open_session(response: Response, user: User) -> None:
        token = new_token()
        with db.session() as session:
            session.add(
                LoginSession(
                    token_hash=token_digest(token),
                    user_id=user.id,
                    expires_at=utcnow() + timedelta(days=settings.session_days),
                )
            )
        response.set_cookie(
            COOKIE,
            token,
            max_age=settings.session_days * 86400,
            httponly=True,
            samesite="lax",
            secure=settings.secure_cookies,
        )

    def me_json(user: User) -> dict[str, Any]:
        return {
            "id": user.id,
            "username": user.username,
            "avatar": user.avatar_id,
            "games_played": user.games_played,
            "games_won": user.games_won,
            "created_at": user.created_at.isoformat(),
        }

    def check_avatar(avatar: str) -> str:
        if avatar not in avatars_by_id():
            raise HTTPException(422, "Ese avatar no existe")
        return avatar

    # --- Cuentas -------------------------------------------------------------------------

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        """Para el alojamiento: responde si el servidor y la base de datos funcionan."""
        with db.session() as session:
            session.execute(text("SELECT 1"))
        return {"status": "ok"}

    @app.get("/api/avatars")
    def avatars() -> dict[str, Any]:
        notice, pack = load_pack()
        return {
            "aviso": notice,
            "avatars": [a.public() | {"images": avatar_images(a.id)} for a in pack],
        }

    @app.post("/api/register", status_code=201)
    def register(body: RegisterIn, response: Response) -> dict[str, Any]:
        try:
            username = check_username(body.username)
            password = check_password(body.password)
        except CredentialError as error:
            raise HTTPException(422, str(error)) from error
        if not body.consent:
            raise HTTPException(422, "Hace falta aceptar el tratamiento de datos")
        check_avatar(body.avatar)
        with db.session() as session:
            taken = session.scalar(select(User).where(User.username == username))
            if taken is not None:
                raise HTTPException(409, "Ese nombre de usuario ya existe")
            user = User(
                username=username,
                password_hash=hash_password(password, n=settings.password_n),
                avatar_id=body.avatar,
            )
            session.add(user)
        open_session(response, user)
        return me_json(user)

    @app.post("/api/login")
    def login(body: LoginIn, response: Response) -> dict[str, Any]:
        now = time.monotonic()
        key = body.username.lower()
        failed[key] = [t for t in failed[key] if now - t < LOCKOUT_SECONDS]
        if len(failed[key]) >= MAX_FAILED_LOGINS:
            raise HTTPException(429, "Demasiados intentos; espera unos minutos")
        with db.session() as session:
            user = session.scalar(select(User).where(User.username == body.username))
            if user is None or not verify_password(body.password, user.password_hash):
                failed[key].append(now)
                raise HTTPException(401, "Usuario o contraseña incorrectos")
        failed.pop(key, None)
        open_session(response, user)
        return me_json(user)

    @app.post("/api/logout")
    def logout(
        response: Response, musst_session: Annotated[str | None, Cookie()] = None
    ) -> dict[str, bool]:
        if musst_session:
            with db.session() as session:
                login = session.get(LoginSession, token_digest(musst_session))
                if login is not None:
                    session.delete(login)
        response.delete_cookie(COOKIE)
        return {"ok": True}

    @app.get("/api/me")
    def me(user: CurrentUser) -> dict[str, Any]:
        return me_json(user)

    @app.put("/api/me/avatar")
    def set_avatar(body: AvatarIn, user: CurrentUser) -> dict[str, Any]:
        check_avatar(body.avatar)
        with db.session() as session:
            row = session.get(User, user.id)
            assert row is not None
            row.avatar_id = body.avatar
        user.avatar_id = body.avatar
        return me_json(user)

    @app.get("/api/me/games")
    def my_games(user: CurrentUser) -> list[dict[str, Any]]:
        with db.session() as session:
            seats = session.scalars(
                select(GameSeat)
                .where(GameSeat.user_id == user.id)
                .order_by(GameSeat.game_id.desc())
                .limit(50)
            ).all()
            return [
                {
                    "id": s.game.id,
                    "finished_at": s.game.finished_at.isoformat(),
                    "mode": s.game.mode,
                    "signals": s.game.signals,
                    "seat": s.seat,
                    "won": s.won,
                    "tantos": s.game.final_tantos,
                }
                for s in seats
            ]

    def profile_json(user_id: int) -> dict[str, object]:
        with db.session() as session:
            row = session.get(ProfileRow, user_id)
            profile = PlayerProfile() if row is None else PlayerProfile.from_json(row.counts)
        return profile.summary()

    @app.get("/api/me/profile")
    def my_profile(user: CurrentUser) -> dict[str, object]:
        """Cómo juegas, según la IA (Fase E)."""
        return profile_json(user.id)

    @app.get("/api/me/export")
    def export(user: CurrentUser) -> dict[str, Any]:
        """Todos los datos del usuario (derecho de acceso)."""
        with db.session() as session:
            row = session.get(User, user.id)
            assert row is not None
            games = [
                {"seat": s.seat, "won": s.won, "mode": s.game.mode, "record": s.game.record}
                for s in row.seats
            ]
            counts = {} if row.profile is None else dict(row.profile.counts)
            return {
                "user": me_json(row),
                "consent_at": row.consent_at.isoformat(),
                "games": games,
                "profile": counts,
            }

    @app.delete("/api/me")
    def delete_me(body: DeleteIn, user: CurrentUser, response: Response) -> dict[str, bool]:
        """Borra la cuenta, sus sesiones y su participación en partidas."""
        with db.session() as session:
            row = session.get(User, user.id)
            assert row is not None
            if not verify_password(body.password, row.password_hash):
                raise HTTPException(401, "Contraseña incorrecta")
            for seat in row.seats:  # su nombre desaparece también de los registros
                record = dict(seat.game.record)
                names = list(record["player_names"])
                names[seat.seat] = DELETED_NAME
                record["player_names"] = names
                seat.game.record = record
            session.delete(row)
        response.delete_cookie(COOKIE)
        return {"ok": True}

    # --- Salas ---------------------------------------------------------------------------

    def room_error(error: RoomError) -> HTTPException:
        return HTTPException(409, str(error))

    @app.post("/api/rooms", status_code=201)
    def create_room(body: RoomIn, user: CurrentUser) -> dict[str, Any]:
        try:
            mode = Mode(body.mode)
        except ValueError as error:
            raise HTTPException(422, "Modo de juego desconocido") from error
        if body.level not in BOT_LEVELS:
            raise HTTPException(422, "Nivel de bots desconocido")
        try:
            room = hub.create(user, mode, body.signals, body.phrases, body.level)
        except RoomError as error:
            raise HTTPException(503, str(error)) from error
        return room.lobby_view()

    @app.get("/api/rooms/{code}")
    def get_room(code: str, user: CurrentUser) -> dict[str, Any]:
        return hub.room(code).lobby_view()

    @app.post("/api/rooms/{code}/join")
    async def join_room(code: str, user: CurrentUser) -> dict[str, Any]:
        room = hub.room(code)
        try:
            room.join(user.id, user.username, avatars_by_id()[user.avatar_id])
        except RoomError as error:
            raise room_error(error) from error
        await hub.broadcast(room)
        return room.lobby_view()

    @app.post("/api/rooms/{code}/leave")
    async def leave_room(code: str, user: CurrentUser) -> dict[str, Any]:
        room = hub.room(code)
        try:
            room.leave(user.id)
        except RoomError as error:
            raise room_error(error) from error
        await hub.broadcast(room)
        return room.lobby_view()

    @app.post("/api/rooms/{code}/start")
    async def start_room(code: str, user: CurrentUser) -> dict[str, Any]:
        room = hub.room(code)
        try:
            room.start(user.id, settings.seed_source(), profiles=hub.load_profiles(room))
        except RoomError as error:
            raise room_error(error) from error
        hub.launch(room)
        await hub.broadcast(room)
        return room.lobby_view()

    # --- Mesa ----------------------------------------------------------------------------

    @app.websocket("/ws/rooms/{code}")
    async def table(socket: WebSocket, code: str) -> None:
        origin = socket.headers.get("origin")
        if origin is not None and urlsplit(origin).netloc != socket.headers.get("host"):
            await socket.close(code=4403)
            return
        user = hub.user_from_token(socket.cookies.get(COOKIE))
        room = hub.rooms.get(code.upper())
        if user is None or room is None or room.seat_of(user.id) is None:
            await socket.close(code=4401)
            return
        await socket.accept()
        hub.sockets[room.code][socket] = user.id
        try:
            await socket.send_json(room.view_for(user.id))
            while True:
                text = await socket.receive_text()
                await handle(socket, room, user.id, text)
        except WebSocketDisconnect:
            pass
        finally:
            hub.sockets[room.code].pop(socket, None)

    async def handle(socket: WebSocket, room: Room, user_id: int, text: str) -> None:
        try:
            if len(text) > MAX_MESSAGE_BYTES:
                raise RoomError("Mensaje demasiado largo")
            try:
                message = json.loads(text)
            except json.JSONDecodeError as error:
                raise RoomError("Mensaje no válido") from error
            if not isinstance(message, dict) or set(message) != {"action"}:
                raise RoomError("Se esperaba {'action': ...}")
            room.human_action(user_id, message["action"])
        except RoomError as error:
            await socket.send_json({"error": str(error)})
            return
        await hub.broadcast(room)
        hub.wake(room)

    # --- Web estática --------------------------------------------------------------------

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(str(static.joinpath("index.html")))

    app.mount("/static", StaticFiles(directory=str(static)), name="static")
    return app
