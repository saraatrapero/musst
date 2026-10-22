"""Avatares: carga y validación del paquete de datos (IA-10).

Los avatares son datos, no código: ``avatars/pack.json`` define apodo, estilo, color y
frases de cada personaje. Las imágenes de las caricaturas, cuando existan, se colocan en
``static/avatars/<id>/`` (``frente.png``, ``izquierda.png``, ``derecha.png``,
``enfrente.png``, ``contento.png``, ``fastidiado.png``); mientras tanto la mesa dibuja un
avatar provisional.

Las frases sólo reaccionan a hechos **públicos** (envites, órdagos, resultados…), nunca a
las cartas de quien habla: una frase no puede dar pistas.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

MOMENTS = frozenset(
    {
        "pide_mus",
        "corta_mus",
        "pasa",
        "envida",
        "ordago",
        "acepta",
        "rechaza",
        "gana_lance",
        "pierde_lance",
        "gana_partida",
        "pierde_partida",
        "revela_31",
    }
)


class AvatarPackError(ValueError):
    """El paquete de avatares está mal formado."""


@dataclass(frozen=True, slots=True)
class Avatar:
    id: str
    nickname: str
    style: str
    color: str
    phrases: dict[str, tuple[str, ...]]

    def public(self) -> dict[str, object]:
        return {
            "id": self.id,
            "nickname": self.nickname,
            "style": self.style,
            "color": self.color,
            "sample": self.sample,
        }

    @property
    def sample(self) -> str:
        """Una frase suya para «escuchar su voz» al elegirlo."""
        for moment in ("gana_partida", "envida", *sorted(self.phrases)):
            if moment in self.phrases:
                return self.phrases[moment][0]
        return f"Soy {self.nickname}."


def parse_pack(data: object) -> tuple[str, tuple[Avatar, ...]]:
    if not isinstance(data, dict) or not isinstance(data.get("avatars"), list):
        raise AvatarPackError("El paquete necesita una lista 'avatars'")
    notice = data.get("aviso")
    if not isinstance(notice, str) or not notice.strip():
        raise AvatarPackError("El paquete necesita el 'aviso' de parodia")
    avatars: list[Avatar] = []
    for raw in data["avatars"]:
        if not isinstance(raw, dict):
            raise AvatarPackError(f"Avatar mal formado: {raw!r}")
        for key in ("id", "nickname", "style", "color"):
            if not isinstance(raw.get(key), str) or not raw[key].strip():
                raise AvatarPackError(f"Avatar sin '{key}': {raw!r}")
        phrases = raw.get("phrases", {})
        if not isinstance(phrases, dict):
            raise AvatarPackError(f"'phrases' debe ser un objeto en {raw['id']}")
        unknown = set(phrases) - MOMENTS
        if unknown:
            raise AvatarPackError(f"Momentos desconocidos en {raw['id']}: {sorted(unknown)}")
        clean: dict[str, tuple[str, ...]] = {}
        for moment, lines in phrases.items():
            if (
                not isinstance(lines, list)
                or not lines
                or not all(isinstance(x, str) and x.strip() for x in lines)
            ):
                raise AvatarPackError(f"Frases vacías o no válidas en {raw['id']}.{moment}")
            clean[moment] = tuple(lines)
        avatars.append(Avatar(raw["id"], raw["nickname"], raw["style"], raw["color"], clean))
    ids = [a.id for a in avatars]
    if len(set(ids)) != len(ids):
        raise AvatarPackError("Hay avatares con el mismo id")
    if not avatars:
        raise AvatarPackError("El paquete no tiene avatares")
    return notice, tuple(avatars)


@lru_cache(maxsize=1)
def load_pack() -> tuple[str, tuple[Avatar, ...]]:
    text = resources.files("mus_web.avatars").joinpath("pack.json").read_text(encoding="utf-8")
    return parse_pack(json.loads(text))


def avatars_by_id() -> dict[str, Avatar]:
    return {a.id: a for a in load_pack()[1]}
