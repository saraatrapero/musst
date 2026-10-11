from __future__ import annotations

import random
from typing import Any

import pytest

from mus_engine.bots.random_bot import RandomBot
from mus_engine.players.seating import ALL_SEATS
from mus_web.avatars_pack import load_pack
from mus_web.rooms import CODE_ALPHABET, CODE_LENGTH, Mode, Room, RoomError, new_code

AVATARS = load_pack()[1]


def make_room(mode: Mode = Mode.CON_BOT, signals: bool = False, phrases: bool = True) -> Room:
    room = Room("SALA22", mode, signals, phrases, 1, AVATARS, random.Random(5))
    room.join(1, "sara", AVATARS[0])
    return room


def human_choice(room: Room, user_id: int, rng: random.Random) -> dict[str, Any]:
    legal = room.view_for(user_id)["game"]["legal"]
    options: list[dict[str, Any]] = [a for a in legal["actions"] if a["type"] != "signal"]
    if legal["bet"] is not None:
        options.append({"type": "bet", "amount": legal["bet"]["min"]})
    if legal["raise"] is not None:
        options.append({"type": "raise", "amount": legal["raise"]["min"]})
    return rng.choice(options)


def play_out(room: Room, seed: int = 0) -> int:
    rng = random.Random(seed)
    steps = 0
    while not room.finished:
        steps += 1
        assert steps < 5000
        if room.bot_to_act() is not None:
            room.bot_step()
            continue
        room.clock()
        assert room.game is not None
        (seat,) = room.game.current_actors()
        occupant = room.seats[seat]
        assert occupant is not None
        assert occupant.user_id is not None
        room.human_action(occupant.user_id, human_choice(room, occupant.user_id, rng))
    return steps


def test_codes_use_unambiguous_alphabet() -> None:
    code = new_code(random.Random(1))
    assert len(code) == CODE_LENGTH
    assert set(code) <= set(CODE_ALPHABET)
    assert not set("O0I1") & set(CODE_ALPHABET)


def test_join_assigns_human_seats_in_order() -> None:
    room = make_room(Mode.DOS_HUMANOS)
    assert room.join(1, "sara", AVATARS[0]) == 0  # ya sentada: mismo asiento
    assert room.join(2, "ana", AVATARS[1]) == 2  # su pareja, enfrente
    with pytest.raises(RoomError, match="completa"):
        room.join(3, "eva", AVATARS[2])
    room.leave(2)
    room.leave(99)  # quien no está sentado no cambia nada
    assert room.seats[2] is None


def test_start_rules() -> None:
    room = make_room(Mode.DOS_HUMANOS)
    with pytest.raises(RoomError, match="Sólo quien"):
        room.start(2, seed=1)
    with pytest.raises(RoomError, match="Faltan"):
        room.start(1, seed=1)
    room.join(2, "ana", AVATARS[0])
    room.start(1, seed=1)
    assert room.started
    with pytest.raises(RoomError, match="ya ha empezado"):
        room.start(1, seed=1)
    with pytest.raises(RoomError, match="ya ha empezado"):
        room.join(3, "eva", AVATARS[0])
    with pytest.raises(RoomError, match="abandonar"):
        room.leave(2)
    # Los bots reciben avatares que no usa nadie.
    bots = [o for o in room.seats if o is not None and o.is_bot]
    assert len(bots) == 2
    assert all(b.avatar.id != AVATARS[0].id for b in bots)
    assert len({b.avatar.id for b in bots}) == 2


def test_bots_reuse_avatars_when_humans_took_them_all() -> None:
    room = Room("X", Mode.CON_BOT, False, True, 1, AVATARS[:2], random.Random(0))
    room.join(1, "sara", AVATARS[0])
    room.start(1, seed=3)
    assert all(o is not None for o in room.seats)


def test_before_start() -> None:
    room = make_room()
    assert room.hand_number == 0
    assert not room.finished
    view = room.view_for(1)
    assert "game" not in view
    assert view["room"]["seats"][0]["name"] == "sara"
    for call in (room.bot_to_act, room.bot_step, room.clock, room.winners):
        with pytest.raises(RoomError, match="no ha empezado"):
            call()
    with pytest.raises(RoomError, match="no ha empezado"):
        room.human_action(1, {"type": "mus"})


@pytest.mark.parametrize(
    ("mode", "signals"),
    [(Mode.CON_BOT, True), (Mode.CON_BOT, False), (Mode.DOS_HUMANOS, True), (Mode.CUATRO, False)],
)
def test_full_games_in_every_mode(mode: Mode, signals: bool) -> None:
    room = make_room(mode, signals)
    for user in range(2, 5):
        if None in [room.seats[s] for s in room.human_seats]:
            room.join(user, f"u{user}", AVATARS[user])
    room.start(1, seed=11)
    play_out(room)
    assert room.finished
    winners = room.winners()
    assert len(winners) == 2
    assert room.view_for(1)["game"]["winner"] in ("A", "B")
    assert room.bot_to_act() is None
    room.clock()  # sin efecto al terminar
    with pytest.raises(RoomError, match="terminado"):
        room.human_action(1, {"type": "pass"})


def test_bots_speak_only_with_phrases_enabled() -> None:
    quiet = make_room(phrases=False)
    quiet.start(1, seed=11)
    play_out(quiet)
    assert quiet.phrases == []
    loud = make_room(phrases=True)
    loud.start(1, seed=11)
    play_out(loud)
    assert loud.phrases
    ids = [p["id"] for p in loud.phrases]
    assert ids == sorted(ids)
    assert len(loud.phrases) <= 6


def test_human_errors() -> None:
    room = make_room()
    room.start(1, seed=2, bot_factory=RandomBot)
    with pytest.raises(RoomError, match="No estás sentado"):
        room.human_action(9, {"type": "mus"})
    with pytest.raises(RoomError, match="No estás sentado"):
        room.view_for(9)
    with pytest.raises(RoomError):
        room.human_action(1, {"type": "hack"})
    # Ilegal para el motor: descartar fuera de la fase de descartes.
    with pytest.raises(RoomError):
        room.human_action(1, {"type": "discard", "cards": ["1O"]})


def test_bot_step_when_a_human_must_play() -> None:
    room = make_room()
    room.start(1, seed=2)
    while room.bot_to_act() is not None:
        room.bot_step()
    with pytest.raises(RoomError, match="ningún bot"):
        room.bot_step()


def test_bot_signals_with_signals_enabled() -> None:
    room = make_room(signals=True)
    room.start(1, seed=4)
    play_out(room, seed=3)
    assert room.game is not None
    made = [e for e in room.game.event_log if type(e.event).__name__ == "SignalMade"]
    bot_seats = {s for s in ALL_SEATS if room.seats[s] is not None and room.seats[s].is_bot}  # type: ignore[union-attr]
    assert made
    assert {e.event.seat for e in made} <= bot_seats  # type: ignore[attr-defined]
