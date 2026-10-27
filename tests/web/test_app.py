from __future__ import annotations

import random
import re
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import mus_web.app as app_module
from mus_engine.players.seating import SeatId
from mus_web.app import Hub, create_app
from mus_web.rooms import Room

from .conftest import fast_settings, register

# --- Cuentas ----------------------------------------------------------------------------


def test_index_static_and_security_headers(client: TestClient) -> None:
    page = client.get("/")
    assert page.status_code == 200
    assert "MUS.ST" in page.text
    assert page.headers["cache-control"] == "no-cache"
    assert re.search(r'/static/app\.js\?v=[0-9a-f]{12}"', page.text)
    assert "default-src 'self'" in page.headers["content-security-policy"]
    assert "wss://testserver" in page.headers["content-security-policy"]
    odd = client.get("/", headers={"host": "evil.example; script-src *"})
    assert "evil" not in odd.headers["content-security-policy"]
    assert page.headers["x-frame-options"] == "DENY"
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/docs").status_code == 404


def test_deck_without_images(client: TestClient) -> None:
    assert client.get("/api/deck").json() == {"images": []}


def test_avatars_endpoint(client: TestClient) -> None:
    data = client.get("/api/avatars").json()
    assert "parodia" in data["aviso"]
    assert len(data["avatars"]) == 8
    assert all(a["images"] == [] for a in data["avatars"])
    assert all("phrases" not in a for a in data["avatars"])


def test_avatar_images_are_listed(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    static = tmp_path / "static"
    (static / "avatars" / "marquesa").mkdir(parents=True)
    for name in ("frente.png", "contento.png", "otra.png", "LEEME.md"):
        (static / "avatars" / "marquesa" / name).write_bytes(b"x")
    (static / "index.html").write_text("MUS.ST")
    for asset in ("style.css", "cards.js", "app.js"):
        (static / asset).write_text("")
    (static / "cards").mkdir()
    for name in ("12O.png", "99X.png", "LEEME.md"):
        (static / "cards" / name).write_bytes(b"x")

    class FakeResources:
        @staticmethod
        def files(_: str) -> Any:
            return tmp_path

    monkeypatch.setattr(app_module, "resources", FakeResources)
    with TestClient(create_app(fast_settings())) as client:
        avatars = {a["id"]: a["images"] for a in client.get("/api/avatars").json()["avatars"]}
        deck = client.get("/api/deck").json()
    assert avatars["marquesa"] == ["contento", "frente"]
    assert deck == {"images": ["12O"]}
    assert avatars["tentador"] == []


def test_register_login_logout(client: TestClient) -> None:
    me = register(client)
    assert me["username"] == "sara"
    assert me["avatar"] == "marquesa"
    assert client.get("/api/me").json()["id"] == me["id"]
    assert client.post("/api/logout").json() == {"ok": True}
    assert client.get("/api/me").status_code == 401
    assert client.post("/api/logout").json() == {"ok": True}  # sin sesión: no pasa nada
    client.cookies.set("musst_session", "inventada")
    assert client.post("/api/logout").json() == {"ok": True}
    assert client.get("/api/me").status_code == 401
    client.cookies.clear()
    ok = client.post("/api/login", json={"username": "sara", "password": "contraseña1"})
    assert ok.status_code == 200
    assert client.get("/api/me").status_code == 200


def test_cookie_is_httponly_and_token_is_not_stored(client: TestClient) -> None:
    response = client.post(
        "/api/register",
        json={"username": "sara", "password": "contraseña1", "avatar": "abuela", "consent": True},
    )
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower()
    token = client.cookies["musst_session"]
    from mus_web.db import LoginSession

    db = client.app.state.db  # type: ignore[attr-defined]
    with db.session() as session:
        stored = [s.token_hash for s in session.query(LoginSession).all()]
    assert token not in stored
    assert len(stored) == 1


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"username": "x", "password": "contraseña1", "avatar": "abuela", "consent": True}, 422),
        ({"username": "sara", "password": "corta", "avatar": "abuela", "consent": True}, 422),
        (
            {"username": "sara", "password": "contraseña1", "avatar": "abuela", "consent": False},
            422,
        ),
        ({"username": "sara", "password": "contraseña1", "avatar": "nadie", "consent": True}, 422),
        ({"username": "sara", "password": "contraseña1"}, 422),
    ],
)
def test_register_validation(client: TestClient, body: dict[str, Any], status: int) -> None:
    assert client.post("/api/register", json=body).status_code == status


