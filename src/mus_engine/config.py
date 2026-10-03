"""Configuración de la partida.

Todos los valores numéricos de reglas viven aquí. Cada campo indica su origen:
un artículo del Reglamento FEM (``C.<capítulo>-<artículo>``) o una decisión aprobada
(``D-xx``, ver ``docs/rules.md``) cuando el reglamento no lo define.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mus_engine.errors import InvalidConfigError


class DeckType(Enum):
    """Barajas soportadas. El reglamento sólo admite la española de 40 (C.II-3)."""

    SPANISH_40 = "spanish_40"


@dataclass(frozen=True, slots=True)
class GameConfig:
    """Parámetros de reglas de una partida. Inmutable y validada al construirse."""

    # Tanteo de un juego. Intro-E: entre 40 y 60 en torneos FEM; 40 por defecto.
    target_score: int = 40
    # Juegos necesarios para ganar la partida (Intro-E: 5 en preclasificación).
    games_to_win: int = 1

    # Baraja y modalidad (C.II-3: ocho reyes y ocho ases).
    deck_type: DeckType = DeckType.SPANISH_40
    kings_are_threes: bool = True
    aces_are_twos: bool = True
    cards_per_hand: int = 4

    # Descartes (D-13).
    min_discard: int = 1
    max_discard: int = 4

    # Envites (Voc. "Envido" = 2; D-18 para el revoque).
    min_bet: int = 2
    min_raise: int = 2

    # Valor de las jugadas (D-02).
    points_pareja: int = 1
    points_medias: int = 2
    points_duples: int = 3
    points_juego_31: int = 3
    points_juego_other: int = 2
    points_punto: int = 1
    points_passed_lance: int = 1  # grande/chica "en paso"

    # Negada (Voc. "Negada") y deje (C.VII-1, Voc. "Deje"; D-16).
    points_negada: int = 1
    points_deje: int = 1

    # Representación del marcador (D-19). No afecta a las reglas.
    tantos_per_amarraco: int = 5

    # Comprobación de invariantes tras cada transición.
    debug_invariants: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.deck_type, DeckType):
            raise InvalidConfigError(f"deck_type no soportado: {self.deck_type!r}")
        for name in (
            "target_score",
            "games_to_win",
            "cards_per_hand",
            "min_discard",
            "max_discard",
            "min_bet",
            "min_raise",
            "points_pareja",
            "points_medias",
            "points_duples",
            "points_juego_31",
            "points_juego_other",
            "points_punto",
            "points_passed_lance",
            "points_negada",
            "points_deje",
            "tantos_per_amarraco",
        ):
            value = getattr(self, name)
            # bool es subclase de int: se rechaza explícitamente.
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise InvalidConfigError(f"{name} debe ser un entero >= 1 (recibido {value!r})")
        if self.cards_per_hand != 4:
            raise InvalidConfigError("El Mus se juega con 4 naipes por jugador")
        if self.max_discard > self.cards_per_hand:
            raise InvalidConfigError("max_discard no puede superar cards_per_hand")
        if self.min_discard > self.max_discard:
            raise InvalidConfigError("min_discard no puede superar max_discard")
        if not (self.points_pareja < self.points_medias < self.points_duples):
            raise InvalidConfigError("Se requiere pareja < medias < duples")
        if self.points_juego_other > self.points_juego_31:
            raise InvalidConfigError("El juego de 31 no puede valer menos que otro juego")
