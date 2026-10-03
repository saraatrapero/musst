"""Fija la salida exacta del barajado para una semilla.

Si este test falla, las partidas guardadas (semilla + acciones) dejarían de
reproducirse igual: cualquier cambio en ``Rng`` es una ruptura de compatibilidad.
"""

from mus_engine.cards import Deck
from mus_engine.rng import Rng

GOLDEN_12345 = (
    "6E 12E 10C 3B 7E 4O 2O 7O 6O 2E 4C 11O 12O 6B 7B 5O 4E 5E 10O 7C "
    "5C 1B 3E 12B 10E 4B 12C 2B 11C 3O 3C 11B 5B 11E 1E 1O 10B 2C 6C 1C"
)


def test_shuffle_seed_12345_is_stable() -> None:
    deck, rng = Deck.standard().shuffled(Rng(12345))
    assert " ".join(card.code for card in deck) == GOLDEN_12345
    assert rng == Rng(12345, stream=1)
