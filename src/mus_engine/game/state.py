"""Estado completo de la partida (FULL_GAME_STATE).

Todo es inmutable: cada transición produce un estado nuevo. Este estado **contiene
información secreta** (manos de todos, mazo, semilla); nunca debe entregarse a un
jugador o bot: para eso existe la observación por jugador.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from mus_engine.cards.card import Card
from mus_engine.cards.deck import Deck
from mus_engine.config import GameConfig
from mus_engine.game.phases import Phase
from mus_engine.players.player import Table
from mus_engine.players.seating import SeatId, TeamId, seat
from mus_engine.rng import Rng
from mus_engine.scoring.score import GameScore


@dataclass(frozen=True, slots=True)
class HandState:
    """Estado de una jugada (desde el reparto hasta el tanteo)."""

    number: int
    dealer: SeatId
    mano: SeatId
    hands: tuple[tuple[Card, ...], ...]
    stock: Deck
    discard_pile: tuple[Card, ...] = ()

    def hand_of(self, player: SeatId) -> tuple[Card, ...]:
        return self.hands[seat(player)]

    def all_cards(self) -> tuple[Card, ...]:
        """Todos los naipes de la jugada: manos + mazo + descartes."""
        in_hands = tuple(card for hand in self.hands for card in hand)
        return in_hands + self.stock.cards + self.discard_pile


@dataclass(frozen=True, slots=True)
class GameState:
    config: GameConfig
    table: Table
    rng: Rng
    phase: Phase = Phase.NOT_STARTED
    score: GameScore = field(default_factory=GameScore)
    pending_dealer: SeatId | None = None  # quién repartirá la próxima jugada
    hand: HandState | None = None
    winner: TeamId | None = None

    def evolve(self, **changes: object) -> GameState:
        """Copia con cambios. Atajo de ``dataclasses.replace`` con tipo de retorno."""
        return replace(self, **changes)  # type: ignore[arg-type]
