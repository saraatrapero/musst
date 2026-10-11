"""Ejecución de un bot en un asiento, protegida frente a fallos.

Dos variantes con la misma interfaz:

- :class:`InProcessSeat`: el bot corre en el mismo proceso. Rápido; útil para
  desarrollo y tests. Mide el tiempo, pero no puede interrumpir un bot colgado.
- :class:`IsolatedSeat`: el bot corre en su propio proceso. Tiempo límite real (se
  mata el proceso), un fallo no afecta a nadie más y dos compañeros no pueden compartir
  memoria (sólo se comunican con señas). Es la que usa el torneo oficial.

Cualquier fallo se traduce en :class:`SeatError`, que el torneo convierte en derrota
de la pareja del bot.
"""

from __future__ import annotations

import contextlib
import multiprocessing
import time
import traceback
from collections.abc import Callable
from enum import Enum
from multiprocessing.connection import Connection
from typing import Any, Protocol

from mus_engine.bots.base import Bot, BotContext
from mus_engine.game.actions import Action, SignalAction
from mus_engine.game.observations import Observation

DEFAULT_TIMEOUT = 2.0  # segundos por llamada


class FailureKind(Enum):
    EXCEPTION = "exception"  # el bot lanzó una excepción
    TIMEOUT = "timeout"  # tardó más del límite
    INVALID_RETURN = "invalid_return"  # devolvió algo que no es una acción
    ILLEGAL_ACTION = "illegal_action"  # el motor rechazó su acción
    CRASH = "crash"  # el proceso del bot murió


class SeatError(Exception):
    def __init__(self, kind: FailureKind, detail: str) -> None:
        super().__init__(f"{kind.value}: {detail}")
        self.kind = kind
        self.detail = detail


class SeatController(Protocol):
    def start(self, context: BotContext) -> None: ...
    def decide(self, observation: Observation) -> Action: ...
    def signal(self, observation: Observation) -> SignalAction | None: ...
    def end(self, observation: Observation) -> None: ...
    def close(self) -> None: ...


def _check_action(result: object) -> Action:
    if not isinstance(result, Action) or isinstance(result, SignalAction):
        raise SeatError(FailureKind.INVALID_RETURN, f"decide() devolvió {result!r}")
    return result


def _check_signal(result: object) -> SignalAction | None:
    if result is not None and not isinstance(result, SignalAction):
        raise SeatError(FailureKind.INVALID_RETURN, f"signal() devolvió {result!r}")
    return result


class InProcessSeat:
    def __init__(self, factory: Callable[[], Bot], timeout: float = DEFAULT_TIMEOUT) -> None:
        self._factory = factory
        self._timeout = timeout
        self._bot: Bot | None = None

    def _call(self, method: str, *args: object) -> object:
        if self._bot is None:
            created = self._guard(self._factory)
            if not isinstance(created, Bot):
                raise SeatError(FailureKind.INVALID_RETURN, f"la fábrica devolvió {created!r}")
            self._bot = created
        bound = getattr(self._bot, method)
        return self._guard(lambda: bound(*args))

    def _guard(self, fn: Callable[[], object]) -> object:
        started = time.perf_counter()
        try:
            result = fn()
        except Exception as exc:  # aislamos el fallo del bot, no del motor
            raise SeatError(FailureKind.EXCEPTION, f"{type(exc).__name__}: {exc}") from exc
        if time.perf_counter() - started > self._timeout:
            raise SeatError(FailureKind.TIMEOUT, f"más de {self._timeout} s")
        return result

    def start(self, context: BotContext) -> None:
        self._call("on_game_start", context)

    def decide(self, observation: Observation) -> Action:
        return _check_action(self._call("decide", observation))

    def signal(self, observation: Observation) -> SignalAction | None:
        return _check_signal(self._call("signal", observation))

    def end(self, observation: Observation) -> None:
        self._call("on_game_end", observation)

    def close(self) -> None:
        self._bot = None


def _worker(
    factory: Callable[[], Bot], conn: Connection
) -> None:  # pragma: no cover - otro proceso
    try:
        bot = factory()
    except Exception:
        conn.send(("error", traceback.format_exc(limit=3)))
        return
    conn.send(("ok", None))
    while True:
        try:
            method, arg = conn.recv()
        except EOFError:
            return
        if method == "close":
            return
        try:
            result = getattr(bot, method)(arg)
        except Exception:
            conn.send(("error", traceback.format_exc(limit=3)))
            continue
        try:
            conn.send(("ok", result))
        except Exception:
            conn.send(("error", f"resultado no serializable: {result!r}"))


class IsolatedSeat:
    """Bot en un proceso propio, con tiempo límite real por llamada."""

    def __init__(self, factory: Callable[[], Bot], timeout: float = DEFAULT_TIMEOUT) -> None:
        method = "fork" if "fork" in multiprocessing.get_all_start_methods() else "spawn"
        context: Any = multiprocessing.get_context(method)
        self._timeout = timeout
        self._conn, child = context.Pipe()
        self._process = context.Process(target=_worker, args=(factory, child), daemon=True)
        self._process.start()
        child.close()
        self._receive()  # creación del bot

    def _receive(self) -> object:
        if not self._conn.poll(self._timeout):
            self._kill()
            raise SeatError(FailureKind.TIMEOUT, f"más de {self._timeout} s")
        try:
            status, payload = self._conn.recv()
        except (EOFError, OSError) as exc:
            self._kill()
            raise SeatError(FailureKind.CRASH, "el proceso del bot terminó") from exc
        if status == "error":
            raise SeatError(FailureKind.EXCEPTION, str(payload))
        return payload

    def _call(self, method: str, arg: object) -> object:
        if not self._process.is_alive():
            raise SeatError(FailureKind.CRASH, "el proceso del bot no está vivo")
        try:
            self._conn.send((method, arg))
        except (BrokenPipeError, OSError) as exc:
            self._kill()
            raise SeatError(FailureKind.CRASH, "el proceso del bot terminó") from exc
        return self._receive()

    def _kill(self) -> None:
        if self._process.is_alive():
            self._process.kill()
        self._process.join(timeout=1)

    def start(self, context: BotContext) -> None:
        self._call("on_game_start", context)

    def decide(self, observation: Observation) -> Action:
        return _check_action(self._call("decide", observation))

    def signal(self, observation: Observation) -> SignalAction | None:
        return _check_signal(self._call("signal", observation))

    def end(self, observation: Observation) -> None:
        self._call("on_game_end", observation)

    def close(self) -> None:
        with contextlib.suppress(BrokenPipeError, OSError):
            self._conn.send(("close", None))
        self._process.join(timeout=1)
        self._kill()
        self._conn.close()
