"""Lances de una jugada (Voc. "Lance"; C.VII-2: se habla y se tantea en este orden)."""

from __future__ import annotations

from enum import Enum


class LanceType(Enum):
    GRANDE = "grande"
    CHICA = "chica"
    PARES = "pares"
    JUEGO = "juego"
    PUNTO = "punto"  # sólo si nadie tiene juego (Voc. "No Juego")
