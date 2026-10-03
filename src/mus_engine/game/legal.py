"""Conjunto de acciones legales de un jugador en un momento dado."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from mus_engine.game.actions import Action, BetAction, RaiseAction


@dataclass(frozen=True, slots=True)
class AmountRange:
    """Importes enteros válidos en ``[minimum, maximum]`` (``maximum=None``: sin límite)."""

    minimum: int
    maximum: int | None = None

    def __contains__(self, amount: object) -> bool:
        if not isinstance(amount, int) or isinstance(amount, bool):
            return False
        return amount >= self.minimum and (self.maximum is None or amount <= self.maximum)


@dataclass(frozen=True, slots=True)
class LegalActions:
    """Acciones legales.

    ``actions`` enumera las acciones discretas. Los envites admiten cualquier importe
    de un rango, así que no se enumeran: se describen con ``bet`` y ``raise_``.
    """

    actions: tuple[Action, ...] = ()
    bet: AmountRange | None = None
    raise_: AmountRange | None = None

    def contains(self, action: Action) -> bool:
        if isinstance(action, BetAction):
            return self.bet is not None and action.amount in self.bet
        if isinstance(action, RaiseAction):
            return self.raise_ is not None and action.amount in self.raise_
        return action in self.actions

    def action_types(self) -> frozenset[type[Action]]:
        types = {type(action) for action in self.actions}
        if self.bet is not None:
            types.add(BetAction)
        if self.raise_ is not None:
            types.add(RaiseAction)
        return frozenset(types)

    def __iter__(self) -> Iterator[Action]:
        """Acciones discretas más el importe mínimo de cada rango (ejemplos concretos)."""
        yield from self.actions
        if self.bet is not None:
            yield BetAction(self.bet.minimum)
        if self.raise_ is not None:
            yield RaiseAction(self.raise_.minimum)

    def __bool__(self) -> bool:
        return bool(self.actions) or self.bet is not None or self.raise_ is not None


NO_ACTIONS = LegalActions()
