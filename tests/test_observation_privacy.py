from musst.cards import Card, Suit
from musst.observation import build_player_observation
from musst.rules import RulesEngine
from musst.state import GamePhase, GameState


def test_observation_hides_opponent_cards() -> None:
    state = GameState(
        player_order=["you", "ally", "bot1", "bot2"],
        hands={
            "you": [Card(Suit.OROS, 1)],
            "ally": [Card(Suit.COPAS, 12)],
            "bot1": [Card(Suit.ESPADAS, 7)],
            "bot2": [Card(Suit.BASTOS, 10)],
        },
        phase=GamePhase.GRANDE,
    )

    obs = build_player_observation(state, "you", RulesEngine())

    assert "hand" in obs["players"]["you"]
    assert "hand" not in obs["players"]["ally"]
    assert "hand" not in obs["players"]["bot1"]
    assert "hand" not in obs["players"]["bot2"]