def test_duplicate_username(client: TestClient) -> None:
    register(client)
    again = client.post(
        "/api/register",
        json={"username": "sara", "password": "contraseña2", "avatar": "abuela", "consent": True},
    )
    assert again.status_code == 409


def test_login_lockout(client: TestClient) -> None:
    register(client)
    client.post("/api/logout")
    for _ in range(5):
        bad = client.post("/api/login", json={"username": "sara", "password": "mala-clave"})
        assert bad.status_code == 401
    good = client.post("/api/login", json={"username": "sara", "password": "contraseña1"})
    assert good.status_code == 429
    unknown = client.post("/api/login", json={"username": "nadie", "password": "contraseña1"})
    assert unknown.status_code == 401


def test_expired_session(client: TestClient) -> None:
    register(client)
    from mus_web.db import LoginSession, utcnow

    db = client.app.state.db  # type: ignore[attr-defined]
    with db.session() as session:
        for login in session.query(LoginSession).all():
            login.expires_at = utcnow().replace(year=2000)
    assert client.get("/api/me").status_code == 401


def test_change_avatar(client: TestClient) -> None:
    register(client)
    assert client.put("/api/me/avatar", json={"avatar": "verbena"}).json()["avatar"] == "verbena"
    assert client.get("/api/me").json()["avatar"] == "verbena"
    assert client.put("/api/me/avatar", json={"avatar": "nadie"}).status_code == 422


def test_requires_login(client: TestClient) -> None:
    for method, path in [
        ("GET", "/api/me"),
        ("GET", "/api/me/games"),
        ("GET", "/api/me/export"),
        ("POST", "/api/rooms/ABC/join"),
        ("GET", "/api/rooms/ABC"),
    ]:
        assert client.request(method, path).status_code == 401


# --- Salas ------------------------------------------------------------------------------


def test_room_lifecycle_over_rest(client: TestClient) -> None:
    register(client, "sara")
    room = client.post("/api/rooms", json={"mode": "dos_humanos", "signals": True}).json()
    code = room["code"]
    assert room["level"] == "medio"  # nivel por defecto
    assert room["seats"][0]["name"] == "sara"
    assert room["signals"] is True
    assert client.get(f"/api/rooms/{code.lower()}").json()["code"] == code
    assert client.post(f"/api/rooms/{code}/start").status_code == 409  # falta la pareja

    with TestClient(client.app) as other:
        register(other, "ana", "tronista")
        assert other.post(f"/api/rooms/{code}/start").status_code == 409  # no es anfitriona
        joined = other.post(f"/api/rooms/{code}/join").json()
        assert joined["seats"][2]["name"] == "ana"
        assert other.post(f"/api/rooms/{code}/leave").json()["seats"][2] is None
        other.post(f"/api/rooms/{code}/join")
        with TestClient(client.app) as third:
            register(third, "eva")
            assert third.post(f"/api/rooms/{code}/join").status_code == 409  # completa

    started = client.post(f"/api/rooms/{code}/start")
    assert started.json()["started"] is True
    assert client.post(f"/api/rooms/{code}/leave").status_code == 409


