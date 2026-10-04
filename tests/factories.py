"""Utilidades de test para construir estados concretos.

Sólo para tests: permiten colocar una partida en un estado preciso (p. ej. terminada o
con un marcador dado) sin recorrer todas las jugadas. El código de producción nunca
expone esta posibilidad.
"""

from __future__ import annotations

from mus_engine import Game, GameState


def game_with_state(state: GameState) -> Game:
    game = Game(players=state.table, config=state.config, seed=state.rng.seed)
    game._state = state
    return game


def started_game(seed: int = 12345, **config: object) -> Game:
    from mus_engine import GameConfig

    game = Game(players=("Ana", "Bea", "Carlos", "Dani"), config=GameConfig(**config), seed=seed)  # type: ignore[arg-type]
    game.start()
    return game


def game_at_lance(
    hands: tuple[str, str, str, str],
    *,
    dealer: int = 3,
    tantos: tuple[int, int] = (0, 0),
    games: tuple[int, int] = (0, 0),
    seed: int = 1,
    **config: object,
) -> Game:
    """Partida con el mus recién cortado (empieza grande) y manos elegidas.

    ``hands[i]`` son los códigos de los naipes del asiento ``i``. El resto de la baraja
    forma el mazo, de modo que los invariantes de naipes se siguen cumpliendo.
    """
    import dataclasses

    from mus_engine import GameScore, Phase
    from mus_engine.cards import SPANISH_40_CARDS, Deck, cards_from_codes
    from mus_engine.game.flow import run_automatic
    from mus_engine.rules import LanceType

    game = started_game(seed=seed, first_dealer=dealer, **config)
    state = game.get_state()
    hand = state.current_hand
    cards = tuple(cards_from_codes(h) for h in hands)
    used = {c for h in cards for c in h}
    stock = Deck(tuple(c for c in SPANISH_40_CARDS if c not in used))
    hand = dataclasses.replace(
        hand,
        hands=cards,
        stock=stock,
        discard_pile=(),
        mus=dataclasses.replace(hand.mus, cut_by=hand.mano),
        lance=LanceType.GRANDE,
    )
    state = state.evolve(hand=hand, phase=Phase.LANCE_START, score=GameScore(tantos, games))
    state, _ = run_automatic(state)
    return game_with_state(state)
