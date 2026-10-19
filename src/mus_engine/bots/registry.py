"""Registro de bots: los incluidos en el motor y los contribuidos en ``mus_bots``.

Para añadir un bot (requisito 2.1) basta con crear un módulo en ``src/mus_bots/``
con una clase que herede de :class:`~mus_engine.bots.base.Bot` y un ``name`` único.
No hay que tocar nada más: el registro lo descubre solo y los tests de conformidad
se le aplican automáticamente.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from collections.abc import Callable

from mus_engine.bots.base import Bot
from mus_engine.bots.medium_bot import MediumBot
from mus_engine.bots.random_bot import RandomBot
from mus_engine.bots.simple_bot import SimpleBot

BotFactory = Callable[[], Bot]

BUILTIN: tuple[type[Bot], ...] = (RandomBot, SimpleBot, MediumBot)
CONTRIB_PACKAGE = "mus_bots"


class RegistryError(Exception):
    """Dos bots con el mismo nombre o un bot mal definido."""


def discover_contrib(package: str = CONTRIB_PACKAGE) -> tuple[type[Bot], ...]:
    """Clases de bot definidas en los módulos del paquete de contribuciones."""
    root = importlib.import_module(package)
    found: list[type[Bot]] = []
    for info in sorted(pkgutil.iter_modules(root.__path__), key=lambda i: i.name):
        module = importlib.import_module(f"{package}.{info.name}")
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(cls, Bot)
                and not inspect.isabstract(cls)
                and cls.__module__ == module.__name__
            ):
                found.append(cls)
    return tuple(found)


def all_bots(package: str = CONTRIB_PACKAGE) -> dict[str, type[Bot]]:
    """Todos los bots disponibles, por nombre."""
    bots: dict[str, type[Bot]] = {}
    for cls in (*BUILTIN, *discover_contrib(package)):
        if not isinstance(cls.name, str) or not cls.name.strip() or cls.name == Bot.name:
            raise RegistryError(f"El bot {cls.__qualname__} necesita un 'name' propio")
        if cls.name in bots:
            raise RegistryError(f"Nombre de bot repetido: {cls.name!r}")
        bots[cls.name] = cls
    return bots