def test_room_errors(client: TestClient) -> None:
    register(client)
    assert client.post("/api/rooms", json={"mode": "cinco"}).status_code == 422
    assert client.post("/api/rooms", json={"mode": "con_bot", "level": "dios"}).status_code == 422
    assert client.get("/api/rooms/NOEXISTE").status_code == 404
    bad: list[dict[str, Any]] = [
        {"target": 50},
        {"tournament_round": 4},
        {"partner": "nadie"},
        {"rivals": ["tentador"]},
        {"partner": "tentador", "rivals": ["tentador", "tronista"]},
    ]
    for extra in bad:
        assert client.post("/api/rooms", json={"mode": "con_bot", **extra}).status_code == 422


def test_choose_partner_rivals_and_target(client: TestClient) -> None:
    register(client)  # avatar marquesa
    body = {
        "mode": "con_bot",
        "target": 30,
        "partner": "tronista",
        "rivals": ["tentador", "abuela"],
        "tournament_round": 2,
    }
    room = client.post("/api/rooms", json=body).json()
    assert (room["target"], room["tournament_round"]) == (30, 2)
    started = client.post(f"/api/rooms/{room['code']}/start").json()
    assert [s["avatar"]["id"] for s in started["seats"]] == [
        "marquesa",
        "tentador",
        "tronista",
        "abuela",
    ]
    hub: Hub = client.app.state.hub  # type: ignore[attr-defined]
    game = hub.rooms[room["code"]].game
    assert game is not None
    assert game.get_state().config.target_score == 30


def test_chosen_avatars_only_with_one_person(client: TestClient) -> None:
    register(client)
    room = client.post("/api/rooms", json={"mode": "dos_humanos", "partner": "tronista"}).json()
    hub: Hub = client.app.state.hub  # type: ignore[attr-defined]
    assert hub.rooms[room["code"]]._chosen_avatars(set()) == {}


