"""Acciones tipadas que un jugador puede solicitar al motor.

Una acción es sólo una **petición**: no tiene efectos por sí misma. Su construcción
valida la forma de los datos (tipos); si la acción es legal en el estado actual lo
decide el motor en ``Game.apply_action``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from mus_engine.cards.card import Card
from mus_engine.errors import InvalidBetError, InvalidDiscardError


@dataclass(frozen=True, slots=True)
class Action:
    """Base de todas las acciones."""


@dataclass(frozen=True, slots=True)
class MusAction(Action):
    """Pedir mus (Voc. "Mus": pedir descarte)."""


@dataclass(frozen=True, slots=True)
class CutMusAction(Action):
    """Cortar el mus ("no hay mus"; para la mano equivale a "paso", Voc. "Paso")."""


@dataclass(frozen=True, slots=True, init=False)
class DiscardAction(Action):
    """Descartar los naipes indicados. Se rechazan duplicados ya en la construcción."""

    cards: frozenset[Card]

    def __init__(self, cards: Iterable[Card]) -> None:
        if isinstance(cards, (str, bytes)) or not isinstance(cards, Iterable):
            raise InvalidDiscardError(f"Se esperaba una colección de naipes: {cards!r}")
        items = tuple(cards)
        for card in items:
            if not isinstance(card, Card):
                raise InvalidDiscardError(f"No es un naipe: {card!r}")
        if len(set(items)) != len(items):
            raise InvalidDiscardError("No se puede descartar el mismo naipe dos veces")
        object.__setattr__(self, "cards", frozenset(items))


@dataclass(frozen=True, slots=True)
class PassAction(Action):
    """Pasar (no envidar) en un lance."""


@dataclass(frozen=True, slots=True)
class BetAction(Action):
    """Envidar ``amount`` tantos (Voc. "Envido": 2, o el número que se diga)."""

    amount: int

    def __post_init__(self) -> None:
        _check_amount(self.amount)


@dataclass(frozen=True, slots=True)
class RaiseAction(Action):
    """Revocar (reenvidar): subir ``amount`` tantos sobre el envite pendiente (D-18)."""

    amount: int

    def __post_init__(self) -> None:
        _check_amount(self.amount)


@dataclass(frozen=True, slots=True)
class AcceptAction(Action):
    """Querer el envite o el órdago pendiente."""


@dataclass(frozen=True, slots=True)
class RejectAction(Action):
    """No querer el envite o el órdago pendiente."""


@dataclass(frozen=True, slots=True)
class OrdagoAction(Action):
    """Órdago: apostar el juego completo en el lance en curso (Voc. "Órdago", C.IV-6)."""


def _check_amount(amount: object) -> None:
    if not isinstance(amount, int) or isinstance(amount, bool) or amount < 1:
        raise InvalidBetError(f"El importe debe ser un entero positivo: {amount!r}")
