"""Generador aleatorio determinista, inmutable y estable entre versiones de Python.

No se usa ``random.Random`` porque su algoritmo de barajado no está garantizado entre
versiones del intérprete, y una partida guardada (semilla + acciones) debe poder
reproducirse siempre igual. Los números se obtienen de SHA-256 en modo contador:

    bloque_i = SHA-256(f"mus-engine:{seed}:{stream}:{i}")

El estado es un valor (``seed``, ``stream``) que vive dentro del estado de la partida:
cada barajado consume un ``stream`` nuevo y devuelve el siguiente ``Rng``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")

_DOMAIN = "mus-engine"


@dataclass(frozen=True, slots=True)
class Rng:
    """Estado del generador. Inmutable: cada operación devuelve un ``Rng`` nuevo."""

    seed: int
    stream: int = 0

    def shuffle(self, items: Sequence[T]) -> tuple[tuple[T, ...], Rng]:
        """Fisher–Yates sobre una copia de ``items``. No modifica la entrada."""
        result = list(items)
        numbers = _UniformSource(self.seed, self.stream)
        for i in range(len(result) - 1, 0, -1):
            j = numbers.below(i + 1)
            result[i], result[j] = result[j], result[i]
        return tuple(result), self.advance()

    def choice_index(self, size: int) -> tuple[int, Rng]:
        """Índice uniforme en ``[0, size)``."""
        if size <= 0:
            raise ValueError("size debe ser positivo")
        return _UniformSource(self.seed, self.stream).below(size), self.advance()

    def advance(self) -> Rng:
        return Rng(self.seed, self.stream + 1)


class _UniformSource:
    """Flujo de enteros uniformes derivado de (seed, stream). Uso interno."""

    def __init__(self, seed: int, stream: int) -> None:
        self._bytes = self._byte_stream(seed, stream)

    @staticmethod
    def _byte_stream(seed: int, stream: int) -> Iterator[int]:
        counter = 0
        while True:
            block = hashlib.sha256(f"{_DOMAIN}:{seed}:{stream}:{counter}".encode()).digest()
            yield from block
            counter += 1

    def _bits(self, n_bytes: int) -> int:
        value = 0
        for _ in range(n_bytes):
            value = (value << 8) | next(self._bytes)
        return value

    def below(self, bound: int) -> int:
        """Entero uniforme en ``[0, bound)`` por muestreo con rechazo (sin sesgo de módulo)."""
        n_bytes = max(1, (bound.bit_length() + 7) // 8)
        space = 1 << (8 * n_bytes)
        limit = space - (space % bound)
        while True:
            value = self._bits(n_bytes)
            if value < limit:
                return value % bound