def test_too_many_rooms(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    register(client)
    monkeypatch.setattr(app_module, "MAX_ROOMS", 2)
    hub: Hub = client.app.state.hub  # type: ignore[attr-defined]
    first = client.post("/api/rooms", json={"mode": "con_bot"}).json()["code"]
    client.post("/api/rooms", json={"mode": "con_bot"})
    # Sin conexiones abiertas, las salas viejas se limpian para hacer sitio.
    client.post("/api/rooms", json={"mode": "con_bot"})
    assert first not in hub.rooms
    client.post("/api/rooms", json={"mode": "con_bot"})
    assert len(hub.rooms) == 2
    # Con todas las salas ocupadas por jugadores conectados, no se crean más.
    for code in hub.rooms:
        hub.sockets[code][object()] = 1  # type: ignore[index]
    full = client.post("/api/rooms", json={"mode": "con_bot"})
    assert full.status_code == 503
    hub.sockets.clear()


# --- Mesa por WebSocket -------------------------------------------------------------------


def choose(game: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    legal = game["legal"]
    options: list[dict[str, Any]] = [a for a in legal["actions"] if a["type"] != "signal"]
    if legal["bet"] is not None:
        options.append({"type": "bet", "amount": legal["bet"]["min"]})
    return rng.choice(options)


def play_over_socket(
    client: TestClient, code: str, seed: int = 0, think: float = 0.0
) -> dict[str, Any]:
    """Juega al azar hasta el final. ``think``: segundos que «piensa» la persona."""
    rng = random.Random(seed)
    with client.websocket_connect(f"/ws/rooms/{code}") as socket:
        for _ in range(20_000):
            view: dict[str, Any] = socket.receive_json()
            if "error" in view:
                continue
            game = view.get("game")
            if game is None:
                continue
            if game["winner"] is not None:
                assert game["phase"] == "game_over"
                return view
            if view["room"]["awaiting_deal"]:
                socket.send_json({"deal": game["hand_number"]})
                continue
            if game["seat"] in game["to_act"]:
                time.sleep(think)
                socket.send_json({"action": choose(game, rng)})
    raise AssertionError("la partida no terminó")


def start_room(client: TestClient, mode: str = "con_bot", signals: bool = False) -> str:
    code: str = client.post("/api/rooms", json={"mode": mode, "signals": signals}).json()["code"]
    return code


def test_full_game_over_websocket_is_saved(client: TestClient) -> None:
    me = register(client)
    code = start_room(client)
    with client.websocket_connect(f"/ws/rooms/{code}") as socket:
        waiting = socket.receive_json()
        assert "game" not in waiting
        client.post(f"/api/rooms/{code}/start")
        assert "game" in socket.receive_json()
    view = play_over_socket(client, code)
    # Sólo mis cartas: las de los demás no aparecen salvo enseñadas al final.
    assert len(view["game"]["my_hand"]) == 4
    games = client.get("/api/me/games").json()
    assert len(games) == 1
    assert games[0]["mode"] == "con_bot"
    me_now = client.get("/api/me").json()
    assert me_now["games_played"] == 1
    assert me_now["games_won"] == int(games[0]["won"])
    export = client.get("/api/me/export").json()
    assert export["user"]["id"] == me["id"]
    assert export["games"][0]["record"]["player_names"][0] == "sara"
    hub: Hub = client.app.state.hub  # type: ignore[attr-defined]
    room = hub.rooms[code]
    hub.save(room)  # guardar dos veces no duplica
    assert len(client.get("/api/me/games").json()) == 1


def test_game_with_signals_ticks_the_clock(client: TestClient) -> None:
    register(client)
    code = start_room(client, signals=True)
    client.post(f"/api/rooms/{code}/start")
    view = play_over_socket(client, code, seed=4, think=0.03)
    assert view["game"]["gaze"] is not None
    hub: Hub = client.app.state.hub  # type: ignore[attr-defined]
    record = hub.rooms[code].game.record  # type: ignore[union-attr]
    assert any(not isinstance(e, tuple) for e in record.actions)  # hubo momentos de reloj


def test_four_humans_see_only_their_own_cards(client: TestClient) -> None:
    register(client, "jug0")
    code = start_room(client, "cuatro")
    others = []
    for name in ("jug1", "jug2", "jug3"):
        other = TestClient(client.app)
        other.__enter__()
        register(other, name)
        other.post(f"/api/rooms/{code}/join")
        others.append(other)
    client.post(f"/api/rooms/{code}/start")
    hub: Hub = client.app.state.hub  # type: ignore[attr-defined]
    room: Room = hub.rooms[code]
    assert room.game is not None
    state = room.game.get_state()
    assert state.hand is not None
    for seat, c in enumerate([client, *others]):
        with c.websocket_connect(f"/ws/rooms/{code}") as socket:
            view = socket.receive_json()
        assert view["seat"] == seat
        game = view["game"]
        mine = {card.code for card in state.hand.hand_of(seat)}  # type: ignore[arg-type]
        assert set(game["my_hand"]) == mine
        assert game["revealed_hands"] is None
        dealt = [e for e in game["events"] if e["type"] == "CardsDealt"]
        assert dealt
        assert all(e["data"]["seat"] == seat for e in dealt)
        hidden = {"DeckShuffled", "RngSeeded", "CardsDiscarded"}
        assert not [e for e in game["events"] if e["type"] in hidden]
    for other in others:
        other.__exit__(None, None, None)


def test_socket_messages_are_validated(client: TestClient) -> None:
    register(client)
    code = start_room(client)
    client.post(f"/api/rooms/{code}/start")
    with client.websocket_connect(f"/ws/rooms/{code}") as socket:
        socket.receive_json()
        bad_messages = (
            "x" * 5000,
            "{no json",
            "[1]",
            '{"action": {"type": "mus"}, "x": 1}',
            '{"action": {"type": "mus"}}',  # antes de repartir
            '{"deal": "uno"}',
        )
        for bad in bad_messages:
            socket.send_text(bad)
            reply = socket.receive_json()
            while "error" not in reply:
                reply = socket.receive_json()
        socket.send_json({"action": {"type": "discard", "cards": ["1O"]}})
        reply = socket.receive_json()
        while "error" not in reply:
            reply = socket.receive_json()


def refused(client: TestClient, path: str, **kwargs: Any) -> int:
    """Código con el que el servidor cierra la conexión."""
    with (
        pytest.raises(WebSocketDisconnect) as closed,
        client.websocket_connect(path, **kwargs) as socket,
    ):
        socket.receive_json()
    code: int = closed.value.code
    return code


def test_socket_rejects_strangers(client: TestClient) -> None:
    register(client)
    code = start_room(client)
    with TestClient(client.app) as stranger:
        assert refused(stranger, f"/ws/rooms/{code}") == 4401  # sin sesión
        register(stranger, "intrusa")
        assert refused(stranger, f"/ws/rooms/{code}") == 4401  # no está sentada
    assert refused(client, "/ws/rooms/NOEXISTE") == 4401
    evil = {"origin": "https://malvado.example"}
    assert refused(client, f"/ws/rooms/{code}", headers=evil) == 4403
    with client.websocket_connect(
        f"/ws/rooms/{code}", headers={"origin": "http://testserver"}
    ) as socket:
        assert socket.receive_json()["seat"] == 0


def test_broadcast_survives_broken_sockets(client: TestClient) -> None:
    register(client)
    code = start_room(client)
    hub: Hub = client.app.state.hub  # type: ignore[attr-defined]

    class Broken:
        async def send_json(self, _: object) -> None:
            raise RuntimeError("cerrado")

    hub.sockets[code][Broken()] = 1  # type: ignore[index]
    assert client.post(f"/api/rooms/{code}/start").status_code == 200


def test_delete_account_anonymises_saved_games(client: TestClient) -> None:
    register(client)
    code = start_room(client)
    client.post(f"/api/rooms/{code}/start")
    play_over_socket(client, code)
    assert client.request("DELETE", "/api/me", json={"password": "mala-clave"}).status_code == 401
    assert client.request("DELETE", "/api/me", json={"password": "contraseña1"}).json() == {
        "ok": True
    }
    assert client.get("/api/me").status_code == 401
    db = client.app.state.db  # type: ignore[attr-defined]
    from mus_web.db import GameRow, GameSeat, User

    with db.session() as session:
        assert session.query(User).count() == 0
        (game,) = session.query(GameRow).all()
        assert game.record["player_names"][0] == app_module.DELETED_NAME
        assert "sara" not in str(game.record)
        assert session.query(GameSeat).filter(GameSeat.user_id.is_not(None)).count() == 0


def test_entry_point_is_importable() -> None:
    from mus_web import __main__ as entry

    assert callable(entry.main)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("postgres://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql://u:p@h/db", "postgresql+psycopg://u:p@h/db"),
        ("postgresql+psycopg://u@h/db", "postgresql+psycopg://u@h/db"),
        ("sqlite:///musst.db", "sqlite:///musst.db"),
    ],
)
def test_postgres_urls_use_psycopg(url: str, expected: str) -> None:
    assert app_module.postgres_driver(url) == expected


def test_health_check(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}


def test_profile_is_learned_and_given_to_the_bots(client: TestClient) -> None:
    register(client)
    assert client.get("/api/me/profile").json()["style"] == "por conocer"
    code = start_room(client)
    client.post(f"/api/rooms/{code}/start")
    play_over_socket(client, code)
    profile = client.get("/api/me/profile").json()
    assert profile["decisions"] > 0
    assert profile["games"] == 1
    assert client.get("/api/me/export").json()["profile"]["games"] == 1
    # Segunda partida: los bots reciben lo aprendido de la persona.
    second = start_room(client)
    client.post(f"/api/rooms/{second}/start")
    hub: Hub = client.app.state.hub  # type: ignore[attr-defined]
    room = hub.rooms[second]
    for occupant in room.seats:
        assert occupant is not None
        if occupant.bot is not None:
            assert occupant.bot.context.profiles[SeatId(0)].counts["games"] == 1
    play_over_socket(client, second)
    assert client.get("/api/me/profile").json()["games"] == 2


def test_profile_of_a_deleted_user_is_not_saved(client: TestClient) -> None:
    register(client)
    code = start_room(client)
    client.post(f"/api/rooms/{code}/start")
    hub: Hub = client.app.state.hub  # type: ignore[attr-defined]
    room = hub.rooms[code]
    room.wait_for_deal = False
    client.request("DELETE", "/api/me", json={"password": "contraseña1"})
    while not room.finished:
        seat = room.bot_to_act()
        if seat is not None:
            room.bot_step()
        else:
            assert room.game is not None
            legal = room.view_for(1)["game"]["legal"]
            options = [a for a in legal["actions"] if a["type"] != "signal"]
            room.human_action(1, options[0] if options else {"type": "bet", "amount": 2})
    hub.save(room)
    from mus_web.db import ProfileRow

    db = client.app.state.db  # type: ignore[attr-defined]
    with db.session() as session:
        assert session.query(ProfileRow).count() == 0


# --- Administración -----------------------------------------------------------------------


def test_admin_stats_and_password_reset() -> None:
    with TestClient(create_app(fast_settings(admins=frozenset({"sara"})))) as client:
        register(client, "pepe")
        assert client.get("/api/me").json()["admin"] is False
        assert client.get("/api/admin/stats").status_code == 403
        assert (
            client.post(
                "/api/admin/password", json={"username": "sara", "password": "otraclave1"}
            ).status_code
            == 403
        )
        client.post("/api/logout")
        register(client, "Sara")
        assert client.get("/api/me").json()["admin"] is True
        code = start_room(client)
        client.post(f"/api/rooms/{code}/start")
        play_over_socket(client, code)
        stats = client.get("/api/admin/stats").json()
        assert stats["users"] == 2
        assert stats["games"] == 1
        (row,) = stats["bots_vs_people"]
        assert row["bot"] == "medio"
        assert row["games"] == 1
        assert 0 <= row["low"] <= row["rate"] <= row["high"] <= 1
        bad = {"username": "pepe", "password": "corta"}
        assert client.post("/api/admin/password", json=bad).status_code == 422
        nobody = {"username": "nadie", "password": "otraclave1"}
        assert client.post("/api/admin/password", json=nobody).status_code == 404
        ok = {"username": "pepe", "password": "otraclave1"}
        assert client.post("/api/admin/password", json=ok).json() == {"ok": True}
        client.post("/api/logout")
        login = {"username": "pepe", "password": "otraclave1"}
        assert client.post("/api/login", json=login).status_code == 200


def test_admin_stats_skip_games_without_people_against_bots() -> None:
    from mus_web.app import win_rate
    from mus_web.db import GameRow, GameSeat

    with TestClient(create_app(fast_settings(admins=frozenset({"sara"})))) as client:
        register(client, "sara")
        db = client.app.state.hub.db  # type: ignore[attr-defined]
        with db.session() as session:
            bots_only = GameRow(
                mode="x",
                signals=False,
                winner_team="A",
                final_tantos=[40, 0],
                final_games=[1, 0],
                record={},
            )
            bots_only.seats = [
                GameSeat(seat=s, bot="medio", avatar_id="marquesa", won=s % 2 == 0)
                for s in range(4)
            ]
            session.add(bots_only)
        assert client.get("/api/admin/stats").json()["bots_vs_people"] == []
    assert win_rate([True, False])["rate"] == 0.5


def admin_client() -> TestClient:
    return TestClient(create_app(fast_settings(admins=frozenset({"sara"}))))


def test_admin_lists_and_inspects_users() -> None:
    with admin_client() as client:
        pepe = register(client, "pepe")
        assert client.get("/api/admin/users").status_code == 403
        code = start_room(client)
        client.post(f"/api/rooms/{code}/start")
        play_over_socket(client, code)
        client.post("/api/logout")
        sara = register(client, "sara")
        users = {u["username"]: u for u in client.get("/api/admin/users").json()}
        assert users["sara"]["admin_source"] == "config"
        assert users["pepe"]["admin_source"] is None
        assert users["pepe"]["games_played"] == 1
        assert users["pepe"]["style"]
        assert users["sara"]["open_sessions"] == 1
        detail = client.get(f"/api/admin/users/{pepe['id']}").json()
        assert detail["profile"]["decisions"] > 0
        (game,) = detail["games"]
        assert len(game["players"]) == 4
        assert any(p["user_id"] == pepe["id"] for p in game["players"])
        assert client.get(f"/api/admin/users/{sara['id']}").json()["profile"] is None
        assert client.get("/api/admin/users/999").status_code == 404
        stats = client.get("/api/admin/stats").json()
        kpis = stats["kpis"]
        assert kpis["users"] == 2
        assert kpis["new_users_7d"] == 2
        assert kpis["active_users_7d"] == 2
        assert kpis["games_today"] == 1
        assert kpis["rooms_open"] == 1
        assert len(stats["games_per_day"]) == app_module.STATS_DAYS
        assert stats["games_per_day"][-1]["games"] == 1
        assert stats["users_per_day"][-1]["users"] == 2
        assert stats["modes"] == {"con_bot": 1}
        assert stats["signals"] == {"con": 0, "sin": 1}
        assert sum(stats["styles"].values()) == 2
        (top,) = stats["top_players"]
        assert top["username"] == "pepe"
        (recent,) = stats["recent_games"]
        assert recent["id"] == game["id"]


def test_admin_edits_users() -> None:
    with admin_client() as client:
        pepe = register(client, "pepe")
        client.post("/api/logout")
        sara = register(client, "sara")
        edit = f"/api/admin/users/{pepe['id']}"
        changed = client.patch(edit, json={"username": "pepa", "avatar": "verbena"}).json()
        assert changed["username"] == "pepa"
        assert changed["avatar"] == "verbena"
        assert client.patch(edit, json={"username": "sara"}).status_code == 409
        assert client.patch(edit, json={"username": "x"}).status_code == 422
        assert client.patch(edit, json={"avatar": "nadie"}).status_code == 422
        assert client.patch(edit, json={"password": "corta"}).status_code == 422
        assert client.patch(edit, json={"password": "nuevaclave1"}).status_code == 200
        # Hacerle administrador desde el panel, y quitárselo.
        assert client.patch(edit, json={"admin": True}).json()["admin_source"] == "panel"
        assert client.patch(edit, json={"admin": True}).json()["admin_source"] == "panel"
        assert client.patch(edit, json={"admin": False}).json()["admin_source"] is None
        mine = f"/api/admin/users/{sara['id']}"
        assert client.patch(mine, json={"admin": False}).status_code == 409
        assert client.patch(mine, json={"username": "sarita"}).status_code == 409
        assert client.patch("/api/admin/users/999", json={}).status_code == 404
        client.patch(edit, json={"admin": True})
        client.post("/api/logout")
        login = {"username": "pepa", "password": "nuevaclave1"}
        assert client.post("/api/login", json=login).status_code == 200
        assert client.get("/api/me").json()["admin"] is True
        assert client.patch(mine, json={"admin": False}).status_code == 409
        assert client.delete(mine).status_code == 409
        # Un administrador del panel no puede quitarse sus propios permisos.
        own = client.patch(edit, json={"admin": False})
        assert own.status_code == 409


def test_admin_closes_sessions_and_deletes_users() -> None:
    with admin_client() as client:
        pepe = register(client, "pepe")
        code = start_room(client)
        client.post(f"/api/rooms/{code}/start")
        play_over_socket(client, code)
        pepe_cookie = client.cookies.get("musst_session")
        client.post("/api/logout")
        sara = register(client, "sara")
        assert client.post(f"/api/admin/users/{pepe['id']}/logout").json() == {"ok": True}
        users = {u["username"]: u for u in client.get("/api/admin/users").json()}
        assert users["pepe"]["open_sessions"] == 0
        assert pepe_cookie
        assert client.delete(f"/api/admin/users/{sara['id']}").status_code == 409
        assert client.delete("/api/admin/users/999").status_code == 404
        assert client.delete(f"/api/admin/users/{pepe['id']}").json() == {"ok": True}
        assert [u["username"] for u in client.get("/api/admin/users").json()] == ["sara"]
        (game,) = client.get("/api/admin/stats").json()["recent_games"]
        assert app_module.DELETED_NAME in [p["name"] for p in game["players"]]


def test_reset_password_from_settings() -> None:
    settings = fast_settings(reset_password="sara:nuevaclave1", admins=frozenset({"sara"}))
    with TestClient(create_app(settings)) as client:  # crea la cuenta que no existía
        login = {"username": "sara", "password": "nuevaclave1"}
        assert client.post("/api/login", json=login).status_code == 200
        assert client.get("/api/me").json()["admin"] is True
        db = client.app.state.hub.db  # type: ignore[attr-defined]
        settings.reset_password = "sara:otraclave22"
        app_module.reset_account(db, settings)  # y a una que ya existe le cambia la clave
        assert client.get("/api/me").status_code == 401  # sus sesiones se cierran
        assert client.post("/api/login", json=login).status_code == 401
        login["password"] = "otraclave22"
        assert client.post("/api/login", json=login).status_code == 200
    with TestClient(create_app(fast_settings(reset_password="sara:corta"))) as client:
        login = {"username": "sara", "password": "corta"}  # arranca, pero no crea nada
        assert client.post("/api/login", json=login).status_code == 401


def test_normal_users_never_reach_admin(client: TestClient) -> None:
    register(client, "pepe")
    assert client.get("/api/me").json()["admin"] is False
    for method, path in [
        ("GET", "/api/admin/stats"),
        ("GET", "/api/admin/users"),
        ("GET", "/api/admin/users/1"),
        ("PATCH", "/api/admin/users/1"),
        ("DELETE", "/api/admin/users/1"),
        ("POST", "/api/admin/users/1/logout"),
        ("POST", "/api/admin/password"),
    ]:
        body = {"username": "pepe", "password": "otraclave1"}
        assert client.request(method, path, json=body).status_code == 403, path


def test_ads_are_set_by_admins_only() -> None:
    tiny_png = "data:image/png;base64,iVBORw0KGgo="
    with admin_client() as client:
        assert client.get("/api/ads").json() == app_module.DEFAULT_ADS
        register(client, "pepe")
        ads = {"card_brand": "Bar Pepe", "drink": "refresco", "drink_brand": "Cola"}
        assert client.put("/api/admin/ads", json=ads).status_code == 403
        client.post("/api/logout")
        register(client, "sara")
        saved = client.put("/api/admin/ads", json=ads | {"card_image": tiny_png}).json()
        assert saved["card_brand"] == "Bar Pepe"
        assert saved["card_image"] == tiny_png
        assert client.get("/api/ads").json() == saved
        again = client.put("/api/admin/ads", json={"card_brand": " Otra "}).json()
        assert again["card_brand"] == "Otra"
        assert again["drink"] == "cerveza"
        for bad in [
            {"card_brand": ""},
            {"card_brand": "x" * 25},
            {"drink_brand": "x" * 25},
            {"card_color": "rojo"},
            {"drink_color": "#12345"},
            {"drink": "whisky"},
            {"card_image": "javascript:alert(1)"},
            {"drink_image": "data:image/svg+xml;base64,PHN2Zz4="},
            {"card_image": "data:image/png;base64," + "A" * app_module.MAX_AD_IMAGE},
        ]:
            assert client.put("/api/admin/ads", json=bad).status_code == 422, bad
